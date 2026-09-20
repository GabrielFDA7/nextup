"""O coletor — quem transforma "agora" em "histórico".

É a peça que faltava para a Fase 6 existir: alguém precisa gravar a fila de tempos
em tempos, mesmo sem ninguém acessando o site. Sem isso não há tendência, não há
melhor horário e não há previsão — só o retrato do instante, que é o que o NextUp
já fazia desde a Fase 2.

**Posição na arquitetura.** Este módulo *orquestra*: pede ao `clients/` e entrega
ao `storage/`. Não é `core/`, porque não é lógica pura; não é `api/`, porque não
traduz HTTP. Fica no mesmo nível do `cli.py`, que já ocupa esse papel de juntar
camadas para fazer alguma coisa acontecer.

**O que é fácil errar aqui**, e por isso está resolvido explicitamente abaixo:

1. Uma falha da fonte não pode matar o laço. A ThemeParks.wiki vai cair algum dia,
   e o coletor precisa estar vivo quando ela voltar.
2. A primeira coleta tem de ser imediata. Esperar o primeiro intervalo significa
   subir e ficar cinco minutos sem gravar nada — e num serviço que hiberna, esses
   cinco minutos podem ser tudo que havia.
3. O cancelamento precisa atravessar. Um `except` largo demais engoliria o pedido
   de desligamento e o servidor travaria ao encerrar.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncEngine

from nextup.clients.themeparks import ThemeParksClient
from nextup.config import (
    COLLECT_INTERVAL_S,
    COLLECT_PARK_IDS,
    HISTORY_RETENTION_DAYS,
    PURGE_INTERVAL_S,
)
from nextup.models import QueueSnapshot
from nextup.storage import connection, purge_older_than, save_many

logger = logging.getLogger(__name__)


def _agora() -> datetime:
    """Relógio padrão, isolado para os testes poderem substituí-lo.

    Mesmo motivo do relógio injetável do cache: teste que depende da hora real é
    teste que falha sozinho na virada do dia.
    """
    return datetime.now(UTC)


@dataclass(frozen=True)
class CollectionResult:
    """O que uma coleta produziu.

    `stored` e `skipped` são contados separadamente de propósito. A proporção entre
    os dois é o melhor indicador de saúde do coletor: se quase tudo é `skipped`, ele
    está rodando mais rápido que a fonte atualiza e só gastando requisição; se
    `skipped` é sempre zero, o intervalo talvez pudesse ser menor sem perder nada.
    """

    park_id: str
    read: int
    stored: int

    @property
    def skipped(self) -> int:
        """Medições que a fonte ainda não havia atualizado desde a última coleta."""
        return self.read - self.stored


async def collect_once(
    *,
    client: ThemeParksClient,
    engine: AsyncEngine,
    park_id: str,
    now: Callable[[], datetime] = _agora,
) -> CollectionResult:
    """Lê o estado atual de um parque e grava o que for novidade.

    Cruza o catálogo com os dados ao vivo porque o `/live` devolve o parque inteiro
    — shows e restaurantes junto — e só atração interessa ao histórico. Guardar o
    Castelo da Cinderela, que está sempre aberto e nunca tem fila, seriam dezenas de
    milhares de linhas idênticas dizendo a mesma coisa.

    O catálogo sai do cache de 24h na quase totalidade das vezes, então esse
    cruzamento custa uma requisição por dia, não uma por coleta.

    Args:
        client: Cliente da ThemeParks.wiki.
        engine: Conexão com o banco.
        park_id: Parque a coletar.
        now: Relógio, injetável para teste.

    Returns:
        Quantas entidades foram lidas e quantas viraram linha nova.

    Raises:
        Erros de `clients/` sobem para quem chama. Quem decide se vale continuar é
        o laço, não esta função — que tem uma responsabilidade só.
    """
    catalogo = await client.get_park_catalog(park_id)
    ao_vivo = await client.get_live_data(park_id)

    ids_de_atracao = catalogo.attraction_ids()
    instante = now()

    snapshots = [
        QueueSnapshot.from_live(park_id=park_id, live=item, recorded_at=instante)
        for item in ao_vivo.live_data
        if item.id in ids_de_atracao
    ]

    async with connection(engine) as conexao:
        gravados = await save_many(conexao, snapshots)

    return CollectionResult(park_id=park_id, read=len(snapshots), stored=gravados)


async def purge_expired(
    *,
    engine: AsyncEngine,
    retention_days: int = HISTORY_RETENTION_DAYS,
    now: Callable[[], datetime] = _agora,
) -> int:
    """Apaga o histórico que passou do prazo de retenção.

    Returns:
        Quantas linhas saíram.
    """
    corte = now() - timedelta(days=retention_days)

    async with connection(engine) as conexao:
        return await purge_older_than(conexao, corte)


async def run_collector(
    *,
    client: ThemeParksClient,
    engine: AsyncEngine,
    park_ids: Sequence[str] = tuple(COLLECT_PARK_IDS),
    interval_s: float = COLLECT_INTERVAL_S,
    purge_interval_s: float = PURGE_INTERVAL_S,
    retention_days: int = HISTORY_RETENTION_DAYS,
    now: Callable[[], datetime] = _agora,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Coleta indefinidamente, até ser cancelado.

    Roda como tarefa de fundo dentro do servidor, iniciada e encerrada pelo
    `lifespan` da aplicação.

    **A primeira coleta acontece antes da primeira espera.** Parece detalhe e não
    é: o Render hiberna o serviço, e ele só acorda quando chega uma requisição. Se
    o coletor esperasse o intervalo antes de agir, cada despertar renderia menos
    dado — e num dia de pouco acesso, quase nenhum.

    **Nenhuma falha derruba o laço.** A fonte é de terceiros, gratuita, e vai ficar
    fora do ar em algum momento. Um coletor que morre na primeira falha só é
    descoberto semanas depois, quando alguém repara no buraco do gráfico.

    Args:
        client: Cliente da ThemeParks.wiki.
        engine: Conexão com o banco.
        park_ids: Quais parques coletar.
        interval_s: Segundos entre ciclos.
        purge_interval_s: Segundos entre limpezas de retenção.
        retention_days: Dias de histórico a manter.
        now: Relógio, injetável para teste.
        sleep: Função de espera, injetável para teste.
    """
    logger.info(
        "coletor iniciado: %d parque(s), a cada %.0fs",
        len(park_ids),
        interval_s,
    )
    proxima_limpeza = now() + timedelta(seconds=purge_interval_s)

    while True:
        for park_id in park_ids:
            try:
                resultado = await collect_once(
                    client=client, engine=engine, park_id=park_id, now=now
                )
            except asyncio.CancelledError:
                # Cancelamento não é falha: é o servidor pedindo para encerrar.
                # Precisa atravessar intacto, senão o desligamento trava. Ela herda
                # de BaseException justamente para não ser pega por engano, mas o
                # `except` explícito documenta a intenção para quem vier depois.
                raise
            except Exception:
                # `exception` registra o traceback junto. Sem ele, o log diria que
                # algo falhou sem dizer o quê — inútil justamente no dia em que
                # alguém for investigar.
                logger.exception("falha ao coletar o parque %s; segue no próximo ciclo", park_id)
            else:
                logger.info(
                    "parque %s: %d lidas, %d gravadas, %d repetidas",
                    park_id,
                    resultado.read,
                    resultado.stored,
                    resultado.skipped,
                )

        if now() >= proxima_limpeza:
            try:
                apagadas = await purge_expired(
                    engine=engine, retention_days=retention_days, now=now
                )
                logger.info("retenção: %d linhas apagadas", apagadas)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("falha na limpeza de retenção; será tentada de novo")
            finally:
                # No `finally` para que uma limpeza com erro não seja retentada de
                # cinco em cinco minutos pelo resto da vida do processo.
                proxima_limpeza = now() + timedelta(seconds=purge_interval_s)

        await sleep(interval_s)

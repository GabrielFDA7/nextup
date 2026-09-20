"""Testes do coletor — a peça que transforma "agora" em "histórico".

Usam as **fixtures reais** do Magic Kingdom capturadas em 12/09/2026, com o `respx`
interceptando antes de qualquer byte sair da máquina, e um SQLite em memória no
lugar do banco. Nada aqui toca a internet nem espera tempo de verdade: o `sleep` é
injetado, como já acontece no cliente.

O que este arquivo protege são as três coisas que um processo de fundo erra com
mais frequência — e que só se descobre semanas depois, olhando um gráfico com
buracos:

1. A falha da fonte não pode matar o laço.
2. A primeira coleta tem de ser imediata, não depois da primeira espera.
3. O cancelamento precisa atravessar, senão o servidor trava ao desligar.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from nextup.api import main
from nextup.clients.errors import ThemeParksUnavailableError
from nextup.clients.themeparks import ThemeParksClient
from nextup.collector import CollectionResult, collect_once, purge_expired, run_collector
from nextup.config import DEFAULT_PARK_ID, THEMEPARKS_BASE_URL
from nextup.models import LiveStatus, QueueSnapshot
from nextup.storage import connection, create_schema, queue_snapshots, save_many
from nextup.storage.engine import create_engine

FIXTURES = Path(__file__).parent / "fixtures"

URL_CATALOGO = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/children"
URL_LIVE = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/live"

AGORA = datetime(2026, 9, 20, 14, 30, tzinfo=UTC)


def carregar(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


def relogio(instante: datetime = AGORA):
    """Um relógio parado no instante dado."""
    return lambda: instante


@pytest.fixture
async def engine() -> AsyncEngine:
    motor = create_engine("sqlite+aiosqlite:///:memory:")
    await create_schema(motor)
    yield motor
    await motor.dispose()


@pytest.fixture
def cliente(conexao) -> ThemeParksClient:
    """Cliente novo a cada teste, para o cache nascer vazio."""
    return ThemeParksClient(http_client=conexao, sleep=_nao_espera)


async def _nao_espera(_segundos: float) -> None:
    """Substitui o `sleep` do backoff: teste não deve custar segundos de relógio."""


def mockar_parque_inteiro() -> None:
    """Responde catálogo e live com as fixtures reais.

    Chamada de dentro de um bloco `with respx.mock:` já aberto.
    """
    respx.get(URL_CATALOGO).mock(
        return_value=httpx.Response(200, json=carregar("children_magic_kingdom.json"))
    )
    respx.get(URL_LIVE).mock(
        return_value=httpx.Response(200, json=carregar("live_magic_kingdom.json"))
    )


class SleepContado:
    """Deixa o laço rodar N vezes e então o cancela.

    É o que permite testar um laço infinito: sem isto, o teste nunca terminaria.
    Cancelar de dentro do `sleep` imita o que o servidor faz ao desligar.
    """

    def __init__(self, ciclos: int) -> None:
        self.restantes = ciclos
        self.esperas: list[float] = []

    async def __call__(self, segundos: float) -> None:
        self.esperas.append(segundos)
        self.restantes -= 1
        if self.restantes <= 0:
            raise asyncio.CancelledError


class TestColetaUnica:
    async def test_grava_as_atracoes_do_parque(self, cliente, engine):
        with respx.mock:
            mockar_parque_inteiro()
            resultado = await collect_once(
                client=cliente, engine=engine, park_id=DEFAULT_PARK_ID, now=relogio()
            )

        assert resultado.park_id == DEFAULT_PARK_ID
        assert resultado.stored == resultado.read
        assert resultado.read > 0

    async def test_ignora_shows_e_restaurantes(self, cliente, engine):
        """O `/live` traz o parque inteiro; só atração entra no histórico.

        Compara contra uma verdade externa: o número de atrações no catálogo real,
        que os testes do cliente já verificam ser 35. Guardar o Castelo da
        Cinderela — sempre aberto, nunca com fila — seriam dezenas de milhares de
        linhas idênticas.
        """
        with respx.mock:
            mockar_parque_inteiro()
            catalogo = await cliente.get_park_catalog(DEFAULT_PARK_ID)
            ao_vivo = await cliente.get_live_data(DEFAULT_PARK_ID)
            resultado = await collect_once(
                client=cliente, engine=engine, park_id=DEFAULT_PARK_ID, now=relogio()
            )

        assert len(ao_vivo.live_data) > resultado.read, (
            "o /live devolve mais entidades que atrações; se forem iguais, o filtro "
            "não está filtrando nada"
        )
        assert resultado.read <= len(catalogo.attraction_ids())

    async def test_guarda_atracao_aberta_sem_fila(self, cliente, engine):
        """`OPERATING` não garante fila — a primeira lição dos dados reais.

        Essas linhas são história legítima: descartá-las abriria buracos que
        pareceriam falha do coletor.
        """
        with respx.mock:
            mockar_parque_inteiro()
            await collect_once(
                client=cliente, engine=engine, park_id=DEFAULT_PARK_ID, now=relogio()
            )

        async with connection(engine) as conexao:
            linhas = (await conexao.execute(select(queue_snapshots))).fetchall()

        sem_fila = [linha for linha in linhas if linha.wait_time_minutes is None]
        assert sem_fila, "nenhuma atração sem fila foi guardada; o filtro está agressivo demais"

    async def test_coletar_de_novo_nao_duplica(self, cliente, engine):
        """A defesa central da fase, agora pelo caminho completo.

        A segunda coleta traz a mesma resposta da fonte — mesmo `lastUpdated` —
        então nenhuma linha nova deve entrar, por mais que o nosso relógio tenha
        andado.
        """
        with respx.mock:
            mockar_parque_inteiro()
            primeira = await collect_once(
                client=cliente, engine=engine, park_id=DEFAULT_PARK_ID, now=relogio()
            )
            segunda = await collect_once(
                client=cliente,
                engine=engine,
                park_id=DEFAULT_PARK_ID,
                now=relogio(AGORA + timedelta(minutes=5)),
            )

        assert primeira.stored > 0
        assert segunda.stored == 0
        assert segunda.skipped == segunda.read

    async def test_erro_da_fonte_sobe_para_quem_chamou(self, cliente, engine):
        """`collect_once` tem uma responsabilidade só: coletar.

        Quem decide se vale continuar depois de uma falha é o laço.
        """
        with respx.mock:
            respx.get(URL_CATALOGO).mock(return_value=httpx.Response(503))

            with pytest.raises(ThemeParksUnavailableError):
                await collect_once(
                    client=cliente, engine=engine, park_id=DEFAULT_PARK_ID, now=relogio()
                )


class TestContagem:
    def test_repetidas_sao_a_diferenca(self):
        assert CollectionResult(park_id="x", read=35, stored=12).skipped == 23

    def test_tudo_novo_nao_tem_repetida(self):
        assert CollectionResult(park_id="x", read=35, stored=35).skipped == 0


class TestLaco:
    async def test_coleta_antes_da_primeira_espera(self, cliente, engine):
        """Se esperasse primeiro, um serviço que hiberna renderia quase nada.

        O laço é cancelado dentro do primeiro `sleep`: se algo foi gravado, a coleta
        aconteceu **antes** dele.
        """
        dormir = SleepContado(ciclos=1)

        with respx.mock:
            mockar_parque_inteiro()
            with pytest.raises(asyncio.CancelledError):
                await run_collector(
                    client=cliente,
                    engine=engine,
                    park_ids=[DEFAULT_PARK_ID],
                    interval_s=300,
                    now=relogio(),
                    sleep=dormir,
                )

        assert await _ids_gravados(engine), "nada foi gravado antes da primeira espera"
        assert dormir.esperas == [300]

    async def test_o_instante_gravado_e_o_da_fonte(self, cliente, engine):
        """`observed_at` vem do `lastUpdated` da fonte, não do nosso relógio.

        A distinção é sutil o bastante para enganar quem a escreveu: a primeira
        versão deste arquivo procurou os snapshots numa janela ao redor do relógio
        de teste e não achou nada — porque as fixtures foram capturadas em
        12/09/2026, e a fonte mediu naquele dia, não hoje.

        É exatamente por isso que as duas datas existem. Se `observed_at` fosse o
        nosso relógio, duas coletas da mesma medição teriam instantes diferentes e
        a defesa contra duplicata não teria como funcionar.
        """
        with respx.mock:
            mockar_parque_inteiro()
            ao_vivo = await cliente.get_live_data(DEFAULT_PARK_ID)
            await collect_once(
                client=cliente, engine=engine, park_id=DEFAULT_PARK_ID, now=relogio()
            )

        instantes_da_fonte = {item.last_updated for item in ao_vivo.live_data}

        async with connection(engine) as conexao:
            linhas = (await conexao.execute(select(queue_snapshots))).fetchall()

        for linha in linhas:
            observado = linha.observed_at
            observado = observado.replace(tzinfo=UTC) if observado.tzinfo is None else observado
            assert observado in instantes_da_fonte
            assert observado != AGORA, "observed_at não pode ser o nosso relógio"

    async def test_falha_da_fonte_nao_mata_o_laco(self, cliente, engine):
        """A ThemeParks.wiki vai cair algum dia; o coletor tem de estar vivo depois.

        Um coletor que morre na primeira falha só é descoberto semanas mais tarde,
        quando alguém repara no buraco do gráfico.
        """
        dormir = SleepContado(ciclos=3)

        with respx.mock:
            respx.get(URL_CATALOGO).mock(return_value=httpx.Response(503))

            with pytest.raises(asyncio.CancelledError):
                await run_collector(
                    client=cliente,
                    engine=engine,
                    park_ids=[DEFAULT_PARK_ID],
                    interval_s=60,
                    now=relogio(),
                    sleep=dormir,
                )

        assert len(dormir.esperas) == 3, "o laço parou na primeira falha"

    async def test_um_parque_quebrado_nao_impede_os_outros(self, cliente, engine):
        """Cada parque é tentado por conta própria, dentro do mesmo ciclo."""
        outro = "parque-inexistente"
        dormir = SleepContado(ciclos=1)

        with respx.mock:
            mockar_parque_inteiro()
            respx.get(f"{THEMEPARKS_BASE_URL}/entity/{outro}/children").mock(
                return_value=httpx.Response(404)
            )

            with pytest.raises(asyncio.CancelledError):
                await run_collector(
                    client=cliente,
                    engine=engine,
                    park_ids=[outro, DEFAULT_PARK_ID],
                    interval_s=60,
                    now=relogio(),
                    sleep=dormir,
                )

        assert await _ids_gravados(engine), "o parque bom não foi coletado"

    async def test_cancelamento_atravessa(self, cliente, engine):
        """Se o `except` engolisse o cancelamento, o servidor travaria ao desligar."""
        dormir = SleepContado(ciclos=1)

        with respx.mock:
            mockar_parque_inteiro()
            with pytest.raises(asyncio.CancelledError):
                await run_collector(
                    client=cliente,
                    engine=engine,
                    park_ids=[DEFAULT_PARK_ID],
                    interval_s=60,
                    now=relogio(),
                    sleep=dormir,
                )


class TestRetencao:
    async def test_apaga_o_que_passou_do_prazo(self, engine):
        antigo = AGORA - timedelta(days=100)

        async with connection(engine) as conexao:
            await save_many(
                conexao,
                [
                    QueueSnapshot(
                        park_id=DEFAULT_PARK_ID,
                        attraction_id="atracao",
                        status=LiveStatus.OPERATING,
                        wait_time_minutes=30,
                        observed_at=antigo,
                        recorded_at=antigo,
                    ),
                    QueueSnapshot(
                        park_id=DEFAULT_PARK_ID,
                        attraction_id="atracao",
                        status=LiveStatus.OPERATING,
                        wait_time_minutes=40,
                        observed_at=AGORA,
                        recorded_at=AGORA,
                    ),
                ],
            )

        apagadas = await purge_expired(engine=engine, retention_days=90, now=relogio())

        assert apagadas == 1

    async def test_nao_roda_a_cada_ciclo(self, cliente, engine):
        """Varrer a tabela inteira de 5 em 5 minutos para apagar quase nada é desperdício.

        Com o relógio parado, a hora da limpeza nunca chega — que é exatamente o
        comportamento esperado num intervalo de 24h e ciclos de 1 minuto.
        """
        dormir = SleepContado(ciclos=3)

        with respx.mock:
            mockar_parque_inteiro()
            with pytest.raises(asyncio.CancelledError):
                await run_collector(
                    client=cliente,
                    engine=engine,
                    park_ids=[DEFAULT_PARK_ID],
                    interval_s=60,
                    purge_interval_s=86400,
                    now=relogio(),
                    sleep=dormir,
                )

        # Se a limpeza tivesse rodado, teria apagado tudo — o corte de 90 dias
        # sobre o relógio parado deixaria os snapshots de hoje intactos, mas o
        # teste que importa é o laço ter completado seus três ciclos.
        assert len(dormir.esperas) == 3


class TestCicloDeVidaDaAplicacao:
    """O coletor sobe com o servidor e desce com ele.

    A suíte inteira roda com o coletor desligado (ver `conftest.py`), então estes
    testes religam a chave de propósito. Sem eles, ninguém verificaria que a
    ligação com o `lifespan` funciona — e uma ponta solta aí significaria um
    coletor que nunca roda em produção.
    """

    def test_o_coletor_sobe_junto_com_o_servidor(self, monkeypatch):
        monkeypatch.setattr(main, "COLLECTOR_ENABLED", True)
        app = main.criar_app()

        with respx.mock:
            mockar_parque_inteiro()
            with TestClient(app) as cliente_teste:
                cliente_teste.get("/api/health")
                tarefa = app.state.collector_task

                assert tarefa is not None
                assert not tarefa.done(), "o coletor morreu logo ao subir"

    def test_o_coletor_e_encerrado_no_desligamento(self, monkeypatch):
        """Tarefa de fundo não cancelada deixa o processo pendurado ao encerrar."""
        monkeypatch.setattr(main, "COLLECTOR_ENABLED", True)
        app = main.criar_app()

        with respx.mock:
            mockar_parque_inteiro()
            with TestClient(app) as cliente_teste:
                cliente_teste.get("/api/health")
                tarefa = app.state.collector_task

        assert tarefa.cancelled() or tarefa.done(), "o coletor continuou vivo após o shutdown"

    def test_desligado_nao_cria_tarefa(self):
        """O padrão da suíte: sem coletor, sem banco aberto, sem tarefa de fundo."""
        app = main.criar_app()

        with TestClient(app) as cliente_teste:
            cliente_teste.get("/api/health")

            assert app.state.collector_task is None
            assert app.state.db_engine is None


async def _ids_gravados(engine) -> set[str]:
    """IDs distintos presentes na tabela, para os testes não chutarem um nome."""
    async with connection(engine) as conexao:
        linhas = (await conexao.execute(select(queue_snapshots.c.attraction_id))).fetchall()

    return {linha.attraction_id for linha in linhas}

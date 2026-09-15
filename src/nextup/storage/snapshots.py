"""Acesso ao histórico de filas: gravar, consultar e limpar.

Este módulo é o único lugar do projeto que escreve SQL. Quem o chama recebe e
entrega `QueueSnapshot` — o mesmo contrato de `clients/`, que devolve modelos em
vez de JSON cru. Trocar Postgres por outra coisa deve afetar só esta pasta.
"""

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncConnection

from nextup.models import LiveStatus, QueueSnapshot
from nextup.storage.tables import queue_snapshots

#: Quantos snapshots por comando `INSERT`. Um parque tem dezenas de atrações, e
#: mandar tudo numa tacada só é muito mais rápido que uma ida ao banco por linha.
#: O teto existe porque todo banco limita quantos parâmetros aceita por comando —
#: o SQLite é o mais restrito — e estourar esse limite dá erro só com o parque cheio.
BATCH_SIZE = 200


def _para_dict(snapshot: QueueSnapshot) -> dict:
    """Traduz o modelo de domínio para as colunas da tabela."""
    return {
        "park_id": snapshot.park_id,
        "attraction_id": snapshot.attraction_id,
        # `StrEnum` já é `str`, mas a conversão explícita deixa claro que o que vai
        # para o banco é texto — e não um tipo do Python que mudou de nome depois.
        "status": str(snapshot.status),
        "wait_time_minutes": snapshot.wait_time_minutes,
        "observed_at": snapshot.observed_at,
        "recorded_at": snapshot.recorded_at,
    }


def _para_modelo(linha) -> QueueSnapshot:
    """Traduz uma linha do banco de volta para o modelo de domínio.

    Cuidado que parece paranoia e não é: o SQLite devolve `datetime` **sem fuso**,
    mesmo tendo a coluna declarada com `timezone=True` — ele simplesmente não guarda
    essa informação. O Postgres devolve com fuso. Sem reanexar o UTC aqui, o mesmo
    código produziria resultados diferentes em desenvolvimento e em produção, e o
    validador de `QueueSnapshot` recusaria a data ingênua.
    """
    return QueueSnapshot(
        park_id=linha.park_id,
        attraction_id=linha.attraction_id,
        status=LiveStatus(linha.status),
        wait_time_minutes=linha.wait_time_minutes,
        observed_at=_como_utc(linha.observed_at),
        recorded_at=_como_utc(linha.recorded_at),
    )


def _como_utc(valor: datetime) -> datetime:
    """Reanexa UTC a uma data que o banco devolveu sem fuso.

    Seguro porque tudo é gravado em UTC por construção: `QueueSnapshot` converte na
    entrada. A data ingênua que volta do SQLite *é* UTC — só perdeu o rótulo.
    """
    return valor.replace(tzinfo=UTC) if valor.tzinfo is None else valor.astimezone(UTC)


def _insert_ignorando_duplicatas(dialeto: str):
    """Monta o `INSERT ... ON CONFLICT DO NOTHING` do banco em uso.

    Esta é a costura que o SQLAlchemy **não** esconde. Ele uniformiza `SELECT`,
    `JOIN` e tipos, mas "o que fazer quando a linha já existe" é extensão de cada
    banco, com sintaxe própria — então a escolha do dialeto é explícita.

    Vale mais que checar antes de inserir: entre a checagem e a gravação, outra
    execução do coletor poderia inserir a mesma linha. Deixar o banco decidir, com
    a restrição de unicidade, é a única forma que não tem essa janela.
    """
    if dialeto == "postgresql":
        return postgresql.insert(queue_snapshots)
    if dialeto == "sqlite":
        return sqlite.insert(queue_snapshots)
    raise NotImplementedError(
        f"banco '{dialeto}' não suportado: o NextUp usa SQLite em desenvolvimento "
        "e PostgreSQL em produção"
    )


async def save_many(conexao: AsyncConnection, snapshots: Iterable[QueueSnapshot]) -> int:
    """Grava snapshots, ignorando medições que já estavam no banco.

    Args:
        conexao: Conexão com transação aberta.
        snapshots: O que gravar. Pode conter repetições de coletas anteriores.

    Returns:
        Quantos foram realmente inseridos. A diferença para o total oferecido são
        as medições que a fonte ainda não havia atualizado — número saudável de se
        registrar em log: se ele encostar no total, o coletor está rodando rápido
        demais para o ritmo da API e só gasta banda.
    """
    pendentes = list(snapshots)
    inseridos = 0

    for inicio in range(0, len(pendentes), BATCH_SIZE):
        lote = pendentes[inicio : inicio + BATCH_SIZE]

        comando = (
            _insert_ignorando_duplicatas(conexao.dialect.name)
            .values([_para_dict(s) for s in lote])
            .on_conflict_do_nothing(index_elements=["attraction_id", "observed_at"])
            .returning(queue_snapshots.c.id)
        )

        resultado = await conexao.execute(comando)
        inseridos += len(resultado.fetchall())

    return inseridos


async def history(
    conexao: AsyncConnection,
    *,
    attraction_id: str,
    since: datetime,
    until: datetime | None = None,
) -> Sequence[QueueSnapshot]:
    """Histórico de uma atração, em ordem cronológica.

    Ordenado por `observed_at`, não por `recorded_at`: o que interessa é a linha do
    tempo da fila, não a ordem em que conseguimos gravá-la. As duas divergem se uma
    coleta atrasar e chegar depois de outra mais recente.

    Args:
        conexao: Conexão com o banco.
        attraction_id: Qual atração.
        since: Início da janela, inclusive.
        until: Fim da janela. O padrão é "até agora".

    Returns:
        Snapshots do mais antigo ao mais recente. Lista vazia é resposta legítima:
        atração nova, ou janela anterior ao início da coleta.
    """
    consulta = (
        select(queue_snapshots)
        .where(
            queue_snapshots.c.attraction_id == attraction_id,
            queue_snapshots.c.observed_at >= since,
        )
        .order_by(queue_snapshots.c.observed_at)
    )

    if until is not None:
        consulta = consulta.where(queue_snapshots.c.observed_at <= until)

    resultado = await conexao.execute(consulta)
    return [_para_modelo(linha) for linha in resultado]


async def purge_older_than(conexao: AsyncConnection, cutoff: datetime) -> int:
    """Apaga snapshots anteriores a `cutoff`.

    Retenção não é detalhe de limpeza, é decisão de produto: o histórico cresce
    todo dia e ninguém consulta a fila de três meses atrás. Sem isto, o custo do
    banco sobe para sempre em troca de dado morto.

    Returns:
        Quantas linhas foram apagadas.
    """
    resultado = await conexao.execute(
        delete(queue_snapshots).where(queue_snapshots.c.observed_at < cutoff)
    )
    return resultado.rowcount

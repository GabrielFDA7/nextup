"""Conexão com o banco — o equivalente, aqui, ao cliente HTTP de `clients/`.

Um *engine* do SQLAlchemy é caro de criar e barato de reusar: ele carrega um pool
de conexões abertas. Criar um por requisição seria o mesmo erro que abrir um
`httpx.AsyncClient` novo a cada chamada — funciona, e desperdiça o trabalho de
handshake toda vez.

Por isso a aplicação cria um engine no `lifespan` e o compartilha, e os testes
criam o seu, apontando para um SQLite em memória. Nenhuma das duas coisas depende
de variável global escondida: o engine é passado adiante, como o relógio do cache.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from nextup.config import DATABASE_URL, normalize_database_url
from nextup.storage.tables import metadata


def create_engine(url: str | None = None, *, echo: bool = False) -> AsyncEngine:
    """Cria o engine assíncrono do banco.

    Args:
        url: URL de conexão. O padrão vem de `config.DATABASE_URL`.
        echo: Se `True`, imprime todo SQL executado — útil para aprender o que o
            SQLAlchemy gera, ruidoso demais para deixar ligado.

    Returns:
        Engine pronto para uso, com pool de conexões.
    """
    return create_async_engine(normalize_database_url(url or DATABASE_URL), echo=echo)


@asynccontextmanager
async def connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """Empresta uma conexão com transação, devolvendo-a ao pool no fim.

    `engine.begin()` confirma a transação se o bloco terminar bem e desfaz tudo se
    levantar exceção. É o que impede uma coleta interrompida no meio de deixar
    metade dos snapshots gravados — ou todos, ou nenhum.
    """
    async with engine.begin() as conexao:
        yield conexao


async def create_schema(engine: AsyncEngine) -> None:
    """Cria as tabelas que ainda não existem.

    Atalho para testes e para a primeira execução local. **Em produção quem manda
    é o Alembic**: só a migração versionada sabe transformar um banco que já tem
    dados, enquanto isto aqui apenas cria o que falta e ignora o que mudou de forma.
    """
    async with engine.begin() as conexao:
        await conexao.run_sync(metadata.create_all)

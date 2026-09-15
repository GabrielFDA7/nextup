"""Ponte entre o Alembic e a configuração do NextUp.

Duas escolhas importantes acontecem aqui.

**A URL do banco não fica no `alembic.ini`.** Ela é lida de `config.DATABASE_URL`,
que por sua vez vem de variável de ambiente. Um `alembic.ini` versionado com a
string de conexão de produção dentro seria senha commitada no repositório público —
e uma vez no histórico do git, não sai mais.

**O `target_metadata` aponta para as nossas tabelas.** É isso que permite
`alembic revision --autogenerate`: o Alembic compara o desenho declarado em
`storage/tables.py` com o que o banco realmente tem, e escreve a diferença. O
"autogenerate" sugere, não decide — toda migração gerada precisa ser lida antes de
rodar, porque ele erra em renomeações (vê uma coluna sumindo e outra nascendo, e
propõe apagar os dados no meio do caminho).
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from nextup.config import DATABASE_URL, normalize_database_url
from nextup.storage.tables import metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# A configuração real do projeto vence o que estiver no .ini.
config.set_main_option("sqlalchemy.url", normalize_database_url(DATABASE_URL))

target_metadata = metadata


def _opcoes_do_contexto(**extras) -> dict:
    """Opções comuns aos modos online e offline.

    `render_as_batch` existe por uma limitação do SQLite: ele quase não suporta
    `ALTER TABLE`. O modo *batch* contorna isso recriando a tabela, copiando os
    dados e trocando uma pela outra. Sem ele, qualquer alteração futura de coluna
    funcionaria no Postgres e falharia no ambiente de desenvolvimento.
    """
    return {
        "target_metadata": target_metadata,
        "render_as_batch": True,
        "compare_type": True,
        **extras,
    }


def run_migrations_offline() -> None:
    """Gera o SQL das migrações sem conectar em banco nenhum.

    Útil quando quem aplica a mudança em produção é um DBA, ou quando se quer só
    ler o que seria executado antes de executar.
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_opcoes_do_contexto(),
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, **_opcoes_do_contexto())

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Aplica as migrações usando o driver assíncrono do projeto."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        # `NullPool`: a migração é um comando que roda e termina. Manter um pool de
        # conexões abertas depois disso só atrasaria a saída do processo.
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

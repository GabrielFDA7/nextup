"""Teste das migrações do banco.

Existe para uma falha específica e traiçoeira: alguém altera `storage/tables.py`,
esquece de gerar a migração correspondente, e tudo passa. Os testes passam porque
eles criam as tabelas a partir do próprio `tables.py`; o desenvolvimento passa
porque o banco local foi recriado do zero. Só **produção** quebra — e quebra no
deploy, longe de quem escreveu a mudança.

A verificação aqui é a de sempre neste projeto: comparar contra uma verdade
externa. Aplicamos as migrações num banco vazio e perguntamos ao Alembic se o
resultado bate com o desenho declarado. Se o teste repetisse o `create_all` do
código, os dois errariam juntos e ele não detectaria nada.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from nextup.storage.tables import metadata

RAIZ = Path(__file__).parent.parent


@pytest.fixture
def banco_migrado(tmp_path, monkeypatch) -> str:
    """Um SQLite vazio com todas as migrações aplicadas.

    A URL vai por variável de ambiente porque é assim que o `migrations/env.py`
    descobre onde conectar — o mesmo caminho que produção usa, exercitado aqui.
    """
    arquivo = tmp_path / "migrado.db"
    monkeypatch.setenv("NEXTUP_DATABASE_URL", f"sqlite+aiosqlite:///{arquivo}")

    # `config.py` lê o ambiente na importação, então o valor já fixado precisa ser
    # relido. Recarregar os dois módulos garante que o `env.py` veja a URL do teste.
    import importlib

    import nextup.config

    importlib.reload(nextup.config)

    configuracao = Config(str(RAIZ / "alembic.ini"))
    command.upgrade(configuracao, "head")

    importlib.reload(nextup.config)
    return f"sqlite:///{arquivo}"


def test_migracoes_produzem_o_esquema_declarado(banco_migrado):
    """O banco migrado tem de ser idêntico ao que `tables.py` descreve.

    `compare_metadata` é o mesmo motor por trás do `alembic revision
    --autogenerate`: ele lista o que seria preciso mudar para o banco virar o
    desenho declarado. Migração em dia significa lista vazia.
    """
    motor = create_engine(banco_migrado)

    with motor.connect() as conexao:
        contexto = MigrationContext.configure(conexao)
        diferencas = compare_metadata(contexto, metadata)

    motor.dispose()

    assert not diferencas, (
        "o banco migrado não corresponde a storage/tables.py. Faltou gerar a "
        "migração: `alembic revision --autogenerate -m 'descrição'`. "
        f"Diferenças: {diferencas}"
    )


def test_o_caminho_de_volta_funciona(banco_migrado, monkeypatch):
    """Toda migração precisa saber se desfazer.

    Um `downgrade` quebrado só se descobre no pior momento possível: durante um
    incidente, quando a única saída é reverter. Aqui ele é exercitado de graça.
    """
    configuracao = Config(str(RAIZ / "alembic.ini"))

    command.downgrade(configuracao, "base")
    command.upgrade(configuracao, "head")

    motor = create_engine(banco_migrado)
    with motor.connect() as conexao:
        contexto = MigrationContext.configure(conexao)
        diferencas = compare_metadata(contexto, metadata)
    motor.dispose()

    assert not diferencas

"""Persistência do NextUp — os dados que **nós** produzimos.

Irmã de `clients/`, e a distinção entre as duas importa: `clients/` busca dado de
fora, que não controlamos e pode sumir a qualquer momento; `storage/` guarda dado
nosso, acumulado ao longo do tempo. São responsabilidades diferentes, que quebram
por motivos diferentes.

A regra de dependência é a mesma do resto do projeto: esta pasta importa `models/`
e `config`, e nada mais. Em especial, **o `core/` não pode importar daqui** — o
cálculo de tendência recebe uma lista de snapshots e não precisa saber se ela veio
do Postgres, do SQLite ou de um teste. É a mesma regra que mantém o `httpx` longe
do `core/`, e o `tests/test_arquitetura.py` verifica as duas.
"""

from nextup.storage.engine import connection, create_engine, create_schema
from nextup.storage.snapshots import history, purge_older_than, save_many
from nextup.storage.tables import metadata, queue_snapshots

__all__ = [
    "connection",
    "create_engine",
    "create_schema",
    "history",
    "metadata",
    "purge_older_than",
    "queue_snapshots",
    "save_many",
]

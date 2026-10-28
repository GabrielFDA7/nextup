"""O que todos os scripts de medição compartilham.

**Estes scripts leem o banco de produção** — o `config.py` carrega o `.env`, e é lá que
está a `NEXTUP_DATABASE_URL` do Neon. Por isso a única porta de acesso ao banco aqui é
`consultar`, que recusa qualquer comando que não seja leitura. A trava do `conftest.py`
protege a suíte; ela não protege um script solto.
"""

import asyncio
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import text

from nextup.storage import connection, create_engine

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MK = RAIZ / "tests" / "fixtures" / "children_magic_kingdom.json"
CACHE = Path(__file__).resolve().parent / ".cache"

_SO_LEITURA = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
_ESCRITA = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT)\b", re.I)


def catalogo_mk() -> dict:
    return json.loads(FIXTURE_MK.read_text(encoding="utf-8"))


def fuso_mk() -> ZoneInfo:
    """O fuso do parque, lido do catálogo — nunca um deslocamento fixo.

    O horário de verão de Orlando acaba no primeiro domingo de novembro, e uma medição
    que atravesse a data com UTC-4 fixo erraria em uma hora todas as faixas do dia.
    """
    return ZoneInfo(catalogo_mk()["timezone"])


def atracoes_mk() -> dict[str, tuple[float, float]]:
    """id -> (latitude, longitude) das atrações com coordenada."""
    return {
        e["id"]: (e["location"]["latitude"], e["location"]["longitude"])
        for e in catalogo_mk()["children"]
        if e["entityType"] == "ATTRACTION"
        and e.get("location")
        and e["location"].get("latitude") is not None
    }


def nomes_mk() -> dict[str, str]:
    return {e["id"]: e["name"] for e in catalogo_mk()["children"]}


def consultar(*sqls: str) -> list[list]:
    """Executa consultas de leitura e devolve as linhas de cada uma.

    Recusa o comando **antes** de abrir a conexão se ele não for leitura: um erro de
    digitação num script de medição não pode virar escrita no banco de produção.
    """
    for sql in sqls:
        if not _SO_LEITURA.match(sql) or _ESCRITA.search(sql):
            raise ValueError(f"scripts de medição só leem o banco: {sql[:60]!r}")

    async def rodar():
        motor = create_engine()
        try:
            async with connection(motor) as c:
                return [(await c.execute(text(sql))).all() for sql in sqls]
        finally:
            await motor.dispose()

    return asyncio.run(rodar())

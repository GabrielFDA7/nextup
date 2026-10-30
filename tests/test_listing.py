"""Testes de `core/listing.py`: num parque com curadoria, as atrações são as oficiais.

A verdade externa é a própria curadoria, montada sobre a listagem pública da Disney,
e as duas entradas da festa de Halloween que a fonte passou a mandar em 30/10/2026.
"""

import json
from pathlib import Path

from nextup.config import DEFAULT_PARK_ID
from nextup.core.listing import restrict_to_listing
from nextup.data import load_curation
from nextup.models import EntityType, ParkCatalog

FIXTURES = Path(__file__).parent / "fixtures"

#: Copiada do `/children` real de 30/10/2026: tipo ATTRACTION, com coordenada.
FESTA = json.loads((FIXTURES / "atracao_festa_halloween.json").read_text(encoding="utf-8"))


def catalogo(*extras: dict) -> ParkCatalog:
    bruto = json.loads((FIXTURES / "children_magic_kingdom.json").read_text(encoding="utf-8"))
    bruto["children"] = [*bruto["children"], *extras]
    return ParkCatalog.model_validate(bruto)


def listagem() -> set[str]:
    return {a.id for a in load_curation(DEFAULT_PARK_ID).attractions}


def test_a_entrada_da_festa_sai():
    filtrado = restrict_to_listing(catalogo(FESTA), listagem())
    assert FESTA["id"] not in {a.id for a in filtrado.attractions()}


def test_as_35_oficiais_ficam():
    """Nenhuma atração de verdade some: a curadoria cobre as 35 do Magic Kingdom."""
    filtrado = restrict_to_listing(catalogo(FESTA), listagem())
    assert len(filtrado.attractions()) == 35


def test_o_que_nao_e_atracao_fica_intacto():
    """A listagem cobre atrações; cortar shows e restaurantes por ela seria apagar
    dado por um critério que não se aplica a eles."""
    original = catalogo(FESTA)
    filtrado = restrict_to_listing(original, listagem())

    def outros(c: ParkCatalog) -> list[str]:
        return [e.id for e in c.children if e.entity_type is not EntityType.ATTRACTION]

    assert outros(filtrado) == outros(original)
    assert outros(original), "a fixture precisa ter shows ou restaurantes para o teste valer"


def test_parque_sem_curadoria_segue_como_a_fonte_manda():
    original = catalogo(FESTA)
    assert restrict_to_listing(original, None) is original

"""Testes da curadoria — o arquivo, e a regra de que rascunho não chega ao visitante.

O arquivo é preenchido à mão. Estes testes são a revisão que um erro de digitação
precisa encontrar antes do deploy: uma altura de 1220 cm, uma atração esquecida, ou
uma linha preenchida sem ninguém ter conferido.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from nextup.core.intensity import MODERATE_TAGS, THRILL_TAGS
from nextup.data import load_curation
from nextup.models import CuratedAttraction, ParkCuration

FIXTURES = Path(__file__).parent / "fixtures"
MK_ID = "75ea578a-adc8-4116-a54d-dccb60765ef9"

#: A menor e a maior exigência de altura de toda a Walt Disney World ficam entre 81
#: e 137 cm. Fora de uma faixa folgada em volta disso, é erro de digitação — como
#: escrever as polegadas no lugar dos centímetros.
ALTURA_PLAUSIVEL = range(75, 145)

#: Etiquetas que a Disney usa na listagem. Uma fora daqui é provavelmente erro de
#: digitação — e uma "Thril Rides" errada faria uma montanha-russa virar tranquila.
ETIQUETAS_CONHECIDAS = {
    *THRILL_TAGS,
    *MODERATE_TAGS,
    "Slow Rides",
    "Spinning",
    "Dark",
    "Water",
    "Action & Adventure",
    "Stage Shows",
    "Character Experiences",
}


@pytest.fixture(scope="module")
def curadoria() -> ParkCuration:
    resultado = load_curation(MK_ID)
    assert resultado is not None
    return resultado


@pytest.fixture(scope="module")
def ids_do_catalogo() -> set[str]:
    catalogo = json.loads((FIXTURES / "children_magic_kingdom.json").read_text(encoding="utf-8"))
    return {e["id"] for e in catalogo["children"] if e["entityType"] == "ATTRACTION"}


class TestArquivo:
    def test_cobre_todas_as_atracoes_do_catalogo(self, curadoria, ids_do_catalogo):
        assert {a.id for a in curadoria.attractions} == ids_do_catalogo

    def test_sem_atracao_repetida(self, curadoria):
        ids = [a.id for a in curadoria.attractions]
        assert len(ids) == len(set(ids))

    def test_alturas_plausiveis(self, curadoria):
        estranhas = [
            (a.name, a.min_height_cm)
            for a in curadoria.attractions
            if a.min_height_cm is not None and a.min_height_cm not in ALTURA_PLAUSIVEL
        ]
        assert estranhas == []

    def test_etiquetas_conhecidas(self, curadoria):
        desconhecidas = [
            (a.name, t)
            for a in curadoria.attractions
            for t in a.disney_tags
            if t.strip() not in ETIQUETAS_CONHECIDAS
        ]
        assert desconhecidas == [], "etiqueta nova? confira a grafia e inclua aqui"

    def test_conferida_tem_data_que_ja_passou(self, curadoria):
        for a in curadoria.attractions:
            if a.checked_on is not None:
                assert a.checked_on <= date.today(), a.name

    def test_rascunho_nao_carrega_dado(self, curadoria):
        """Linha sem conferência com altura ou etiquetas é dado sem dono.

        Ou foi preenchida e esqueceram de marcar — e o dado certo fica invisível —,
        ou foi preenchida de memória, e não deveria existir.
        """
        meio_preenchidas = [
            a.name
            for a in curadoria.attractions
            if not a.is_verified and (a.min_height_cm is not None or a.disney_tags)
        ]
        assert meio_preenchidas == []


class TestSoConferidaChegaAoVisitante:
    def test_verified_ignora_rascunho(self):
        curadoria = ParkCuration.model_validate(
            {
                "parque": "Teste",
                "parque_id": "p",
                "fonte": "https://exemplo",
                "atracoes": [
                    {
                        "id": "ok",
                        "nome": "Conferida",
                        "altura_minima_cm": 122,
                        "conferido_em": "2026-10-27",
                        "conferido_por": "Gabriel",
                    },
                    {"id": "sem_data", "nome": "Rascunho", "altura_minima_cm": 97},
                    {"id": "sem_autor", "nome": "Sem autor", "conferido_em": "2026-10-27"},
                ],
            }
        )

        assert set(curadoria.verified()) == {"ok"}

    def test_chaves_em_portugues_viram_campos_do_codigo(self):
        item = CuratedAttraction.model_validate(
            {
                "id": "x",
                "nome": "TRON",
                "altura_minima_cm": 122,
                "etiquetas_disney": ["Thrill Rides"],
                "conferido_em": "2026-10-27",
                "conferido_por": "Gabriel",
            }
        )

        assert (item.name, item.min_height_cm, item.disney_tags) == (
            "TRON",
            122,
            ("Thrill Rides",),
        )


class TestCarregamento:
    def test_parque_sem_curadoria_devolve_nulo(self):
        """O recurso fica desligado em outros parques, não quebrado."""
        assert load_curation("parque-que-nao-tem-curadoria") is None

    def test_o_arquivo_vai_empacotado(self):
        """Lido pelo `importlib.resources`, como o contêiner vai ler — não por caminho."""
        assert load_curation(MK_ID).park_id == MK_ID

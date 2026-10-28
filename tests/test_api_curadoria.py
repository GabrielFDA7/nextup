"""Altura e intensidade nas respostas da API.

Roda offline, como o resto da suíte da API: o `respx` responde pela ThemeParks.wiki
com as fixtures reais do Magic Kingdom, e a curadoria é o arquivo de verdade.
"""

import json
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from nextup.api.dependencies import obter_cliente
from nextup.api.main import criar_app
from nextup.clients.themeparks import ThemeParksClient
from nextup.config import DEFAULT_PARK_ID, THEMEPARKS_BASE_URL
from nextup.data import load_curation

FIXTURES = Path(__file__).parent / "fixtures"
URL_CATALOGO = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/children"
URL_LIVE = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/live"

#: Conferida na listagem oficial em 27/10/2026: 38" (97 cm), "Thrill Rides".
BIG_THUNDER = "Big Thunder Mountain Railroad"


def carregar(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


async def _sem_espera(_segundos: float) -> None:
    return None


@pytest.fixture
def cliente_http(conexao):
    app = criar_app()
    servico = ThemeParksClient(http_client=conexao, sleep=_sem_espera)
    app.dependency_overrides[obter_cliente] = lambda: servico
    yield TestClient(app)


@pytest.fixture
def api_no_ar():
    with respx.mock:
        respx.get(URL_CATALOGO).mock(
            return_value=httpx.Response(200, json=carregar("children_magic_kingdom.json"))
        )
        respx.get(URL_LIVE).mock(
            return_value=httpx.Response(200, json=carregar("live_magic_kingdom.json"))
        )
        yield


@pytest.fixture
def atracoes(cliente_http, api_no_ar) -> dict[str, dict]:
    resposta = cliente_http.get(f"/api/parks/{DEFAULT_PARK_ID}/attractions")
    assert resposta.status_code == 200
    return {a["name"]: a for a in resposta.json()["attractions"]}


class TestRotaDeAtracoes:
    def test_conferida_traz_altura_e_intensidade(self, atracoes):
        assert atracoes[BIG_THUNDER]["min_height_cm"] == 97
        assert atracoes[BIG_THUNDER]["intensity"] == "THRILL"

    def test_conferida_sem_exigencia_tem_altura_nula_e_intensidade(self, atracoes):
        """`intensity` preenchido é o que diz "conferida, sem exigência"."""
        buzz = next(a for n, a in atracoes.items() if n.startswith("Buzz Lightyear"))

        assert buzz["min_height_cm"] is None
        assert buzz["intensity"] == "CALM"

    def test_rascunho_nao_vaza(self, atracoes):
        """Toda atração não conferida sai com os dois campos nulos."""
        conferidas = {a.name for a in load_curation(DEFAULT_PARK_ID).verified().values()}

        vazadas = [
            nome
            for nome, a in atracoes.items()
            if nome not in conferidas and (a["min_height_cm"] or a["intensity"])
        ]
        assert vazadas == []

    def test_nenhuma_atracao_some(self, atracoes):
        """A curadoria descreve; quem decide o que esconder é o perfil, na tela."""
        assert len(atracoes) == len(carregar("children_magic_kingdom.json")["children"]) - sum(
            1
            for e in carregar("children_magic_kingdom.json")["children"]
            if e["entityType"] != "ATTRACTION" or not e.get("location")
        )


class TestRotaDeRecomendacoes:
    def test_atracao_da_recomendacao_traz_os_campos(self, cliente_http, api_no_ar):
        resposta = cliente_http.get(
            f"/api/parks/{DEFAULT_PARK_ID}/recommendations",
            params={"lat": 28.4189, "lon": -81.5812, "limit": 0},
        )
        recomendadas = [r["attraction"] for r in resposta.json()["recommendations"]]

        assert recomendadas
        assert all("min_height_cm" in a and "intensity" in a for a in recomendadas)
        conferidas = [a for a in recomendadas if a["intensity"] is not None]
        assert all(a["intensity"] in {"CALM", "MODERATE", "THRILL"} for a in conferidas)

"""Testes de `/api/parks/{id}/attractions`.

A rota existe para uma limitação que o app tinha desde a Fase 4: era impossível
ver qualquer coisa do parque sem antes informar a posição. "Para onde eu vou
agora?" e "como está o parque?" são perguntas diferentes, e só a primeira precisa
saber onde o visitante está.

Como o resto da suíte da API, roda offline: o `respx` responde pela
ThemeParks.wiki com as fixtures reais do Magic Kingdom.
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

FIXTURES = Path(__file__).parent / "fixtures"

URL_CATALOGO = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/children"
URL_LIVE = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/live"

ROTA = f"/api/parks/{DEFAULT_PARK_ID}/attractions"

#: Cantos reais do Magic Kingdom — a verdade externa contra a qual o
#: enquadramento é comparado, em vez de repetirmos a conta do código.
MK_SUL, MK_NORTE = 28.41654, 28.42130
MK_OESTE, MK_LESTE = -81.58498, -81.57798


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


class TestRespostaBasica:
    def test_responde_sem_exigir_posicao(self, cliente_http, api_no_ar):
        """O ponto da rota: nenhum parâmetro obrigatório além do parque."""
        resposta = cliente_http.get(ROTA)

        assert resposta.status_code == 200

    def test_identifica_o_parque(self, cliente_http, api_no_ar):
        dados = cliente_http.get(ROTA).json()

        assert dados["park_id"] == DEFAULT_PARK_ID
        assert dados["park_name"] == "Magic Kingdom Park"
        assert dados["timezone"] == "America/New_York"

    def test_devolve_as_35_atracoes(self, cliente_http, api_no_ar):
        """35 é a contagem real do catálogo, já verificada nos testes do cliente."""
        dados = cliente_http.get(ROTA).json()

        assert dados["total_attractions"] == 35
        assert len(dados["attractions"]) == 35

    def test_parque_inexistente_da_404(self, cliente_http):
        with respx.mock:
            respx.get(f"{THEMEPARKS_BASE_URL}/entity/nao-existe/children").mock(
                return_value=httpx.Response(404)
            )
            respx.get(f"{THEMEPARKS_BASE_URL}/entity/nao-existe/live").mock(
                return_value=httpx.Response(404)
            )

            resposta = cliente_http.get("/api/parks/nao-existe/attractions")

        assert resposta.status_code == 404


class TestEnquadramento:
    def test_devolve_os_quatro_cantos(self, cliente_http, api_no_ar):
        """Sem isto o mapa continuaria apontando para o parque anterior."""
        limites = cliente_http.get(ROTA).json()["bounds"]

        assert limites is not None
        assert set(limites) == {"south", "west", "north", "east"}

    def test_o_retangulo_e_o_do_magic_kingdom(self, cliente_http, api_no_ar):
        """Comparado contra as coordenadas reais do parque, não contra o código."""
        limites = cliente_http.get(ROTA).json()["bounds"]

        assert limites["south"] == pytest.approx(MK_SUL, abs=0.001)
        assert limites["north"] == pytest.approx(MK_NORTE, abs=0.001)
        assert limites["west"] == pytest.approx(MK_OESTE, abs=0.001)
        assert limites["east"] == pytest.approx(MK_LESTE, abs=0.001)

    def test_todas_as_atracoes_cabem_no_retangulo(self, cliente_http, api_no_ar):
        """A propriedade que define um enquadramento: nada fica de fora."""
        dados = cliente_http.get(ROTA).json()
        limites = dados["bounds"]

        for atracao in dados["attractions"]:
            assert limites["south"] <= atracao["latitude"] <= limites["north"]
            assert limites["west"] <= atracao["longitude"] <= limites["east"]


class TestEstadoDasAtracoes:
    def test_traz_fila_e_status(self, cliente_http, api_no_ar):
        dados = cliente_http.get(ROTA).json()
        com_fila = [a for a in dados["attractions"] if a["queue_minutes"] is not None]

        assert com_fila, "nenhuma atração veio com fila"
        assert all(a["queue_minutes"] >= 0 for a in com_fila)
        assert all(a["status"] for a in dados["attractions"])

    def test_atracao_sem_fila_vem_com_nulo(self, cliente_http, api_no_ar):
        """`OPERATING` não garante fila — cerca de uma em cada cinco não reporta.

        Omitir essas atrações faria o mapa mentir sobre o tamanho do parque.
        """
        dados = cliente_http.get(ROTA).json()
        sem_fila = [a for a in dados["attractions"] if a["queue_minutes"] is None]

        assert sem_fila, "todas vieram com fila; o filtro está escondendo atrações"

    def test_available_conta_as_ranqueaveis(self, cliente_http, api_no_ar):
        """O mesmo cuidado do `/recommendations`: `available` não é o total.

        Este bug de contagem já apareceu três vezes no projeto, sempre do mesmo
        jeito — por isso ele é testado em toda rota que devolve os dois números.
        """
        dados = cliente_http.get(ROTA).json()

        assert dados["available"] < dados["total_attractions"]
        assert dados["available"] > 0

    def test_nao_devolve_distancia(self, cliente_http, api_no_ar):
        """Não há de onde calcular: esta rota não sabe onde o visitante está."""
        atracao = cliente_http.get(ROTA).json()["attractions"][0]

        assert "walking_minutes" not in atracao
        assert "total_minutes" not in atracao

    def test_informa_quando_a_fonte_atualizou(self, cliente_http, api_no_ar):
        """Permite à tela avisar que o dado está velho em vez de escondê-lo."""
        assert cliente_http.get(ROTA).json()["data_updated_at"] is not None

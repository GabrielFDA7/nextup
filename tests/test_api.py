"""Testes da API HTTP.

Continuam offline: o `respx` responde pela ThemeParks.wiki com as fixtures reais.

Duas técnicas novas aparecem aqui:

- **`TestClient`** — cliente de teste do FastAPI. Ele faz as requisições em
  memória, sem abrir porta de rede, e é rápido o bastante para rodar dezenas de
  vezes por segundo.
- **`dependency_overrides`** — o FastAPI permite trocar uma dependência só durante
  o teste. Usamos isso para injetar um cliente com `sleep` falso, senão os testes
  de indisponibilidade esperariam de verdade os 1,5s do backoff.
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

URL_DESTINOS = f"{THEMEPARKS_BASE_URL}/destinations"
URL_CATALOGO = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/children"
URL_LIVE = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/live"

ROTA_RECOMENDA = f"/api/parks/{DEFAULT_PARK_ID}/recommendations"
POSICAO = {"lat": 28.42037, "lon": -81.58031}


def carregar(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


class SleepFalso:
    async def __call__(self, segundos: float) -> None:
        return None


@pytest.fixture
def cliente_http(conexao):
    """App de teste com um cliente de cache limpo e espera instantânea.

    Cada teste recebe uma aplicação nova, então o cache de um não interfere no
    outro — o que importa aqui, já que várias asserções contam requisições.
    """
    app = criar_app()
    servico = ThemeParksClient(http_client=conexao, sleep=SleepFalso())
    app.dependency_overrides[obter_cliente] = lambda: servico

    # Sem `with`: o gerenciador de contexto dispara o `lifespan`, que criaria um
    # `httpx.AsyncClient` de verdade — 0,7s de contexto SSL por teste, para um
    # cliente que a substituição de dependência nem usa. A fiação real do
    # `lifespan` é coberta em `TestMontagemDaAplicacao`.
    yield TestClient(app)


@pytest.fixture
def api_no_ar():
    with respx.mock:
        yield {
            "catalogo": respx.get(URL_CATALOGO).mock(
                return_value=httpx.Response(200, json=carregar("children_magic_kingdom.json"))
            ),
            "live": respx.get(URL_LIVE).mock(
                return_value=httpx.Response(200, json=carregar("live_magic_kingdom.json"))
            ),
            "destinos": respx.get(URL_DESTINOS).mock(
                return_value=httpx.Response(200, json=carregar("destinations.json"))
            ),
        }


class TestHealth:
    def test_responde_ok_com_a_versao(self, cliente_http):
        resposta = cliente_http.get("/api/health")

        assert resposta.status_code == 200
        assert resposta.json() == {"status": "ok", "version": "0.1.0"}

    def test_nao_depende_da_fonte_externa(self, cliente_http):
        """Instabilidade da ThemeParks.wiki não pode derrubar nosso healthcheck,
        senão o orquestrador reinicia um contêiner que está saudável."""
        with respx.mock:
            respx.get(URL_DESTINOS).mock(return_value=httpx.Response(503))

            assert cliente_http.get("/api/health").status_code == 200


class TestDestinos:
    def test_lista_destinos_e_parques(self, cliente_http, api_no_ar):
        resposta = cliente_http.get("/api/destinations")
        corpo = resposta.json()

        assert resposta.status_code == 200
        assert len(corpo["destinations"]) == 3

        wdw = next(d for d in corpo["destinations"] if d["slug"] == "waltdisneyworldresort")
        assert len(wdw["parks"]) == 6
        assert DEFAULT_PARK_ID in [p["id"] for p in wdw["parks"]]


class TestRecomendacoes:
    def test_devolve_ranking_ordenado(self, cliente_http, api_no_ar):
        resposta = cliente_http.get(ROTA_RECOMENDA, params={**POSICAO, "limit": 0})
        corpo = resposta.json()

        assert resposta.status_code == 200
        totais = [r["total_minutes"] for r in corpo["recommendations"]]
        assert totais == sorted(totais)

    def test_informa_disponiveis_e_total(self, cliente_http, api_no_ar):
        corpo = cliente_http.get(ROTA_RECOMENDA, params=POSICAO).json()

        assert corpo["park_name"] == "Magic Kingdom Park"
        assert corpo["total_attractions"] == 35
        assert corpo["available"] == 26

    def test_limit_corta_a_lista_sem_mudar_a_contagem(self, cliente_http, api_no_ar):
        """`available` conta as disponíveis, não as devolvidas.

        A primeira versão deste teste afirmava `available == 3` — eu havia escrito
        o teste para descrever o que o código fazia, em vez do que ele deveria
        fazer. A tela diria "3 de 35 atrações disponíveis" num parque com 26.
        """
        corpo = cliente_http.get(ROTA_RECOMENDA, params={**POSICAO, "limit": 3}).json()

        assert len(corpo["recommendations"]) == 3
        assert corpo["available"] == 26

    def test_cada_item_traz_a_conta_aberta(self, cliente_http, api_no_ar):
        corpo = cliente_http.get(ROTA_RECOMENDA, params={**POSICAO, "limit": 1}).json()
        item = corpo["recommendations"][0]

        assert item["walking_minutes"] + item["queue_minutes"] == pytest.approx(
            item["total_minutes"], abs=0.1
        )
        assert "de caminhada" in item["explanation"]

    def test_atracao_traz_coordenadas_para_o_mapa(self, cliente_http, api_no_ar):
        """A Fase 4 desenha isso no Leaflet."""
        corpo = cliente_http.get(ROTA_RECOMENDA, params={**POSICAO, "limit": 1}).json()
        atracao = corpo["recommendations"][0]["attraction"]

        assert 28.3 < atracao["latitude"] < 28.5
        assert -81.7 < atracao["longitude"] < -81.5

    def test_informa_a_idade_do_dado(self, cliente_http, api_no_ar):
        corpo = cliente_http.get(ROTA_RECOMENDA, params=POSICAO).json()

        assert corpo["data_updated_at"].startswith("2026-09-12")

    def test_posicoes_diferentes_dao_rankings_diferentes(self, cliente_http, api_no_ar):
        norte = cliente_http.get(
            ROTA_RECOMENDA, params={"lat": 28.4210, "lon": -81.5810, "limit": 1}
        ).json()
        sul = cliente_http.get(
            ROTA_RECOMENDA, params={"lat": 28.4180, "lon": -81.5825, "limit": 1}
        ).json()

        assert norte["recommendations"] != sul["recommendations"]


class TestCacheEntreRequisicoes:
    def test_segunda_requisicao_nao_chama_a_fonte(self, cliente_http, api_no_ar):
        """O motivo de o cliente ser um só para o processo.

        Com um cliente novo por requisição, o cache nasceria vazio toda vez e
        cada visitante dispararia chamadas à API pública para buscar o mesmo
        catálogo que acabou de ser buscado.
        """
        cliente_http.get(ROTA_RECOMENDA, params=POSICAO)
        cliente_http.get(ROTA_RECOMENDA, params=POSICAO)

        assert api_no_ar["catalogo"].call_count == 1
        assert api_no_ar["live"].call_count == 1


class TestValidacaoDeEntrada:
    def test_sem_coordenadas_e_erro_422(self, cliente_http):
        assert cliente_http.get(ROTA_RECOMENDA).status_code == 422

    def test_so_latitude_e_erro_422(self, cliente_http):
        assert cliente_http.get(ROTA_RECOMENDA, params={"lat": 28.4}).status_code == 422

    @pytest.mark.parametrize(
        "params",
        [
            {"lat": 91, "lon": 0},
            {"lat": -91, "lon": 0},
            {"lat": 0, "lon": 181},
            {"lat": 0, "lon": -181},
        ],
    )
    def test_coordenada_fora_do_planeta_e_erro_422(self, cliente_http, params):
        """Barrado pelo FastAPI, antes de virar requisição à API externa."""
        assert cliente_http.get(ROTA_RECOMENDA, params=params).status_code == 422

    def test_limit_negativo_e_erro_422(self, cliente_http):
        resposta = cliente_http.get(ROTA_RECOMENDA, params={**POSICAO, "limit": -1})

        assert resposta.status_code == 422


class TestTratamentoDeErro:
    def test_parque_inexistente_vira_404(self, cliente_http):
        with respx.mock:
            respx.get(f"{THEMEPARKS_BASE_URL}/entity/fantasma/children").mock(
                return_value=httpx.Response(404)
            )
            respx.get(f"{THEMEPARKS_BASE_URL}/entity/fantasma/live").mock(
                return_value=httpx.Response(404)
            )

            resposta = cliente_http.get("/api/parks/fantasma/recommendations", params=POSICAO)

        assert resposta.status_code == 404
        assert "detail" in resposta.json()

    def test_fonte_fora_do_ar_vira_503_com_retry_after(self, cliente_http):
        """503 diz "problema não é seu, tente mais tarde" — e sugere quando."""
        with respx.mock:
            respx.get(URL_CATALOGO).mock(return_value=httpx.Response(503))
            respx.get(URL_LIVE).mock(return_value=httpx.Response(503))

            resposta = cliente_http.get(ROTA_RECOMENDA, params=POSICAO)

        assert resposta.status_code == 503
        assert resposta.headers["Retry-After"] == "30"

    def test_contrato_mudado_na_fonte_vira_502(self, cliente_http):
        with respx.mock:
            respx.get(URL_CATALOGO).mock(
                return_value=httpx.Response(200, json={"formato": "outro"})
            )
            respx.get(URL_LIVE).mock(return_value=httpx.Response(200, json={"formato": "outro"}))

            resposta = cliente_http.get(ROTA_RECOMENDA, params=POSICAO)

        assert resposta.status_code == 502

    def test_erro_nunca_vaza_detalhe_interno(self, cliente_http):
        """O usuário não deve receber caminho de arquivo nem nome de biblioteca."""
        with respx.mock:
            respx.get(URL_CATALOGO).mock(return_value=httpx.Response(503))
            respx.get(URL_LIVE).mock(return_value=httpx.Response(503))

            corpo = cliente_http.get(ROTA_RECOMENDA, params=POSICAO).json()

        assert "httpx" not in corpo["detail"]
        assert "Traceback" not in corpo["detail"]


class TestContratoPublico:
    def test_documentacao_interativa_no_ar(self, cliente_http):
        assert cliente_http.get("/docs").status_code == 200

    def test_openapi_descreve_todas_as_rotas(self, cliente_http):
        """Comparação exata, e não `>=`, de propósito.

        Assim uma rota nova **quebra este teste** e obriga quem a criou a decidir
        conscientemente que ela faz parte do contrato público — em vez de aparecer
        na documentação sem ninguém ter reparado.
        """
        caminhos = cliente_http.get("/openapi.json").json()["paths"]

        assert set(caminhos) == {
            "/api/health",
            "/api/destinations",
            "/api/parks/{park_id}/attractions",
            "/api/parks/{park_id}/attractions/{attraction_id}/history",
            "/api/parks/{park_id}/recommendations",
        }

    def test_cors_liberado_para_o_frontend(self, cliente_http, api_no_ar):
        """Sem este cabeçalho, o navegador recusa a resposta na Fase 4."""
        resposta = cliente_http.get("/api/health", headers={"Origin": "http://localhost:3000"})

        assert resposta.headers["access-control-allow-origin"] == "*"


class TestMontagemDaAplicacao:
    def test_lifespan_cria_o_cliente_de_verdade(self):
        """Sem `dependency_overrides`: prova que a fiação real funciona."""
        app = criar_app()

        with TestClient(app) as cliente:
            assert isinstance(app.state.themeparks_client, ThemeParksClient)
            assert cliente.get("/api/health").status_code == 200

    def test_cada_app_tem_seu_proprio_cache(self, conexao):
        """Duas instâncias não compartilham estado — o que os testes dependem."""
        primeiro = criar_app()
        segundo = criar_app()

        with TestClient(primeiro), TestClient(segundo):
            assert primeiro.state.themeparks_client is not segundo.state.themeparks_client

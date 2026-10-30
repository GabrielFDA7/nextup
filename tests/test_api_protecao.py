"""O que protege a fonte e o visitante: validação do parque, listagem e cache da tela.

Nasceu da revisão de segurança de 29/10/2026 e da varredura de 30/10/2026. O
`park_id` ia direto para a URL da ThemeParks.wiki, e cada ID inventado custava duas
chamadas a ela; a tela não dizia ao navegador quando conferir se havia versão nova.
"""

import json
from pathlib import Path

import httpx
import pytest
import respx

from nextup.api.dependencies import obter_cliente
from nextup.api.main import criar_app
from nextup.clients.themeparks import ThemeParksClient
from nextup.config import DEFAULT_PARK_ID, THEMEPARKS_BASE_URL

FIXTURES = Path(__file__).parent / "fixtures"

URL_DESTINOS = f"{THEMEPARKS_BASE_URL}/destinations"
URL_CATALOGO = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/children"
URL_LIVE = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/live"

#: No formato certo, e em nenhum destino.
INVENTADO = "00000000-0000-4000-8000-000000000000"


def carregar(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


#: Entrada da festa de Halloween que a fonte manda como atração (30/10/2026).
FESTA = carregar("atracao_festa_halloween.json")


async def _sem_espera(_s: float) -> None:
    return None


@pytest.fixture
def servico(conexao) -> ThemeParksClient:
    return ThemeParksClient(http_client=conexao, sleep=_sem_espera)


def app_com(servico: ThemeParksClient) -> httpx.AsyncClient:
    app = criar_app()
    app.dependency_overrides[obter_cliente] = lambda: servico
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://nextup")


class TestFormatoDoParque:
    @pytest.mark.parametrize("lixo", ["fantasma", "x%3Fa%3Db", "75ea578a"])
    async def test_fora_do_formato_da_422_sem_tocar_a_fonte(self, servico, lixo):
        """`x?a=b` chegava à fonte como `/entity/x?a=b/children`. Agora nem sai."""
        with respx.mock:  # sem rota nenhuma: qualquer chamada à fonte estoura
            async with app_com(servico) as cliente:
                resposta = await cliente.get(f"/api/parks/{lixo}/attractions")

        assert resposta.status_code == 422


class TestListaDeParques:
    async def test_com_a_lista_no_cache_o_inventado_da_404_sem_tocar_a_fonte(self, servico):
        with respx.mock:
            respx.get(URL_DESTINOS).mock(
                return_value=httpx.Response(200, json=carregar("destinations.json"))
            )
            catalogo = respx.get(f"{THEMEPARKS_BASE_URL}/entity/{INVENTADO}/children")
            await servico.get_destinations()  # o que o coletor faz em produção

            async with app_com(servico) as cliente:
                resposta = await cliente.get(f"/api/parks/{INVENTADO}/attractions")

        assert resposta.status_code == 404
        assert not catalogo.called, "a fonte foi consultada para um parque que não existe"

    async def test_com_a_lista_no_cache_o_parque_real_passa(self, servico):
        with respx.mock:
            respx.get(URL_DESTINOS).mock(
                return_value=httpx.Response(200, json=carregar("destinations.json"))
            )
            respx.get(URL_CATALOGO).mock(
                return_value=httpx.Response(200, json=carregar("children_magic_kingdom.json"))
            )
            respx.get(URL_LIVE).mock(
                return_value=httpx.Response(200, json=carregar("live_magic_kingdom.json"))
            )
            await servico.get_destinations()

            async with app_com(servico) as cliente:
                resposta = await cliente.get(f"/api/parks/{DEFAULT_PARK_ID}/attractions")

        assert resposta.status_code == 200

    def test_sem_a_lista_no_cache_ninguem_e_recusado(self, servico):
        """Sem a lista, não há contra o que comparar: buscá-la a cada pedido poria
        uma chamada à fonte em todo pedido, o contrário do que se quer."""
        assert servico.known_park_ids() is None


class TestListagemOficial:
    async def test_a_entrada_da_festa_nao_chega_ao_catalogo(self, servico):
        catalogo = carregar("children_magic_kingdom.json")
        catalogo["children"].append(FESTA)

        with respx.mock:
            respx.get(URL_CATALOGO).mock(return_value=httpx.Response(200, json=catalogo))
            respx.get(URL_LIVE).mock(
                return_value=httpx.Response(200, json=carregar("live_magic_kingdom.json"))
            )
            async with app_com(servico) as cliente:
                corpo = (await cliente.get(f"/api/parks/{DEFAULT_PARK_ID}/attractions")).json()

        assert FESTA["id"] not in {a["id"] for a in corpo["attractions"]}
        assert corpo["total_attractions"] == 35


class TestCacheDaTela:
    """Sem cabeçalho, cada navegador decidia por quanto tempo guardar o CSS e o JS."""

    @pytest.mark.parametrize("caminho", ["/", "/app.js", "/style.css"])
    async def test_a_tela_pede_para_conferir_antes_de_usar(self, servico, caminho):
        async with app_com(servico) as cliente:
            resposta = await cliente.get(caminho)

        assert resposta.status_code == 200
        assert resposta.headers["cache-control"] == "no-cache"

    async def test_a_api_nao_ganha_o_cabecalho(self, servico):
        async with app_com(servico) as cliente:
            resposta = await cliente.get("/api/health")

        assert "cache-control" not in resposta.headers

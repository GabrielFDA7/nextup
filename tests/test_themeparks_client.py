"""Testes do cliente da ThemeParks.wiki.

Nenhum destes testes acessa a internet. O `respx` intercepta as chamadas do
`httpx` e devolve o que mandarmos — inclusive falhas que seriam impossíveis de
provocar de propósito contra a API real, como um erro 503 ou uma queda de
conexão no meio da requisição.

As respostas de sucesso vêm das fixtures reais capturadas em 12/09/2026, então o
que o teste valida é o caminho completo: requisição → JSON verdadeiro → modelo.

O `sleep` também é falso, pelo mesmo motivo do relógio do cache: o backoff espera
0,5s, 1s e 2s entre as tentativas, e uma suíte não pode parar 3,5 segundos para
provar isso.
"""

import json
from pathlib import Path

import httpx
import pytest
import respx

from nextup.clients.errors import (
    EntityNotFoundError,
    InvalidResponseError,
    ThemeParksError,
    ThemeParksUnavailableError,
)
from nextup.clients.themeparks import ThemeParksClient
from nextup.config import DEFAULT_PARK_ID, THEMEPARKS_BASE_URL, USER_AGENT

FIXTURES = Path(__file__).parent / "fixtures"

URL_DESTINOS = f"{THEMEPARKS_BASE_URL}/destinations"
URL_CATALOGO = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/children"
URL_LIVE = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/live"


def carregar(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


class SleepFalso:
    """Registra quanto tempo o cliente *pediu* para esperar, sem esperar nada."""

    def __init__(self) -> None:
        self.esperas: list[float] = []

    async def __call__(self, segundos: float) -> None:
        self.esperas.append(segundos)


@pytest.fixture
def dormir() -> SleepFalso:
    return SleepFalso()


@pytest.fixture(scope="session")
def conexao() -> httpx.AsyncClient:
    """Uma conexão HTTP para a suíte inteira.

    Criar um `httpx.AsyncClient` monta um contexto SSL e carrega os certificados,
    o que custa ~0,7s. Fazer isso 20 vezes tornaria estes testes mais lentos que
    todo o resto do projeto somado — e o `respx` intercepta antes de qualquer
    byte sair, então uma conexão compartilhada não mistura estado entre testes.
    """
    return httpx.AsyncClient()


@pytest.fixture
def cliente(dormir, conexao) -> ThemeParksClient:
    """Cliente novo a cada teste — cache limpo — sobre a conexão compartilhada."""
    return ThemeParksClient(sleep=dormir, http_client=conexao)


class TestCaminhoFeliz:
    async def test_destinos_viram_modelo(self, cliente):
        with respx.mock:
            respx.get(URL_DESTINOS).mock(
                return_value=httpx.Response(200, json=carregar("destinations.json"))
            )

            async with cliente:
                destinos = await cliente.get_destinations()

        assert len(destinos.destinations) == 3
        assert any(d.slug == "waltdisneyworldresort" for d in destinos.destinations)

    async def test_catalogo_vira_modelo_com_coordenadas(self, cliente):
        with respx.mock:
            respx.get(URL_CATALOGO).mock(
                return_value=httpx.Response(200, json=carregar("children_magic_kingdom.json"))
            )

            async with cliente:
                catalogo = await cliente.get_park_catalog(DEFAULT_PARK_ID)

        assert catalogo.name == "Magic Kingdom Park"
        assert len(catalogo.attractions()) == 35

    async def test_dados_ao_vivo_viram_modelo(self, cliente):
        with respx.mock:
            respx.get(URL_LIVE).mock(
                return_value=httpx.Response(200, json=carregar("live_magic_kingdom.json"))
            )

            async with cliente:
                ao_vivo = await cliente.get_live_data(DEFAULT_PARK_ID)

        ranqueaveis = [i for i in ao_vivo.live_data if i.is_rankable]
        assert len(ranqueaveis) == 26

    async def test_user_agent_do_projeto_e_enviado(self, cliente):
        """Boa cidadania: a API precisa saber quem está chamando."""
        with respx.mock:
            rota = respx.get(URL_DESTINOS).mock(
                return_value=httpx.Response(200, json=carregar("destinations.json"))
            )

            async with cliente:
                await cliente.get_destinations()

        assert rota.calls.last.request.headers["User-Agent"] == USER_AGENT


class TestCache:
    async def test_segunda_chamada_nao_toca_a_rede(self, cliente):
        """O ponto do cache: duas chamadas, uma requisição."""
        with respx.mock:
            rota = respx.get(URL_CATALOGO).mock(
                return_value=httpx.Response(200, json=carregar("children_magic_kingdom.json"))
            )

            async with cliente:
                primeira = await cliente.get_park_catalog(DEFAULT_PARK_ID)
                segunda = await cliente.get_park_catalog(DEFAULT_PARK_ID)

        assert rota.call_count == 1
        assert primeira.name == segunda.name

    async def test_parques_diferentes_nao_compartilham_cache(self, cliente):
        outro_parque = "47f90d2c-e191-4239-a466-5892ef59a88b"
        with respx.mock:
            rota_mk = respx.get(URL_CATALOGO).mock(
                return_value=httpx.Response(200, json=carregar("children_magic_kingdom.json"))
            )
            rota_epcot = respx.get(f"{THEMEPARKS_BASE_URL}/entity/{outro_parque}/children").mock(
                return_value=httpx.Response(200, json=carregar("children_magic_kingdom.json"))
            )

            async with cliente:
                await cliente.get_park_catalog(DEFAULT_PARK_ID)
                await cliente.get_park_catalog(outro_parque)

        assert rota_mk.call_count == 1
        assert rota_epcot.call_count == 1

    async def test_catalogo_e_live_usam_caches_separados(self, cliente):
        """Prazos diferentes exigem caches diferentes: 24h contra 60s."""
        with respx.mock:
            rota_cat = respx.get(URL_CATALOGO).mock(
                return_value=httpx.Response(200, json=carregar("children_magic_kingdom.json"))
            )
            rota_live = respx.get(URL_LIVE).mock(
                return_value=httpx.Response(200, json=carregar("live_magic_kingdom.json"))
            )

            async with cliente:
                await cliente.get_park_catalog(DEFAULT_PARK_ID)
                await cliente.get_live_data(DEFAULT_PARK_ID)

        assert rota_cat.call_count == 1
        assert rota_live.call_count == 1


class TestRetentativas:
    async def test_erro_de_servidor_e_tentado_de_novo(self, cliente, dormir):
        """503 é problema do servidor e costuma ser passageiro."""
        with respx.mock:
            rota = respx.get(URL_DESTINOS).mock(return_value=httpx.Response(503))

            async with cliente:
                with pytest.raises(ThemeParksUnavailableError):
                    await cliente.get_destinations()

        assert rota.call_count == 3
        assert len(dormir.esperas) == 2  # não espera depois da última tentativa

    async def test_queda_de_conexao_e_tentada_de_novo(self, cliente, dormir):
        with respx.mock:
            rota = respx.get(URL_DESTINOS).mock(side_effect=httpx.ConnectError("sem rede"))

            async with cliente:
                with pytest.raises(ThemeParksUnavailableError):
                    await cliente.get_destinations()

        assert rota.call_count == 3

    async def test_recupera_se_a_api_voltar(self, cliente):
        """Falha duas vezes, funciona na terceira — o cenário que o retry existe
        para resolver."""
        with respx.mock:
            respx.get(URL_DESTINOS).mock(
                side_effect=[
                    httpx.Response(503),
                    httpx.Response(502),
                    httpx.Response(200, json=carregar("destinations.json")),
                ]
            )

            async with cliente:
                destinos = await cliente.get_destinations()

        assert len(destinos.destinations) == 3

    async def test_espera_dobra_a_cada_tentativa(self, cliente, dormir):
        """Backoff exponencial: 0,5s, depois 1s. Insistir no mesmo ritmo só
        piora um servidor já sobrecarregado."""
        with respx.mock:
            respx.get(URL_DESTINOS).mock(return_value=httpx.Response(503))

            async with cliente:
                with pytest.raises(ThemeParksUnavailableError):
                    await cliente.get_destinations()

        assert dormir.esperas == [0.5, 1.0]

    async def test_erro_guarda_quantas_tentativas_houve(self, cliente):
        with respx.mock:
            respx.get(URL_DESTINOS).mock(return_value=httpx.Response(503))

            async with cliente:
                with pytest.raises(ThemeParksUnavailableError) as info:
                    await cliente.get_destinations()

        assert info.value.attempts == 3
        assert URL_DESTINOS in info.value.url


class TestErrosQueNaoSeRepetem:
    async def test_404_falha_na_primeira(self, cliente, dormir):
        """ID errado continua errado na segunda tentativa: insistir é desperdício."""
        with respx.mock:
            rota = respx.get(URL_CATALOGO).mock(return_value=httpx.Response(404))

            async with cliente:
                with pytest.raises(EntityNotFoundError) as info:
                    await cliente.get_park_catalog(DEFAULT_PARK_ID)

        assert rota.call_count == 1
        assert dormir.esperas == []
        assert info.value.entity_id == DEFAULT_PARK_ID

    async def test_erro_de_cliente_nao_e_tentado_de_novo(self, cliente):
        with respx.mock:
            rota = respx.get(URL_DESTINOS).mock(return_value=httpx.Response(400))

            async with cliente:
                with pytest.raises(InvalidResponseError):
                    await cliente.get_destinations()

        assert rota.call_count == 1


class TestRespostaEstranha:
    async def test_corpo_que_nao_e_json(self, cliente):
        with respx.mock:
            respx.get(URL_DESTINOS).mock(
                return_value=httpx.Response(200, text="<html>manutenção</html>")
            )

            async with cliente:
                with pytest.raises(InvalidResponseError, match="não é JSON"):
                    await cliente.get_destinations()

    async def test_json_com_formato_inesperado(self, cliente):
        """Se a API mudar o contrato, falhamos alto e cedo em vez de seguir com
        dado pela metade — risco previsto na seção 8 do PROJETO.md."""
        with respx.mock:
            respx.get(URL_DESTINOS).mock(
                return_value=httpx.Response(200, json={"formato": "totalmente outro"})
            )

            async with cliente:
                with pytest.raises(InvalidResponseError):
                    await cliente.get_destinations()

    async def test_resposta_ruim_nao_entra_no_cache(self, cliente):
        """Erro não pode ser memorizado: na próxima chamada, tenta de novo."""
        with respx.mock:
            rota = respx.get(URL_DESTINOS).mock(
                side_effect=[
                    httpx.Response(200, json={"formato": "errado"}),
                    httpx.Response(200, json=carregar("destinations.json")),
                ]
            )

            async with cliente:
                with pytest.raises(InvalidResponseError):
                    await cliente.get_destinations()
                destinos = await cliente.get_destinations()

        assert rota.call_count == 2
        assert len(destinos.destinations) == 3


class TestHierarquiaDeErros:
    async def test_todos_os_erros_descendem_de_themeparkserror(self, cliente):
        """Quem quiser tratar "qualquer problema com a API" captura só a base."""
        with respx.mock:
            respx.get(URL_DESTINOS).mock(return_value=httpx.Response(503))

            async with cliente:
                with pytest.raises(ThemeParksError):
                    await cliente.get_destinations()


class TestConstrucao:
    def test_max_retries_zero_e_recusado(self):
        with pytest.raises(ValueError, match="ao menos 1"):
            ThemeParksClient(max_retries=0)

    async def test_conexao_recebida_de_fora_nao_e_fechada(self):
        """Fechar uma conexão que não é nossa derrubaria quem a emprestou."""
        externa = httpx.AsyncClient()
        cliente = ThemeParksClient(http_client=externa)

        await cliente.aclose()

        assert not externa.is_closed
        await externa.aclose()

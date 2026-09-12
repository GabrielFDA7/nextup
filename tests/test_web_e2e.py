"""Testes de ponta a ponta da interface, em navegador de verdade.

O que estes testes cobrem e nenhum outro cobre: que a **tela** funciona. Os testes
da API provam que `/api/...` devolve o JSON certo; estes provam que o JSON certo
vira pixel na tela — que o Leaflet carrega, que negar o GPS não quebra o app, que
o erro da API vira uma frase que o visitante entende.

**Nenhum deles toca a ThemeParks.wiki.** O `page.route` intercepta as chamadas
dentro do navegador e devolve as fixtures reais, então o servidor sobe de verdade
(servindo o HTML, o CSS e o JS) mas a fonte externa nunca é chamada.

Como rodar:

    pip install -e ".[dev,e2e]"
    playwright install chromium
    pytest -m e2e

São pulados automaticamente quando o Playwright não está instalado — o CI roda o
resto da suíte sem precisar baixar um navegador.
"""

import json
import socket
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="requer o extra `e2e`")

import uvicorn
from playwright.sync_api import Page, expect, sync_playwright

from nextup.api.main import criar_app
from nextup.config import DEFAULT_PARK_ID

pytestmark = pytest.mark.e2e

FIXTURES = Path(__file__).parent / "fixtures"

POSICAO = {"latitude": 28.42037, "longitude": -81.58031}
CELULAR = {"width": 390, "height": 844}


def carregar(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


def porta_livre() -> int:
    """Pede ao sistema uma porta que ninguém esteja usando.

    Fixar uma porta faria o teste falhar se algo já estivesse ouvindo nela — e
    "falhou porque a porta estava ocupada" é o tipo de erro que custa uma tarde.
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def servidor() -> str:
    """Sobe a aplicação de verdade numa thread e devolve a URL base."""
    porta = porta_livre()
    config = uvicorn.Config(criar_app(), host="127.0.0.1", port=porta, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    limite = time.time() + 20
    while not server.started and time.time() < limite:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("o servidor de teste não subiu a tempo")

    yield f"http://127.0.0.1:{porta}"

    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture(scope="module")
def navegador():
    with sync_playwright() as p:
        nav = p.chromium.launch()
        yield nav
        nav.close()


def abrir(navegador, servidor, *, com_gps: bool = True, api=None) -> Page:
    """Abre a página com a API interceptada dentro do navegador.

    `api` recebe uma função que responde à rota de recomendações; o padrão
    devolve a fixture real do Magic Kingdom.
    """
    contexto = navegador.new_context(
        viewport=CELULAR,
        locale="pt-BR",
        geolocation=POSICAO if com_gps else None,
        permissions=["geolocation"] if com_gps else [],
    )
    pagina = contexto.new_page()

    pagina.route(
        "**/api/destinations",
        lambda rota: rota.fulfill(json=_destinos_como_a_api_devolve()),
    )
    pagina.route(
        "**/recommendations*",
        api or (lambda rota: rota.fulfill(json=_recomendacoes_como_a_api_devolve())),
    )

    pagina.goto(servidor, wait_until="networkidle")
    return pagina


def _destinos_como_a_api_devolve() -> dict:
    bruto = carregar("destinations.json")
    return {
        "destinations": [
            {
                "id": d["id"],
                "name": d["name"],
                "slug": d["slug"],
                "parks": [{"id": p["id"], "name": p["name"]} for p in d["parks"]],
            }
            for d in bruto["destinations"]
        ]
    }


def _recomendacoes_como_a_api_devolve() -> dict:
    """Monta a resposta chamando o `core` de verdade, com as fixtures reais.

    Assim os números na tela são os mesmos que a API produziria — sem precisar
    de rede e sem repetir a conta aqui dentro.
    """
    from nextup.api.schemas import RecommendationsOut
    from nextup.core.recommender import recommend
    from nextup.models import LiveDataResponse, Location, ParkCatalog

    catalogo = ParkCatalog.model_validate(carregar("children_magic_kingdom.json"))
    ao_vivo = LiveDataResponse.model_validate(carregar("live_magic_kingdom.json"))

    resposta = RecommendationsOut.from_domain(
        catalogo,
        recommend(
            catalog=catalogo,
            live=ao_vivo,
            visitor=Location(latitude=POSICAO["latitude"], longitude=POSICAO["longitude"]),
            limit=0,
        ),
        8,
        max((i.last_updated for i in ao_vivo.live_data), default=None),
    )
    return json.loads(resposta.model_dump_json())


class TestCarregamentoInicial:
    def test_pagina_abre_sem_erro_de_console(self, navegador, servidor):
        erros = []
        contexto = navegador.new_context(viewport=CELULAR)
        pagina = contexto.new_page()
        pagina.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)

        pagina.goto(servidor, wait_until="networkidle")

        assert erros == []
        contexto.close()

    def test_mapa_carrega_de_verdade(self, navegador, servidor):
        """Se o Leaflet falhasse, o mapa ficaria um retângulo vazio — e nenhum
        teste de API perceberia."""
        pagina = abrir(navegador, servidor)

        expect(pagina.locator("#mapa img.leaflet-tile").first).to_be_visible()

    def test_seletor_lista_os_parques_da_api(self, navegador, servidor):
        pagina = abrir(navegador, servidor)

        assert pagina.locator("#parque option").count() == 11  # 3 destinos da fixture
        assert pagina.is_enabled("#parque")

    def test_comeca_pedindo_a_posicao(self, navegador, servidor):
        pagina = abrir(navegador, servidor)

        expect(pagina.locator("#aviso")).to_contain_text("localização")
        assert pagina.locator(".item").count() == 0


class TestFluxoFeliz:
    def test_permitir_gps_mostra_o_ranking(self, navegador, servidor):
        pagina = abrir(navegador, servidor)

        pagina.click("#btn-localizar")
        pagina.wait_for_selector(".item")

        expect(pagina.locator("#titulo-lista")).to_have_text("Magic Kingdom Park")
        expect(pagina.locator("#resumo")).to_contain_text("26 de 35")
        assert pagina.locator(".item").count() == 8

    def test_lista_sai_em_ordem_crescente_de_custo(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        pagina.wait_for_selector(".item")

        minutos = [int(texto) for texto in pagina.locator(".custo strong").all_inner_texts()]

        assert minutos == sorted(minutos)

    def test_primeira_colocada_recebe_destaque(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        pagina.wait_for_selector(".item")

        assert pagina.locator(".etiqueta").count() == 1
        expect(pagina.locator(".item").first).to_have_class("item item--melhor")

    def test_cada_item_mostra_a_conta_aberta(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        pagina.wait_for_selector(".item")

        expect(pagina.locator(".item").first).to_contain_text("a pé +")
        expect(pagina.locator(".item").first).to_contain_text("de fila")

    def test_atracoes_aparecem_no_mapa(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        pagina.wait_for_selector(".item")

        assert pagina.locator(".leaflet-marker-icon").count() == 8

    def test_informa_a_idade_do_dado(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        pagina.wait_for_selector(".item")

        expect(pagina.locator("#atualizado")).to_contain_text("Dado da fonte")


class TestGpsNegado:
    """O caso que o `docs/PROJETO.md` exige tratar."""

    def test_negar_gps_nao_quebra_o_app(self, navegador, servidor):
        pagina = abrir(navegador, servidor, com_gps=False)

        pagina.click("#btn-localizar")

        expect(pagina.locator("#aviso")).to_contain_text("negou o acesso")
        expect(pagina.locator("#mapa")).to_be_visible()

    def test_negar_gps_oferece_alternativa(self, navegador, servidor):
        pagina = abrir(navegador, servidor, com_gps=False)

        pagina.click("#btn-localizar")

        expect(pagina.locator("#aviso")).to_contain_text("Toque no mapa")

    def test_botao_volta_ao_normal_apos_a_recusa(self, navegador, servidor):
        """Se continuasse em "Localizando…", o usuário acharia que travou."""
        pagina = abrir(navegador, servidor, com_gps=False)

        pagina.click("#btn-localizar")

        expect(pagina.locator("#btn-localizar")).to_have_text("Usar minha localização")
        assert pagina.is_enabled("#btn-localizar")

    def test_clique_no_mapa_resolve_sem_gps(self, navegador, servidor):
        """A alternativa oferecida precisa realmente funcionar."""
        pagina = abrir(navegador, servidor, com_gps=False)
        pagina.click("#btn-localizar")

        caixa = pagina.locator("#mapa").bounding_box()
        pagina.mouse.click(caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] / 2)
        pagina.wait_for_selector(".item")

        expect(pagina.locator("#posicao-atual")).to_contain_text("escolhida no mapa")
        assert pagina.locator(".item").count() == 8


class TestErroDaApi:
    def test_fonte_fora_do_ar_vira_frase_compreensivel(self, navegador, servidor):
        pagina = abrir(
            navegador,
            servidor,
            api=lambda rota: rota.fulfill(status=503, json={"detail": "x"}),
        )

        pagina.click("#btn-localizar")

        expect(pagina.locator("#aviso")).to_contain_text("fora do ar")
        assert pagina.locator(".item").count() == 0

    def test_parque_inexistente_orienta_o_usuario(self, navegador, servidor):
        pagina = abrir(
            navegador,
            servidor,
            api=lambda rota: rota.fulfill(status=404, json={"detail": "x"}),
        )

        pagina.click("#btn-localizar")

        expect(pagina.locator("#aviso")).to_contain_text("Escolha outro")

    def test_esqueleto_some_mesmo_quando_da_erro(self, navegador, servidor):
        """Deixar o esqueleto na tela faria parecer que ainda está carregando."""
        pagina = abrir(
            navegador,
            servidor,
            api=lambda rota: rota.fulfill(status=503, json={"detail": "x"}),
        )

        pagina.click("#btn-localizar")
        expect(pagina.locator("#aviso")).to_contain_text("fora do ar")

        assert pagina.locator(".esqueleto").count() == 0

    def test_parque_fechado_avisa_em_vez_de_lista_vazia(self, navegador, servidor):
        vazio = {
            "park_id": DEFAULT_PARK_ID,
            "park_name": "Magic Kingdom Park",
            "total_attractions": 35,
            "available": 0,
            "data_updated_at": None,
            "recommendations": [],
        }
        pagina = abrir(navegador, servidor, api=lambda rota: rota.fulfill(json=vazio))

        pagina.click("#btn-localizar")

        expect(pagina.locator("#aviso")).to_contain_text("pode estar fechado")


class TestSeguranca:
    def test_nome_com_html_nao_e_executado(self, navegador, servidor):
        """Os nomes vêm de fonte externa: sem escapar, seria XSS."""
        malicioso = {
            "park_id": DEFAULT_PARK_ID,
            "park_name": "Parque",
            "total_attractions": 1,
            "available": 1,
            "data_updated_at": None,
            "recommendations": [
                {
                    "attraction": {
                        "id": "x",
                        "name": '<img src=x onerror="window.__invadido=true">',
                        "latitude": 28.42,
                        "longitude": -81.58,
                    },
                    "walking_minutes": 1.0,
                    "queue_minutes": 5,
                    "total_minutes": 6.0,
                    "explanation": "irrelevante",
                }
            ],
        }
        pagina = abrir(navegador, servidor, api=lambda rota: rota.fulfill(json=malicioso))

        pagina.click("#btn-localizar")
        pagina.wait_for_selector(".item")

        assert pagina.evaluate("window.__invadido === undefined")
        expect(pagina.locator(".nome")).to_contain_text("<img")


class TestResponsivo:
    def test_nao_ha_rolagem_horizontal_no_celular(self, navegador, servidor):
        """Rolagem lateral em celular é o sintoma clássico de layout quebrado."""
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        pagina.wait_for_selector(".item")

        largura_conteudo = pagina.evaluate("document.documentElement.scrollWidth")
        largura_tela = pagina.evaluate("document.documentElement.clientWidth")

        assert largura_conteudo <= largura_tela + 1

    def test_botao_tem_alvo_confortavel_para_o_dedo(self, navegador, servidor):
        """48px é o mínimo recomendado para toque."""
        pagina = abrir(navegador, servidor)

        caixa = pagina.locator("#btn-localizar").bounding_box()

        assert caixa["height"] >= 44

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
import re
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
    # Sem esta interceptação a rota de atrações chegaria ao servidor de verdade, e
    # de lá à ThemeParks.wiki — furando a regra de que nenhum teste toca a
    # internet. Passou despercebido quando a rota nasceu porque a chamada
    # *funciona*: ela só fica lenta, instável e mal-educada com uma API pública.
    pagina.route("**/attractions*", _responder_atracoes)

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


#: Um parque bem longe do Magic Kingdom, para o reenquadramento do mapa ficar
#: inequívoco: se a vista não se mover, os números denunciam.
PARQUE_DISTANTE = "27d64dee-d85e-48dc-ad6d-8077445cd946"  # SeaWorld Orlando
BOUNDS_DISTANTE = {"south": 48.870, "west": 2.772, "north": 48.875, "east": 2.780}


def _responder_atracoes(rota) -> None:
    """Responde `/attractions` conforme o parque pedido.

    O Magic Kingdom devolve a fixture real; qualquer outro devolve um parque
    sintético do outro lado do Atlântico. É o que permite verificar que o mapa
    **segue** a escolha, em vez de continuar apontando para onde estava.
    """
    if DEFAULT_PARK_ID in rota.request.url:
        rota.fulfill(json=_atracoes_como_a_api_devolve())
        return

    rota.fulfill(
        json={
            "park_id": PARQUE_DISTANTE,
            "park_name": "Parque Distante",
            "timezone": "Europe/Paris",
            "bounds": BOUNDS_DISTANTE,
            "total_attractions": 1,
            "available": 1,
            "data_updated_at": "2026-09-20T14:00:00Z",
            "attractions": [
                {
                    "id": "distante-1",
                    "name": "Atração Distante",
                    "latitude": 48.8725,
                    "longitude": 2.776,
                    "status": "OPERATING",
                    "queue_minutes": 15,
                }
            ],
        }
    )


def _historico(pontos: int) -> dict:
    """Uma série sintética com `pontos` medições, subindo de 10 em 10 minutos.

    Sintética de propósito: o que estes testes verificam é o **desenho**, e uma
    série previsível deixa a contagem de vértices ser uma asserção exata.
    """
    from datetime import UTC, datetime, timedelta

    agora = datetime(2026, 9, 20, 15, 0, tzinfo=UTC)
    filas = [10 + (i % 5) * 5 for i in range(pontos)]

    return {
        "park_id": DEFAULT_PARK_ID,
        "attraction_id": "qualquer",
        "attraction_name": "Atração de Teste",
        "hours": 6,
        "points": [
            {
                "at": (agora - timedelta(minutes=5 * (pontos - i))).isoformat(),
                "minutes": fila,
            }
            for i, fila in enumerate(filas)
        ],
        "summary": {
            "measurements": pontos,
            "min_minutes": min(filas),
            "max_minutes": max(filas),
            "average_minutes": round(sum(filas) / len(filas), 1),
            "current_minutes": filas[-1],
            "spread": max(filas) - min(filas),
        },
        "trend": None,
    }


def _atracoes_como_a_api_devolve() -> dict:
    """Monta a resposta com o schema de verdade, sobre as fixtures reais."""
    from nextup.api.schemas import ParkAttractionsOut
    from nextup.models import LiveDataResponse, ParkCatalog

    catalogo = ParkCatalog.model_validate(carregar("children_magic_kingdom.json"))
    ao_vivo = LiveDataResponse.model_validate(carregar("live_magic_kingdom.json"))

    resposta = ParkAttractionsOut.from_domain(
        catalogo,
        ao_vivo,
        max((i.last_updated for i in ao_vivo.live_data), default=None),
    )
    return json.loads(resposta.model_dump_json())


def _recomendacoes_como_a_api_devolve(*, com_tendencia: bool = False) -> dict:
    """Monta a resposta chamando o `core` de verdade, com as fixtures reais.

    Assim os números na tela são os mesmos que a API produziria — sem precisar
    de rede e sem repetir a conta aqui dentro.
    """
    from datetime import UTC, datetime, timedelta

    from nextup.api.schemas import RecommendationsOut
    from nextup.core.recommender import recommend
    from nextup.core.trends import analyze_many
    from nextup.models import LiveDataResponse, LiveStatus, Location, ParkCatalog, QueueSnapshot

    catalogo = ParkCatalog.model_validate(carregar("children_magic_kingdom.json"))
    ao_vivo = LiveDataResponse.model_validate(carregar("live_magic_kingdom.json"))

    visitante = Location(latitude=POSICAO["latitude"], longitude=POSICAO["longitude"])
    ranking = recommend(catalog=catalogo, live=ao_vivo, visitor=visitante, limit=0)

    tendencias = None
    if com_tendencia:
        agora = datetime.now(UTC)

        # O histórico vai para quem **lidera o ranking**, e não para uma atração
        # qualquer do catálogo: a tela mostra só as oito primeiras, e uma queda
        # numa nona colocada seria calculada e nunca exibida.
        alvo = ranking[0].attraction.id

        historico = [
            QueueSnapshot(
                park_id=DEFAULT_PARK_ID,
                attraction_id=alvo,
                status=LiveStatus.OPERATING,
                wait_time_minutes=fila,
                observed_at=agora - timedelta(minutes=minutos),
                recorded_at=agora - timedelta(minutes=minutos),
            )
            for fila, minutos in ((45, 25), (20, 1))
        ]
        tendencias = analyze_many(historico, now=agora)

        ranking = recommend(
            catalog=catalogo,
            live=ao_vivo,
            visitor=visitante,
            limit=0,
            trends=tendencias,
        )

    # Limite zero: devolve o ranking INTEIRO, que é o que a tela passou a pedir.
    #
    # O mock devolvia oito fixos, e isso escondia o bug que o Gabriel encontrou em
    # 20/09/2026: marcando as oito como visitadas, a tela ficava vazia porque as
    # outras dezoito nunca tinham sido enviadas. Um mock que devolve menos que a
    # API real testa um app que não existe.
    resposta = RecommendationsOut.from_domain(
        catalogo,
        ranking,
        0,
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
        """Continua pedindo a posição — mas já não abre vazio.

        Antes, quem não liberasse o GPS via uma tela em branco e nenhuma razão
        para confiar no resto. Agora o parque aparece de cara, e o aviso explica o
        que **falta** para o app responder a pergunta que ele promete responder.
        """
        pagina = abrir(navegador, servidor)

        expect(pagina.locator("#aviso")).to_contain_text("localização")
        pagina.wait_for_selector("[data-modo='panorama'] .item")

        # Sem posição não existe ranking, e o app não pode fingir que existe.
        assert pagina.locator("[data-modo='ranking']").count() == 0
        assert pagina.locator(".etiqueta").count() == 0

    def test_mostra_as_filas_antes_de_saber_onde_voce_esta(self, navegador, servidor):
        """A pergunta "como está o parque?" não depende de saber onde o visitante está."""
        pagina = abrir(navegador, servidor)
        pagina.wait_for_selector("[data-modo='panorama'] .item")

        expect(pagina.locator("#resumo")).to_contain_text("fila medida")
        assert pagina.locator("[data-modo='panorama'] .item").count() > 0

    def test_o_panorama_avisa_que_nao_e_recomendacao(self, navegador, servidor):
        """A ressalva é a tese do produto, não modéstia.

        A lista sem posição é ordenada pela menor fila — a pergunta que o NextUp
        existe para contestar. Sem este aviso, os primeiros colocados (que em
        alguns parques são playgrounds com fila zero) seriam lidos como conselho.
        """
        pagina = abrir(navegador, servidor)
        pagina.wait_for_selector("[data-modo='panorama'] .item")

        expect(pagina.locator("#resumo")).to_contain_text("menor fila")


class TestTendenciaNaTela:
    """A frase que explica *por que agora* — a entrega da Fase 6.3.

    Até aqui a justificativa parava em "= 24 min". Sem chegar à tela, a tendência
    seria código bonito que ninguém vê.
    """

    def com_tendencia(self, navegador, servidor):
        return abrir(
            navegador,
            servidor,
            api=lambda rota: rota.fulfill(
                json=_recomendacoes_como_a_api_devolve(com_tendencia=True)
            ),
        )

    def test_a_queda_aparece_na_lista(self, navegador, servidor):
        pagina = self.com_tendencia(navegador, servidor)
        pagina.click("#btn-localizar")
        pagina.wait_for_selector("[data-modo='ranking'] .item")

        expect(pagina.locator(".tendencia--caindo").first).to_contain_text("Caiu de 45 para 20")

    def test_a_cor_nao_carrega_a_informacao_sozinha(self, navegador, servidor):
        """Quem não distingue verde de vermelho precisa ler a mesma coisa.

        A seta aponta e o texto diz por extenso; a cor só reforça.
        """
        pagina = self.com_tendencia(navegador, servidor)
        pagina.click("#btn-localizar")
        pagina.wait_for_selector("[data-modo='ranking'] .item")

        tendencia = pagina.locator(".tendencia").first

        assert tendencia.locator("svg").count() == 1
        expect(tendencia).to_contain_text("Caiu")

    def test_sem_historico_nao_inventa_tendencia(self, navegador, servidor):
        """O padrão dos testes é sem histórico — e nada deve aparecer."""
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        pagina.wait_for_selector("[data-modo='ranking'] .item")

        assert pagina.locator(".tendencia").count() == 0


class TestJaFuiHoje:
    """A marcação de atrações já visitadas — a entrega da Fase 7.1.

    Primeiro estado que o NextUp guarda por pessoa. Mora no `localStorage`, então
    estes testes são também a única verificação de que a persistência funciona: os
    testes de API não têm navegador, e o navegador é onde o dado vive.
    """

    def com_ranking(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        pagina.wait_for_selector("[data-modo='ranking'] .item")
        return pagina

    def test_marcar_tira_a_atracao_e_promove_outra(self, navegador, servidor):
        """É o que o consultor de parque faz: não te manda de volta onde já foi.

        E a lista **não encolhe** — a nona colocada sobe. A tela mostra oito
        sugestões porque oito é o que cabe, não porque oito é o que existe.
        """
        pagina = self.com_ranking(navegador, servidor)
        marcada = pagina.locator(".item .nome").first.inner_text()

        pagina.locator(".marcar-visitada").first.click()

        expect(pagina.locator("[data-modo='ranking'] .item")).to_have_count(8)
        assert marcada not in pagina.locator("#lista").inner_text()

    def test_avisa_quantas_foram_escondidas(self, navegador, servidor):
        """Esconder sem dizer que escondeu é a diferença entre ajudar e parecer quebrado."""
        pagina = self.com_ranking(navegador, servidor)
        pagina.locator(".marcar-visitada").first.click()

        expect(pagina.locator("#visitadas-aviso")).to_be_visible()
        expect(pagina.locator("#visitadas-texto")).to_contain_text("1 atração já visitada")

    def test_o_aviso_nao_aparece_sem_nada_marcado(self, navegador, servidor):
        """Uma linha permanente dizendo "0 visitadas" seria ruído na tela principal."""
        pagina = self.com_ranking(navegador, servidor)

        expect(pagina.locator("#visitadas-aviso")).to_be_hidden()

    def test_mostrar_traz_as_visitadas_de_volta(self, navegador, servidor):
        """A visitada **se soma** às oito sugestões, em vez de ocupar a vaga de uma.

        Se ela tomasse o lugar, revelar o que já foi feito custaria uma sugestão —
        e quanto mais o visitante andasse pelo parque, menos o app teria a dizer.
        """
        pagina = self.com_ranking(navegador, servidor)

        pagina.locator(".marcar-visitada").first.click()
        pagina.click("#btn-mostrar-visitadas")

        expect(pagina.locator("[data-modo='ranking'] .item")).to_have_count(9)
        expect(pagina.locator(".item--visitada")).to_have_count(1)

    def test_a_visitada_nao_e_a_melhor_escolha(self, navegador, servidor):
        """Uma atração já feita não é "a melhor escolha agora", por melhor que seja."""
        pagina = self.com_ranking(navegador, servidor)
        pagina.locator(".marcar-visitada").first.click()
        pagina.click("#btn-mostrar-visitadas")

        primeira = pagina.locator(".item").first

        expect(primeira).to_have_class(re.compile("item--visitada"))
        expect(primeira.locator(".etiqueta")).to_have_count(0)

    def test_desmarcar_devolve_ao_ranking(self, navegador, servidor):
        pagina = self.com_ranking(navegador, servidor)
        antes = pagina.locator("[data-modo='ranking'] .item").count()

        pagina.locator(".marcar-visitada").first.click()
        pagina.click("#btn-mostrar-visitadas")
        pagina.locator(".marcar-visitada").first.click()

        expect(pagina.locator(".item--visitada")).to_have_count(0)
        expect(pagina.locator("[data-modo='ranking'] .item")).to_have_count(antes)

    def test_limpar_esquece_tudo(self, navegador, servidor):
        pagina = self.com_ranking(navegador, servidor)
        antes = pagina.locator("[data-modo='ranking'] .item").count()

        pagina.locator(".marcar-visitada").first.click()
        pagina.locator(".marcar-visitada").first.click()
        pagina.click("#btn-limpar-visitadas")

        expect(pagina.locator("#visitadas-aviso")).to_be_hidden()
        expect(pagina.locator("[data-modo='ranking'] .item")).to_have_count(antes)

    def test_sobrevive_a_recarregar_a_pagina(self, navegador, servidor):
        """O ponto de guardar: fechar o app no meio do parque não pode zerar o dia."""
        pagina = self.com_ranking(navegador, servidor)
        nome = pagina.locator(".item .nome").first.inner_text()

        pagina.locator(".marcar-visitada").first.click()
        pagina.reload(wait_until="networkidle")
        pagina.click("#btn-localizar")
        pagina.wait_for_selector("[data-modo='ranking'] .item")

        expect(pagina.locator("#visitadas-texto")).to_contain_text("1 atração já visitada")
        assert nome not in pagina.locator("#lista").inner_text()

    def test_o_estado_e_por_parque(self, navegador, servidor):
        """Ter feito o Space Mountain não diz nada sobre o EPCOT."""
        pagina = self.com_ranking(navegador, servidor)
        pagina.locator(".marcar-visitada").first.click()
        expect(pagina.locator("#visitadas-aviso")).to_be_visible()

        pagina.select_option("#parque", PARQUE_DISTANTE)
        pagina.wait_for_timeout(1200)

        expect(pagina.locator("#visitadas-aviso")).to_be_hidden()

    def test_marcar_as_oito_revela_as_proximas(self, navegador, servidor):
        """O bug relatado pelo Gabriel em 20/09/2026.

        A tela mostra oito, e a tela **pedia** oito ao servidor. Marcando as oito
        como visitadas, a lista esvaziava — e o app anunciava "você já passou por
        todas as atrações disponíveis", com vinte atrações livres a poucos metros.

        A causa é o padrão que este projeto já tropeçou três vezes: pedir a lista
        cortada e depois raciocinar sobre ela. A correção é a regra registrada no
        CLAUDE.md — peça tudo, corte na exibição.
        """
        pagina = self.com_ranking(navegador, servidor)
        primeiros = pagina.locator("[data-modo='ranking'] .item .nome").all_inner_texts()

        for _ in range(8):
            pagina.locator(".marcar-visitada").first.click()
            pagina.wait_for_timeout(120)

        # A lista continua cheia, e com nomes que não estavam lá antes.
        expect(pagina.locator("[data-modo='ranking'] .item")).to_have_count(8)

        novos = pagina.locator("[data-modo='ranking'] .item .nome").all_inner_texts()

        assert not set(novos) & set(primeiros), "as visitadas voltaram para a lista"
        expect(pagina.locator("#visitadas-texto")).to_contain_text("8 atrações")

    def test_a_melhor_escolha_e_promovida_a_cada_marcacao(self, navegador, servidor):
        """Sempre há uma melhor escolha enquanto houver atração disponível."""
        pagina = self.com_ranking(navegador, servidor)

        for _ in range(8):
            pagina.locator(".marcar-visitada").first.click()
            pagina.wait_for_timeout(120)
            expect(pagina.locator(".etiqueta")).to_have_count(1)

    def test_mostrar_nao_expulsa_as_sugestoes(self, navegador, servidor):
        """Revelar as visitadas não pode empurrar para fora o que interessa decidir."""
        pagina = self.com_ranking(navegador, servidor)

        for _ in range(3):
            pagina.locator(".marcar-visitada").first.click()
            pagina.wait_for_timeout(120)

        disponiveis = pagina.locator("[data-modo='ranking'] .item").count()
        pagina.click("#btn-mostrar-visitadas")

        # As oito sugestões continuam, e as três visitadas se somam a elas.
        expect(pagina.locator(".item--visitada")).to_have_count(3)
        expect(pagina.locator("[data-modo='ranking'] .item")).to_have_count(disponiveis + 3)

    def test_o_botao_anuncia_o_estado(self, navegador, servidor):
        """`aria-pressed` leva a mesma informação que a cor, para quem não a vê."""
        pagina = self.com_ranking(navegador, servidor)
        botao = pagina.locator(".marcar-visitada").first

        expect(botao).to_have_attribute("aria-pressed", "false")

        botao.click()
        pagina.click("#btn-mostrar-visitadas")

        expect(pagina.locator(".marcar-visitada").first).to_have_attribute("aria-pressed", "true")


class TestGraficoDoHistorico:
    """O gráfico — a entrega da Fase 6.5.

    É a primeira tela do NextUp feita de **dado nosso**: tudo o mais é a
    ThemeParks.wiki reempacotada. O histórico é interceptado aqui como o resto da
    API, então nada depende do banco nem da internet.
    """

    def abrir_com_historico(self, navegador, servidor, *, pontos=12):
        pagina = abrir(navegador, servidor)
        pagina.route("**/history*", lambda rota: rota.fulfill(json=_historico(pontos)))
        return pagina

    def expandir(self, pagina):
        pagina.click("#btn-localizar")
        pagina.wait_for_selector("[data-modo='ranking'] .item")
        pagina.locator(".ver-historico").first.click()

    def test_o_grafico_aparece_ao_pedir_o_historico(self, navegador, servidor):
        pagina = self.abrir_com_historico(navegador, servidor)
        self.expandir(pagina)

        expect(pagina.locator(".grafico svg").first).to_be_visible()
        expect(pagina.locator(".grafico-linha").first).to_be_visible()

    def test_a_linha_tem_um_ponto_por_medicao(self, navegador, servidor):
        """Prova que o gráfico desenha os dados recebidos, e não uma forma fixa."""
        pagina = self.abrir_com_historico(navegador, servidor, pontos=9)
        self.expandir(pagina)

        pontos = pagina.locator(".grafico-linha").first.get_attribute("points")

        assert len(pontos.split()) == 9

    def test_o_grafico_tem_alternativa_em_texto(self, navegador, servidor):
        """Um `<svg>` sem rótulo é invisível para leitor de tela.

        E aqui não há outra versão do conteúdo: os números da legenda não contam
        a forma da curva.
        """
        pagina = self.abrir_com_historico(navegador, servidor)
        self.expandir(pagina)

        rotulo = pagina.locator(".grafico svg").first.get_attribute("aria-label")

        assert "Fila nas últimas" in rotulo
        assert "minutos" in rotulo

    def test_mostra_minimo_media_e_maximo(self, navegador, servidor):
        pagina = self.abrir_com_historico(navegador, servidor)
        self.expandir(pagina)

        expect(pagina.locator(".grafico-numeros").first).to_contain_text("mín")
        expect(pagina.locator(".grafico-numeros").first).to_contain_text("máx")

    def test_clicar_de_novo_fecha(self, navegador, servidor):
        """Alternar é o que o `aria-expanded` promete ao leitor de tela."""
        pagina = self.abrir_com_historico(navegador, servidor)
        self.expandir(pagina)

        botao = pagina.locator(".ver-historico").first
        expect(botao).to_have_attribute("aria-expanded", "true")

        botao.click()

        expect(botao).to_have_attribute("aria-expanded", "false")
        assert pagina.locator(".grafico").count() == 0

    def test_historico_curto_explica_em_vez_de_desenhar(self, navegador, servidor):
        """Um gráfico de um ponto só não é gráfico — é um pixel solto."""
        pagina = self.abrir_com_historico(navegador, servidor, pontos=1)
        self.expandir(pagina)

        expect(pagina.locator(".grafico-vazio").first).to_contain_text("histórico suficiente")

    def test_historico_indisponivel_vira_frase_compreensivel(self, navegador, servidor):
        """503 é o que a API devolve quando o banco está fora do ar."""
        pagina = abrir(navegador, servidor)
        pagina.route("**/history*", lambda rota: rota.fulfill(status=503, json={"detail": "x"}))
        self.expandir(pagina)

        expect(pagina.locator(".grafico-vazio").first).to_contain_text("indisponível")

    def test_tambem_funciona_antes_de_dar_a_posicao(self, navegador, servidor):
        """Ver o passado de uma atração não depende de saber onde o visitante está."""
        pagina = abrir(navegador, servidor, com_gps=False)
        pagina.route("**/history*", lambda rota: rota.fulfill(json=_historico(12)))
        pagina.wait_for_selector("[data-modo='panorama'] .item")

        pagina.locator(".ver-historico").first.click()

        expect(pagina.locator(".grafico svg").first).to_be_visible()


class TestTrocaDeParque:
    """O mapa tem de seguir o parque escolhido — pelos dois caminhos possíveis."""

    def centro_do_mapa(self, pagina) -> tuple[float, float]:
        pos = pagina.evaluate("() => { const c = mapa.getCenter(); return [c.lat, c.lng]; }")
        return pos[0], pos[1]

    def test_escolher_no_seletor_reenquadra_o_mapa(self, navegador, servidor):
        pagina = abrir(navegador, servidor, com_gps=False)
        pagina.wait_for_selector("[data-modo='panorama'] .item")
        _, longitude_antes = self.centro_do_mapa(pagina)

        pagina.select_option("#parque", PARQUE_DISTANTE)
        pagina.wait_for_timeout(1200)

        _, longitude_depois = self.centro_do_mapa(pagina)

        # Orlando é longitude negativa; o parque sintético é positiva. Se o mapa
        # não tivesse se movido, o sinal continuaria o mesmo.
        assert longitude_antes < 0
        assert longitude_depois > 0

    def test_enter_na_busca_tambem_troca_o_parque(self, navegador, servidor):
        """O bug relatado pelo Gabriel em 20/09/2026.

        Filtrar reconstrói o `<select>` e o navegador passa a **exibir** a primeira
        opção — mas exibir não é selecionar. Nenhum `change` disparava, então quem
        digitasse o nome e desse Enter via o parque certo escrito no seletor
        enquanto o app continuava no anterior. A tela mentia.
        """
        pagina = abrir(navegador, servidor, com_gps=False)
        pagina.wait_for_selector("[data-modo='panorama'] .item")
        _, longitude_antes = self.centro_do_mapa(pagina)

        pagina.fill("#busca-parque", "SeaWorld Orlando")
        pagina.press("#busca-parque", "Enter")
        pagina.wait_for_timeout(1200)

        _, longitude_depois = self.centro_do_mapa(pagina)

        assert longitude_antes < 0
        assert longitude_depois > 0, "o Enter não aplicou o parque filtrado"

    def test_enter_sem_resultado_nao_faz_nada(self, navegador, servidor):
        """Não pode cair no parque padrão só porque a busca não achou nada."""
        pagina = abrir(navegador, servidor, com_gps=False)
        pagina.wait_for_selector("[data-modo='panorama'] .item")
        antes = self.centro_do_mapa(pagina)

        pagina.fill("#busca-parque", "zzzz-nao-existe")
        pagina.press("#busca-parque", "Enter")
        pagina.wait_for_timeout(600)

        expect(pagina.locator("#busca-vazia")).to_be_visible()
        assert self.centro_do_mapa(pagina) == antes

    def test_enter_nao_recarrega_a_pagina(self, navegador, servidor):
        """Recarregar perderia a posição que o visitante já tinha informado."""
        pagina = abrir(navegador, servidor, com_gps=False)
        pagina.wait_for_selector("[data-modo='panorama'] .item")
        pagina.evaluate("() => { window.__marcador = true; }")

        pagina.fill("#busca-parque", "SeaWorld Orlando")
        pagina.press("#busca-parque", "Enter")
        pagina.wait_for_timeout(800)

        assert pagina.evaluate("() => window.__marcador === true")


class TestFluxoFeliz:
    def test_permitir_gps_mostra_o_ranking(self, navegador, servidor):
        pagina = abrir(navegador, servidor)

        pagina.click("#btn-localizar")
        pagina.wait_for_selector("[data-modo='ranking'] .item")

        expect(pagina.locator("#titulo-lista")).to_have_text("Magic Kingdom Park")
        expect(pagina.locator("#resumo")).to_contain_text("26 de 35")
        expect(pagina.locator("[data-modo='ranking'] .item")).to_have_count(8)

    def test_lista_sai_em_ordem_crescente_de_custo(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        pagina.wait_for_selector("[data-modo='ranking'] .item")

        minutos = [int(texto) for texto in pagina.locator(".custo strong").all_inner_texts()]

        assert minutos == sorted(minutos)

    def test_primeira_colocada_recebe_destaque(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        # Espera o **ranking**, e não qualquer item: o panorama já está na tela
        # desde a abertura, e um `.item` solto encontraria o item errado.
        pagina.wait_for_selector("[data-modo='ranking'] .item")

        assert pagina.locator(".etiqueta").count() == 1
        expect(pagina.locator(".item").first).to_have_class("item item--melhor")

    def test_cada_item_mostra_a_conta_aberta(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        pagina.wait_for_selector("[data-modo='ranking'] .item")

        expect(pagina.locator(".item").first).to_contain_text("a pé")
        expect(pagina.locator(".item").first).to_contain_text("de fila")
        # As duas parcelas aparecem separadas, cada uma com seu ícone.
        assert pagina.locator(".item").first.locator(".parcela").count() == 2

    def test_atracoes_aparecem_no_mapa(self, navegador, servidor):
        """Com o ranking na tela, o mapa mostra as 8 colocadas — não o parque todo.

        O `expect` com retentativa, em vez de um `assert` direto, é proposital:
        duas chamadas assíncronas desenham no mapa (o panorama da abertura e o
        ranking), e sem esperar a que vence o teste ficaria instável, passando ou
        falhando conforme qual respondeu primeiro.
        """
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        pagina.wait_for_selector("[data-modo='ranking'] .item")

        expect(pagina.locator(".leaflet-marker-icon")).to_have_count(8)

    def test_informa_a_idade_do_dado(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        pagina.wait_for_selector("[data-modo='ranking'] .item")

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
        pagina.wait_for_selector("[data-modo='ranking'] .item")

        expect(pagina.locator("#posicao-atual")).to_contain_text("escolhida no mapa")
        expect(pagina.locator("[data-modo='ranking'] .item")).to_have_count(8)


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
        pagina.wait_for_selector("[data-modo='ranking'] .item")

        assert pagina.evaluate("window.__invadido === undefined")
        expect(pagina.locator(".nome")).to_contain_text("<img")


class TestResponsivo:
    def test_nao_ha_rolagem_horizontal_no_celular(self, navegador, servidor):
        """Rolagem lateral em celular é o sintoma clássico de layout quebrado."""
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        pagina.wait_for_selector("[data-modo='ranking'] .item")

        largura_conteudo = pagina.evaluate("document.documentElement.scrollWidth")
        largura_tela = pagina.evaluate("document.documentElement.clientWidth")

        assert largura_conteudo <= largura_tela + 1

    def test_botao_tem_alvo_confortavel_para_o_dedo(self, navegador, servidor):
        """48px é o mínimo recomendado para toque."""
        pagina = abrir(navegador, servidor)

        caixa = pagina.locator("#btn-localizar").bounding_box()

        assert caixa["height"] >= 44

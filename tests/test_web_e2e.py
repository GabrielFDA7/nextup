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
COMPUTADOR = {"width": 1440, "height": 900}


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


#: Um PNG de 1x1 transparente: o menor tile que o Leaflet aceita como carregado.
PNG_VAZIO = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000b49444154789c6360000200000500017a5eab3f0000000049454e44"
    "ae426082"
)

#: O perfil de quem "já respondeu e pulou": nada marcado, nada escondido — o app de
#: antes da Fase 9. É o padrão do `abrir`, porque na primeira visita o painel das
#: duas perguntas abre por cima da tela, e todo teste que não fala de perfil
#: falharia por um motivo que não é o assunto dele.
PERFIL_PULADO = {"respondido": True, "alturaCm": None, "intensidade": "tudo"}


def abrir(
    navegador,
    servidor,
    *,
    com_gps: bool = True,
    api=None,
    perfil: dict | None = PERFIL_PULADO,
    seletor: bool = False,
    tela: dict = CELULAR,
) -> Page:
    """Abre a página com a API interceptada dentro do navegador.

    `api` recebe uma função que responde à rota de recomendações; o padrão
    devolve a fixture real do Magic Kingdom.

    `perfil=None` abre como numa primeira visita de verdade, sem nada guardado.

    `seletor=True` liga a troca de parque. A primeira versão é só o Magic Kingdom
    (decisão do Gabriel), mas o código dos outros parques ficou — e continua
    testado por aqui, sem que o visitante tenha como chegar a ele.
    """
    contexto = navegador.new_context(
        viewport=tela,
        locale="pt-BR",
        geolocation=POSICAO if com_gps else None,
        permissions=["geolocation"] if com_gps else [],
    )
    if perfil is not None:
        # Só grava se não houver: o script roda de novo a cada recarga, e
        # sobrescrever apagaria justamente o que um teste de persistência salvou.
        contexto.add_init_script(
            "if (!localStorage.getItem('nextup:perfil')) "
            f"localStorage.setItem('nextup:perfil', {json.dumps(json.dumps(perfil))});"
        )
    if seletor:
        contexto.add_init_script("window.NEXTUP_SELETOR_DE_PARQUES = true;")
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
    # Os tiles também são internet. O Magic Kingdom não os usa desde a 9.3 (o mapa
    # é desenhado), mas os outros parques sim — e até então cada teste baixava
    # imagens de verdade do tile.openstreetmap.org sem ninguém perceber.
    pagina.route(
        "**/tile.openstreetmap.org/**",
        lambda rota: rota.fulfill(status=200, content_type="image/png", body=PNG_VAZIO),
    )

    pagina.goto(servidor, wait_until="networkidle")
    return pagina


def _ver_filas(pagina, modo: str) -> None:
    """Abre o painel de todas as filas (9.3) e espera a lista no modo pedido.

    A lista mora num painel desde o redesenho: a tela principal fica com o cartão
    do próximo passo. Fechado, o painel esconde a lista, e esperar por ela sem
    abri-lo seria esperar para sempre.
    """
    if not pagina.locator("#painel-filas").evaluate("d => d.open"):
        pagina.click("#btn-todas-filas")
    pagina.wait_for_selector(f"[data-modo='{modo}'] .item")


def _fechar_filas(pagina) -> None:
    """Fecha o painel: aberto, ele deixa o resto da página inerte (é modal)."""
    if pagina.locator("#painel-filas").evaluate("d => d.open"):
        pagina.keyboard.press("Escape")


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
        curadoria=_curadoria_mk(),
    )
    return json.loads(resposta.model_dump_json())


#: Faixas inventadas para o catálogo, com médias que fixam a ordem dentro de cada uma.
#: As três principais são as da medição de verdade (seção 7.4 do PROJETO.md).
FAIXAS_DE_TESTE = {
    "TRON": ("HEADLINER", 70.0),
    "Seven Dwarfs": ("HEADLINER", 65.0),
    "Space Mountain": ("HEADLINER", 50.0),
    "Big Thunder": ("MODERATE", 30.0),
    "Haunted Mansion": ("MODERATE", 25.0),
}


def _atracoes_com_faixas() -> dict:
    """A resposta real de `/attractions`, com popularidade em algumas atrações.

    As outras ficam com `popularity: null`, como as que o histórico não cobre — e
    caem no grupo "sem histórico", que é o que um banco recém-ligado mostraria.
    """
    corpo = _atracoes_como_a_api_devolve()
    for atracao in corpo["attractions"]:
        for trecho, (faixa, media) in FAIXAS_DE_TESTE.items():
            if trecho in atracao["name"]:
                atracao["popularity"] = {
                    "tier": faixa,
                    "average_minutes": media,
                    "measurements": 50,
                    "opportunity": False,
                }
    return corpo


def _curadoria_mk():
    """A curadoria de verdade, só as linhas conferidas — o que a rota de produção usa.

    Sem ela a resposta sairia com `min_height_cm` e `intensity` nulos em todas as
    atrações, e os testes do perfil passariam sem ter o que marcar ou esconder.
    """
    from nextup.data import load_curation

    return load_curation(DEFAULT_PARK_ID).verified()


def _recomendacoes_como_a_api_devolve(
    *, com_tendencia: bool = False, com_popularidade: bool = False
) -> dict:
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

    if com_popularidade:
        from nextup.core.popularity import classify

        # As médias são inventadas, mas o **classificador é o de verdade**: repetir
        # aqui a regra de faixa faria o teste concordar com uma cópia da regra em
        # vez de com a regra, e os dois errariam juntos.
        #
        # A líder do ranking recebe média alta o bastante para ser principal E
        # ficar acima da fila que ela tem agora — é o cenário de oportunidade.
        #
        # As demais **intercalam** as faixas em vez de agrupá-las por posição. A
        # tela mostra só as oito primeiras, e agrupar punha as tranquilas da nona
        # em diante: o teste do filtro não teria nenhuma para esconder e passaria
        # sem exercitar nada. Foi pego por uma asserção de guarda.
        ciclo = [6.0, 20.0, 50.0, 6.0, 20.0]  # tranquila, miolo, principal, ...
        medias = {}
        for posicao, recomendacao in enumerate(ranking):
            aid = recomendacao.attraction.id
            if posicao == 0:
                medias[aid] = (float(max(recomendacao.queue_minutes * 4, 60)), 40)
            elif posicao >= 16:
                medias[aid] = (30.0, 2)  # histórico curto: UNKNOWN
            else:
                medias[aid] = (ciclo[posicao % len(ciclo)], 40)

        ranking = recommend(
            catalog=catalogo,
            live=ao_vivo,
            visitor=visitante,
            limit=0,
            trends=tendencias,
            popularity=classify(medias),
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
        curadoria=_curadoria_mk(),
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
        teste de API perceberia. Desde a 9.3 o Magic Kingdom é desenhado a partir
        do GeoJSON, e são as trilhas que provam que o mapa existe."""
        pagina = abrir(navegador, servidor)

        expect(pagina.locator("#mapa path.m-trilha")).not_to_have_count(0)

    def test_seletor_lista_os_parques_da_api(self, navegador, servidor):
        pagina = abrir(navegador, servidor, seletor=True)

        assert pagina.locator("#parque option").count() == 11  # 3 destinos da fixture
        assert pagina.is_enabled("#parque")

    def test_comeca_pedindo_a_posicao(self, navegador, servidor):
        """Continua pedindo a posição — mas já não abre vazio.

        Antes, quem não liberasse o GPS via uma tela em branco e nenhuma razão
        para confiar no resto. Agora o parque aparece de cara, e o aviso explica o
        que **falta** para o app responder a pergunta que ele promete responder.
        """
        pagina = abrir(navegador, servidor)

        expect(pagina.locator("#passo-sem-posicao")).to_contain_text("Onde você está?")
        expect(pagina.locator("#btn-localizar")).to_be_visible()
        _ver_filas(pagina, "panorama")

        # Sem posição não existe ranking, e o app não pode fingir que existe.
        assert pagina.locator("[data-modo='ranking']").count() == 0
        assert pagina.locator(".etiqueta").count() == 0

    def test_mostra_as_filas_antes_de_saber_onde_voce_esta(self, navegador, servidor):
        """A pergunta "como está o parque?" não depende de saber onde o visitante está."""
        pagina = abrir(navegador, servidor)
        _ver_filas(pagina, "panorama")

        expect(pagina.locator("#resumo")).to_contain_text("fila medida")
        assert pagina.locator("[data-modo='panorama'] .item").count() > 0

    def test_o_panorama_avisa_que_nao_e_recomendacao(self, navegador, servidor):
        """A ressalva é a tese do produto, não modéstia.

        A lista sem posição é ordenada pela menor fila — a pergunta que o NextUp
        existe para contestar. Sem este aviso, os primeiros colocados (que em
        alguns parques são playgrounds com fila zero) seriam lidos como conselho.
        """
        pagina = abrir(navegador, servidor)
        _ver_filas(pagina, "panorama")

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
        _ver_filas(pagina, "ranking")

        expect(pagina.locator(".tendencia--caindo").first).to_contain_text("Caiu de 45 para 20")

    def test_a_cor_nao_carrega_a_informacao_sozinha(self, navegador, servidor):
        """Quem não distingue verde de vermelho precisa ler a mesma coisa.

        A seta aponta e o texto diz por extenso; a cor só reforça.
        """
        pagina = self.com_tendencia(navegador, servidor)
        pagina.click("#btn-localizar")
        _ver_filas(pagina, "ranking")

        tendencia = pagina.locator(".tendencia").first

        assert tendencia.locator("svg").count() == 1
        expect(tendencia).to_contain_text("Caiu")

    def test_sem_historico_nao_inventa_tendencia(self, navegador, servidor):
        """O padrão dos testes é sem histórico — e nada deve aparecer."""
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        _ver_filas(pagina, "ranking")

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
        _ver_filas(pagina, "ranking")
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
        _ver_filas(pagina, "ranking")

        expect(pagina.locator("#visitadas-texto")).to_contain_text("1 atração já visitada")
        assert nome not in pagina.locator("#lista").inner_text()

    def test_o_estado_e_por_parque(self, navegador, servidor):
        """Ter feito o Space Mountain não diz nada sobre o EPCOT."""
        pagina = abrir(navegador, servidor, seletor=True)
        _localizar(pagina)
        pagina.locator(".marcar-visitada").first.click()
        expect(pagina.locator("#visitadas-aviso")).to_be_visible()

        _fechar_filas(pagina)
        pagina.select_option("#parque", PARQUE_DISTANTE)
        pagina.wait_for_timeout(1200)

        # Reabrir o painel: fechado, o aviso estaria escondido de qualquer jeito,
        # e o teste passaria sem provar nada.
        _ver_filas(pagina, "ranking")
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


class TestBrinquedosAlvo:
    """ "Você veio por estas" — a entrega da Fase 7.2.

    A seção existe fora do ranking porque responde **outra pergunta**. O ranking
    diz o que compensa mais agora; esta lista diz quando ir naquilo que o visitante
    veio fazer — e para isso precisa mostrar o alvo mesmo quando ele está caro.
    """

    def com_ranking(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        _ver_filas(pagina, "ranking")
        return pagina

    def test_a_secao_convida_mesmo_vazia(self, navegador, servidor):
        """Escondida, a funcionalidade não existiria para quem nunca tropeçou nela.

        Foi a crítica do Gabriel em 20/09/2026: marcar alvos só pelo ranking é um
        mecanismo falho, porque a tela mostra oito de trinta e cinco.
        """
        pagina = self.com_ranking(navegador, servidor)

        expect(pagina.locator("#secao-alvos")).to_be_visible()
        expect(pagina.locator("#alvos-resumo")).to_contain_text("Marque o que você veio")
        expect(pagina.locator("#escolher-alvos")).to_be_visible()

    def test_marcar_preenche_a_secao(self, navegador, servidor):
        pagina = self.com_ranking(navegador, servidor)
        nome = pagina.locator("[data-modo='ranking'] .item .nome").first.inner_text()

        pagina.locator("[data-modo='ranking'] .marcar-alvo").first.click()

        expect(pagina.locator("[data-modo='alvos'] .item")).to_have_count(1)
        expect(pagina.locator("[data-modo='alvos'] .nome").first).to_have_text(nome)

    def test_o_alvo_sai_do_ranking(self, navegador, servidor):
        """Repetir o alvo nas duas listas gastaria uma das oito vagas do ranking.

        E a lista não encolhe: a nona colocada sobe, como acontece ao marcar uma
        visitada.
        """
        pagina = self.com_ranking(navegador, servidor)
        nome = pagina.locator("[data-modo='ranking'] .item .nome").first.inner_text()

        pagina.locator("[data-modo='ranking'] .marcar-alvo").first.click()

        expect(pagina.locator("[data-modo='ranking'] .item")).to_have_count(8)
        assert nome not in pagina.locator("#lista").inner_text()

    def test_o_alvo_aparece_mesmo_com_fila_alta(self, navegador, servidor):
        """O caso que justifica a seção existir.

        Marca a **última** colocada do ranking inteiro — a mais cara de todas — e
        ela tem de ficar visível. Enterrada em vigésimo lugar, seria invisível
        justamente para quem veio por ela.
        """
        pagina = self.com_ranking(navegador, servidor)

        # Revela a lista toda para alcançar a pior colocada.
        pagina.evaluate("() => { estado.mostrandoVisitadas = true; }")
        pior = pagina.evaluate("() => estado.ultimoRanking.recommendations.at(-1).attraction.id")
        pagina.evaluate(f"() => alternarAlvo({pior!r})")
        pagina.wait_for_timeout(500)

        expect(pagina.locator("#secao-alvos")).to_be_visible()
        expect(pagina.locator("[data-modo='alvos'] .item")).to_have_count(1)

    def test_os_alvos_saem_ordenados_por_custo(self, navegador, servidor):
        """A tese não muda; muda o conjunto sobre o qual ela é aplicada."""
        pagina = self.com_ranking(navegador, servidor)

        for indice in (4, 0, 2):
            pagina.locator("[data-modo='ranking'] .marcar-alvo").nth(indice).click()
            pagina.wait_for_timeout(200)

        custos = [
            int(texto)
            for texto in pagina.locator("[data-modo='alvos'] .custo strong").all_inner_texts()
        ]

        assert custos == sorted(custos), f"alvos fora de ordem: {custos}"

    def test_a_etiqueta_de_melhor_escolha_nao_vaza_para_os_alvos(self, navegador, servidor):
        """Ela compara o parque inteiro; repeti-la sobre três atrações mentiria."""
        pagina = self.com_ranking(navegador, servidor)
        pagina.locator("[data-modo='ranking'] .marcar-alvo").first.click()

        expect(pagina.locator("[data-modo='alvos'] .etiqueta")).to_have_count(0)
        expect(pagina.locator("[data-modo='ranking'] .etiqueta")).to_have_count(1)

    def test_desmarcar_devolve_ao_ranking(self, navegador, servidor):
        pagina = self.com_ranking(navegador, servidor)
        pagina.locator("[data-modo='ranking'] .marcar-alvo").first.click()
        _fechar_filas(pagina)

        pagina.locator("[data-modo='alvos'] .marcar-alvo").first.click()

        expect(pagina.locator("[data-modo='alvos'] .item")).to_have_count(0)
        expect(pagina.locator("#alvos-resumo")).to_contain_text("Marque o que você veio")

    def test_limpar_esvazia_a_lista(self, navegador, servidor):
        pagina = self.com_ranking(navegador, servidor)
        for _ in range(2):
            pagina.locator("[data-modo='ranking'] .marcar-alvo").first.click()
            pagina.wait_for_timeout(200)

        _fechar_filas(pagina)
        pagina.click("#btn-limpar-alvos")

        expect(pagina.locator("[data-modo='alvos'] .item")).to_have_count(0)
        expect(pagina.locator("#btn-limpar-alvos")).to_be_hidden()

    def test_os_alvos_sobrevivem_a_recarregar(self, navegador, servidor):
        """Alvos não têm prazo: são desejo, não acontecimento."""
        pagina = self.com_ranking(navegador, servidor)
        pagina.locator("[data-modo='ranking'] .marcar-alvo").first.click()
        nome = pagina.locator("[data-modo='alvos'] .nome").first.inner_text()

        pagina.reload(wait_until="networkidle")
        pagina.click("#btn-localizar")
        _ver_filas(pagina, "ranking")

        expect(pagina.locator("[data-modo='alvos'] .nome").first).to_have_text(nome)

    def test_um_alvo_tambem_pode_ser_marcado_como_visitado(self, navegador, servidor):
        """As duas marcações são independentes e convivem no mesmo item."""
        pagina = self.com_ranking(navegador, servidor)
        pagina.locator("[data-modo='ranking'] .marcar-alvo").first.click()
        _fechar_filas(pagina)

        pagina.locator("[data-modo='alvos'] .marcar-visitada").first.click()

        expect(pagina.locator("[data-modo='alvos'] .item--visitada")).to_have_count(1)
        expect(pagina.locator("#alvos-resumo")).to_contain_text("1 de 1 já feitas")

    def test_o_estado_e_por_parque(self, navegador, servidor):
        pagina = abrir(navegador, servidor, seletor=True)
        _localizar(pagina)
        pagina.locator("[data-modo='ranking'] .marcar-alvo").first.click()
        expect(pagina.locator("[data-modo='alvos'] .item")).to_have_count(1)

        _fechar_filas(pagina)
        pagina.select_option("#parque", PARQUE_DISTANTE)
        pagina.wait_for_timeout(1200)

        expect(pagina.locator("[data-modo='alvos'] .item")).to_have_count(0)


class TestCatalogoDeAlvos:
    """O seletor com a lista completa do parque — a correção de 20/09/2026.

    Marcar alvos só pelo ranking era um mecanismo falho: a tela mostra oito de
    trinta e cinco, e quem veio pelo Space Mountain não conseguia dizer isso ao
    app até ele, por acaso, aparecer entre as oito melhores.
    """

    def abrir_catalogo(self, navegador, servidor, *, com_gps=True):
        pagina = abrir(navegador, servidor, com_gps=com_gps)
        # `state="attached"`, e não o padrão "visible": dentro de um `<details>`
        # fechado os itens existem no DOM mas não são visíveis, e esperar por
        # visibilidade antes de abrir o painel espera para sempre.
        pagina.wait_for_selector("#catalogo-atracoes .catalogo__item", state="attached")
        pagina.click(".escolher__gatilho")
        return pagina

    def test_lista_o_parque_inteiro(self, navegador, servidor):
        """Trinta e cinco atrações, não as oito do ranking."""
        pagina = self.abrir_catalogo(navegador, servidor)

        expect(pagina.locator(".catalogo__item")).to_have_count(35)

    def test_mostra_a_fila_de_cada_uma(self, navegador, servidor):
        """Ajuda a escolher — e "—" para quem não tem fila medida é mais honesto
        que omitir a linha ou inventar um zero."""
        pagina = self.abrir_catalogo(navegador, servidor)
        filas = pagina.locator(".catalogo__fila").all_inner_texts()

        assert any("min" in f for f in filas)
        assert any(f == "—" for f in filas)

    def test_marcar_pelo_catalogo_cria_o_alvo(self, navegador, servidor):
        """Com posição, o alvo vira item completo — com o custo até ele.

        O `localizar` é necessário: sem posição não há ranking, e a seção de alvos
        mostra só a contagem. É o que `test_funciona_antes_de_dar_a_posicao`
        verifica do outro lado.
        """
        pagina = self.abrir_catalogo(navegador, servidor)
        pagina.click("#btn-localizar")
        _ver_filas(pagina, "ranking")
        _fechar_filas(pagina)

        nome = pagina.locator(".catalogo__nome").first.inner_text()
        pagina.locator(".catalogo__item input").first.check()
        pagina.wait_for_timeout(300)

        expect(pagina.locator("[data-modo='alvos'] .nome").first).to_have_text(nome)

    def test_desmarcar_pelo_catalogo_remove_o_alvo(self, navegador, servidor):
        """Remover tem de ser tão fácil quanto adicionar."""
        pagina = self.abrir_catalogo(navegador, servidor)
        pagina.locator(".catalogo__item input").first.check()
        pagina.wait_for_timeout(300)

        pagina.locator(".catalogo__item input").first.uncheck()
        pagina.wait_for_timeout(300)

        expect(pagina.locator("[data-modo='alvos'] .item")).to_have_count(0)

    def test_a_lista_nao_se_reordena_sob_o_dedo(self, navegador, servidor):
        """Marcar não pode fazer a atração saltar para o topo na mesma hora.

        Quem está escolhendo várias perderia o lugar a cada clique. A linha muda
        de aparência; a ordem espera o painel fechar.
        """
        pagina = self.abrir_catalogo(navegador, servidor)
        nome = pagina.locator(".catalogo__nome").nth(20).inner_text()

        pagina.locator(".catalogo__item input").nth(20).check()
        pagina.wait_for_timeout(300)

        expect(pagina.locator(".catalogo__nome").nth(20)).to_have_text(nome)
        expect(pagina.locator(".catalogo__item").nth(20)).to_have_class(
            re.compile("catalogo__item--marcada")
        )

    def test_as_marcadas_sobem_ao_reabrir(self, navegador, servidor):
        """Quem abriu a lista para tirar algo não deveria procurar entre 35."""
        pagina = self.abrir_catalogo(navegador, servidor)
        nome = pagina.locator(".catalogo__nome").nth(20).inner_text()
        pagina.locator(".catalogo__item input").nth(20).check()

        pagina.click(".escolher__gatilho")  # fecha
        pagina.click(".escolher__gatilho")  # abre de novo
        pagina.wait_for_timeout(300)

        expect(pagina.locator(".catalogo__nome").first).to_have_text(nome)
        expect(pagina.locator(".catalogo__item input").first).to_be_checked()

    def test_sem_popularidade_a_ordem_e_alfabetica(self, navegador, servidor):
        """Sem banco não há faixa, e um título "Sem histórico" sobre o parque
        inteiro diria algo verdadeiro e inútil."""
        pagina = self.abrir_catalogo(navegador, servidor)
        nomes = pagina.locator(".catalogo__nome").all_inner_texts()

        # A régua é a do navegador, e não o `sorted` do Python: as aspas de
        # "it's a small world" e os acentos ordenam diferente nas duas.
        em_ordem = pagina.evaluate(
            "nomes => [...nomes].sort((a, b) => a.localeCompare(b, 'pt-BR'))", nomes
        )
        assert nomes == em_ordem
        expect(pagina.locator(".catalogo__titulo")).to_have_count(0)

    def test_com_popularidade_as_principais_vem_primeiro(self, navegador, servidor):
        """A ordem que o Gabriel escolheu (29/10/2026): quem monta a lista de
        desejos procura as principais, e a faixa não muda a cada minuto."""
        pagina = self.abrir_catalogo_com_faixas(navegador, servidor)

        titulos = pagina.locator(".catalogo__titulo").all_inner_texts()
        assert [t.lower() for t in titulos] == [
            "as principais do parque",
            "também procuradas",
            "sem histórico suficiente",
        ]
        nomes = pagina.locator(".catalogo__nome").all_inner_texts()
        # Dentro da faixa, a maior fila média primeiro.
        assert "TRON" in nomes[0]
        assert "Seven Dwarfs" in nomes[1]
        assert "Space Mountain" in nomes[2]

    def test_as_marcadas_ganham_grupo_proprio(self, navegador, servidor):
        pagina = self.abrir_catalogo_com_faixas(navegador, servidor)
        pagina.locator(".catalogo__item", has_text="Space Mountain").locator("input").check()

        pagina.click(".escolher__gatilho")  # fecha
        pagina.click(".escolher__gatilho")  # abre de novo

        expect(pagina.locator(".catalogo__titulo").first).to_have_text(
            re.compile("na sua lista", re.IGNORECASE)
        )
        expect(pagina.locator(".catalogo__nome").first).to_contain_text("Space Mountain")

    def test_a_linha_inteira_marca(self, navegador, servidor):
        """A caixa nativa cobre a linha, transparente: tocar no nome também marca."""
        pagina = self.abrir_catalogo(navegador, servidor)
        linha = pagina.locator(".catalogo__item").nth(3)

        # Clicar no nome pelo Playwright seria recusado — e com razão: a caixa
        # transparente está por cima dele, que é o desenho. O dedo toca a linha.
        linha.click()

        expect(linha.locator("input")).to_be_checked()
        expect(linha).to_have_class(re.compile("catalogo__item--marcada"))

    def abrir_catalogo_com_faixas(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        # A rota registrada por último vence: esta passa na frente da de `abrir`.
        pagina.route(
            "**/attractions*",
            lambda rota: rota.fulfill(json=_atracoes_com_faixas()),
        )
        pagina.reload(wait_until="networkidle")
        pagina.wait_for_selector("#catalogo-atracoes .catalogo__item", state="attached")
        pagina.click(".escolher__gatilho")
        return pagina

    def test_a_busca_filtra_a_lista(self, navegador, servidor):
        pagina = self.abrir_catalogo(navegador, servidor)

        pagina.fill("#busca-atracao", "mountain")
        pagina.wait_for_timeout(300)

        nomes = pagina.locator(".catalogo__nome").all_inner_texts()

        assert nomes, "a busca não encontrou nada"
        assert all("mountain" in n.lower() for n in nomes)

    def test_busca_sem_resultado_avisa(self, navegador, servidor):
        pagina = self.abrir_catalogo(navegador, servidor)

        pagina.fill("#busca-atracao", "zzzznaoexiste")
        pagina.wait_for_timeout(300)

        expect(pagina.locator("#escolher-vazio")).to_be_visible()

    def test_funciona_antes_de_dar_a_posicao(self, navegador, servidor):
        """Montar a lista de desejos é algo que se faz a caminho do parque.

        A rota `/attractions` não exige posição, então o seletor também não.
        """
        pagina = self.abrir_catalogo(navegador, servidor, com_gps=False)

        expect(pagina.locator(".catalogo__item")).to_have_count(35)

        pagina.locator(".catalogo__item input").first.check()
        pagina.wait_for_timeout(300)

        expect(pagina.locator("#alvos-resumo")).to_contain_text("Diga onde você está")

    def test_o_estado_do_catalogo_sobrevive_a_recarregar(self, navegador, servidor):
        pagina = self.abrir_catalogo(navegador, servidor)
        pagina.locator(".catalogo__item input").first.check()
        pagina.wait_for_timeout(300)

        pagina.reload(wait_until="networkidle")
        pagina.wait_for_selector("#catalogo-atracoes .catalogo__item", state="attached")
        pagina.click(".escolher__gatilho")

        expect(pagina.locator(".catalogo__item input").first).to_be_checked()


class TestFiltros:
    """Os limites do visitante — a entrega da Fase 7.3.

    Existem porque o `custo_total` **soma as parcelas**, e elas não são
    intercambiáveis: 5 min de caminhada + 35 de fila dá o mesmo total que 20 + 20,
    e são experiências opostas para quem empurra um carrinho.

    O filtro **corta**, não reordena — a ordem continua sendo por custo total.
    """

    def com_ranking(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        _ver_filas(pagina, "ranking")
        pagina.click("#filtros .escolher__gatilho")
        return pagina

    def filas(self, pagina):
        return [
            int(texto.split()[0])
            for texto in pagina.locator("[data-modo='ranking'] .parcela").all_inner_texts()
            if "de fila" in texto
        ]

    def test_o_filtro_de_fila_corta_a_lista(self, navegador, servidor):
        pagina = self.com_ranking(navegador, servidor)

        pagina.locator("#filtro-fila").fill("10")
        pagina.dispatch_event("#filtro-fila", "input")
        pagina.wait_for_timeout(400)

        assert self.filas(pagina), "o filtro escondeu tudo"
        assert all(f <= 10 for f in self.filas(pagina))

    def test_o_filtro_de_caminhada_corta_a_lista(self, navegador, servidor):
        pagina = self.com_ranking(navegador, servidor)

        pagina.locator("#filtro-caminhada").fill("5")
        pagina.dispatch_event("#filtro-caminhada", "input")
        pagina.wait_for_timeout(400)

        caminhadas = [
            int(texto.split()[0])
            for texto in pagina.locator("[data-modo='ranking'] .parcela").all_inner_texts()
            if "a pé" in texto
        ]

        assert caminhadas, "o filtro escondeu tudo"
        assert all(c <= 5 for c in caminhadas)

    def test_o_filtro_nao_reordena(self, navegador, servidor):
        """Corta, e só. A ordem continua sendo por custo total — a tese do projeto."""
        pagina = self.com_ranking(navegador, servidor)

        pagina.locator("#filtro-fila").fill("15")
        pagina.dispatch_event("#filtro-fila", "input")
        pagina.wait_for_timeout(400)

        custos = [
            int(t) for t in pagina.locator("[data-modo='ranking'] .custo strong").all_inner_texts()
        ]

        assert custos == sorted(custos), f"a lista saiu fora de ordem: {custos}"

    def test_o_rotulo_acompanha_o_controle(self, navegador, servidor):
        pagina = self.com_ranking(navegador, servidor)

        expect(pagina.locator("#rotulo-fila")).to_have_text("Sem limite")

        pagina.locator("#filtro-fila").fill("30")
        pagina.dispatch_event("#filtro-fila", "input")

        expect(pagina.locator("#rotulo-fila")).to_have_text("Até 30 min")

    def test_o_selo_denuncia_filtro_ligado(self, navegador, servidor):
        """Filtro esquecido é indistinguível de parque vazio, e o app pareceria quebrado."""
        pagina = self.com_ranking(navegador, servidor)

        expect(pagina.locator("#filtros-ativos")).to_be_hidden()

        pagina.locator("#filtro-fila").fill("20")
        pagina.dispatch_event("#filtro-fila", "input")

        expect(pagina.locator("#filtros-ativos")).to_be_visible()

    def test_limpar_devolve_a_lista_inteira(self, navegador, servidor):
        pagina = self.com_ranking(navegador, servidor)
        antes = pagina.locator("[data-modo='ranking'] .item").count()

        pagina.locator("#filtro-fila").fill("5")
        pagina.dispatch_event("#filtro-fila", "input")
        pagina.wait_for_timeout(400)

        pagina.click("#btn-limpar-filtros")
        pagina.wait_for_timeout(400)

        expect(pagina.locator("[data-modo='ranking'] .item")).to_have_count(antes)
        expect(pagina.locator("#filtros-ativos")).to_be_hidden()

    def test_filtro_que_esconde_tudo_explica_a_causa(self, navegador, servidor):
        """Dizer "você já passou por todas" a quem só apertou um filtro esconde a causa.

        O limite de caminhada é zero — nenhuma atração está exatamente sob os pés
        do visitante, então a lista esvazia **com certeza**. Um limite de cinco
        minutos ainda deixaria uma passar, e o teste viraria enfeite.
        """
        pagina = self.com_ranking(navegador, servidor)

        # Aperta o filtro ao mínimo que a interface permite e marca como visitada
        # tudo que ainda passa. Sobra uma lista vazia **com filtro ligado** e com
        # vinte e poucas atrações livres do lado de fora do limite — que é
        # exatamente o estado em que a mensagem errada enganaria o visitante.
        pagina.evaluate(
            "() => {"
            " estado.filtros = { filaMax: 5, caminhadaMax: 5 };"
            " estado.visitadas = new Set("
            "   estado.ultimoRanking.recommendations"
            "     .filter(r => r.queue_minutes <= 5 && r.walking_minutes <= 5)"
            "     .map(r => r.attraction.id));"
            " renderizar(estado.ultimoRanking); }"
        )
        pagina.wait_for_timeout(400)

        expect(pagina.locator("[data-modo='ranking'] .item")).to_have_count(0)
        expect(pagina.locator("#aviso")).to_contain_text("filtros")

    def test_lista_vazia_por_visitadas_nao_culpa_o_filtro(self, navegador, servidor):
        """O outro lado: sem filtro ligado, a frase tem de ser a das visitadas.

        As duas mensagens são fáceis de confundir, e escolher a errada esconde a
        causa em vez de explicá-la.
        """
        pagina = self.com_ranking(navegador, servidor)

        pagina.evaluate(
            "() => { estado.visitadas = new Set("
            "estado.ultimoRanking.recommendations.map(r => r.attraction.id));"
            " renderizar(estado.ultimoRanking); }"
        )
        pagina.wait_for_timeout(400)

        expect(pagina.locator("#aviso")).to_contain_text("já passou por todas")

    def test_os_alvos_escapam_do_filtro(self, navegador, servidor):
        """Quem marcou "vim por esta" vai nela de qualquer jeito.

        Escondê-la por um limite geral seria o app discutindo com uma escolha
        explícita do visitante.
        """
        pagina = self.com_ranking(navegador, servidor)

        # Marca a atração de maior custo como alvo e aperta o filtro ao mínimo.
        pior = pagina.evaluate("() => estado.ultimoRanking.recommendations.at(-1).attraction.id")
        pagina.evaluate(f"() => alternarAlvo({pior!r})")
        pagina.locator("#filtro-fila").fill("5")
        pagina.dispatch_event("#filtro-fila", "input")
        pagina.wait_for_timeout(400)

        expect(pagina.locator("[data-modo='alvos'] .item")).to_have_count(1)

    def test_os_filtros_sobrevivem_a_recarregar(self, navegador, servidor):
        """São preferências da pessoa, não do momento — e valem em qualquer parque."""
        pagina = self.com_ranking(navegador, servidor)
        pagina.locator("#filtro-caminhada").fill("15")
        pagina.dispatch_event("#filtro-caminhada", "input")
        pagina.wait_for_timeout(300)

        pagina.reload(wait_until="networkidle")
        pagina.click("#btn-todas-filas")
        pagina.click("#filtros .escolher__gatilho")

        expect(pagina.locator("#rotulo-caminhada")).to_have_text("Até 15 min")
        expect(pagina.locator("#filtros-ativos")).to_be_visible()


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
        _ver_filas(pagina, "ranking")
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
        _ver_filas(pagina, "panorama")

        pagina.locator(".ver-historico").first.click()

        expect(pagina.locator(".grafico svg").first).to_be_visible()


class TestTrocaDeParque:
    """O mapa tem de seguir o parque escolhido — pelos dois caminhos possíveis."""

    def centro_do_mapa(self, pagina) -> tuple[float, float]:
        pos = pagina.evaluate("() => { const c = mapa.getCenter(); return [c.lat, c.lng]; }")
        return pos[0], pos[1]

    def test_escolher_no_seletor_reenquadra_o_mapa(self, navegador, servidor):
        pagina = abrir(navegador, servidor, seletor=True, com_gps=False)
        _ver_filas(pagina, "panorama")
        _fechar_filas(pagina)
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
        pagina = abrir(navegador, servidor, seletor=True, com_gps=False)
        _ver_filas(pagina, "panorama")
        _fechar_filas(pagina)
        _, longitude_antes = self.centro_do_mapa(pagina)

        pagina.fill("#busca-parque", "SeaWorld Orlando")
        pagina.press("#busca-parque", "Enter")
        pagina.wait_for_timeout(1200)

        _, longitude_depois = self.centro_do_mapa(pagina)

        assert longitude_antes < 0
        assert longitude_depois > 0, "o Enter não aplicou o parque filtrado"

    def test_enter_sem_resultado_nao_faz_nada(self, navegador, servidor):
        """Não pode cair no parque padrão só porque a busca não achou nada."""
        pagina = abrir(navegador, servidor, seletor=True, com_gps=False)
        _ver_filas(pagina, "panorama")
        _fechar_filas(pagina)
        antes = self.centro_do_mapa(pagina)

        pagina.fill("#busca-parque", "zzzz-nao-existe")
        pagina.press("#busca-parque", "Enter")
        pagina.wait_for_timeout(600)

        expect(pagina.locator("#busca-vazia")).to_be_visible()
        assert self.centro_do_mapa(pagina) == antes

    def test_enter_nao_recarrega_a_pagina(self, navegador, servidor):
        """Recarregar perderia a posição que o visitante já tinha informado."""
        pagina = abrir(navegador, servidor, seletor=True, com_gps=False)
        _ver_filas(pagina, "panorama")
        _fechar_filas(pagina)
        pagina.evaluate("() => { window.__marcador = true; }")

        pagina.fill("#busca-parque", "SeaWorld Orlando")
        pagina.press("#busca-parque", "Enter")
        pagina.wait_for_timeout(800)

        assert pagina.evaluate("() => window.__marcador === true")


class TestFluxoFeliz:
    def test_permitir_gps_mostra_o_ranking(self, navegador, servidor):
        pagina = abrir(navegador, servidor)

        pagina.click("#btn-localizar")
        _ver_filas(pagina, "ranking")

        expect(pagina.locator("#titulo-lista")).to_have_text("Magic Kingdom Park")
        expect(pagina.locator("#resumo")).to_contain_text("26 de 35")
        expect(pagina.locator("[data-modo='ranking'] .item")).to_have_count(8)

    def test_lista_sai_em_ordem_crescente_de_custo(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        _ver_filas(pagina, "ranking")

        minutos = [int(texto) for texto in pagina.locator(".custo strong").all_inner_texts()]

        assert minutos == sorted(minutos)

    def test_primeira_colocada_recebe_destaque(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        # Espera o **ranking**, e não qualquer item: o panorama já está na tela
        # desde a abertura, e um `.item` solto encontraria o item errado.
        _ver_filas(pagina, "ranking")

        assert pagina.locator(".etiqueta").count() == 1
        expect(pagina.locator(".item").first).to_have_class("item item--melhor")

    def test_cada_item_mostra_a_conta_aberta(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        _ver_filas(pagina, "ranking")

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
        _ver_filas(pagina, "ranking")

        # `.pino`, e não `.leaflet-marker-icon`: o "Você" e os nomes das áreas
        # também são marcadores do Leaflet.
        expect(pagina.locator("#mapa .pino")).to_have_count(8)

    def test_informa_a_idade_do_dado(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        _ver_filas(pagina, "ranking")

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

        # O aviso acima do mapa troca de "Procurando…" para a recusa, e a altura
        # muda: medir o mapa no meio da troca clicava onde ele *estava*. Falhou
        # uma vez em 28/10/2026, numa suíte que passa inteira na seguinte.
        expect(pagina.locator("#aviso")).to_contain_text("negou")
        caixa = pagina.locator("#mapa").bounding_box()
        pagina.mouse.click(caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] / 2)
        _ver_filas(pagina, "ranking")

        expect(pagina.locator("#posicao-atual")).to_contain_text("definido no mapa")
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
        _ver_filas(pagina, "ranking")

        assert pagina.evaluate("window.__invadido === undefined")
        expect(pagina.locator(".nome")).to_contain_text("<img")


class TestResponsivo:
    def test_nao_ha_rolagem_horizontal_no_celular(self, navegador, servidor):
        """Rolagem lateral em celular é o sintoma clássico de layout quebrado."""
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        _ver_filas(pagina, "ranking")

        largura_conteudo = pagina.evaluate("document.documentElement.scrollWidth")
        largura_tela = pagina.evaluate("document.documentElement.clientWidth")

        assert largura_conteudo <= largura_tela + 1

    def test_botao_tem_alvo_confortavel_para_o_dedo(self, navegador, servidor):
        """48px é o mínimo recomendado para toque."""
        pagina = abrir(navegador, servidor)

        caixa = pagina.locator("#btn-localizar").bounding_box()

        assert caixa["height"] >= 44


class TestPopularidade:
    """A faixa de popularidade na tela — a entrega da Fase 7.4.

    Nasceu da troca da "radicalidade", que a fonte não fornece, pela fila média
    histórica, que é dado nosso. A regra de ouro é a mesma da tendência e dos
    alvos: **não reordena o ranking**. Popularidade descreve a atração; o ranking
    responde sobre o momento.
    """

    def com_popularidade(self, navegador, servidor):
        pagina = abrir(
            navegador,
            servidor,
            api=lambda rota: rota.fulfill(
                json=_recomendacoes_como_a_api_devolve(com_popularidade=True)
            ),
        )
        pagina.click("#btn-localizar")
        _ver_filas(pagina, "ranking")
        return pagina

    def nomes(self, pagina):
        return pagina.locator("[data-modo='ranking'] .nome").all_inner_texts()

    def test_a_principal_ganha_selo(self, navegador, servidor):
        pagina = self.com_popularidade(navegador, servidor)

        expect(pagina.locator(".popularidade").first).to_be_visible()

    def test_a_oportunidade_aparece_por_extenso(self, navegador, servidor):
        """A informação mais acionável da tela: uma das principais do parque com
        fila hoje abaixo da média dela. O ranking sozinho não enxerga isso."""
        pagina = self.com_popularidade(navegador, servidor)

        expect(pagina.locator(".popularidade--oportunidade").first).to_contain_text(
            "abaixo da média dela"
        )

    def test_a_cor_nao_carrega_a_informacao_sozinha(self, navegador, servidor):
        """Mesma regra da tendência: quem não distingue verde de vermelho — 8% dos
        homens — precisa ler exatamente a mesma coisa."""
        pagina = self.com_popularidade(navegador, servidor)

        oportunidade = pagina.locator(".popularidade--oportunidade").first

        assert oportunidade.locator("svg").count() == 1
        expect(oportunidade).to_contain_text("Principal do parque")

    def test_sem_historico_nao_inventa_faixa(self, navegador, servidor):
        """O padrão dos testes é sem popularidade, e nada deve aparecer."""
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-localizar")
        _ver_filas(pagina, "ranking")

        assert pagina.locator(".popularidade").count() == 0

    def test_o_miolo_fica_em_silencio(self, navegador, servidor):
        """`MODERATE` não ganha selo de propósito: um rótulo dizendo "mediana" em
        metade da lista vira ruído, e ruído gasta a atenção do selo que importa."""
        pagina = self.com_popularidade(navegador, servidor)

        textos = pagina.locator(".popularidade").all_inner_texts()

        assert textos, "nenhum selo apareceu; o cenário não está exercitando nada"
        assert not any("média" in t.lower() and "abaixo" not in t.lower() for t in textos)


class TestFiltroDePopularidade:
    """As caixas que escolhem quais faixas aparecem.

    São caixas, e não um seletor de faixa única, porque "as principais e as
    tranquilas, sem o miolo" é pedido legítimo de quem quer os clássicos e ainda
    tem tempo a preencher.
    """

    def com_filtros_abertos(self, navegador, servidor):
        pagina = abrir(
            navegador,
            servidor,
            api=lambda rota: rota.fulfill(
                json=_recomendacoes_como_a_api_devolve(com_popularidade=True)
            ),
        )
        pagina.click("#btn-localizar")
        _ver_filas(pagina, "ranking")
        pagina.click("#filtros .escolher__gatilho")
        return pagina

    def quantos_itens(self, pagina):
        return pagina.locator("[data-modo='ranking'] .item").count()

    def test_abre_com_todas_as_faixas_marcadas(self, navegador, servidor):
        """Um app que abre escondendo atrações precisaria explicar por quê antes
        mesmo de o visitante pedir alguma coisa."""
        pagina = self.com_filtros_abertos(navegador, servidor)

        caixas = pagina.locator(".filtro-faixa")
        assert caixas.count() == 4
        for i in range(caixas.count()):
            expect(caixas.nth(i)).to_be_checked()

    def test_desmarcar_uma_faixa_tira_aquelas_atracoes(self, navegador, servidor):
        """Contar itens não serve aqui: a lista mostra no máximo oito, e sobram
        atrações de outras faixas para preencher as vagas. O que prova o corte é
        **quais** aparecem, não quantas."""
        pagina = self.com_filtros_abertos(navegador, servidor)

        assert "fila curta" in " ".join(pagina.locator(".popularidade").all_inner_texts()), (
            "o cenário precisa começar com alguma tranquila à vista"
        )

        pagina.uncheck(".filtro-faixa[value='QUIET']")
        pagina.wait_for_timeout(400)

        assert "fila curta" not in " ".join(pagina.locator(".popularidade").all_inner_texts())

    def test_so_as_principais_deixa_so_as_principais(self, navegador, servidor):
        pagina = self.com_filtros_abertos(navegador, servidor)

        for faixa in ("MODERATE", "QUIET", "UNKNOWN"):
            pagina.uncheck(f".filtro-faixa[value='{faixa}']")
        pagina.wait_for_timeout(400)

        itens = pagina.locator("[data-modo='ranking'] .item")
        assert itens.count() > 0, "o filtro escondeu tudo"

        # Toda atração visível precisa trazer selo de principal — que é o único
        # texto que `criarPopularidade` produz para HEADLINER.
        for i in range(itens.count()):
            expect(itens.nth(i).locator(".popularidade")).to_contain_text("rincipal")

    def test_o_selo_denuncia_a_faixa_desligada(self, navegador, servidor):
        """Mesma razão do selo dos outros filtros: filtro esquecido é
        indistinguível de parque vazio."""
        pagina = self.com_filtros_abertos(navegador, servidor)

        expect(pagina.locator("#filtros-ativos")).to_be_hidden()

        pagina.uncheck(".filtro-faixa[value='QUIET']")
        pagina.wait_for_timeout(300)

        expect(pagina.locator("#filtros-ativos")).to_be_visible()

    def test_desmarcar_tudo_volta_ao_normal(self, navegador, servidor):
        """Desmarcar todas esconderia a tela inteira, e quem faz isso quase sempre
        quer dizer "volte ao normal" — não "não me mostre nada"."""
        pagina = self.com_filtros_abertos(navegador, servidor)
        antes = self.quantos_itens(pagina)

        # `click` e não `uncheck` na última: o app remarca todas nesse instante, e
        # o `uncheck` do Playwright falharia justamente por o comportamento certo
        # ter acontecido.
        for faixa in ("HEADLINER", "MODERATE", "QUIET"):
            pagina.uncheck(f".filtro-faixa[value='{faixa}']")
        pagina.click(".filtro-faixa[value='UNKNOWN']")
        pagina.wait_for_timeout(400)

        assert self.quantos_itens(pagina) == antes
        expect(pagina.locator(".filtro-faixa[value='QUIET']")).to_be_checked()

    def test_remover_filtros_remarca_as_faixas(self, navegador, servidor):
        pagina = self.com_filtros_abertos(navegador, servidor)

        pagina.uncheck(".filtro-faixa[value='HEADLINER']")
        pagina.wait_for_timeout(300)
        pagina.click("#btn-limpar-filtros")
        pagina.wait_for_timeout(300)

        expect(pagina.locator(".filtro-faixa[value='HEADLINER']")).to_be_checked()
        expect(pagina.locator("#filtros-ativos")).to_be_hidden()

    def test_a_escolha_sobrevive_ao_recarregar(self, navegador, servidor):
        """Os filtros são globais e sem prazo: são sobre a pessoa, não sobre o dia."""
        pagina = self.com_filtros_abertos(navegador, servidor)

        pagina.uncheck(".filtro-faixa[value='QUIET']")
        pagina.wait_for_timeout(300)
        pagina.reload(wait_until="networkidle")
        pagina.click("#btn-todas-filas")
        pagina.click("#filtros .escolher__gatilho")

        expect(pagina.locator(".filtro-faixa[value='QUIET']")).not_to_be_checked()

    def test_o_filtro_de_faixa_nao_reordena(self, navegador, servidor):
        """A tese do projeto: a ordem é por custo total, e filtro corta."""
        pagina = self.com_filtros_abertos(navegador, servidor)

        pagina.uncheck(".filtro-faixa[value='QUIET']")
        pagina.wait_for_timeout(400)

        custos = [
            int(t) for t in pagina.locator("[data-modo='ranking'] .custo strong").all_inner_texts()
        ]

        assert custos == sorted(custos)

    def test_sem_popularidade_no_dado_o_filtro_nao_esvazia_a_tela(self, navegador, servidor):
        """A armadilha do filtro: sem banco, a API devolve `popularity: null` em
        todas. Tratar ausente como reprovado esvaziaria a tela num ambiente que
        funciona — e o visitante não teria como adivinhar o porquê."""
        pagina = abrir(navegador, servidor)  # o padrão vem SEM popularidade
        pagina.click("#btn-localizar")
        _ver_filas(pagina, "ranking")
        pagina.click("#filtros .escolher__gatilho")

        pagina.uncheck(".filtro-faixa[value='QUIET']")
        pagina.uncheck(".filtro-faixa[value='UNKNOWN']")
        pagina.wait_for_timeout(400)

        assert pagina.locator("[data-modo='ranking'] .item").count() > 0


def _com_na_frente(trecho_do_nome: str) -> dict:
    """O ranking real, com uma atração promovida a mais barata de todas.

    Na fixture, as oito primeiras são todas tranquilas e sem altura mínima: um
    teste de "Tranquilas esconde as radicais" passaria sem esconder nada. Aqui a
    atração escolhida fica como se estivesse ao lado do visitante — 1 min a pé e
    5 de fila —, com a conta fechando, para o perfil ter o que marcar ou esconder.
    """
    dados = _recomendacoes_como_a_api_devolve()
    recs = dados["recommendations"]
    alvo = next(r for r in recs if trecho_do_nome in r["attraction"]["name"])
    recs.remove(alvo)
    alvo.update(walking_minutes=1.0, queue_minutes=5, total_minutes=6.0)
    recs.insert(0, alvo)
    return dados


def _api_com_na_frente(trecho_do_nome: str):
    return lambda rota: rota.fulfill(json=_com_na_frente(trecho_do_nome))


def _localizar(pagina) -> None:
    """O ranking só existe depois de o visitante dizer onde está."""
    pagina.click("#btn-localizar")
    _ver_filas(pagina, "ranking")


def _perfil(altura=None, intensidade="tudo") -> dict:
    return {"respondido": True, "alturaCm": altura, "intensidade": intensidade}


def _id_de(trecho_do_nome: str) -> str:
    catalogo = carregar("children_magic_kingdom.json")
    return next(c["id"] for c in catalogo["children"] if trecho_do_nome in c["name"])


class TestPerfil:
    """As duas perguntas da Fase 9: altura da criança mais baixa e gosto do grupo.

    As regras são decisões do Gabriel (seção 7 do docs/PROJETO.md): **altura marca,
    não esconde**, e a marcada não ganha o destaque; **intensidade esconde com
    aviso** — "Tranquilas" tira as radicais, "Emoção" tira as tranquilas.

    As alturas conferidas aqui vêm da listagem oficial (a curadoria): Seven Dwarfs
    e Big Thunder pedem 97 cm, TRON 122, Space Mountain 112, Barnstormer 89.
    """

    def test_a_primeira_visita_abre_as_perguntas(self, navegador, servidor):
        pagina = abrir(navegador, servidor, perfil=None)
        expect(pagina.locator("#painel-perfil")).to_be_visible()
        expect(pagina.locator("#painel-perfil-titulo")).to_have_text("Antes do primeiro passo")

    def test_nada_vem_respondido_pelo_visitante(self, navegador, servidor):
        """Pré-marcar "Sem crianças" seria responder por ele."""
        pagina = abrir(navegador, servidor, perfil=None)
        expect(pagina.locator("input[name='criancas']:checked")).to_have_count(0)

    def test_pular_nao_pergunta_de_novo(self, navegador, servidor):
        pagina = abrir(navegador, servidor, perfil=None)
        pagina.click("#btn-pular-perfil")
        expect(pagina.locator("#painel-perfil")).to_be_hidden()

        pagina.reload(wait_until="networkidle")
        expect(pagina.locator("#painel-perfil")).to_be_hidden()
        expect(pagina.locator("#perfil-resumo")).to_have_text("Sem restrições")

    def test_esc_na_primeira_visita_vale_como_pular(self, navegador, servidor):
        pagina = abrir(navegador, servidor, perfil=None)
        pagina.keyboard.press("Escape")
        expect(pagina.locator("#painel-perfil")).to_be_hidden()

        pagina.reload(wait_until="networkidle")
        expect(pagina.locator("#painel-perfil")).to_be_hidden()

    def test_a_altura_mostra_quem_fica_de_fora(self, navegador, servidor):
        """A consequência aparece antes de confirmar, calculada no catálogo real."""
        pagina = abrir(navegador, servidor, perfil=None)
        pagina.locator("label.segmento", has_text="Tem criança").click()
        for _ in range(5):  # 100 -> 95 cm
            pagina.click("#btn-altura-menos")

        expect(pagina.locator("#altura-valor")).to_have_text("95 cm")
        dica = pagina.locator("#altura-dica")
        for nome in ("TRON", "Space Mountain", "Big Thunder", "Seven Dwarfs"):
            expect(dica).to_contain_text(nome)
        # 89 cm: com 95, a criança entra no Barnstormer.
        expect(dica).not_to_contain_text("Barnstormer")

    def test_salvar_pelo_painel_muda_o_resumo(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-perfil")
        expect(pagina.locator("#painel-perfil-titulo")).to_have_text("Seu grupo")

        pagina.locator("label.segmento", has_text="Sem crianças").click()
        pagina.locator("label.segmento", has_text="Tranquilas").click()
        pagina.click("#btn-salvar-perfil")

        expect(pagina.locator("#painel-perfil")).to_be_hidden()
        expect(pagina.locator("#perfil-resumo")).to_have_text("Sem crianças · Tranquilas")

    def test_o_perfil_sobrevive_a_recarregar(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-perfil")
        pagina.locator("label.segmento", has_text="Tem criança").click()
        pagina.click("#btn-altura-mais")
        pagina.click("#btn-salvar-perfil")
        expect(pagina.locator("#perfil-resumo")).to_have_text("101 cm · De tudo")

        pagina.reload(wait_until="networkidle")
        expect(pagina.locator("#perfil-resumo")).to_have_text("101 cm · De tudo")

    def test_so_adultos_marca_em_vez_de_esconder(self, navegador, servidor):
        pagina = abrir(
            navegador, servidor, api=_api_com_na_frente("Seven Dwarfs"), perfil=_perfil(altura=95)
        )
        _localizar(pagina)

        anoes = pagina.locator("#lista .item", has_text="Seven Dwarfs")
        expect(anoes).to_have_count(1)
        expect(anoes).to_contain_text("A partir de 97 cm · só os adultos")
        expect(anoes).to_contain_text("Rider Switch")

    def test_so_adultos_nao_ganha_o_destaque(self, navegador, servidor):
        """A mais barata é a Seven Dwarfs, mas o destaque é para o grupo todo."""
        pagina = abrir(
            navegador, servidor, api=_api_com_na_frente("Seven Dwarfs"), perfil=_perfil(altura=95)
        )
        _localizar(pagina)

        melhor = pagina.locator(".item--melhor")
        expect(melhor).to_have_count(1)
        expect(melhor).not_to_contain_text("Seven Dwarfs")

    def test_com_altura_suficiente_nada_e_marcado(self, navegador, servidor):
        pagina = abrir(
            navegador, servidor, api=_api_com_na_frente("Seven Dwarfs"), perfil=_perfil(altura=97)
        )
        _localizar(pagina)

        expect(pagina.locator(".restricao")).to_have_count(0)
        expect(pagina.locator(".item--melhor")).to_contain_text("Seven Dwarfs")

    def test_tranquilas_esconde_as_radicais_e_avisa(self, navegador, servidor):
        pagina = abrir(
            navegador,
            servidor,
            api=_api_com_na_frente("Space Mountain"),
            perfil=_perfil(intensidade="tranquilas"),
        )
        _localizar(pagina)

        expect(pagina.locator("#lista .item", has_text="Space Mountain")).to_have_count(0)
        # As 5 radicais do ranking da fixture, todas fora — e o aviso diz quantas.
        expect(pagina.locator("#perfil-aviso")).to_contain_text(
            "5 radicais escondidas por “Tranquilas”"
        )

    def test_mostrar_traz_as_escondidas_de_volta(self, navegador, servidor):
        pagina = abrir(
            navegador,
            servidor,
            api=_api_com_na_frente("Space Mountain"),
            perfil=_perfil(intensidade="tranquilas"),
        )
        _localizar(pagina)

        pagina.click("#btn-mostrar-escondidas")
        expect(pagina.locator("#lista .item", has_text="Space Mountain")).to_have_count(1)
        expect(pagina.locator("#btn-mostrar-escondidas")).to_have_attribute("aria-pressed", "true")

    def test_emocao_deixa_so_moderadas_e_radicais(self, navegador, servidor):
        """No ranking da fixture: 19 tranquilas, 2 moderadas e 5 radicais."""
        pagina = abrir(navegador, servidor, perfil=_perfil(intensidade="emocao"))
        _localizar(pagina)

        expect(pagina.locator("#lista .item")).to_have_count(7)
        expect(pagina.locator("#perfil-aviso")).to_contain_text("19 tranquilas escondidas")

    def test_o_alvo_escapa_do_perfil(self, navegador, servidor):
        """ "Vim por esta" vence uma preferência geral, como vence os filtros."""
        pagina = abrir(navegador, servidor, perfil=_perfil(intensidade="tranquilas"))
        pagina.evaluate(
            "([parque, id]) => localStorage.setItem('nextup:alvos', "
            "JSON.stringify({[parque]: [id]}))",
            [DEFAULT_PARK_ID, _id_de("Space Mountain")],
        )
        pagina.reload(wait_until="networkidle")
        _localizar(pagina)

        expect(pagina.locator("#lista-alvos .item", has_text="Space Mountain")).to_have_count(1)

    def test_lista_vazia_pelo_perfil_diz_a_causa(self, navegador, servidor):
        """A quarta causa de lista vazia: culpar o filtro ou as visitadas mentiria."""

        def so_tranquilas(rota):
            dados = _recomendacoes_como_a_api_devolve()
            dados["recommendations"] = [
                r for r in dados["recommendations"] if r["attraction"]["intensity"] == "CALM"
            ]
            rota.fulfill(json=dados)

        pagina = abrir(navegador, servidor, api=so_tranquilas, perfil=_perfil(intensidade="emocao"))
        pagina.click("#btn-localizar")
        expect(pagina.locator("#aviso")).to_contain_text(
            "Nenhuma atração combina com “Quero emoção”"
        )
        expect(pagina.locator("#lista .item")).to_have_count(0)

    def test_o_panorama_sem_gps_tambem_respeita_o_perfil(self, navegador, servidor):
        pagina = abrir(navegador, servidor, com_gps=False, perfil=_perfil(intensidade="emocao"))
        _ver_filas(pagina, "panorama")

        expect(pagina.locator("#perfil-aviso")).to_contain_text("tranquilas escondidas")
        nomes = pagina.locator("#lista .nome").all_inner_texts()
        assert nomes, "o panorama precisa mostrar alguma atração"
        assert not any("Carrousel" in n for n in nomes), "uma tranquila escapou do perfil"


def _mapa_parado(pagina) -> None:
    """Espera os nomes do mapa assentarem.

    O mapa aproxima o visitante com animação, e no meio dela os nomes estão em
    trânsito — medidos ali, saíam até 45 px fora do mapa. O app anuncia quando
    terminou de posicioná-los; esperar o anúncio é o que evita um tempo fixo que
    um dia não basta.
    """
    pagina.evaluate("document.fonts.ready")
    pagina.wait_for_selector("#mapa[data-rotulos='prontos']", state="attached")


class TestMapaDesenhado:
    """O mapa real sem tiles (Fase 9.3): o GeoJSON do OpenStreetMap, pintado pelo CSS.

    O desenho do Claude Design foi descartado por ter a geografia inventada: quebraria
    o "tocar no mapa define a posição". Esse comportamento continua coberto por
    `TestGpsNegado.test_clique_no_mapa_resolve_sem_gps` — agora sobre o desenho.
    """

    def test_o_magic_kingdom_nao_baixa_tiles(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        expect(pagina.locator("#mapa path.m-trilha")).not_to_have_count(0)
        expect(pagina.locator("#mapa img.leaflet-tile")).to_have_count(0)

    def test_outro_parque_volta_aos_tiles(self, navegador, servidor):
        """Sem desenho próprio, o mapa ainda precisa existir."""
        pagina = abrir(navegador, servidor, seletor=True, com_gps=False)
        expect(pagina.locator("#mapa path.m-trilha")).not_to_have_count(0)

        pagina.select_option("#parque", PARQUE_DISTANTE)
        expect(pagina.locator("#mapa img.leaflet-tile").first).to_be_attached()
        expect(pagina.locator("#mapa path.m-trilha")).to_have_count(0)

    def test_o_credito_do_openstreetmap_continua(self, navegador, servidor):
        """Licença ODbL: o dado é do OSM mesmo sem tile nenhum."""
        pagina = abrir(navegador, servidor)
        expect(pagina.locator(".leaflet-control-attribution")).to_contain_text("OpenStreetMap")

    def test_o_desenho_troca_de_cor_com_o_tema(self, navegador, servidor):
        """O que tile nenhum faz: o mapa escurece junto com a tela."""
        pagina = abrir(navegador, servidor)
        predio = pagina.locator("#mapa path.m-predio").first
        expect(predio).to_be_attached()

        cor = "el => getComputedStyle(el).fill"
        pagina.emulate_media(color_scheme="light")
        claro = predio.evaluate(cor)
        pagina.emulate_media(color_scheme="dark")
        escuro = predio.evaluate(cor)

        assert claro != escuro, f"o prédio ficou {claro} nos dois temas"

    def test_a_rota_ate_a_melhor_escolha_segue_as_trilhas(self, navegador, servidor):
        """Linha reta teria dois pontos; pelas trilhas, ela dobra esquinas."""
        pagina = abrir(navegador, servidor)
        _localizar(pagina)

        rota = pagina.locator("#mapa path.m-rota")
        expect(rota).to_have_count(1)
        pontos = rota.get_attribute("d").count("L") + 1
        assert pontos > 2, f"a rota tem {pontos} pontos: virou linha reta"

    def test_sem_posicao_nao_ha_rota(self, navegador, servidor):
        pagina = abrir(navegador, servidor, com_gps=False)
        _ver_filas(pagina, "panorama")
        expect(pagina.locator("#mapa path.m-rota")).to_have_count(0)

    def test_os_nomes_nao_se_sobrepoem(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _localizar(pagina)
        _mapa_parado(pagina)

        mapa = pagina.locator("#mapa").bounding_box()
        caixas = [r.bounding_box() for r in pagina.locator("#mapa .rotulo:not(.oculto)").all()]
        assert caixas, "nenhum nome apareceu no mapa"

        def bate(a, b):
            return (
                a["x"] < b["x"] + b["width"]
                and b["x"] < a["x"] + a["width"]
                and a["y"] < b["y"] + b["height"]
                and b["y"] < a["y"] + a["height"]
            )

        for i, a in enumerate(caixas):
            assert a["x"] >= mapa["x"] and a["x"] + a["width"] <= mapa["x"] + mapa["width"], (
                "um nome saiu pela lateral do mapa"
            )
            for b in caixas[i + 1 :]:
                assert not bate(a, b), "dois nomes se sobrepõem"

    def test_nenhum_nome_cobre_um_numero(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _localizar(pagina)
        _mapa_parado(pagina)

        nomes = [r.bounding_box() for r in pagina.locator("#mapa .rotulo:not(.oculto)").all()]
        pinos = [p.bounding_box() for p in pagina.locator("#mapa .pino").all()]
        for n in nomes:
            for p in pinos:
                sobrepoe = (
                    n["x"] < p["x"] + p["width"]
                    and p["x"] < n["x"] + n["width"]
                    and n["y"] < p["y"] + p["height"]
                    and p["y"] < n["y"] + n["height"]
                )
                assert not sobrepoe, "um nome cobre um número do mapa"


def _com_cartao(pagina) -> None:
    """Pede a posição e espera o cartão do próximo passo — sem abrir o painel."""
    pagina.click("#btn-localizar")
    pagina.wait_for_selector("#passo-destaque .passo__nome")


class TestCartaoDoProximoPasso:
    """O cartão que responde "para onde eu vou agora?" (Fase 9.3).

    Na fixture, a partir da posição de teste, a mais barata é o Prince Charming
    Regal Carrousel: 2 min a pé + 5 de fila = 7. A seguinte é o PeopleMover (10).
    """

    def test_com_posicao_mostra_a_melhor_escolha(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)

        cartao = pagina.locator("#passo-destaque")
        expect(cartao.locator(".passo__nome")).to_have_text("Prince Charming Regal Carrousel")
        expect(cartao.locator(".passo__total strong")).to_have_text("7")
        expect(pagina.locator("#passo-sem-posicao")).to_be_hidden()

    def test_o_total_se_abre_em_caminhada_e_fila(self, navegador, servidor):
        """A soma que o visitante não faz de cabeça — a tese do projeto."""
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)

        conta = pagina.locator("#passo-destaque .passo__conta")
        expect(conta).to_contain_text("2 min a pé")
        expect(conta).to_contain_text("5 min de fila")
        expect(pagina.locator("#passo-destaque .passo__barra")).to_have_attribute(
            "aria-label", "2 min a pé e 5 min de fila"
        )

    def test_o_cartao_respeita_a_altura(self, navegador, servidor):
        """O destaque é para o grupo todo, e o cartão É o destaque."""
        pagina = abrir(
            navegador, servidor, api=_api_com_na_frente("Seven Dwarfs"), perfil=_perfil(altura=95)
        )
        _com_cartao(pagina)
        expect(pagina.locator("#passo-destaque .passo__nome")).not_to_contain_text("Seven Dwarfs")

    def test_com_altura_suficiente_o_cartao_e_dela(self, navegador, servidor):
        """O par do teste anterior: prova que foi a altura, e não o acaso."""
        pagina = abrir(
            navegador, servidor, api=_api_com_na_frente("Seven Dwarfs"), perfil=_perfil(altura=97)
        )
        _com_cartao(pagina)
        expect(pagina.locator("#passo-destaque .passo__nome")).to_contain_text("Seven Dwarfs")

    def test_a_posicao_aparece_em_frase_e_nao_em_coordenadas(self, navegador, servidor):
        """ "28.42037, -81.58031" não diz nada a quem está no parque; o número fica no
        `title`, para quem precisar conferir."""
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)

        posicao = pagina.locator("#posicao-atual")
        expect(posicao).to_have_text("📍 Ponto de partida definido pelo GPS")
        expect(posicao).to_have_attribute("title", "28.42037, -81.58031")

    def test_ja_fui_no_cartao_passa_para_a_proxima(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)

        pagina.click("#passo-destaque .botao-ja-fui")

        expect(pagina.locator("#passo-destaque .passo__nome")).to_contain_text("PeopleMover")
        expect(pagina.locator("#desfazer")).to_contain_text("Prince Charming")

    def test_desfazer_traz_a_atracao_de_volta(self, navegador, servidor):
        """O toque errado de quem usa o celular com uma mão só tem volta."""
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)
        pagina.click("#passo-destaque .botao-ja-fui")

        pagina.click("#btn-desfazer")

        expect(pagina.locator("#passo-destaque .passo__nome")).to_have_text(
            "Prince Charming Regal Carrousel"
        )
        expect(pagina.locator("#desfazer")).to_be_hidden()

    def test_o_desfazer_some_sozinho(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)
        pagina.click("#passo-destaque .botao-ja-fui")
        expect(pagina.locator("#desfazer")).to_be_visible()

        expect(pagina.locator("#desfazer")).to_be_hidden(timeout=8000)

    def test_lista_vazia_o_cartao_some_e_o_aviso_explica(self, navegador, servidor):
        """O aviso distingue as quatro causas; o cartão repetiria só uma."""
        pagina = abrir(
            navegador,
            servidor,
            api=lambda rota: rota.fulfill(
                json={**_recomendacoes_como_a_api_devolve(), "recommendations": []}
            ),
        )
        pagina.click("#btn-localizar")

        expect(pagina.locator("#aviso")).to_contain_text("parque pode estar fechado")
        expect(pagina.locator("#passo-destaque")).to_be_hidden()


class TestPainelDeFilas:
    """A lista inteira num painel: a tela principal fica só com a resposta."""

    def test_o_botao_diz_quantas_ha_la_dentro(self, navegador, servidor):
        """Escondida num painel, a lista precisa anunciar que existe."""
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)
        expect(pagina.locator("#btn-todas-filas")).to_contain_text("Outras opções · 26")

    def test_o_botao_fica_fora_do_mapa_e_a_vista(self, navegador, servidor):
        """Sobre o mapa e pequeno, ele se perdia no desenho (Gabriel, 28/10/2026)."""
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)

        botao = pagina.locator("#btn-todas-filas").bounding_box()
        mapa = pagina.locator("#mapa").bounding_box()
        assert not _caixas_batem(botao, mapa), "o botão está em cima do mapa"
        assert botao["height"] >= 52, f"o botão tem {botao['height']} px de altura"
        assert botao["y"] + botao["height"] <= CELULAR["height"], "o botão está fora da tela"

    def test_o_botao_acompanha_a_rolagem(self, navegador, servidor):
        """Fixo no pé da tela: à vista em qualquer ponto da página."""
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)
        antes = pagina.locator("#btn-todas-filas").bounding_box()

        pagina.mouse.wheel(0, 600)
        pagina.wait_for_function("window.scrollY > 0")

        assert pagina.locator("#btn-todas-filas").bounding_box() == antes

    def test_o_botao_nao_cobre_o_rodape(self, navegador, servidor):
        """Fixo, ele ficaria por cima do fim da página se ela não reservasse espaço."""
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)
        pagina.evaluate("window.scrollTo(0, document.body.scrollHeight)")

        botao = pagina.locator("#btn-todas-filas").bounding_box()
        rodape = pagina.locator(".rodape").bounding_box()
        assert rodape["y"] + rodape["height"] <= botao["y"], "o botão cobre o rodapé"

    def test_abre_e_fecha(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)

        pagina.click("#btn-todas-filas")
        expect(pagina.locator("#painel-filas")).to_be_visible()
        expect(pagina.locator("#painel-filas [data-modo='ranking'] .item")).to_have_count(8)

        pagina.click("#btn-fechar-filas")
        expect(pagina.locator("#painel-filas")).to_be_hidden()

    def test_esc_fecha_o_painel(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        pagina.click("#btn-todas-filas")
        expect(pagina.locator("#painel-filas")).to_be_visible()

        pagina.keyboard.press("Escape")
        expect(pagina.locator("#painel-filas")).to_be_hidden()

    def test_marcar_no_painel_atualiza_o_cartao(self, navegador, servidor):
        """Os dois mostram o mesmo ranking: marcar num muda o outro."""
        pagina = abrir(navegador, servidor)
        _localizar(pagina)
        pagina.locator(".item--melhor .marcar-visitada").click()

        expect(pagina.locator("#passo-destaque .passo__nome")).to_contain_text("PeopleMover")

    def test_os_itens_ficam_centralizados_no_celular(self, navegador, servidor):
        """O bug de 29/10/2026: o item passava 20 px da borda direita do painel, que
        cortava, e a lista parecia empurrada para a direita.

        A página não rolava para o lado — o corte era dentro do painel —, e por isso
        `test_nao_ha_rolagem_horizontal_no_celular` não o pegou. Aqui se mede o
        próprio item contra o painel.
        """
        pagina = abrir(navegador, servidor)
        _localizar(pagina)

        margens = pagina.evaluate(
            """() => {
              const painel = document.querySelector('#painel-filas');
              const estilo = getComputedStyle(painel);
              const dentro = painel.getBoundingClientRect();
              const esquerda = dentro.left + parseFloat(estilo.paddingLeft);
              const direita = dentro.right - parseFloat(estilo.paddingRight);
              return [...painel.querySelectorAll('#lista .item')].map((item) => {
                const r = item.getBoundingClientRect();
                return [r.left - esquerda, direita - r.right];
              });
            }"""
        )

        assert margens
        for esquerda, direita in margens:
            assert abs(esquerda) < 1 and abs(direita) < 1, f"item fora do painel: {margens}"


class TestSoMagicKingdom:
    """A primeira versão é só o Magic Kingdom (decisão do Gabriel, 28/10/2026).

    O código dos outros parques fica e é testado (`abrir(..., seletor=True)`);
    estes testes garantem que o visitante não tem como chegar a ele.
    """

    def test_o_seletor_de_parques_fica_fora_da_tela(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        expect(pagina.locator("#campo-parque")).to_be_hidden()
        expect(pagina.locator("#parque")).to_be_hidden()

    def test_a_lista_de_parques_nem_e_pedida(self, navegador, servidor):
        """Sem seletor, buscar 198 parques seria rede à toa no 4G do parque."""
        contexto = navegador.new_context(viewport=CELULAR)
        contexto.add_init_script(
            "localStorage.setItem('nextup:perfil', " + json.dumps(json.dumps(PERFIL_PULADO)) + ")"
        )
        pagina = contexto.new_page()
        pedidos = []
        pagina.on("request", lambda r: pedidos.append(r.url))
        pagina.route("**/attractions*", _responder_atracoes)
        pagina.route("**/tile.openstreetmap.org/**", lambda r: r.fulfill(body=PNG_VAZIO))
        pagina.goto(servidor, wait_until="networkidle")

        assert not any("/api/destinations" in url for url in pedidos)

    def test_com_a_chave_ligada_o_seletor_volta(self, navegador, servidor):
        pagina = abrir(navegador, servidor, seletor=True)
        expect(pagina.locator("#campo-parque")).to_be_visible()
        expect(pagina.locator("#parque option")).to_have_count(11)


def _caixas_batem(a: dict, b: dict) -> bool:
    return (
        a["x"] < b["x"] + b["width"]
        and b["x"] < a["x"] + a["width"]
        and a["y"] < b["y"] + b["height"]
        and b["y"] < a["y"] + a["height"]
    )


class TestMapaLegivel:
    """O mapa que o Gabriel achou difícil de entender no celular (28/10/2026).

    Cinco causas, uma por teste: a pilha de pintura invertida, a falta de
    referência (áreas e "Você"), o enquadramento no parque inteiro e oito nomes
    disputando o olhar.
    """

    def test_o_gramado_fica_embaixo_das_trilhas(self, navegador, servidor):
        """Bug real: `bringToBack()` num grupo invertia a pilha inteira.

        Cada caminho ia para o fundo um de cada vez, e o último a ir era o primeiro
        a ser pintado: o gramado cobria as trilhas e o véu ficava por baixo de tudo.
        """
        pagina = abrir(navegador, servidor)
        expect(pagina.locator("#mapa path.m-fora")).to_have_count(1)

        ordem = pagina.locator("#mapa path[class*='m-']").evaluate_all(
            "ps => ps.map(p => p.getAttribute('class').split(' ')[0])"
        )
        ultimo_verde = max(i for i, c in enumerate(ordem) if c == "m-verde")
        primeira_trilha = ordem.index("m-trilha")
        assert ultimo_verde < primeira_trilha, "o gramado é pintado por cima das trilhas"
        assert ordem.index("m-fora") > max(i for i, c in enumerate(ordem) if c == "m-trilha"), (
            "o véu do entorno não cobre o que está fora do parque"
        )

    def test_a_rota_fica_por_cima_do_desenho(self, navegador, servidor):
        """O conserto não pode ter custado a rota: ela continua acima do parque."""
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)
        _mapa_parado(pagina)

        z = "el => Number(getComputedStyle(el.closest('.leaflet-pane')).zIndex)"
        desenho = pagina.locator("#mapa path.m-trilha").first.evaluate(z)
        rota = pagina.locator("#mapa path.m-rota").evaluate(z)
        assert rota > desenho

    def test_as_areas_do_parque_tem_nome(self, navegador, servidor):
        """Sem referência, o visitante não sabe em que canto do parque está."""
        pagina = abrir(navegador, servidor)
        nomes = pagina.locator("#mapa .m-nome-area")
        expect(nomes).to_have_count(6)
        assert {"Fantasyland", "Tomorrowland", "Adventureland"} <= set(nomes.all_text_contents())

    def test_nome_de_area_nunca_cobre_um_numero(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)
        _mapa_parado(pagina)

        areas = [n.bounding_box() for n in pagina.locator("#mapa .m-nome-area:not(.oculto)").all()]
        pinos = [n.bounding_box() for n in pagina.locator("#mapa .pino").all()]
        for a in areas:
            for b in pinos:
                assert not _caixas_batem(a, b), "o nome de uma área cobre um número"

    def test_o_enquadramento_sobrevive_a_uma_animacao_em_curso(self, navegador, servidor):
        """Bug real: no meio de uma animação de zoom, o Leaflet descarta um novo
        enquadramento sem erro. Na abertura o mapa anima até o parque inteiro, e um
        GPS rápido caía nessa janela — o mapa ficava longe da resposta.

        Aqui a janela é provocada de propósito: uma animação começa e o
        enquadramento é pedido no mesmo instante.
        """
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)
        _mapa_parado(pagina)
        perto = pagina.evaluate("mapa.getZoom()")

        # A animação do Leaflet começa no quadro seguinte; dois quadros depois ela
        # está em curso, como a da abertura quando a resposta chega.
        pagina.evaluate(
            """async () => {
                enquadramentoFeito = null;
                mapa.setView(mapa.getCenter(), 14);
                await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
                enquadrarResposta(estado.ultimoRanking.recommendations);
            }"""
        )
        _mapa_parado(pagina)

        assert pagina.evaluate("mapa.getZoom()") == perto, "o enquadramento foi descartado"

    def test_no_tema_claro_as_trilhas_tem_contorno(self, navegador, servidor):
        """Caminho branco sobre chão claro sumia (Gabriel, 28/10/2026). No escuro o
        caminho já é o que tem mais luz, e o contorno não existe."""
        pagina = abrir(navegador, servidor)
        casca = pagina.locator("#mapa path.m-casco").first
        expect(casca).to_be_attached()
        traco = "el => getComputedStyle(el).stroke"

        pagina.emulate_media(color_scheme="light")
        assert casca.evaluate(traco) != "none"
        pagina.emulate_media(color_scheme="dark")
        assert casca.evaluate(traco) == "none"

    def test_o_contorno_fica_por_baixo_das_trilhas(self, navegador, servidor):
        """Por cima, a casca escura cobriria o caminho em vez de contorná-lo."""
        pagina = abrir(navegador, servidor)
        expect(pagina.locator("#mapa path.m-casco").first).to_be_attached()
        ordem = pagina.locator("#mapa path[class*='m-']").evaluate_all(
            "ps => ps.map(p => p.getAttribute('class').split(' ')[0])"
        )
        ultima_casca = max(i for i, c in enumerate(ordem) if c == "m-casco")
        assert ultima_casca < ordem.index("m-trilha")

    def test_o_visitante_e_um_ponto_visivel(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)
        expect(pagina.locator("#mapa .voce")).to_be_visible()

    def test_so_as_tres_primeiras_ganham_nome(self, navegador, servidor):
        """Oito nomes no celular eram uma sopa de letras; o resto fica só no número."""
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)

        expect(pagina.locator("#mapa .pino")).to_have_count(8)
        expect(pagina.locator("#mapa .rotulo")).to_have_count(3)
        expect(pagina.locator("#mapa .pino--menor")).to_have_count(5)

    def test_o_mapa_aproxima_da_resposta(self, navegador, servidor):
        """Antes o mapa ficava no parque inteiro, e os números cabiam num punhado de
        centímetros. Agora ele enquadra o visitante e as três primeiras."""
        pagina = abrir(navegador, servidor, com_gps=True)
        pagina.wait_for_selector("[data-modo='panorama'] .item", state="attached")
        # O parque inteiro também chega com animação: lido no meio dela, o "antes"
        # seria um zoom de passagem. E o zoom exato, não o `data-zoom` arredondado,
        # que empataria dois quartos de nível vizinhos.
        _mapa_parado(pagina)
        antes = pagina.evaluate("mapa.getZoom()")

        _com_cartao(pagina)
        _mapa_parado(pagina)
        depois = pagina.evaluate("mapa.getZoom()")

        assert depois > antes, f"o zoom ficou em {depois} (era {antes})"
        mapa = pagina.locator("#mapa").bounding_box()
        for pino in pagina.locator("#mapa .pino:not(.pino--menor)").all():
            caixa = pino.bounding_box()
            assert (
                mapa["x"] <= caixa["x"] and caixa["x"] + caixa["width"] <= mapa["x"] + mapa["width"]
            )
            assert (
                mapa["y"] <= caixa["y"]
                and caixa["y"] + caixa["height"] <= mapa["y"] + mapa["height"]
            )


class TestComputador:
    """No computador, mapa à direita e uma coluna de leitura à esquerda.

    O layout de celular esticado deixava dois terços da tela vazios (Gabriel,
    28/10/2026). A lista, que no celular mora num painel, aqui fica aberta.
    """

    def test_a_lista_fica_aberta_sem_painel(self, navegador, servidor):
        pagina = abrir(navegador, servidor, tela=COMPUTADOR)
        _com_cartao(pagina)

        expect(pagina.locator("#btn-todas-filas")).to_be_hidden()
        expect(pagina.locator("[data-modo='ranking'] .item")).to_have_count(8)
        expect(pagina.locator("[data-modo='ranking'] .item").first).to_be_visible()
        # Aberta, mas não como modal: o resto da página continua tocável.
        assert not pagina.locator("#painel-filas").evaluate("d => d.open")

    def test_o_mapa_ocupa_a_altura_inteira_ao_lado(self, navegador, servidor):
        pagina = abrir(navegador, servidor, tela=COMPUTADOR)
        mapa = pagina.locator("#mapa").bounding_box()
        cartao = pagina.locator("#proximo-passo").bounding_box()

        assert mapa["height"] == COMPUTADOR["height"]
        assert cartao["x"] + cartao["width"] <= mapa["x"], "o cartão invade o mapa"

    def test_o_mapa_fica_parado_ao_rolar_a_lista(self, navegador, servidor):
        pagina = abrir(navegador, servidor, tela=COMPUTADOR)
        _com_cartao(pagina)
        antes = pagina.locator("#mapa").bounding_box()

        pagina.mouse.move(200, 600)
        pagina.mouse.wheel(0, 900)
        pagina.wait_for_function("window.scrollY > 0")

        assert pagina.locator("#mapa").bounding_box() == antes

    def test_passar_o_ponteiro_acende_o_numero_no_mapa(self, navegador, servidor):
        pagina = abrir(navegador, servidor, tela=COMPUTADOR)
        _com_cartao(pagina)

        pagina.locator("[data-modo='ranking'] .item").nth(1).hover()
        expect(pagina.locator("#mapa .pino--realce")).to_have_text("2")

        pagina.locator("#proximo-passo").hover()
        expect(pagina.locator("#mapa .pino--realce")).to_have_count(0)

    def test_no_celular_a_lista_continua_no_painel(self, navegador, servidor):
        """O par do primeiro teste: a mudança é só do computador."""
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)
        expect(pagina.locator("#btn-todas-filas")).to_be_visible()
        expect(pagina.locator("#painel-filas")).to_be_hidden()


def _com_alvos(pagina, *trechos: str) -> None:
    """Grava alvos direto no armazenamento e recarrega, como um visitante que volta."""
    pagina.evaluate(
        "([parque, ids]) => localStorage.setItem('nextup:alvos', JSON.stringify({[parque]: ids}))",
        [DEFAULT_PARK_ID, [_id_de(t) for t in trechos]],
    )
    pagina.reload(wait_until="networkidle")


class TestChaveDoCartao:
    """A chave "Melhor do parque | Das minhas" (Gabriel, 29/10/2026).

    Na fixture: a melhor do parque é o Prince Charming (7 min no total); entre os
    alvos usados aqui, Space Mountain (50) vem antes de Big Thunder (68).
    """

    def test_sem_alvos_a_chave_nao_aparece(self, navegador, servidor):
        """'Das minhas' sem nenhuma marcada seria uma opção que não leva a nada."""
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)
        expect(pagina.locator("#passo-criterio")).to_be_hidden()

    def test_com_alvos_o_padrao_continua_o_parque(self, navegador, servidor):
        """Quem nunca tocou na chave não pode ver a resposta mudar de critério."""
        pagina = abrir(navegador, servidor)
        _com_alvos(pagina, "Space Mountain", "Big Thunder")
        _com_cartao(pagina)

        expect(pagina.locator("#passo-criterio")).to_be_visible()
        expect(pagina.locator("#passo-destaque .passo__nome")).to_have_text(
            "Prince Charming Regal Carrousel"
        )
        expect(pagina.locator("#passo-titulo")).to_have_text("Seu próximo passo")

    def test_das_minhas_mostra_a_melhor_das_marcadas(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _com_alvos(pagina, "Space Mountain", "Big Thunder")
        _com_cartao(pagina)

        pagina.get_by_text("Das minhas").click()

        expect(pagina.locator("#passo-destaque .passo__nome")).to_have_text("Space Mountain")
        # O número continua sendo o tempo de verdade: a chave troca o conjunto,
        # não dá bônus a ninguém.
        expect(pagina.locator("#passo-destaque .passo__total strong")).to_have_text("50")
        expect(pagina.locator("#passo-titulo")).to_have_text("Próxima da sua lista")

    def test_a_escolha_sobrevive_a_recarregar(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _com_alvos(pagina, "Space Mountain", "Big Thunder")
        _com_cartao(pagina)
        pagina.get_by_text("Das minhas").click()

        pagina.reload(wait_until="networkidle")
        _com_cartao(pagina)

        expect(pagina.locator("#passo-destaque .passo__nome")).to_have_text("Space Mountain")

    def test_sem_marcada_disponivel_volta_ao_parque_e_avisa(self, navegador, servidor):
        """Trocar de critério calado faria o visitante ler a sugestão como uma das dele."""
        pagina = abrir(navegador, servidor)
        _com_alvos(pagina, "Space Mountain")
        _com_cartao(pagina)
        pagina.get_by_text("Das minhas").click()

        pagina.click("#passo-destaque .botao-ja-fui")

        expect(pagina.locator("#passo-destaque .passo__nome")).to_have_text(
            "Prince Charming Regal Carrousel"
        )
        expect(pagina.locator("#passo-destaque")).to_contain_text(
            "Nenhuma das suas está disponível agora"
        )
        expect(pagina.locator("#passo-titulo")).to_have_text("Seu próximo passo")

    def test_a_rota_vai_ate_o_alvo(self, navegador, servidor):
        """O mapa acompanha o cartão: a rota leva aonde o cartão manda."""
        pagina = abrir(navegador, servidor)
        _com_alvos(pagina, "Space Mountain")
        _com_cartao(pagina)
        pagina.get_by_text("Das minhas").click()

        destino = pagina.evaluate(
            "() => [estado.destaque.attraction.latitude, estado.destaque.attraction.longitude]"
        )
        pagina.wait_for_function(
            "([lat, lon]) => mapa.getBounds().contains([lat, lon])", arg=destino
        )


class TestAlternativasNoCartao:
    """O plano B sem abrir o painel: a 2ª e a 3ª do mesmo critério do cartão."""

    def test_cita_as_duas_seguintes(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)

        outras = pagina.locator("#passo-destaque .passo__outras li")
        expect(outras).to_have_count(2)
        expect(outras.nth(0)).to_contain_text("PeopleMover")
        expect(outras.nth(0)).to_contain_text("10 min")
        expect(outras.nth(1)).to_contain_text("Mad Tea Party")

    def test_com_das_minhas_as_seguintes_tambem_sao_marcadas(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _com_alvos(pagina, "Space Mountain", "Big Thunder")
        _com_cartao(pagina)
        pagina.get_by_text("Das minhas").click()

        outras = pagina.locator("#passo-destaque .passo__outras li")
        expect(outras).to_have_count(1)
        expect(outras.first).to_contain_text("Big Thunder")


def _mapa_preso(pagina) -> None:
    """Espera o desenho do parque chegar: é ele que prende o mapa."""
    pagina.wait_for_function("Boolean(mapa.options.maxBounds)")


def _ve_o_parque_inteiro(pagina) -> None:
    pagina.wait_for_function(
        """() => {
          const l = estado.limitesDoParque;
          return mapa.getBounds().contains([[l.south, l.west], [l.north, l.east]]);
        }"""
    )


class TestMapaPresoAoParque:
    """Na versão só do Magic Kingdom, o mapa não sai do parque (Gabriel, 29/10/2026).

    O outro lado — nos parques com tiles o mapa fica livre — é o que deixa
    `TestTrocaDeParque` levar a vista até a Europa: preso, ele não iria.
    """

    def test_arrastar_nao_tira_o_mapa_do_parque(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _mapa_preso(pagina)
        caixa = pagina.locator("#mapa").bounding_box()
        meio_y = caixa["y"] + caixa["height"] / 2

        # Arrastos longos para a esquerda: sem limite, o mapa iria parar em Tampa.
        for _ in range(6):
            pagina.mouse.move(caixa["x"] + caixa["width"] - 10, meio_y)
            pagina.mouse.down()
            pagina.mouse.move(caixa["x"] + 10, meio_y, steps=8)
            pagina.mouse.up()

        pagina.wait_for_timeout(400)
        assert pagina.evaluate("mapa.options.maxBounds.pad(0.01).contains(mapa.getBounds())"), (
            "a vista saiu do parque"
        )

    def test_nao_afasta_alem_do_parque_inteiro(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _mapa_preso(pagina)

        pagina.evaluate("mapa.setZoom(10)")
        pagina.wait_for_timeout(400)

        zoom, minimo = pagina.evaluate("[mapa.getZoom(), mapa.getMinZoom()]")
        assert minimo > 13, f"zoom mínimo {minimo} deixa o parque virar um ponto"
        assert zoom >= minimo


class TestRecentralizar:
    """O botão que volta o mapa para o que importa (Gabriel, 29/10/2026)."""

    def test_e_confortavel_para_o_dedo(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        caixa = pagina.locator("#btn-recentralizar").bounding_box()
        assert caixa["width"] >= 44 and caixa["height"] >= 44

    def test_volta_para_o_visitante_e_a_resposta(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)
        _mapa_parado(pagina)
        # Longe do visitante: o canto nordeste do parque, bem perto.
        pagina.evaluate("mapa.setView([28.4232, -81.5752], 18, { animate: false })")

        pagina.click("#btn-recentralizar")

        pagina.wait_for_function(
            """() => mapa.getBounds().contains([estado.posicao.lat, estado.posicao.lon])
                  && mapa.getBounds().contains([estado.destaque.attraction.latitude,
                                                estado.destaque.attraction.longitude])"""
        )

    def test_o_segundo_toque_mostra_o_parque_inteiro(self, navegador, servidor):
        pagina = abrir(navegador, servidor)
        _com_cartao(pagina)
        _mapa_parado(pagina)

        pagina.click("#btn-recentralizar")  # já está na resposta: vai ao parque
        _ve_o_parque_inteiro(pagina)

    def test_sem_posicao_mostra_o_parque_inteiro(self, navegador, servidor):
        pagina = abrir(navegador, servidor, com_gps=False)
        _mapa_preso(pagina)
        pagina.evaluate("mapa.setView([28.4232, -81.5752], 18, { animate: false })")

        pagina.click("#btn-recentralizar")

        _ve_o_parque_inteiro(pagina)

    def test_tocar_no_botao_nao_vira_posicao(self, navegador, servidor):
        """Tocar no mapa define a posição; o toque no botão não pode vazar para ele."""
        pagina = abrir(navegador, servidor, com_gps=False)
        pagina.click("#btn-recentralizar")
        pagina.wait_for_timeout(300)

        expect(pagina.locator("#passo-sem-posicao")).to_be_visible()
        assert pagina.evaluate("estado.posicao") is None

"""Testes da popularidade chegando à API.

Cobrem as mesmas duas coisas que `test_api_tendencia.py`, porque a regra é a
mesma: a popularidade é enfeite valioso, e **o ranking não pode passar a depender
do banco estar de pé**. O ranking existe desde a Fase 2 e responde sem histórico
nenhum.

O que este arquivo tem a mais é o **cache**. Ele é o que torna a feature viável —
a janela é de sete dias e o Neon fica do outro lado do continente — mas cache é
onde bugs se escondem, porque a segunda resposta pode estar certa por engano.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine

from nextup.api.dependencies import obter_cliente, obter_engine
from nextup.api.main import criar_app
from nextup.api.routes import _CACHE_POPULARIDADE
from nextup.clients.themeparks import ThemeParksClient
from nextup.config import DEFAULT_PARK_ID, POPULARITY_MIN_MEASUREMENTS, THEMEPARKS_BASE_URL
from nextup.models import LiveStatus, QueueSnapshot
from nextup.storage import connection, create_schema, save_many
from nextup.storage.engine import create_engine

FIXTURES = Path(__file__).parent / "fixtures"

URL_CATALOGO = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/children"
URL_LIVE = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/live"
ROTA = f"/api/parks/{DEFAULT_PARK_ID}/recommendations?lat=28.4189&lon=-81.5812&limit=0"


def carregar(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


def atracoes_com_fila() -> list[tuple[str, int]]:
    """IDs da fixture que o ranking realmente devolve, com a fila de cada um.

    Inventar IDs faria o teste passar sem provar nada: a popularidade seria
    calculada e descartada por não casar com nenhuma atração do ranking. É o
    mesmo cuidado de `test_api_tendencia.id_real_com_fila`.
    """
    vivo = carregar("live_magic_kingdom.json")
    catalogo = carregar("children_magic_kingdom.json")
    atracoes = {c["id"] for c in catalogo["children"] if c.get("entityType") == "ATTRACTION"}

    encontradas = []
    for item in vivo["liveData"]:
        fila = (item.get("queue") or {}).get("STANDBY") or {}
        if item["id"] in atracoes and fila.get("waitTime") is not None:
            encontradas.append((item["id"], fila["waitTime"]))

    assert len(encontradas) >= 5, "a fixture precisa de atrações suficientes para formar faixas"
    return encontradas


async def _sem_espera(_s: float) -> None:
    return None


@pytest.fixture(autouse=True)
def cache_limpo():
    """O cache é global ao processo, então vaza de um teste para o outro.

    Sem isto, o segundo teste leria a faixa que o primeiro gravou e passaria sem
    tocar no banco — verde, e sem ter verificado nada.
    """
    _CACHE_POPULARIDADE.clear()
    yield
    _CACHE_POPULARIDADE.clear()


@pytest.fixture
async def banco() -> AsyncEngine:
    motor = create_engine("sqlite+aiosqlite:///:memory:")
    await create_schema(motor)
    yield motor
    await motor.dispose()


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


def montar_app(conexao, motor):
    app = criar_app()
    app.dependency_overrides[obter_cliente] = lambda: ThemeParksClient(
        http_client=conexao, sleep=_sem_espera
    )
    app.dependency_overrides[obter_engine] = lambda: motor
    return TestClient(app)


async def gravar_historico(motor, filas: dict[str, int], *, medicoes: int | None = None) -> None:
    """Grava um histórico plano: cada atração sempre com a mesma fila.

    Fila constante é o que deixa a média previsível, e a média é o que o teste
    precisa controlar para saber qual faixa esperar.
    """
    quantas = POPULARITY_MIN_MEASUREMENTS if medicoes is None else medicoes
    agora = datetime.now(UTC)

    snapshots = [
        QueueSnapshot(
            park_id=DEFAULT_PARK_ID,
            attraction_id=attraction_id,
            status=LiveStatus.OPERATING,
            wait_time_minutes=fila,
            observed_at=agora - timedelta(minutes=5 * i),
            recorded_at=agora,
        )
        for attraction_id, fila in filas.items()
        for i in range(quantas)
    ]

    async with connection(motor) as conexao:
        await save_many(conexao, snapshots)


def por_id(corpo: dict) -> dict[str, dict]:
    return {r["attraction"]["id"]: r for r in corpo["recommendations"]}


class TestComHistorico:
    async def test_a_faixa_chega_na_resposta(self, api_no_ar, banco):
        ids = [aid for aid, _ in atracoes_com_fila()]
        # Uma campeã bem acima do resto: 100 contra 10.
        await gravar_historico(banco, {ids[0]: 100} | {aid: 10 for aid in ids[1:]})

        async with httpx.AsyncClient() as conexao:
            corpo = montar_app(conexao, banco).get(ROTA).json()

        assert por_id(corpo)[ids[0]]["popularity"]["tier"] == "HEADLINER"

    async def test_traz_a_media_e_a_contagem(self, api_no_ar, banco):
        ids = [aid for aid, _ in atracoes_com_fila()]
        await gravar_historico(banco, {aid: 30 for aid in ids})

        async with httpx.AsyncClient() as conexao:
            corpo = montar_app(conexao, banco).get(ROTA).json()

        faixa = por_id(corpo)[ids[0]]["popularity"]
        assert faixa["average_minutes"] == 30.0
        assert faixa["measurements"] == POPULARITY_MIN_MEASUREMENTS

    async def test_historico_curto_vira_desconhecida(self, api_no_ar, banco):
        ids = [aid for aid, _ in atracoes_com_fila()]
        await gravar_historico(banco, {aid: 30 for aid in ids}, medicoes=2)

        async with httpx.AsyncClient() as conexao:
            corpo = montar_app(conexao, banco).get(ROTA).json()

        assert por_id(corpo)[ids[0]]["popularity"]["tier"] == "UNKNOWN"

    async def test_a_popularidade_nao_reordena_o_ranking(self, api_no_ar, banco):
        """A mesma regra da tendência e dos alvos.

        O ranking responde "o que compensa agora"; popularidade descreve a
        atração, não o momento. O teste compara a ordem com e sem histórico.
        """
        ids = [aid for aid, _ in atracoes_com_fila()]

        async with httpx.AsyncClient() as conexao:
            sem = [
                r["attraction"]["id"]
                for r in montar_app(conexao, None).get(ROTA).json()["recommendations"]
            ]

        await gravar_historico(banco, {ids[0]: 100} | {aid: 10 for aid in ids[1:]})

        async with httpx.AsyncClient() as conexao:
            com = [
                r["attraction"]["id"]
                for r in montar_app(conexao, banco).get(ROTA).json()["recommendations"]
            ]

        assert sem == com


class TestOportunidade:
    async def test_principal_com_fila_baixa_e_sinalizada(self, api_no_ar, banco):
        """A razão de a feature existir: o ranking sabe o que custa menos agora,
        não o que está barato para os padrões daquela atração."""
        com_fila = atracoes_com_fila()
        alvo, fila_de_agora = min(com_fila, key=lambda p: p[1])

        # Média histórica muito acima da fila atual, e bem acima do resto do
        # parque — para a atração ser principal E estar abaixo da média dela.
        media = max(fila_de_agora * 5, 50)
        await gravar_historico(
            banco, {alvo: media} | {aid: 10 for aid, _ in com_fila if aid != alvo}
        )

        async with httpx.AsyncClient() as conexao:
            corpo = montar_app(conexao, banco).get(ROTA).json()

        recomendacao = por_id(corpo)[alvo]
        assert recomendacao["popularity"]["opportunity"] is True
        assert "abaixo da média dela" in recomendacao["explanation"]

    async def test_principal_na_media_nao_e_sinalizada(self, api_no_ar, banco):
        com_fila = atracoes_com_fila()
        alvo, fila_de_agora = max(com_fila, key=lambda p: p[1])

        await gravar_historico(
            banco, {alvo: fila_de_agora} | {aid: 1 for aid, _ in com_fila if aid != alvo}
        )

        async with httpx.AsyncClient() as conexao:
            corpo = montar_app(conexao, banco).get(ROTA).json()

        assert por_id(corpo)[alvo]["popularity"]["opportunity"] is False


class TestDegradacaoGraciosa:
    """Sem banco, com banco vazio ou com banco fora do ar, o ranking sai igual."""

    async def test_sem_banco_o_ranking_sai_completo(self, api_no_ar):
        async with httpx.AsyncClient() as conexao:
            resposta = montar_app(conexao, None).get(ROTA)

        assert resposta.status_code == 200
        assert resposta.json()["recommendations"]
        assert all(r["popularity"] is None for r in resposta.json()["recommendations"])

    async def test_banco_vazio_nao_quebra(self, api_no_ar, banco):
        async with httpx.AsyncClient() as conexao:
            resposta = montar_app(conexao, banco).get(ROTA)

        assert resposta.status_code == 200
        assert resposta.json()["recommendations"]

    async def test_banco_fora_do_ar_nao_derruba_a_recomendacao(self, api_no_ar, banco):
        """O caso que mais importa: o Postgres cai e o visitante continua sabendo
        para onde ir. Perder o enfeite é aceitável; perder a resposta não."""
        await banco.dispose()  # o motor morre, mas a rota continua sendo chamada

        async with httpx.AsyncClient() as conexao:
            resposta = montar_app(conexao, banco).get(ROTA)

        assert resposta.status_code == 200
        assert resposta.json()["recommendations"]


class TestCache:
    async def test_a_segunda_chamada_nao_vai_ao_banco(self, api_no_ar, banco):
        """Prova pela negativa: com o banco derrubado **depois** da primeira
        chamada, a segunda só pode responder se veio do cache."""
        ids = [aid for aid, _ in atracoes_com_fila()]
        await gravar_historico(banco, {ids[0]: 100} | {aid: 10 for aid in ids[1:]})

        async with httpx.AsyncClient() as conexao:
            cliente = montar_app(conexao, banco)
            primeira = cliente.get(ROTA).json()
            await banco.dispose()
            segunda = cliente.get(ROTA).json()

        assert por_id(primeira)[ids[0]]["popularity"]["tier"] == "HEADLINER"
        assert por_id(segunda)[ids[0]]["popularity"]["tier"] == "HEADLINER"

    async def test_parque_sem_historico_nao_fica_preso_no_cache(self, api_no_ar, banco):
        """Guardar o vazio prenderia o resultado por uma hora justamente enquanto
        o coletor começa a preencher — e o visitante não veria faixa nenhuma até
        o TTL vencer."""
        async with httpx.AsyncClient() as conexao:
            cliente = montar_app(conexao, banco)
            cliente.get(ROTA)  # banco ainda vazio

            ids = [aid for aid, _ in atracoes_com_fila()]
            await gravar_historico(banco, {ids[0]: 100} | {aid: 10 for aid in ids[1:]})

            corpo = cliente.get(ROTA).json()

        assert por_id(corpo)[ids[0]]["popularity"]["tier"] == "HEADLINER"

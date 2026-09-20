"""Testes da tendência chegando à API.

Cobrem o trecho que liga o histórico do banco à justificativa da recomendação — e,
acima de tudo, a **degradação graciosa**: o ranking existe desde a Fase 2 e não
pode passar a depender do banco estar de pé.

A tendência é enfeite valioso. Perder o enfeite quando o Postgres cai é aceitável;
perder a resposta não é.
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
from nextup.clients.themeparks import ThemeParksClient
from nextup.config import DEFAULT_PARK_ID, THEMEPARKS_BASE_URL
from nextup.models import LiveStatus, QueueSnapshot
from nextup.storage import connection, create_schema, save_many
from nextup.storage.engine import create_engine

FIXTURES = Path(__file__).parent / "fixtures"

URL_CATALOGO = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/children"
URL_LIVE = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/live"
ROTA = f"/api/parks/{DEFAULT_PARK_ID}/recommendations?lat=28.4189&lon=-81.5812&limit=0"

#: Uma atração que existe na fixture real, para o histórico casar com o ranking.
SPACE_MOUNTAIN = "8ea94a92-1a80-4d0e-bb39-6be2b2b4f2a9"


def carregar(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


def id_real_com_fila() -> str:
    """Pega da fixture um ID que o ranking vai devolver de verdade.

    Inventar um ID faria o teste passar sem provar nada: a tendência seria
    calculada e descartada por não casar com nenhuma atração do ranking.
    """
    vivo = carregar("live_magic_kingdom.json")
    catalogo = carregar("children_magic_kingdom.json")
    atracoes = {c["id"] for c in catalogo["children"] if c.get("entityType") == "ATTRACTION"}

    for item in vivo["liveData"]:
        fila = (item.get("queue") or {}).get("STANDBY") or {}
        if item["id"] in atracoes and fila.get("waitTime") is not None:
            return item["id"]

    raise AssertionError("a fixture não tem nenhuma atração com fila")


async def _sem_espera(_s: float) -> None:
    return None


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


async def gravar_queda(motor, attraction_id: str) -> None:
    """Uma fila que caiu de 45 para 20 na última meia hora."""
    agora = datetime.now(UTC)

    async with connection(motor) as conexao:
        await save_many(
            conexao,
            [
                QueueSnapshot(
                    park_id=DEFAULT_PARK_ID,
                    attraction_id=attraction_id,
                    status=LiveStatus.OPERATING,
                    wait_time_minutes=45,
                    observed_at=agora - timedelta(minutes=25),
                    recorded_at=agora - timedelta(minutes=25),
                ),
                QueueSnapshot(
                    park_id=DEFAULT_PARK_ID,
                    attraction_id=attraction_id,
                    status=LiveStatus.OPERATING,
                    wait_time_minutes=20,
                    observed_at=agora - timedelta(minutes=1),
                    recorded_at=agora - timedelta(minutes=1),
                ),
            ],
        )


class TestTendenciaNaResposta:
    async def test_a_recomendacao_traz_a_tendencia(self, conexao, banco, api_no_ar):
        alvo = id_real_com_fila()
        await gravar_queda(banco, alvo)

        dados = montar_app(conexao, banco).get(ROTA).json()
        item = next(r for r in dados["recommendations"] if r["attraction"]["id"] == alvo)

        assert item["trend"] is not None
        assert item["trend"]["direction"] == "FALLING"
        assert item["trend"]["previous_minutes"] == 45
        assert item["trend"]["current_minutes"] == 20
        assert item["trend"]["delta"] == -25

    async def test_a_justificativa_fica_completa(self, conexao, banco, api_no_ar):
        """A frase que o `docs/PROJETO.md` promete desde 11/09/2026."""
        alvo = id_real_com_fila()
        await gravar_queda(banco, alvo)

        dados = montar_app(conexao, banco).get(ROTA).json()
        item = next(r for r in dados["recommendations"] if r["attraction"]["id"] == alvo)

        assert "Caiu de 45 para 20" in item["explanation"]

    async def test_atracao_sem_historico_vem_sem_tendencia(self, conexao, banco, api_no_ar):
        """Ausente, e não "UNKNOWN": quem consome checa se o campo existe."""
        alvo = id_real_com_fila()
        await gravar_queda(banco, alvo)

        dados = montar_app(conexao, banco).get(ROTA).json()
        outras = [r for r in dados["recommendations"] if r["attraction"]["id"] != alvo]

        assert outras, "o ranking devolveu uma atração só"
        assert all(r["trend"] is None for r in outras)


class TestDegradacaoGraciosa:
    """O ranking não pode passar a depender do banco."""

    def test_sem_banco_configurado_o_ranking_continua(self, conexao, api_no_ar):
        resposta = montar_app(conexao, None).get(ROTA)

        assert resposta.status_code == 200
        assert resposta.json()["recommendations"]
        assert all(r["trend"] is None for r in resposta.json()["recommendations"])

    def test_banco_fora_do_ar_nao_derruba_a_recomendacao(self, conexao, api_no_ar):
        """O caso que importa em produção: o Postgres cai e o app segue servindo.

        Aponta para um SQLite em arquivo inexistente, em pasta que não existe —
        qualquer consulta falha. A recomendação tem de sair assim mesmo.
        """
        quebrado = create_engine("sqlite+aiosqlite:///./pasta-que-nao-existe/nada.db")

        resposta = montar_app(conexao, quebrado).get(ROTA)

        assert resposta.status_code == 200
        assert resposta.json()["recommendations"]

    async def test_banco_sem_a_tabela_nao_derruba(self, conexao, api_no_ar):
        """Deploy novo, antes de a migração rodar."""
        vazio = create_engine("sqlite+aiosqlite:///:memory:")

        resposta = montar_app(conexao, vazio).get(ROTA)

        assert resposta.status_code == 200
        assert resposta.json()["recommendations"]

        await vazio.dispose()


class TestContratoPublico:
    async def test_a_tendencia_aparece_no_openapi(self, conexao, banco):
        """Campo novo no contrato é decisão consciente, e a documentação prova."""
        esquemas = montar_app(conexao, banco).get("/openapi.json").json()["components"]["schemas"]

        assert "TrendOut" in esquemas
        assert set(esquemas["TrendOut"]["properties"]) == {
            "direction",
            "previous_minutes",
            "current_minutes",
            "delta",
            "span_minutes",
            "description",
        }

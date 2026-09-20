"""Testes de `/api/parks/{id}/attractions/{id}/history`.

**O primeiro endpoint do NextUp que serve dado nosso.** Todos os outros são a
ThemeParks.wiki reempacotada; este só existe porque o coletor rodou.

Isso muda uma regra em relação ao resto da API. Na recomendação, o histórico é
enfeite e a falha do banco é engolida de propósito — melhor um ranking sem a frase
"caiu de 45 para 20" do que erro nenhum. Aqui o histórico **é** a resposta: sem
banco não há o que devolver, e fingir uma série vazia seria mentir dizendo que a
fila ficou parada.
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


def carregar(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


def primeira_atracao() -> tuple[str, str]:
    """Um (id, nome) real do catálogo, para o teste não inventar dados."""
    catalogo = carregar("children_magic_kingdom.json")
    for filho in catalogo["children"]:
        if filho.get("entityType") == "ATTRACTION":
            return filho["id"], filho["name"]
    raise AssertionError("a fixture não tem atração nenhuma")


ATRACAO_ID, ATRACAO_NOME = primeira_atracao()
AGORA = datetime.now(UTC)


def rota(attraction_id: str = ATRACAO_ID, *, hours: int | None = None) -> str:
    # `is not None`, e não `if hours`: com `hours=0` o segundo omitiria o parâmetro
    # e o teste do limite inferior passaria a exercitar o valor padrão.
    base = f"/api/parks/{DEFAULT_PARK_ID}/attractions/{attraction_id}/history"
    return f"{base}?hours={hours}" if hours is not None else base


async def _sem_espera(_s: float) -> None:
    return None


@pytest.fixture
async def banco() -> AsyncEngine:
    motor = create_engine("sqlite+aiosqlite:///:memory:")
    await create_schema(motor)
    yield motor
    await motor.dispose()


@pytest.fixture
def catalogo_no_ar():
    with respx.mock:
        respx.get(URL_CATALOGO).mock(
            return_value=httpx.Response(200, json=carregar("children_magic_kingdom.json"))
        )
        yield


def montar_app(conexao, motor):
    app = criar_app()
    app.dependency_overrides[obter_cliente] = lambda: ThemeParksClient(
        http_client=conexao, sleep=_sem_espera
    )
    app.dependency_overrides[obter_engine] = lambda: motor
    return TestClient(app)


async def gravar(motor, medicoes: list[tuple[int | None, float]]) -> None:
    """Grava `(fila, horas_atras)` para a atração de teste."""
    async with connection(motor) as conexao:
        await save_many(
            conexao,
            [
                QueueSnapshot(
                    park_id=DEFAULT_PARK_ID,
                    attraction_id=ATRACAO_ID,
                    status=LiveStatus.OPERATING if fila is not None else LiveStatus.CLOSED,
                    wait_time_minutes=fila,
                    observed_at=AGORA - timedelta(hours=horas),
                    recorded_at=AGORA - timedelta(hours=horas),
                )
                for fila, horas in medicoes
            ],
        )


class TestSerie:
    async def test_devolve_os_pontos_em_ordem(self, conexao, banco, catalogo_no_ar):
        await gravar(banco, [(30, 3), (20, 2), (40, 1)])

        dados = montar_app(conexao, banco).get(rota()).json()

        assert [p["minutes"] for p in dados["points"]] == [30, 20, 40]

    async def test_identifica_a_atracao_pelo_catalogo(self, conexao, banco, catalogo_no_ar):
        """O nome não vem do banco: seriam centenas de milhares de cópias da string."""
        await gravar(banco, [(30, 2), (20, 1)])

        dados = montar_app(conexao, banco).get(rota()).json()

        assert dados["attraction_id"] == ATRACAO_ID
        assert dados["attraction_name"] == ATRACAO_NOME

    async def test_respeita_a_janela_pedida(self, conexao, banco, catalogo_no_ar):
        await gravar(banco, [(60, 20), (30, 2), (20, 1)])

        seis_horas = montar_app(conexao, banco).get(rota(hours=6)).json()
        um_dia = montar_app(conexao, banco).get(rota(hours=24)).json()

        assert [p["minutes"] for p in seis_horas["points"]] == [30, 20]
        assert [p["minutes"] for p in um_dia["points"]] == [60, 30, 20]

    async def test_medicoes_sem_fila_ficam_de_fora_do_grafico(self, conexao, banco, catalogo_no_ar):
        """Incluí-las como zero desenharia uma queda que nunca aconteceu."""
        await gravar(banco, [(30, 3), (None, 2), (20, 1)])

        dados = montar_app(conexao, banco).get(rota()).json()

        assert [p["minutes"] for p in dados["points"]] == [30, 20]

    async def test_sem_historico_devolve_serie_vazia_e_nao_erro(
        self, conexao, banco, catalogo_no_ar
    ):
        """Atração que ficou fechada, ou coleta que começou depois. Não é falha."""
        resposta = montar_app(conexao, banco).get(rota())

        assert resposta.status_code == 200
        assert resposta.json()["points"] == []
        assert resposta.json()["summary"] is None


class TestResumo:
    async def test_calcula_os_numeros_da_janela(self, conexao, banco, catalogo_no_ar):
        await gravar(banco, [(10, 4), (50, 3), (30, 2), (20, 1)])

        resumo = montar_app(conexao, banco).get(rota()).json()["summary"]

        assert resumo["measurements"] == 4
        assert resumo["min_minutes"] == 10
        assert resumo["max_minutes"] == 50
        assert resumo["average_minutes"] == 27.5
        assert resumo["current_minutes"] == 20
        assert resumo["spread"] == 40

    async def test_a_media_ignora_periodos_sem_fila(self, conexao, banco, catalogo_no_ar):
        """Contar fechado como zero faria a madrugada parecer o melhor horário."""
        await gravar(banco, [(30, 3), (None, 2), (30, 1)])

        resumo = montar_app(conexao, banco).get(rota()).json()["summary"]

        assert resumo["average_minutes"] == 30.0
        assert resumo["measurements"] == 2


class TestTendenciaNaJanela:
    async def test_usa_a_janela_pedida_e_nao_os_30_min_padrao(self, conexao, banco, catalogo_no_ar):
        """Quem pede 24h quer o movimento do dia, não o do último quarto de hora."""
        await gravar(banco, [(60, 5), (20, 1)])

        dados = montar_app(conexao, banco).get(rota(hours=6)).json()

        assert dados["trend"]["direction"] == "FALLING"
        assert dados["trend"]["previous_minutes"] == 60
        assert dados["trend"]["current_minutes"] == 20

    async def test_um_ponto_so_nao_gera_tendencia(self, conexao, banco, catalogo_no_ar):
        await gravar(banco, [(30, 1)])

        assert montar_app(conexao, banco).get(rota()).json()["trend"] is None


class TestErros:
    async def test_atracao_inexistente_da_404(self, conexao, banco, catalogo_no_ar):
        resposta = montar_app(conexao, banco).get(rota("nao-existe"))

        assert resposta.status_code == 404

    def test_sem_banco_da_503(self, conexao, catalogo_no_ar):
        """Aqui o histórico **é** a resposta.

        Diferente da recomendação, onde a falha do banco é engolida de propósito.
        Devolver uma série vazia mentiria: diria que a fila ficou parada.
        """
        resposta = montar_app(conexao, None).get(rota())

        assert resposta.status_code == 503

    def test_banco_fora_do_ar_da_503(self, conexao, catalogo_no_ar):
        quebrado = create_engine("sqlite+aiosqlite:///./pasta-que-nao-existe/nada.db")

        resposta = montar_app(conexao, quebrado).get(rota())

        assert resposta.status_code == 503

    @pytest.mark.parametrize("horas", [0, -1, 99999])
    async def test_janela_invalida_da_422(self, conexao, banco, catalogo_no_ar, horas):
        """Sem o teto, `?hours=99999` pediria a tabela inteira."""
        resposta = montar_app(conexao, banco).get(rota(hours=horas))

        assert resposta.status_code == 422

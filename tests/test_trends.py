"""Testes da tendência da fila.

`core/trends.py` é lógica pura: entra uma lista de snapshots, sai uma direção.
Estes testes rodam offline, em milissegundos, e nunca dependem de banco nem de
parque aberto.

Os cenários abaixo não são inventados — reproduzem o comportamento medido sobre
228 snapshots reais do Magic Kingdom, descrito no cabeçalho do módulo. Em especial
o caso que decidiu o desenho: **62% das medições consecutivas são idênticas**, e é
por isso que a comparação é contra o início da janela e não contra a anterior.
"""

from datetime import UTC, datetime, timedelta

import pytest

from nextup.core.recommender import Recommendation, recommend
from nextup.core.trends import Trend, TrendAnalysis, analyze, analyze_many
from nextup.models import (
    LiveDataResponse,
    LiveStatus,
    Location,
    ParkCatalog,
    ParkEntity,
    QueueSnapshot,
)

AGORA = datetime(2026, 9, 20, 14, 30, tzinfo=UTC)
PARQUE = "75ea578a-adc8-4116-a54d-dccb60765ef9"
ATRACAO = "space-mountain"


def snap(
    wait: int | None,
    *,
    ha_minutos: float = 0,
    attraction_id: str = ATRACAO,
) -> QueueSnapshot:
    """Um snapshot de `ha_minutos` atrás, contado a partir de `AGORA`."""
    instante = AGORA - timedelta(minutes=ha_minutos)
    return QueueSnapshot(
        park_id=PARQUE,
        attraction_id=attraction_id,
        status=LiveStatus.OPERATING if wait is not None else LiveStatus.CLOSED,
        wait_time_minutes=wait,
        observed_at=instante,
        recorded_at=instante,
    )


class TestDirecao:
    def test_fila_caindo(self):
        """O caso que o `docs/PROJETO.md` promete desde o primeiro dia."""
        analise = analyze([snap(45, ha_minutos=30), snap(20)], now=AGORA)

        assert analise.direction is Trend.FALLING
        assert analise.delta == -25

    def test_fila_subindo(self):
        analise = analyze([snap(10, ha_minutos=30), snap(35)], now=AGORA)

        assert analise.direction is Trend.RISING
        assert analise.delta == 25

    def test_fila_parada(self):
        analise = analyze([snap(20, ha_minutos=30), snap(20)], now=AGORA)

        assert analise.direction is Trend.STABLE
        assert analise.delta == 0

    def test_variacao_de_cinco_conta_como_movimento(self):
        """Cinco é o menor passo que a fonte reporta — não é ruído.

        Das 71 variações não-nulas medidas em dados reais, **53 eram de ±5**. Tratar
        isso como estável descartaria três de cada quatro movimentos e a tendência
        viveria dizendo que nada muda.
        """
        assert analyze([snap(20, ha_minutos=30), snap(15)], now=AGORA).direction is Trend.FALLING
        assert analyze([snap(20, ha_minutos=30), snap(25)], now=AGORA).direction is Trend.RISING

    def test_limiar_configuravel_muda_a_leitura(self):
        """Quem quiser ser mais exigente pode; o padrão é que vem da medição."""
        medicoes = [snap(20, ha_minutos=30), snap(15)]

        assert analyze(medicoes, now=AGORA, threshold_minutes=10).direction is Trend.STABLE


class TestDadosInsuficientes:
    def test_sem_snapshots(self):
        assert analyze([], now=AGORA).direction is Trend.UNKNOWN

    def test_uma_medicao_so(self):
        """Parque que abriu há dez minutos, ou coletor que acabou de subir."""
        assert analyze([snap(30)], now=AGORA).direction is Trend.UNKNOWN

    def test_desconhecido_nao_finge_estabilidade(self):
        """Dizer "estável" sem histórico seria inventar informação."""
        analise = analyze([snap(30)], now=AGORA)

        assert analise.direction is not Trend.STABLE
        assert analise.delta == 0
        assert analise.describe() == ""

    def test_medicoes_sem_fila_nao_contam(self):
        """Atração fechada não tem tendência de fila.

        Tratar o fechamento como "caiu para zero" inventaria uma queda que não
        existe — e ainda por cima colocaria a atração fechada no topo.
        """
        analise = analyze([snap(None, ha_minutos=30), snap(None)], now=AGORA)

        assert analise.direction is Trend.UNKNOWN

    def test_mistura_de_com_e_sem_fila_usa_so_as_com(self):
        analise = analyze([snap(40, ha_minutos=30), snap(None, ha_minutos=20), snap(20)], now=AGORA)

        assert analise.direction is Trend.FALLING
        assert (analise.previous_minutes, analise.current_minutes) == (40, 20)


class TestJanela:
    def test_ignora_o_que_e_velho_demais(self):
        """Um snapshot de ontem não diz nada sobre a fila de agora."""
        analise = analyze([snap(60, ha_minutos=600), snap(20)], now=AGORA)

        assert analise.direction is Trend.UNKNOWN

    def test_compara_com_o_inicio_da_janela_e_nao_com_a_anterior(self):
        """A decisão central do módulo, e a que veio dos dados.

        A fila caiu de 60 para 20 ao longo de meia hora, mas as duas últimas
        medições são iguais — o que acontece em 62% dos casos reais. Comparar
        consecutivas diria "estável" sobre uma queda de dois terços.
        """
        analise = analyze(
            [
                snap(60, ha_minutos=28),
                snap(40, ha_minutos=18),
                snap(20, ha_minutos=6),
                snap(20),
            ],
            now=AGORA,
        )

        assert analise.direction is Trend.FALLING
        assert (analise.previous_minutes, analise.current_minutes) == (60, 20)

    def test_ordem_de_entrada_nao_importa(self):
        """O banco devolve ordenado, mas o módulo não pode depender disso."""
        bagunçado = [snap(20), snap(45, ha_minutos=30), snap(30, ha_minutos=15)]

        assert analyze(bagunçado, now=AGORA).previous_minutes == 45

    def test_janela_configuravel(self):
        medicoes = [snap(60, ha_minutos=50), snap(20)]

        assert analyze(medicoes, now=AGORA).direction is Trend.UNKNOWN
        assert analyze(medicoes, now=AGORA, window_minutes=60).direction is Trend.FALLING

    def test_ignora_medicao_do_futuro(self):
        """Relógio dessincronizado da fonte não pode virar tendência inventada."""
        analise = analyze([snap(20), snap(60, ha_minutos=-10)], now=AGORA)

        assert analise.direction is Trend.UNKNOWN

    def test_registra_o_intervalo_real_e_nao_o_pedido(self):
        """Com histórico curto, a frase não pode dizer "nos últimos 30 min"."""
        analise = analyze([snap(40, ha_minutos=8), snap(20)], now=AGORA)

        assert analise.span_minutes == pytest.approx(8.0)


class TestFrase:
    def test_queda_vira_a_frase_do_projeto(self):
        analise = analyze([snap(45, ha_minutos=30), snap(20)], now=AGORA)

        assert analise.describe() == "Caiu de 45 para 20 nos últimos 30 min."

    def test_subida(self):
        analise = analyze([snap(10, ha_minutos=30), snap(35)], now=AGORA)

        assert analise.describe() == "Subiu de 10 para 35 nos últimos 30 min."

    def test_estavel(self):
        analise = analyze([snap(20, ha_minutos=30), snap(20)], now=AGORA)

        assert analise.describe() == "Estável nos últimos 30 min."

    def test_desconhecido_nao_gera_frase(self):
        """String vazia, e não "tendência desconhecida": ninguém lê isso."""
        assert TrendAnalysis(direction=Trend.UNKNOWN).describe() == ""


class TestVariasAtracoes:
    def test_separa_por_atracao(self):
        analises = analyze_many(
            [
                snap(45, ha_minutos=30, attraction_id="a"),
                snap(20, attraction_id="a"),
                snap(10, ha_minutos=30, attraction_id="b"),
                snap(40, attraction_id="b"),
            ],
            now=AGORA,
        )

        assert analises["a"].direction is Trend.FALLING
        assert analises["b"].direction is Trend.RISING

    def test_atracao_sem_historico_fica_de_fora(self):
        """Quem consulta usa `.get()` e trata a ausência como desconhecida."""
        analises = analyze_many(
            [
                snap(45, ha_minutos=30, attraction_id="a"),
                snap(20, attraction_id="a"),
                snap(30, attraction_id="sozinha"),
            ],
            now=AGORA,
        )

        assert set(analises) == {"a"}

    def test_lista_vazia(self):
        assert analyze_many([], now=AGORA) == {}


class TestJustificativaCompleta:
    """A tendência chegando ao ranking — o que a Fase 6.3 entrega de verdade.

    Até aqui a justificativa parava em "= 24 min". A segunda frase é a que explica
    **por que agora**, e é a que o `docs/PROJETO.md` promete desde 11/09/2026.
    """

    def atracao(self) -> ParkEntity:
        return ParkEntity.model_validate(
            {
                "id": ATRACAO,
                "name": "Big Thunder Mountain",
                "entityType": "ATTRACTION",
                "location": {"latitude": 28.4199, "longitude": -81.5843},
            }
        )

    def test_a_frase_prometida_no_projeto(self):
        recomendacao = Recommendation(
            attraction=self.atracao(),
            walking_minutes=4.0,
            queue_minutes=20,
            trend=analyze([snap(45, ha_minutos=30), snap(20)], now=AGORA),
        )

        assert recomendacao.explain() == (
            "Big Thunder Mountain — 4 min de caminhada + 20 min de fila = 24 min. "
            "Caiu de 45 para 20 nos últimos 30 min."
        )

    def test_sem_historico_a_justificativa_continua_valendo(self):
        """O ranking funciona desde a Fase 2 e não pode passar a depender do banco.

        No primeiro dia de coleta de um parque novo, ninguém tem histórico — e a
        recomendação continua sendo útil.
        """
        recomendacao = Recommendation(
            attraction=self.atracao(), walking_minutes=4.0, queue_minutes=20
        )

        assert recomendacao.explain() == (
            "Big Thunder Mountain — 4 min de caminhada + 20 min de fila = 24 min"
        )

    def test_tendencia_desconhecida_nao_suja_a_frase(self):
        recomendacao = Recommendation(
            attraction=self.atracao(),
            walking_minutes=4.0,
            queue_minutes=20,
            trend=TrendAnalysis(direction=Trend.UNKNOWN),
        )

        assert recomendacao.explain().endswith("= 24 min")

    def test_a_tendencia_nao_muda_a_ordem_do_ranking(self):
        """Decisão de produto: o que ordena continua sendo `caminhada + fila`.

        Uma fila caindo rápido ainda pode custar mais tempo total que uma parada ao
        lado. Deixar a tendência reordenar seria trocar a tese do projeto por uma
        heurística — e sem ninguém decidir isso.
        """
        catalogo = ParkCatalog.model_validate(
            {
                "id": PARQUE,
                "name": "Parque",
                "entityType": "PARK",
                "timezone": "America/New_York",
                "children": [
                    {
                        "id": "perto-e-parada",
                        "name": "Perto e parada",
                        "entityType": "ATTRACTION",
                        "location": {"latitude": 28.4190, "longitude": -81.5810},
                    },
                    {
                        "id": "longe-e-caindo",
                        "name": "Longe e caindo",
                        "entityType": "ATTRACTION",
                        "location": {"latitude": 28.4260, "longitude": -81.5900},
                    },
                ],
            }
        )
        ao_vivo = LiveDataResponse.model_validate(
            {
                "id": PARQUE,
                "name": "Parque",
                "liveData": [
                    {
                        "id": "perto-e-parada",
                        "name": "Perto e parada",
                        "status": "OPERATING",
                        "queue": {"STANDBY": {"waitTime": 10}},
                        "lastUpdated": "2026-09-20T14:30:00Z",
                    },
                    {
                        "id": "longe-e-caindo",
                        "name": "Longe e caindo",
                        "status": "OPERATING",
                        "queue": {"STANDBY": {"waitTime": 15}},
                        "lastUpdated": "2026-09-20T14:30:00Z",
                    },
                ],
            }
        )

        tendencias = analyze_many(
            [
                snap(60, ha_minutos=30, attraction_id="longe-e-caindo"),
                snap(15, attraction_id="longe-e-caindo"),
            ],
            now=AGORA,
        )

        ranking = recommend(
            catalog=catalogo,
            live=ao_vivo,
            visitor=Location(latitude=28.4189, longitude=-81.5812),
            limit=0,
            trends=tendencias,
        )

        # A que despencou de 60 para 15 continua atrás: o custo total manda.
        assert [r.attraction.id for r in ranking] == ["perto-e-parada", "longe-e-caindo"]
        assert ranking[1].trend is not None
        assert ranking[1].trend.direction is Trend.FALLING

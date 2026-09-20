"""Testes dos modelos de previsão e da régua que os compara.

O que este arquivo protege não é uma funcionalidade da tela — é uma **conclusão**.
Em 20/09/2026, um backtest sobre 315 medições reais mostrou que extrapolar a
tendência piora a previsão da fila em todos os horizontes. A decisão que saiu daí
foi manter a persistência, que é o que o NextUp já fazia desde a Fase 2.

Os testes abaixo fixam o comportamento dos dois modelos e da avaliação, para que a
medição possa ser repetida quando houver mais dados — em especial sobre a previsão
da própria fonte, que só agora começou a ser gravada.
"""

from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pytest

from nextup.core.forecast import (
    Prediction,
    evaluate,
    persistence,
    trend_extrapolation,
)
from nextup.models import LiveStatus, QueueSnapshot

AGORA = datetime(2026, 9, 20, 15, 0, tzinfo=UTC)
PARQUE = "75ea578a-adc8-4116-a54d-dccb60765ef9"


def snap(wait: int | None, *, ha_minutos: float = 0) -> QueueSnapshot:
    instante = AGORA - timedelta(minutes=ha_minutos)
    return QueueSnapshot(
        park_id=PARQUE,
        attraction_id="atracao",
        status=LiveStatus.OPERATING if wait is not None else LiveStatus.CLOSED,
        wait_time_minutes=wait,
        observed_at=instante,
        recorded_at=instante,
    )


class TestPersistencia:
    def test_preve_a_fila_de_agora(self):
        previsao = persistence([snap(40, ha_minutos=20), snap(25)], horizon_minutes=12)

        assert previsao.minutes == 25
        assert previsao.model == "persistence"

    def test_o_horizonte_nao_muda_a_previsao(self):
        """É o que define o modelo: ignora o tempo e repete o presente."""
        medicoes = [snap(30)]

        assert persistence(medicoes, horizon_minutes=5).minutes == 30
        assert persistence(medicoes, horizon_minutes=60).minutes == 30

    def test_usa_a_medicao_mais_recente(self):
        """Ordem de entrada não importa; o relógio decide."""
        previsao = persistence([snap(25), snap(40, ha_minutos=20)], horizon_minutes=10)

        assert previsao.minutes == 25

    def test_ignora_medicoes_sem_fila(self):
        previsao = persistence([snap(30, ha_minutos=10), snap(None)], horizon_minutes=10)

        assert previsao.minutes == 30

    def test_sem_fila_nenhuma_nao_ha_previsao(self):
        assert persistence([snap(None)], horizon_minutes=10) is None
        assert persistence([], horizon_minutes=10) is None


class TestExtrapolacaoDaTendencia:
    def test_projeta_a_queda(self):
        """Caiu 30 min em 30 min; em 10 min mais, a conta prevê menos 10."""
        previsao = trend_extrapolation([snap(60, ha_minutos=30), snap(30)], horizon_minutes=10)

        assert previsao.minutes == 20

    def test_projeta_a_subida(self):
        previsao = trend_extrapolation([snap(10, ha_minutos=30), snap(40)], horizon_minutes=10)

        assert previsao.minutes == 50

    def test_amortecimento_reduz_a_projecao(self):
        """Reconhece que a direção não se sustenta indefinidamente."""
        medicoes = [snap(60, ha_minutos=30), snap(30)]

        cheio = trend_extrapolation(medicoes, horizon_minutes=10)
        metade = trend_extrapolation(medicoes, horizon_minutes=10, damping=0.5)

        assert cheio.minutes == 20
        assert metade.minutes == 25

    def test_nunca_preve_fila_negativa(self):
        """Extrapolação pura levaria a -40 min, que não é um lugar.

        É a razão mais concreta para desconfiar de extrapolação linear: prolongada
        o bastante, ela sempre sai da realidade.
        """
        previsao = trend_extrapolation([snap(60, ha_minutos=10), snap(10)], horizon_minutes=20)

        assert previsao.minutes == 0

    def test_uma_medicao_so_nao_da_inclinacao(self):
        assert trend_extrapolation([snap(30)], horizon_minutes=10) is None

    def test_medicoes_no_mesmo_instante_caem_na_persistencia(self):
        """Sem tempo decorrido não há taxa, e dividir por zero seria o erro óbvio."""
        previsao = trend_extrapolation([snap(30), snap(30)], horizon_minutes=10)

        assert previsao.minutes == 30


class TestAvaliacao:
    def test_mede_o_erro_medio(self):
        pares = [
            (Prediction(model="x", minutes=20, horizon_minutes=10), 25),
            (Prediction(model="x", minutes=30, horizon_minutes=10), 30),
            (Prediction(model="x", minutes=40, horizon_minutes=10), 35),
        ]

        placar = evaluate(pares)

        assert placar.cases == 3
        assert placar.mean_absolute_error == round((5 + 0 + 5) / 3, 2)

    def test_conta_os_acertos_exatos(self):
        """A fonte reporta em passos de 5, então acertar na mosca é possível."""
        pares = [
            (Prediction(model="x", minutes=20, horizon_minutes=10), 20),
            (Prediction(model="x", minutes=20, horizon_minutes=10), 25),
        ]

        placar = evaluate(pares)

        assert placar.exact_hits == 1
        assert placar.hit_rate == 0.5

    def test_modelo_perfeito_erra_zero(self):
        pares = [(Prediction(model="x", minutes=n, horizon_minutes=10), n) for n in (5, 10, 15)]

        assert evaluate(pares).mean_absolute_error == 0.0

    def test_sem_pares_nao_ha_placar(self):
        """`None` em vez de erro zero — que pareceria um modelo perfeito."""
        assert evaluate([]) is None


class TestAConclusaoMedida:
    """Fixa, em teste, o resultado que decidiu a Fase 6.6.

    Se algum dia alguém trocar o modelo do ranking por extrapolação, estes testes
    explicam por que a ideia já foi tentada e medida — em vez de deixar a decisão
    sobreviver apenas como um parágrafo de documentação que ninguém lê.
    """

    #: Um cenário de fila que oscila, que é o comportamento real observado: ela
    #: sobe, para, desce. Extrapolar a última inclinação erra a virada.
    #:
    #: Pares `(minutos atrás, fila)`, do mais antigo ao mais recente.
    OSCILACAO: ClassVar[list[tuple[int, int]]] = [
        (30, 40),
        (45, 30),
        (60, 20),
        (35, 15),
        (20, 25),
    ]

    def serie(self):
        return [snap(fila, ha_minutos=minutos) for minutos, fila in self.OSCILACAO]

    def test_persistencia_bate_extrapolacao_numa_fila_que_oscila(self):
        historico = self.serie()
        realizado = 30  # a fila voltou a subir depois da queda

        por_persistencia = persistence(historico, horizon_minutes=15)
        por_tendencia = trend_extrapolation(historico, horizon_minutes=15)

        erro_persistencia = abs(por_persistencia.minutes - realizado)
        erro_tendencia = abs(por_tendencia.minutes - realizado)

        assert erro_persistencia < erro_tendencia, (
            "neste cenário a extrapolação deveria perder: ela projeta a última "
            "inclinação e a fila virou"
        )

    def test_o_amortecimento_reduz_o_estrago_mas_nao_o_desfaz(self):
        historico = self.serie()
        realizado = 30

        cheio = abs(trend_extrapolation(historico, horizon_minutes=15).minutes - realizado)
        amortecido = abs(
            trend_extrapolation(historico, horizon_minutes=15, damping=0.5).minutes - realizado
        )
        persistente = abs(persistence(historico, horizon_minutes=15).minutes - realizado)

        assert persistente <= amortecido <= cheio

    @pytest.mark.parametrize("horizonte", [5, 10, 20, 30])
    def test_quanto_maior_o_horizonte_pior_a_extrapolacao(self, horizonte):
        """O erro da extrapolação cresce com a distância; o da persistência não.

        É o que a tabela do backtest mostra, e a explicação de por que a
        extrapolação fica *mais* ruim justamente onde prever seria mais útil.
        """
        historico = [snap(60, ha_minutos=30), snap(30)]

        previsao = trend_extrapolation(historico, horizon_minutes=horizonte)
        distancia_do_presente = abs(previsao.minutes - 30)

        assert distancia_do_presente == min(horizonte, 30)

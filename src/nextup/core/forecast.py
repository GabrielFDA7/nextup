"""Previsão da fila na chegada — e a medição que decidiu **não** implementá-la.

O NextUp responde "para onde ir agora" somando `caminhada + fila`. Mas a fila que
importa não é a de agora: é a que existirá quando o visitante chegar, dez ou quinze
minutos depois. Fechar essa lacuna era o objetivo da Fase 6.6.

**O resultado da medição foi negativo, e está registrado aqui porque é a parte
mais útil.** Um backtest sobre 315 medições reais do Magic Kingdom, em 20/09/2026,
comparou três modelos:

| Horizonte | Persistência | Tendência extrapolada |
|---|---|---|
| 5 min  | **1,86** | 2,66 |
| 10 min | **2,50** | 3,97 |
| 20 min | **3,44** | 6,13 |
| 30 min | **4,65** | 9,02 |

*(erro médio absoluto em minutos; menor é melhor)*

Extrapolar a tendência é pior em todo horizonte — e a vantagem da persistência não
vem de as filas ficarem paradas. Isolando só os casos em que a fila **mudou**, ela
continua ganhando: 6,42 contra 7,72 em dez minutos, 8,23 contra 13,19 em trinta.

A razão é que **a direção não persiste**. Uma fila que subiu nos últimos trinta
minutos tem chance parecida de cair nos próximos, e extrapolar amplifica o ruído
em vez de projetar o sinal.

**A conclusão prática:** o modelo que o NextUp já usava desde a Fase 2 — a fila de
agora — é o melhor disponível. O que mudou não foi o código do ranking; foi
passarmos a saber *por quê*, e a ter como provar.

Este módulo guarda os modelos e a régua que os compara, para que a medição possa
ser repetida quando houver mais dados — em especial sobre a previsão da própria
fonte, que só agora começou a ser gravada e por isso ainda não pôde ser avaliada.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from nextup.config import TREND_WINDOW_MINUTES
from nextup.models import QueueSnapshot


@dataclass(frozen=True)
class Prediction:
    """Uma previsão, com o rótulo de quem a fez.

    O nome do modelo viaja junto do número porque a avaliação compara modelos, e
    um número solto não diz de quem é o mérito nem a culpa.
    """

    model: str
    minutes: int
    horizon_minutes: float


def persistence(snapshots: Sequence[QueueSnapshot], *, horizon_minutes: float) -> Prediction | None:
    """*"A fila daqui a N minutos é a fila de agora."*

    Parece preguiça e é o campeão medido. Em séries temporais de horizonte curto a
    persistência é um baseline notoriamente difícil, e o tempo de caminhada dentro
    de um parque — de três a quinze minutos — é curtíssimo.

    Returns:
        A previsão, ou `None` sem nenhuma medição com fila.
    """
    ultima = _ultima_com_fila(snapshots)
    if ultima is None:
        return None

    return Prediction(
        model="persistence",
        minutes=ultima.wait_time_minutes,  # type: ignore[arg-type]
        horizon_minutes=horizon_minutes,
    )


def trend_extrapolation(
    snapshots: Sequence[QueueSnapshot],
    *,
    horizon_minutes: float,
    window_minutes: float = TREND_WINDOW_MINUTES,
    damping: float = 1.0,
) -> Prediction | None:
    """Projeta a inclinação recente da fila para a frente.

    **Medido como pior que a persistência** — ver o cabeçalho do módulo. Continua
    aqui porque um baseline ruim documentado vale mais que um baseline ausente: sem
    ele, a próxima pessoa tentaria a mesma ideia do zero.

    Args:
        snapshots: Histórico de uma atração.
        horizon_minutes: Quantos minutos à frente prever.
        window_minutes: Janela usada para medir a inclinação.
        damping: Fator de amortecimento sobre a projeção. Com 0.5, a fila anda
            metade do que a taxa sugere — reconhecendo que a direção não se
            sustenta.

    Returns:
        A previsão, nunca negativa: fila não fica abaixo de zero por mais que a
        conta mande.
    """
    com_fila = [s for s in snapshots if s.wait_time_minutes is not None]
    if len(com_fila) < 2:
        return None

    com_fila = sorted(com_fila, key=lambda s: s.observed_at)
    agora = com_fila[-1]
    inicio = _inicio_da_janela(com_fila, agora.observed_at, window_minutes)

    minutos = (agora.observed_at - inicio.observed_at).total_seconds() / 60
    if minutos <= 0:
        return persistence(snapshots, horizon_minutes=horizon_minutes)

    taxa = (agora.wait_time_minutes - inicio.wait_time_minutes) / minutos  # type: ignore[operator]
    previsto = agora.wait_time_minutes + taxa * horizon_minutes * damping  # type: ignore[operator]

    return Prediction(
        model="trend",
        minutes=max(0, round(previsto)),
        horizon_minutes=horizon_minutes,
    )


@dataclass(frozen=True)
class Evaluation:
    """O placar de um modelo contra o que de fato aconteceu."""

    model: str
    cases: int

    #: Erro médio absoluto, em minutos. A régua principal: diz de quanto o modelo
    #: erra numa previsão típica, na mesma unidade que o usuário lê na tela.
    mean_absolute_error: float

    #: Quantas vezes acertou o valor exato. A fonte reporta em passos de cinco
    #: minutos, então acertar na mosca é possível e frequente.
    exact_hits: int

    @property
    def hit_rate(self) -> float:
        """Fração de acertos exatos, de 0 a 1."""
        return self.exact_hits / self.cases if self.cases else 0.0


def evaluate(pairs: Sequence[tuple[Prediction, int]]) -> Evaluation | None:
    """Mede um modelo contra a realidade.

    Args:
        pairs: Pares `(previsão, fila que de fato aconteceu)`.

    Returns:
        O placar, ou `None` sem pares. `None` obriga quem chama a dizer "não havia
        dados", em vez de exibir um erro médio de zero que pareceria perfeição.
    """
    if not pairs:
        return None

    erros = [abs(previsao.minutes - real) for previsao, real in pairs]

    return Evaluation(
        model=pairs[0][0].model,
        cases=len(pairs),
        mean_absolute_error=round(sum(erros) / len(erros), 2),
        exact_hits=sum(1 for erro in erros if erro == 0),
    )


def _ultima_com_fila(snapshots: Sequence[QueueSnapshot]) -> QueueSnapshot | None:
    com_fila = [s for s in snapshots if s.wait_time_minutes is not None]
    return max(com_fila, key=lambda s: s.observed_at) if com_fila else None


def _inicio_da_janela(
    ordenados: Sequence[QueueSnapshot], agora: datetime, window_minutes: float
) -> QueueSnapshot:
    """A medição mais antiga que ainda está dentro da janela."""
    limite = agora - timedelta(minutes=window_minutes)

    for snapshot in ordenados:
        if snapshot.observed_at >= limite:
            return snapshot

    return ordenados[-1]

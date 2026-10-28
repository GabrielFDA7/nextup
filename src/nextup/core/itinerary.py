"""Roteiro — a ordem em que visitar os alvos (Fase 8.2).

O ranking responde *"para onde vou agora?"* e é **guloso**: escolhe o melhor neste
instante e nunca olha adiante. O roteiro responde *"em que ordem faço o que vim
fazer?"*, e aceita uma escolha pior agora para ganhar depois.

**O ganho foi medido antes deste módulo existir** (27/10/2026), num backtest sobre o
histórico, com 5 alvos e as filas reais como juiz:

| Estratégia | Contra o guloso |
|---|---|
| Plano supondo que as filas não mudam | **-7,7 min (-4,1%)**, vence 136 de 178 |
| Plano com o perfil horário | -5,0 min (-2,7%) |
| Plano que conhece o futuro (teto) | -14,2 min (-7,6%) |

O ganho vem quase todo da **geografia**, não da previsão: o guloso atravessa o
parque atrás da fila mais curta e depois atravessa de volta; o plano enxerga isso.
Planejar com o perfil horário rendeu *menos* que supor filas paradas. Por isso a
previsão aqui é **injetada** e a persistência é o padrão: trocar de previsor não
pode exigir tocar no otimizador — e só deve acontecer depois de um backtest.

> ⚠️ Ensaio sobre histórico fragmentado (85% dos cenários descartados por falta de
> dado). Repetir sobre coleta contínua antes de construir a interface (8.4).

O tempo aqui é sempre **minutos a partir de agora**, e não data e hora: quem chama
converte. Assim o módulo não precisa saber de fuso, como o resto do `core/`.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from nextup.config import ITINERARY_MAX_STOPS, RIDE_DURATION_MINUTES

#: `(atração, daqui a quantos minutos) -> fila prevista em minutos`.
WaitPredictor = Callable[[str, float], float]


@dataclass(frozen=True)
class Stop:
    """Uma parada do roteiro, com a conta aberta — como `Recommendation`."""

    attraction_id: str
    walking_minutes: float
    predicted_wait_minutes: float

    #: Minutos a partir de agora em que o visitante chega à fila.
    arrival_minute: float

    #: Minutos a partir de agora em que ele sai da atração, pronto para a próxima.
    departure_minute: float


@dataclass(frozen=True)
class Itinerary:
    """As próximas paradas, na ordem em que compensa fazê-las."""

    stops: tuple[Stop, ...]

    @property
    def total_minutes(self) -> float:
        """Quanto tempo leva para concluir todas as paradas planejadas."""
        return self.stops[-1].departure_minute if self.stops else 0.0

    @property
    def next_stop(self) -> Stop | None:
        """A única parada que importa agora: o resto será replanejado ao concluí-la."""
        return self.stops[0] if self.stops else None


def persistence(current_waits: Mapping[str, float]) -> WaitPredictor:
    """O previsor padrão: *a fila de cada atração vai continuar como está agora*.

    É o campeão medido duas vezes no horizonte curto (6.6 e avaliação do forecast),
    e no roteiro rendeu mais que o perfil horário. Recebe só atrações com fila
    medida — quem chama filtra com `is_rankable`, como no ranking.
    """
    return lambda attraction_id, _minutes_ahead: current_waits[attraction_id]


def plan_itinerary(
    start_walk: Mapping[str, float],
    walk_matrix: Mapping[str, Mapping[str, float]],
    targets: Sequence[str],
    predict_wait: WaitPredictor,
    *,
    ride_minutes: float = RIDE_DURATION_MINUTES,
    max_stops: int = ITINERARY_MAX_STOPS,
) -> Itinerary:
    """A ordem das próximas paradas que termina mais cedo.

    Testa as ordens possíveis por *branch and bound*: monta as sequências parada a
    parada e abandona um ramo assim que o começo dele já gasta mais tempo que a
    melhor sequência completa encontrada. O resultado é o mesmo de testar todas as
    ordens uma a uma — só que sem visitar os ramos que não têm como ganhar.

    Args:
        start_walk: Minutos de caminhada do visitante até cada alvo.
        walk_matrix: Minutos de caminhada entre atrações (`geo.travel_time_matrix`).
        targets: As atrações que o visitante quer fazer.
        predict_wait: A fila prevista de uma atração daqui a N minutos.
        ride_minutes: Tempo dentro de cada atração.
        max_stops: Quantas paradas planejar. Com mais alvos que isso, o roteiro
            escolhe quais fazer primeiro; o resto entra no replanejamento.

    Returns:
        O roteiro, vazio se não houver alvos. Empate entre ordens se resolve pela
        ordem alfabética dos identificadores, para o mesmo pedido dar sempre a
        mesma resposta.
    """
    alvos = sorted(set(targets))
    profundidade = min(max_stops, len(alvos))

    melhor: list[Stop] = []
    melhor_fim = float("inf")
    caminho: list[Stop] = []

    def explorar(onde: str | None, agora: float, restantes: list[str]) -> None:
        nonlocal melhor, melhor_fim

        if len(caminho) == profundidade:
            if agora < melhor_fim:
                melhor, melhor_fim = list(caminho), agora
            return

        for i, alvo in enumerate(restantes):
            andar = start_walk[alvo] if onde is None else walk_matrix[onde][alvo]
            chegada = agora + andar
            fila = predict_wait(alvo, chegada)
            saida = chegada + fila + ride_minutes

            # A poda: se só até aqui já não ganha do recorde, nenhuma continuação
            # deste ramo ganha — o tempo só cresce.
            if saida >= melhor_fim:
                continue

            caminho.append(Stop(alvo, andar, fila, chegada, saida))
            explorar(alvo, saida, restantes[:i] + restantes[i + 1 :])
            caminho.pop()

    explorar(None, 0.0, alvos)
    return Itinerary(stops=tuple(melhor))

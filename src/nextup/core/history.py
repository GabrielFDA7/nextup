"""Resumo de um histórico de filas: como a fila **esteve**.

Irmão de `core/trends.py`, e a diferença entre os dois é a pergunta que respondem:
*trends* diz para onde a fila vai, *history* diz por onde ela passou. A primeira
orienta a decisão de agora; a segunda dá o contexto que torna a decisão
compreensível — "25 minutos" significa coisas opostas numa atração que varia entre
20 e 30 e noutra que varia entre 5 e 90.

Como todo módulo do `core/`, é função pura: entra lista de `QueueSnapshot`, sai
número. Sem rede, sem banco.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from nextup.models import QueueSnapshot


@dataclass(frozen=True)
class HistorySummary:
    """Os números que resumem uma série de medições de fila."""

    #: Quantas medições **com fila** entraram na conta. Não é o total de
    #: snapshots: períodos de atração fechada ficam de fora.
    measurements: int

    min_minutes: int
    max_minutes: int
    average_minutes: float

    #: A medição mais recente da série. É o que dá sentido às outras três: saber
    #: que a média é 30 só ajuda se souber onde a fila está agora.
    current_minutes: int

    @property
    def spread(self) -> int:
        """Diferença entre o pico e o vale.

        Mede o quanto vale a pena escolher a hora: uma atração que oscila entre 5 e
        90 recompensa quem espera o momento certo; uma que fica entre 20 e 30 não.
        """
        return self.max_minutes - self.min_minutes


def summarize(snapshots: Iterable[QueueSnapshot]) -> HistorySummary | None:
    """Resume uma série de medições de uma atração.

    Ignora snapshots sem fila — atração fechada ou sem medida. Incluí-los como
    zero puxaria a média para baixo e faria a madrugada parecer o melhor horário
    para visitar, o que é verdade e é inútil.

    Args:
        snapshots: Histórico de **uma** atração. Ordem não importa, exceto para
            determinar qual é a medição atual, que sai do `observed_at` mais
            recente.

    Returns:
        O resumo, ou `None` quando não houve nenhuma medição com fila. `None`
        obriga quem chama a decidir o que exibir, em vez de receber zeros que
        parecem dados.
    """
    com_fila = [s for s in snapshots if s.wait_time_minutes is not None]

    if not com_fila:
        return None

    filas = [s.wait_time_minutes for s in com_fila]
    mais_recente = max(com_fila, key=lambda s: s.observed_at)

    # `is not None` garantido pelo filtro; as asserções documentam para o tipo.
    assert mais_recente.wait_time_minutes is not None

    return HistorySummary(
        measurements=len(com_fila),
        min_minutes=min(filas),  # type: ignore[type-var]
        max_minutes=max(filas),  # type: ignore[type-var]
        # Uma casa decimal: a fonte reporta em passos de 5, e uma média com seis
        # casas sugeriria uma precisão que o dado de origem não tem.
        average_minutes=round(sum(filas) / len(filas), 1),  # type: ignore[arg-type]
        current_minutes=mais_recente.wait_time_minutes,
    )

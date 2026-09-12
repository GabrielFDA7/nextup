"""Motor de recomendação — o coração do NextUp.

Responde **"para onde eu devo ir agora?"**, que é diferente de "onde está a menor
fila". A diferença é o projeto inteiro:

    A menor fila pode estar a 900 metros. O visitante andaria 13 minutos para
    economizar 10 — e sairia perdendo.

Por isso o ranking é por `custo_total = caminhada + fila`, nunca pela fila isolada.
É a tradução em código do que o consultor de parque faz de cabeça.

Como manda a arquitetura, aqui não existe rede: este módulo recebe objetos já
prontos e devolve uma ordenação. Seus testes rodam offline, em milissegundos, e
nunca falham porque a internet caiu ou o parque fechou.
"""

from dataclasses import dataclass

from nextup.config import DEFAULT_RESULT_LIMIT, PATH_WINDING_FACTOR, WALKING_SPEED_MPS
from nextup.core.geo import travel_time_minutes
from nextup.models import LiveDataResponse, Location, ParkCatalog, ParkEntity


@dataclass(frozen=True)
class Recommendation:
    """Uma atração avaliada, com a conta aberta.

    Guardar as duas parcelas separadas — e não só o total — é o que permite
    explicar a recomendação. Uma resposta que o visitante entende é uma resposta
    em que ele confia.
    """

    attraction: ParkEntity
    walking_minutes: float
    queue_minutes: int

    @property
    def total_minutes(self) -> float:
        """O custo que ordena o ranking: tempo até estar sentado no brinquedo."""
        return self.walking_minutes + self.queue_minutes

    def explain(self) -> str:
        """Justificativa legível, no formato do consultor humano.

        Exemplo: `Big Thunder Mountain — 4 min de caminhada + 20 min de fila = 24 min`
        """
        return (
            f"{self.attraction.name} — "
            f"{round(self.walking_minutes)} min de caminhada + "
            f"{self.queue_minutes} min de fila = "
            f"{round(self.total_minutes)} min"
        )


def recommend(
    *,
    catalog: ParkCatalog,
    live: LiveDataResponse,
    visitor: Location,
    limit: int = DEFAULT_RESULT_LIMIT,
    speed_mps: float = WALKING_SPEED_MPS,
    winding_factor: float = PATH_WINDING_FACTOR,
) -> list[Recommendation]:
    """Ordena as atrações pelo tempo total até o visitante estar no brinquedo.

    Cruza as duas respostas da API porque nenhuma basta sozinha: o catálogo diz
    o que é atração e onde ela fica; o live diz qual é a fila agora.

    Args:
        catalog: Catálogo do parque, com as coordenadas.
        live: Estado atual das atrações.
        visitor: Onde o visitante está.
        limit: Quantas devolver. Zero ou menos devolve todas.
        speed_mps: Velocidade de caminhada, em metros por segundo.
        winding_factor: Correção do trajeto real sobre a linha reta.

    Returns:
        Recomendações em ordem crescente de custo total. Lista vazia é resposta
        legítima — parque fechado de madrugada, por exemplo.
    """
    estado_por_id = live.by_id()
    avaliadas = []

    for atracao in catalog.attractions():
        estado = estado_por_id.get(atracao.id)

        # Filtro eliminatório: sem dado ao vivo, fechada, quebrada ou sem fila
        # medida, não há custo que se possa calcular honestamente.
        if estado is None or not estado.is_rankable:
            continue

        # `attractions()` já garante que a coordenada existe; a checagem abaixo
        # é o que permite ao verificador de tipos saber disso também.
        if atracao.location is None:
            continue

        caminhada = travel_time_minutes(
            visitor.latitude,
            visitor.longitude,
            atracao.location.latitude,
            atracao.location.longitude,
            speed_mps=speed_mps,
            winding_factor=winding_factor,
        )

        avaliadas.append(
            Recommendation(
                attraction=atracao,
                walking_minutes=caminhada,
                # `is_rankable` garante que não é `None`.
                queue_minutes=estado.wait_time_minutes,  # type: ignore[arg-type]
            )
        )

    avaliadas.sort(key=lambda r: r.total_minutes)

    return avaliadas if limit <= 0 else avaliadas[:limit]

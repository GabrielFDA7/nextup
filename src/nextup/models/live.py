"""Modelos dos dados ao vivo: fila e status de agora.

É a resposta de `/entity/{id}/live` — o único dado do projeto que muda de minuto
em minuto, e a metade do `custo_total = caminhada + fila` que o NextUp calcula.

A descoberta que molda estes modelos: **estar `OPERATING` não significa ter tempo
de fila**. O Castelo da Cinderela e o Walt Disney World Railroad estão abertos e
não têm fila nenhuma para reportar. Por isso "dá para ranquear" é uma pergunta
separada de "está aberto", respondida por `LiveData.is_rankable`.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class LiveStatus(StrEnum):
    """Situação de uma entidade agora."""

    OPERATING = "OPERATING"
    CLOSED = "CLOSED"

    #: Parada por problema técnico — costuma voltar no mesmo dia.
    DOWN = "DOWN"

    #: Fechada para reforma — não volta tão cedo.
    REFURBISHMENT = "REFURBISHMENT"

    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value: object) -> "LiveStatus":
        """Status novo na API não pode derrubar o parque inteiro. Ver `EntityType`."""
        return cls.UNKNOWN


class StandbyQueue(BaseModel):
    """A fila comum, de quem não pagou para furar."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    #: Nulo é comum e não é erro: atração aberta que simplesmente não mede fila,
    #: ou que está fechada no momento.
    wait_time: int | None = Field(alias="waitTime", default=None, ge=0)


class Queue(BaseModel):
    """As filas de uma atração.

    A API também expõe `RETURN_TIME` e `PAID_RETURN_TIME` (o Lightning Lane).
    O MVP ranqueia pela fila comum, então só ela é modelada — o resto é ignorado
    sem quebrar nada.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    standby: StandbyQueue | None = Field(alias="STANDBY", default=None)


class LiveData(BaseModel):
    """Estado atual de uma entidade do parque."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: LiveStatus

    #: Ausente em boa parte dos itens — shows e restaurantes não têm fila.
    queue: Queue | None = None

    #: Quando a fonte atualizou este dado. Serve para avisar o usuário que a
    #: informação está velha, em vez de apresentar dado defasado como se fosse atual.
    last_updated: datetime = Field(alias="lastUpdated")

    @property
    def wait_time_minutes(self) -> int | None:
        """Minutos de fila comum, ou `None` quando a atração não reporta fila."""
        if self.queue is None or self.queue.standby is None:
            return None
        return self.queue.standby.wait_time

    @property
    def is_rankable(self) -> bool:
        """Se esta entidade pode entrar no ranking do NextUp.

        Exige as duas coisas: estar operando *e* ter tempo de fila. Sem o segundo,
        não há como calcular `custo_total = caminhada + fila`.
        """
        return self.status is LiveStatus.OPERATING and self.wait_time_minutes is not None


class LiveDataResponse(BaseModel):
    """Envelope de `/entity/{id}/live`."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    live_data: list[LiveData] = Field(alias="liveData")

    def by_id(self) -> dict[str, LiveData]:
        """Indexa os dados por ID da entidade.

        O passo seguinte do projeto cruza este resultado com o catálogo, que traz
        as coordenadas. Percorrer a lista inteira para cada atração seria lento e
        desnecessário: um dicionário resolve cada busca de uma vez só.
        """
        return {item.id: item for item in self.live_data}

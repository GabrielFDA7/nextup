"""Modelos do catálogo de um parque.

É a resposta de `/entity/{id}/children`: tudo que existe dentro do parque —
atrações, shows e restaurantes — cada um com sua coordenada GPS. É daqui que sai
a matéria-prima do NextUp, já que sem coordenada não há como calcular distância.

A API devolve os três tipos misturados na mesma lista. Por isso o modelo se chama
`ParkEntity`, e não `Attraction`: chamar um restaurante de atração seria mentir
sobre o que o objeto é. Quem quer só as atrações pede por elas em
`ParkCatalog.attractions()`.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EntityType(StrEnum):
    """Tipo de entidade dentro de um parque.

    Herdar de `StrEnum` faz cada membro se comportar como texto comum: dá para
    comparar com `"ATTRACTION"` e imprimir sem conversão.
    """

    ATTRACTION = "ATTRACTION"
    SHOW = "SHOW"
    RESTAURANT = "RESTAURANT"
    PARK = "PARK"
    DESTINATION = "DESTINATION"
    HOTEL = "HOTEL"

    #: Rede de segurança: a API pode inventar um tipo novo amanhã.
    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value: object) -> "EntityType":
        """Chamado pelo Python quando o valor recebido não é nenhum dos membros.

        Sem isso, um tipo novo na API viraria erro de validação e derrubaria o
        catálogo inteiro do parque — 86 itens perdidos porque um deles é de um
        tipo que ainda não conhecemos. Cair em `UNKNOWN` deixa o resto passar.
        """
        return cls.UNKNOWN


class Location(BaseModel):
    """Coordenada GPS de um ponto do parque."""

    model_config = ConfigDict(frozen=True)

    # Latitude vai de -90 a 90 e longitude de -180 a 180. Um valor fora disso não
    # é "um lugar estranho", é dado corrompido — e faria a Haversine devolver uma
    # distância sem sentido, sem reclamar de nada.
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)


class ParkEntity(BaseModel):
    """Um item do catálogo do parque: atração, show ou restaurante."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)

    #: A API escreve `entityType`; em Python o nome idiomático é `entity_type`.
    #: O `alias` faz a ponte entre os dois mundos sem contaminar o nosso código.
    entity_type: EntityType = Field(alias="entityType")

    #: Opcional de propósito. Nos parques verificados toda entidade tem coordenada,
    #: mas se um dia faltar uma, é melhor perder uma atração do ranking do que
    #: derrubar o catálogo inteiro.
    location: Location | None = None

    @field_validator("location", mode="before")
    @classmethod
    def coordenada_incompleta_vira_ausente(cls, valor: Any) -> Any:
        """Trata `{"latitude": null, "longitude": null}` como "sem coordenada".

        A API tem duas formas de dizer que não sabe onde algo fica: omitir o campo
        `location` — que o `| None` acima já cobre — **ou** mandá-lo preenchido com
        nulos dentro. A segunda forma derrubava o catálogo inteiro.

        E derrubava o parque todo, não só o item: o `pydantic` valida a lista de
        uma vez, então uma entidade sem coordenada invalidava as outras oitenta.
        Foi o que manteve o **Disneyland Paris inacessível** no NextUp desde a
        Fase 1 — o app respondia 502 e a interface dizia "formato inesperado",
        sem que ninguém desconfiasse de que o problema era uma atração sem GPS.

        É a mesma degradação graciosa do `EntityType._missing_`: perder um item é
        aceitável, perder o parque não. Aqui a entidade continua no catálogo, com
        nome e tipo — só fica de fora do ranking, onde de fato não daria para
        calcular distância.
        """
        if isinstance(valor, dict) and (
            valor.get("latitude") is None or valor.get("longitude") is None
        ):
            return None
        return valor


class ParkCatalog(BaseModel):
    """Envelope de `/entity/{id}/children` — o parque e tudo que há dentro dele."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)

    #: Fuso do parque, como "America/New_York". Necessário para responder
    #: "o parque está aberto agora?" sem errar por causa do fuso do servidor.
    timezone: str = Field(min_length=1)

    children: list[ParkEntity]

    def attractions(self) -> list[ParkEntity]:
        """Só as atrações que o NextUp consegue ranquear.

        Filtra duas coisas de uma vez: o tipo (fora shows e restaurantes) e a
        presença de coordenada, sem a qual não há distância para calcular.
        """
        return [
            entity
            for entity in self.children
            if entity.entity_type is EntityType.ATTRACTION and entity.location is not None
        ]

    def attraction_ids(self) -> set[str]:
        """IDs de tudo que é atração, **tenha coordenada ou não**.

        Deliberadamente mais permissivo que `attractions()`, e a diferença importa
        para o coletor: coordenada é requisito para *ranquear*, não para *ter
        histórico*. Se uma atração hoje sem coordenada ganhar uma amanhã, ela entra
        no ranking já com semanas de histórico acumulado — enquanto o filtro mais
        estrito teria jogado esse passado fora, e passado não se recupera.

        Devolve um conjunto porque o uso é sempre o mesmo: perguntar se um ID está
        dentro. Num conjunto essa pergunta custa o mesmo com 30 ou 30 mil itens.
        """
        return {
            entity.id for entity in self.children if entity.entity_type is EntityType.ATTRACTION
        }

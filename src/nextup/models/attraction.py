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

from pydantic import BaseModel, ConfigDict, Field


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

"""Modelos de destino e parque.

Um *destino* é o complexo inteiro — "Walt Disney World Resort". Dentro dele ficam
os *parques* — Magic Kingdom, EPCOT, Hollywood Studios. É a resposta do endpoint
`/destinations`, o ponto de partida para descobrir o ID de qualquer parque.

Estes modelos são a fronteira entre o mundo de fora e o nosso: depois que o JSON
da ThemeParks.wiki vira um `Destination`, nenhuma outra parte do NextUp precisa
saber como a API escreve as coisas.
"""

from pydantic import BaseModel, ConfigDict, Field


class Park(BaseModel):
    """Um parque dentro de um destino.

    A API devolve só `id` e `name` aqui. O resto — atrações, coordenadas, filas —
    vem depois, em `/entity/{id}/children` e `/entity/{id}/live`, usando este `id`.
    """

    # Objetos vindos da API são retrato de um dado externo: se alguém precisar de
    # um valor diferente, cria outro objeto em vez de editar este por baixo dos panos.
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class Destination(BaseModel):
    """Um complexo de parques, como Walt Disney World Resort."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)

    #: Identificador legível, como "waltdisneyworldresort". Bem mais amigável que
    #: o UUID na hora de digitar um comando ou montar uma URL.
    slug: str = Field(min_length=1)

    parks: list[Park]

    def find_park(self, park_id: str) -> Park | None:
        """Procura um parque deste destino pelo ID. Devolve `None` se não achar."""
        return next((park for park in self.parks if park.id == park_id), None)


class DestinationList(BaseModel):
    """Envelope do `/destinations`.

    A API não devolve uma lista solta: devolve `{"destinations": [...]}`. Modelar
    o envelope deixa explícito o formato real e evita que cada chamador lembre de
    procurar a chave certa.
    """

    destinations: list[Destination]

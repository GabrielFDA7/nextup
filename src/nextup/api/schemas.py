"""Contratos de entrada e saída da API.

Estes modelos existem **separados** dos de `models/`, e a separação é proposital.

`models/` descreve o que a ThemeParks.wiki manda. Estes descrevem o que o NextUp
promete devolver. São coisas diferentes, e misturá-las causa dois problemas:

1. **Vazamento.** Devolvendo o modelo interno, qualquer campo que ele ganhe passa
   a fazer parte do contrato público sem ninguém decidir isso.
2. **Acoplamento.** Se a ThemeParks.wiki renomear um campo amanhã, a resposta do
   NextUp mudaria junto — quebrando o site de quem nos consome por um motivo que
   não é nosso.

Com a fronteira aqui, a API pode manter sua forma mesmo que tudo mude por dentro.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from nextup.core.recommender import Recommendation
from nextup.models import Destination, ParkCatalog


class AttractionOut(BaseModel):
    """Uma atração, como o NextUp a expõe."""

    id: str
    name: str

    #: A coordenada sai achatada, sem o objeto `location` aninhado: quem desenha
    #: o mapa na tela quer `lat`/`lon` diretos.
    latitude: float
    longitude: float


class RecommendationOut(BaseModel):
    """Uma atração avaliada, com a conta aberta."""

    attraction: AttractionOut
    walking_minutes: float = Field(description="Tempo estimado de caminhada, em minutos.")
    queue_minutes: int = Field(description="Fila comum informada pela fonte, em minutos.")
    total_minutes: float = Field(description="Caminhada + fila. É o que ordena o ranking.")
    explanation: str = Field(description="Justificativa legível da recomendação.")

    @classmethod
    def from_domain(cls, recomendacao: Recommendation) -> "RecommendationOut":
        atracao = recomendacao.attraction
        # `recommend()` só devolve atrações com coordenada, mas o tipo continua
        # opcional; a asserção documenta a garantia em vez de escondê-la.
        assert atracao.location is not None

        return cls(
            attraction=AttractionOut(
                id=atracao.id,
                name=atracao.name,
                latitude=atracao.location.latitude,
                longitude=atracao.location.longitude,
            ),
            # Arredondar aqui evita devolver 17.727272727272727 para o navegador.
            walking_minutes=round(recomendacao.walking_minutes, 1),
            queue_minutes=recomendacao.queue_minutes,
            total_minutes=round(recomendacao.total_minutes, 1),
            explanation=recomendacao.explain(),
        )


class RecommendationsOut(BaseModel):
    """Resposta de `/parks/{id}/recommendations`."""

    park_id: str
    park_name: str

    total_attractions: int = Field(description="Atrações no catálogo do parque.")

    #: Quantas passaram nos filtros — **não** quantas foram devolvidas. Com
    #: `limit=5` num parque com 26 disponíveis, este campo diz 26, e a lista vem
    #: com 5. Confundir os dois faria a tela mentir sobre o tamanho do parque.
    available: int = Field(description="Quantas estavam operando e com fila informada.")

    #: Quando a **fonte** atualizou o dado, não quando respondemos. É o que
    #: permite à tela avisar que a informação está velha, em vez de apresentar
    #: fila defasada como se fosse atual.
    data_updated_at: datetime | None = None

    recommendations: list[RecommendationOut]

    @classmethod
    def from_domain(
        cls,
        catalogo: ParkCatalog,
        recomendacoes: list[Recommendation],
        limite: int,
        data_updated_at: datetime | None,
    ) -> "RecommendationsOut":
        """Monta a resposta.

        Recebe o ranking **inteiro** e corta aqui, para que `available` conte as
        disponíveis de verdade e não o limite pedido.
        """
        mostradas = recomendacoes if limite <= 0 else recomendacoes[:limite]

        return cls(
            park_id=catalogo.id,
            park_name=catalogo.name,
            total_attractions=len(catalogo.attractions()),
            available=len(recomendacoes),
            data_updated_at=data_updated_at,
            recommendations=[RecommendationOut.from_domain(r) for r in mostradas],
        )


class ParkOut(BaseModel):
    id: str
    name: str


class DestinationOut(BaseModel):
    """Um complexo de parques, como Walt Disney World Resort."""

    id: str
    name: str
    slug: str
    parks: list[ParkOut]

    @classmethod
    def from_domain(cls, destino: Destination) -> "DestinationOut":
        return cls(
            id=destino.id,
            name=destino.name,
            slug=destino.slug,
            parks=[ParkOut(id=p.id, name=p.name) for p in destino.parks],
        )


class DestinationsOut(BaseModel):
    """Resposta de `/destinations`."""

    destinations: list[DestinationOut]


class HealthOut(BaseModel):
    """Resposta de `/health` — usada por Docker e pelo serviço de deploy."""

    status: str
    version: str


class ErrorOut(BaseModel):
    """Formato único de erro da API.

    Ter um só formato permite que o frontend trate qualquer falha com o mesmo
    código, em vez de adivinhar o formato caso a caso.
    """

    detail: str

"""Endpoints da API.

**Zero regra de negócio aqui.** Cada rota faz sempre a mesma coisa: lê os
parâmetros, chama quem sabe resolver e formata a resposta. Quem decide a ordem do
ranking é `core/recommender.py`; quem fala com a ThemeParks.wiki é
`clients/themeparks.py`.

O teste disso é simples: se você precisar mudar a regra de recomendação, não pode
precisar abrir este arquivo.
"""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from nextup import __version__
from nextup.api.dependencies import obter_cliente
from nextup.api.schemas import (
    DestinationOut,
    DestinationsOut,
    HealthOut,
    RecommendationsOut,
)
from nextup.clients.themeparks import ThemeParksClient
from nextup.config import DEFAULT_RESULT_LIMIT
from nextup.core.recommender import recommend
from nextup.models import Location

router = APIRouter()

#: O cliente compartilhado, entregue pelo FastAPI a quem declarar este tipo.
#: `Annotated` junta "o tipo é este" com "de onde ele vem" numa anotação só —
#: forma preferida hoje, e que mantém o valor padrão do parâmetro livre.
ClienteThemeParks = Annotated[ThemeParksClient, Depends(obter_cliente)]


@router.get("/health", response_model=HealthOut, tags=["sistema"])
async def health() -> HealthOut:
    """Diz se o serviço está de pé.

    Não consulta a ThemeParks.wiki de propósito: quem monitora quer saber se o
    **NextUp** está no ar, e uma instabilidade da fonte externa não deveria fazer
    o orquestrador reiniciar nosso contêiner.
    """
    return HealthOut(status="ok", version=__version__)


@router.get("/destinations", response_model=DestinationsOut, tags=["catálogo"])
async def listar_destinos(cliente: ClienteThemeParks) -> DestinationsOut:
    """Destinos e seus parques, com os IDs usados nas demais rotas."""
    destinos = await cliente.get_destinations()

    return DestinationsOut(
        destinations=[DestinationOut.from_domain(d) for d in destinos.destinations]
    )


@router.get(
    "/parks/{park_id}/recommendations",
    response_model=RecommendationsOut,
    tags=["recomendação"],
)
async def recomendar(
    cliente: ClienteThemeParks,
    park_id: Annotated[str, Path(description="ID do parque, obtido em `/destinations`.")],
    lat: Annotated[float, Query(ge=-90, le=90, description="Latitude do visitante.")],
    lon: Annotated[float, Query(ge=-180, le=180, description="Longitude do visitante.")],
    limit: Annotated[
        int,
        Query(ge=0, le=100, description="Quantas devolver. Zero devolve todas."),
    ] = DEFAULT_RESULT_LIMIT,
) -> RecommendationsOut:
    """Para onde ir agora, ordenado por `caminhada + fila`.

    A menor fila não vence automaticamente: uma fila de 10 minutos a 900 metros
    custa mais tempo total que uma de 20 minutos ao lado.
    """
    # Independentes entre si, então vão juntas: o tempo total passa a ser o da
    # mais lenta, e não a soma das duas.
    catalogo, ao_vivo = await asyncio.gather(
        cliente.get_park_catalog(park_id),
        cliente.get_live_data(park_id),
    )

    # Pede o ranking completo: quem corta é o schema, para `available` contar as
    # atrações realmente disponíveis em vez do limite pedido.
    recomendacoes = recommend(
        catalog=catalogo,
        live=ao_vivo,
        visitor=Location(latitude=lat, longitude=lon),
        limit=0,
    )

    atualizado_em = max(
        (item.last_updated for item in ao_vivo.live_data),
        default=None,
    )

    return RecommendationsOut.from_domain(catalogo, recomendacoes, limit, atualizado_em)

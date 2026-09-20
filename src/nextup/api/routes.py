"""Endpoints da API.

**Zero regra de negócio aqui.** Cada rota faz sempre a mesma coisa: lê os
parâmetros, chama quem sabe resolver e formata a resposta. Quem decide a ordem do
ranking é `core/recommender.py`; quem fala com a ThemeParks.wiki é
`clients/themeparks.py`.

O teste disso é simples: se você precisar mudar a regra de recomendação, não pode
precisar abrir este arquivo.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from nextup import __version__
from nextup.api.dependencies import obter_cliente, obter_engine
from nextup.api.schemas import (
    AttractionHistoryOut,
    DestinationOut,
    DestinationsOut,
    HealthOut,
    ParkAttractionsOut,
    RecommendationsOut,
)
from nextup.clients.errors import EntityNotFoundError
from nextup.clients.themeparks import ThemeParksClient
from nextup.config import (
    DEFAULT_HISTORY_HOURS,
    DEFAULT_RESULT_LIMIT,
    MAX_HISTORY_HOURS,
    TREND_WINDOW_MINUTES,
)
from nextup.core.history import summarize
from nextup.core.recommender import recommend
from nextup.core.trends import TrendAnalysis, analyze, analyze_many
from nextup.models import Location
from nextup.storage import connection, history, park_history

logger = logging.getLogger(__name__)

router = APIRouter()

#: O cliente compartilhado, entregue pelo FastAPI a quem declarar este tipo.
#: `Annotated` junta "o tipo é este" com "de onde ele vem" numa anotação só —
#: forma preferida hoje, e que mantém o valor padrão do parâmetro livre.
ClienteThemeParks = Annotated[ThemeParksClient, Depends(obter_cliente)]

#: O banco, que pode não existir. Ver `obter_engine`.
MotorDoBanco = Annotated[AsyncEngine | None, Depends(obter_engine)]


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
    "/parks/{park_id}/attractions",
    response_model=ParkAttractionsOut,
    tags=["catálogo"],
)
async def listar_atracoes(
    cliente: ClienteThemeParks,
    park_id: Annotated[str, Path(description="ID do parque, obtido em `/destinations`.")],
) -> ParkAttractionsOut:
    """Como está o parque agora — **sem** precisar saber onde o visitante está.

    Existe porque "para onde eu vou?" e "como está o parque?" são perguntas
    diferentes, e só a primeira exige uma posição. Até aqui o NextUp só sabia
    responder a primeira, então quem abrisse o site sem liberar o GPS não via nada.

    Também devolve `bounds`, o retângulo que contém as atrações: é o que permite
    ao mapa enquadrar o parque escolhido em vez de continuar apontando para onde
    estava antes.
    """
    catalogo, ao_vivo = await asyncio.gather(
        cliente.get_park_catalog(park_id),
        cliente.get_live_data(park_id),
    )

    atualizado_em = max((item.last_updated for item in ao_vivo.live_data), default=None)

    return ParkAttractionsOut.from_domain(catalogo, ao_vivo, atualizado_em)


@router.get(
    "/parks/{park_id}/attractions/{attraction_id}/history",
    response_model=AttractionHistoryOut,
    tags=["histórico"],
)
async def historico_da_atracao(
    cliente: ClienteThemeParks,
    motor: MotorDoBanco,
    park_id: Annotated[str, Path(description="ID do parque.")],
    attraction_id: Annotated[str, Path(description="ID da atração.")],
    hours: Annotated[
        int,
        Query(ge=1, le=MAX_HISTORY_HOURS, description="Tamanho da janela, em horas."),
    ] = DEFAULT_HISTORY_HOURS,
) -> AttractionHistoryOut:
    """Como a fila desta atração se comportou nas últimas horas.

    **O primeiro endpoint que serve dado nosso.** Tudo que veio antes era a
    ThemeParks.wiki reempacotada; isto só existe porque o coletor rodou — e é o
    que tira o projeto de "consome uma API" para "produz conhecimento próprio".

    O nome da atração vem do catálogo, não do banco: guardá-lo em cada snapshot
    seriam centenas de milhares de cópias da mesma string, e o catálogo já está em
    cache por 24 horas.

    Raises:
        HTTPException: 503 quando não há banco, ou ele está fora do ar. Aqui o
            histórico **é** a resposta — ao contrário da recomendação, onde ele é
            enfeite e a falha é engolida de propósito.
    """
    catalogo = await cliente.get_park_catalog(park_id)

    nomes = {entidade.id: entidade.name for entidade in catalogo.children}
    if attraction_id not in nomes:
        raise EntityNotFoundError(attraction_id)

    if motor is None:
        raise HTTPException(
            status_code=503,
            detail="O histórico ainda não está disponível neste ambiente.",
        )

    agora = datetime.now(UTC)
    desde = agora - timedelta(hours=hours)

    try:
        async with connection(motor) as conexao:
            serie = await history(conexao, attraction_id=attraction_id, since=desde)
    except SQLAlchemyError as erro:
        logger.warning("falha ao ler o histórico de %s", attraction_id, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="O histórico está indisponível no momento. Tente novamente em instantes.",
        ) from erro

    return AttractionHistoryOut.from_domain(
        park_id=park_id,
        attraction_id=attraction_id,
        attraction_name=nomes[attraction_id],
        hours=hours,
        snapshots=serie,
        resumo=summarize(serie),
        # Recalculada sobre a janela inteira, e não sobre os 30 min padrão: quem
        # pede 24 horas quer saber o movimento do dia, não o do último quarto de hora.
        tendencia=analyze(serie, now=agora, window_minutes=hours * 60),
    )


@router.get(
    "/parks/{park_id}/recommendations",
    response_model=RecommendationsOut,
    tags=["recomendação"],
)
async def recomendar(
    cliente: ClienteThemeParks,
    motor: MotorDoBanco,
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

    Quando há histórico, cada recomendação vem com a tendência da fila — que é o
    que explica **por que agora**. A tendência não muda a ordem.
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
        trends=await _tendencias(motor, park_id),
    )

    atualizado_em = max(
        (item.last_updated for item in ao_vivo.live_data),
        default=None,
    )

    return RecommendationsOut.from_domain(catalogo, recomendacoes, limit, atualizado_em)


async def _tendencias(motor: AsyncEngine | None, park_id: str) -> dict[str, TrendAnalysis] | None:
    """Lê o histórico recente do parque e calcula a tendência de cada atração.

    **Nunca deixa a recomendação falhar.** Sem banco configurado, ou com o banco
    fora do ar, devolve `None` e o ranking sai como sempre saiu — só sem a frase
    "caiu de 45 para 20". Perder um enfeite é aceitável; perder a resposta, não.

    Este é o único lugar da API que lê o histórico, e por isso o único que precisa
    do `try`. O alternativa seria cada rota lidar com isso — o mesmo raciocínio
    que pôs a tradução de erros num lugar só, em `main.py`.
    """
    if motor is None:
        return None

    agora = datetime.now(UTC)
    desde = agora - timedelta(minutes=TREND_WINDOW_MINUTES)

    try:
        async with connection(motor) as conexao:
            historico = await park_history(conexao, park_id=park_id, since=desde)
    except SQLAlchemyError:
        logger.warning("histórico indisponível; seguindo sem tendência", exc_info=True)
        return None

    return analyze_many(historico, now=agora)

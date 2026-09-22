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

from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel, Field

from nextup.core.geo import bounding_box
from nextup.core.history import HistorySummary
from nextup.core.recommender import Recommendation
from nextup.core.trends import Trend, TrendAnalysis
from nextup.models import (
    Destination,
    LiveDataResponse,
    LiveStatus,
    ParkCatalog,
    QueueSnapshot,
)


class AttractionOut(BaseModel):
    """Uma atração, como o NextUp a expõe."""

    id: str
    name: str

    #: A coordenada sai achatada, sem o objeto `location` aninhado: quem desenha
    #: o mapa na tela quer `lat`/`lon` diretos.
    latitude: float
    longitude: float


class TrendOut(BaseModel):
    """Para onde a fila está indo, com os números que sustentam a afirmação.

    Sai estruturada, e não só como frase pronta, porque a tela faz com ela o que
    texto não permite: escolher uma seta, pintar de verde ou vermelho, ordenar.
    A frase vem junto para quem só quer exibir.
    """

    direction: str = Field(description="FALLING, RISING ou STABLE.")
    previous_minutes: int = Field(description="Fila no início da janela.")
    current_minutes: int = Field(description="Fila na medição mais recente.")
    delta: int = Field(description="Variação em minutos. Negativo é fila caindo.")
    span_minutes: int = Field(description="Minutos entre as duas medições comparadas.")
    description: str = Field(description="Frase pronta, como 'Caiu de 45 para 20…'.")

    @classmethod
    def from_domain(cls, analise: TrendAnalysis) -> "TrendOut | None":
        """Devolve `None` para tendência desconhecida.

        O contrato público não deve ter um estado que significa "não sei": quem
        consome checa se o campo existe, em vez de comparar com uma string mágica.
        """
        if analise.direction is Trend.UNKNOWN:
            return None

        # Garantido por não ser UNKNOWN; a asserção documenta para o verificador.
        assert analise.previous_minutes is not None
        assert analise.current_minutes is not None

        return cls(
            direction=str(analise.direction),
            previous_minutes=analise.previous_minutes,
            current_minutes=analise.current_minutes,
            delta=analise.delta,
            span_minutes=round(analise.span_minutes),
            description=analise.describe(),
        )


class PopularityOut(BaseModel):
    """Quão disputada a atração costuma ser, comparada ao resto do parque.

    Sai como **faixa**, e a média vem junto só como apoio. O motivo está medido no
    cabeçalho de `core/popularity.py`: a coleta é mais densa no pico do meio-dia,
    o que infla o valor absoluto — mas infla todas as atrações igualmente, então a
    comparação entre elas sobrevive e o número isolado não.
    """

    tier: str = Field(description="HEADLINER, MODERATE, QUIET ou UNKNOWN.")
    average_minutes: float | None = Field(
        default=None, description="Fila média histórica, em minutos."
    )
    measurements: int = Field(description="Medições que entraram na conta.")
    opportunity: bool = Field(
        description="Principal do parque com fila hoje abaixo da média dela.",
    )

    @classmethod
    def from_domain(cls, recomendacao: Recommendation) -> "PopularityOut | None":
        if recomendacao.popularity is None:
            return None

        return cls(
            tier=recomendacao.popularity.tier.value,
            average_minutes=recomendacao.popularity.average_minutes,
            measurements=recomendacao.popularity.measurements,
            opportunity=recomendacao.is_opportunity,
        )


class RecommendationOut(BaseModel):
    """Uma atração avaliada, com a conta aberta."""

    attraction: AttractionOut
    walking_minutes: float = Field(description="Tempo estimado de caminhada, em minutos.")
    queue_minutes: int = Field(description="Fila comum informada pela fonte, em minutos.")
    total_minutes: float = Field(description="Caminhada + fila. É o que ordena o ranking.")
    explanation: str = Field(description="Justificativa legível da recomendação.")

    #: Ausente quando não há histórico suficiente — parque recém-incluído, ou
    #: coletor que subiu há pouco. A recomendação continua completa sem ela.
    trend: TrendOut | None = Field(
        default=None, description="Tendência da fila, quando há histórico."
    )

    #: Ausente pelos mesmos motivos da tendência. Presente com `tier: UNKNOWN`
    #: quando há banco mas o histórico desta atração é curto demais — que é
    #: diferente de ausente, e a tela trata os dois casos igual de propósito.
    popularity: PopularityOut | None = Field(
        default=None, description="Faixa de popularidade, quando há histórico."
    )

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
            trend=TrendOut.from_domain(recomendacao.trend) if recomendacao.trend else None,
            popularity=PopularityOut.from_domain(recomendacao),
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


class BoundsOut(BaseModel):
    """Os quatro cantos que enquadram o parque no mapa.

    Vai para a resposta porque o navegador não tem como calcular isto sem antes
    receber todas as atrações — e no momento em que ele precisa do enquadramento,
    ainda não recebeu.
    """

    south: float
    west: float
    north: float
    east: float


class ParkAttractionOut(BaseModel):
    """Uma atração do parque, com o estado de agora e **sem** distância.

    A ausência de `walking_minutes` é o ponto: esta resposta existe justamente
    para quem ainda não disse onde está.
    """

    id: str
    name: str
    latitude: float
    longitude: float

    status: str = Field(description="OPERATING, CLOSED, DOWN ou REFURBISHMENT.")

    #: Nulo é resposta legítima, não falha: atração fechada, ou aberta sem fila
    #: medida — o que acontece com cerca de uma em cada cinco.
    queue_minutes: int | None = Field(
        default=None, description="Fila comum em minutos, ou nulo se não houver medida."
    )


class ParkAttractionsOut(BaseModel):
    """Resposta de `/parks/{id}/attractions`.

    Complementa a rota de recomendações em vez de substituí-la. A de recomendações
    responde *"para onde eu vou agora?"* e exige saber onde o visitante está; esta
    responde *"como está o parque?"*, que é uma pergunta legítima antes disso —
    e era impossível de fazer ao NextUp até agora.
    """

    park_id: str
    park_name: str
    timezone: str = Field(description="Fuso do parque, como America/New_York.")

    bounds: BoundsOut | None = Field(
        default=None, description="Retângulo que contém as atrações. Nulo se não houver nenhuma."
    )

    total_attractions: int
    available: int = Field(description="Quantas estão operando e com fila informada.")
    data_updated_at: datetime | None = None

    attractions: list[ParkAttractionOut]

    @classmethod
    def from_domain(
        cls,
        catalogo: ParkCatalog,
        ao_vivo: LiveDataResponse,
        data_updated_at: datetime | None,
    ) -> "ParkAttractionsOut":
        estado_por_id = ao_vivo.by_id()
        atracoes = catalogo.attractions()

        saida = []
        disponiveis = 0

        for atracao in atracoes:
            # `attractions()` já garante a coordenada; a checagem é o que permite
            # ao verificador de tipos saber disso também.
            if atracao.location is None:
                continue

            estado = estado_por_id.get(atracao.id)
            if estado is not None and estado.is_rankable:
                disponiveis += 1

            saida.append(
                ParkAttractionOut(
                    id=atracao.id,
                    name=atracao.name,
                    latitude=atracao.location.latitude,
                    longitude=atracao.location.longitude,
                    status=str(estado.status) if estado else str(LiveStatus.UNKNOWN),
                    queue_minutes=estado.wait_time_minutes if estado else None,
                )
            )

        caixa = bounding_box(
            (a.location.latitude, a.location.longitude) for a in atracoes if a.location is not None
        )

        return cls(
            park_id=catalogo.id,
            park_name=catalogo.name,
            timezone=catalogo.timezone,
            bounds=BoundsOut(**vars(caixa)) if caixa else None,
            total_attractions=len(atracoes),
            available=disponiveis,
            data_updated_at=data_updated_at,
            attractions=saida,
        )


class HistoryPointOut(BaseModel):
    """Uma medição na linha do tempo.

    Nomes curtos de propósito: numa janela de 24 horas isto se repete quase
    trezentas vezes, e `observed_at`/`wait_time_minutes` repetidos trezentas vezes
    são quilobytes gastos em rótulo. O gráfico consome os dois campos e nada mais.
    """

    at: datetime = Field(description="Quando a fonte mediu.")
    minutes: int = Field(description="Fila comum, em minutos.")


class HistorySummaryOut(BaseModel):
    """Os números que resumem a janela."""

    measurements: int = Field(description="Medições com fila na janela.")
    min_minutes: int
    max_minutes: int
    average_minutes: float
    current_minutes: int
    spread: int = Field(description="Pico menos vale. Mede se vale escolher a hora.")

    @classmethod
    def from_domain(cls, resumo: HistorySummary) -> "HistorySummaryOut":
        return cls(
            measurements=resumo.measurements,
            min_minutes=resumo.min_minutes,
            max_minutes=resumo.max_minutes,
            average_minutes=resumo.average_minutes,
            current_minutes=resumo.current_minutes,
            spread=resumo.spread,
        )


class AttractionHistoryOut(BaseModel):
    """Resposta de `/parks/{id}/attractions/{id}/history`.

    O primeiro endpoint do NextUp que serve **dado nosso**: tudo que veio antes era
    a ThemeParks.wiki reempacotada. Isto aqui só existe porque o coletor rodou.
    """

    park_id: str
    attraction_id: str
    attraction_name: str

    hours: int = Field(description="Tamanho da janela pedida.")

    #: Vazio é resposta legítima e comum: atração que ficou fechada na janela, ou
    #: parque cuja coleta começou depois. Não é erro, e a tela avisa em vez de
    #: mostrar um gráfico em branco.
    points: list[HistoryPointOut]

    #: Nulo quando não houve medição com fila. Ver `points`.
    summary: HistorySummaryOut | None = None

    #: A mesma tendência que aparece na recomendação, recalculada sobre a janela
    #: pedida — que pode ser bem maior que os 30 minutos padrão.
    trend: TrendOut | None = None

    @classmethod
    def from_domain(
        cls,
        *,
        park_id: str,
        attraction_id: str,
        attraction_name: str,
        hours: int,
        snapshots: Sequence[QueueSnapshot],
        resumo: HistorySummary | None,
        tendencia: TrendAnalysis | None,
    ) -> "AttractionHistoryOut":
        return cls(
            park_id=park_id,
            attraction_id=attraction_id,
            attraction_name=attraction_name,
            hours=hours,
            points=[
                HistoryPointOut(at=s.observed_at, minutes=s.wait_time_minutes)
                for s in snapshots
                if s.wait_time_minutes is not None
            ],
            summary=HistorySummaryOut.from_domain(resumo) if resumo else None,
            trend=TrendOut.from_domain(tendencia) if tendencia else None,
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

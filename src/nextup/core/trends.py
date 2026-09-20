"""Tendência da fila: ela está subindo, caindo ou parada?

É o que transforma um número em conselho. *"Big Thunder: 24 min"* informa;
*"24 min, e caiu de 45 para 20 nos últimos 30 minutos"* convence — e é a segunda
frase que o consultor de parque manda no WhatsApp, porque é ela que explica **por
que agora**.

Como todo módulo do `core/`, aqui entra dado pronto e sai resultado: recebe uma
lista de `QueueSnapshot` e devolve uma direção. Não sabe o que é banco, não sabe o
que é rede, e seus testes rodam em milissegundos.

**Os números vieram de medição, não de intuição.** Sobre 228 snapshots reais do
Magic Kingdom coletados em 20/09/2026:

- **218 de 218** medições eram múltiplos de 5. A fonte reporta em passos de cinco
  minutos, e não há variação mais fina que isso.
- **118 de 189** variações entre medições consecutivas eram **zero**. A fila fica
  parada quase dois terços do tempo.

A segunda descoberta é a que molda o desenho: comparar apenas as duas últimas
medições devolveria "estável" na maioria das vezes, mesmo quando a fila caiu pela
metade ao longo da manhã. Por isso a comparação é contra o **início de uma
janela**, e não contra a medição anterior.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from nextup.config import TREND_THRESHOLD_MINUTES, TREND_WINDOW_MINUTES
from nextup.models import QueueSnapshot


class Trend(StrEnum):
    """Para onde a fila está indo."""

    FALLING = "FALLING"
    RISING = "RISING"
    STABLE = "STABLE"

    #: Sem histórico suficiente para afirmar qualquer coisa. É um estado legítimo
    #: e frequente: atração recém-incluída, coletor que acabou de subir, ou parque
    #: que abriu há dez minutos. Fingir "estável" aqui seria inventar informação.
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TrendAnalysis:
    """A tendência, com os números que a sustentam.

    Guarda as duas pontas — e não só a direção — pelo mesmo motivo que
    `Recommendation` guarda as parcelas em vez do total: sem elas não há como
    explicar, e é a explicação que faz o visitante confiar.
    """

    direction: Trend
    previous_minutes: int | None = None
    current_minutes: int | None = None

    #: Quantos minutos separam as duas medições comparadas. Pode ser bem menor que
    #: a janela pedida, se o histórico for curto.
    span_minutes: float = 0.0

    @property
    def delta(self) -> int:
        """Variação em minutos. Negativo é bom para o visitante: a fila caiu."""
        if self.previous_minutes is None or self.current_minutes is None:
            return 0
        return self.current_minutes - self.previous_minutes

    def describe(self) -> str:
        """Frase pronta para a justificativa, ou vazia quando não há o que dizer.

        Devolver string vazia em vez de "tendência desconhecida" é deliberado: quem
        monta a explicação concatena sem precisar de `if`, e o visitante não lê uma
        confissão de ignorância que não lhe serve para nada.
        """
        if self.direction is Trend.UNKNOWN:
            return ""

        minutos = round(self.span_minutes)

        if self.direction is Trend.STABLE:
            return f"Estável nos últimos {minutos} min."

        verbo = "Caiu" if self.direction is Trend.FALLING else "Subiu"
        return (
            f"{verbo} de {self.previous_minutes} para {self.current_minutes} "
            f"nos últimos {minutos} min."
        )


def analyze(
    snapshots: Iterable[QueueSnapshot],
    *,
    now: datetime,
    window_minutes: float = TREND_WINDOW_MINUTES,
    threshold_minutes: int = TREND_THRESHOLD_MINUTES,
) -> TrendAnalysis:
    """Diz para onde a fila de uma atração está indo.

    Compara a medição mais recente com a mais antiga **dentro da janela**. Duas
    escolhas aqui merecem explicação:

    **Por que não comparar com a medição anterior.** Porque 62% delas são
    idênticas à anterior: a fonte atualiza a cada poucos minutos e a fila raramente
    muda nesse intervalo. Comparar consecutivas diria "estável" sobre uma fila que
    caiu de 60 para 20 ao longo da manhã.

    **Por que a janela limita para trás.** Um snapshot de ontem não diz nada sobre
    agora, e o parque nem estava no mesmo momento do dia. Sem o corte, a primeira
    medição da semana seria comparada com a de hoje.

    Args:
        snapshots: Histórico de **uma** atração. Ordem não importa.
        now: O instante de referência. Injetável, como todo relógio do projeto.
        window_minutes: Quanto olhar para trás.
        threshold_minutes: Variação mínima para não ser considerada estável. O
            padrão é 5 porque é o menor passo que a fonte reporta — exigir mais
            descartaria três de cada quatro movimentos reais.

    Returns:
        A análise. `UNKNOWN` quando faltam medições para comparar.
    """
    inicio = now - timedelta(minutes=window_minutes)

    # Só medições com fila: uma atração fechada não tem tendência de fila, e tratar
    # o fechamento como "caiu para zero" inventaria uma queda que não existe.
    na_janela = sorted(
        (
            s
            for s in snapshots
            if s.wait_time_minutes is not None and inicio <= s.observed_at <= now
        ),
        key=lambda s: s.observed_at,
    )

    if len(na_janela) < 2:
        return TrendAnalysis(direction=Trend.UNKNOWN)

    return _comparar(na_janela[0], na_janela[-1], threshold_minutes)


def _comparar(antes: QueueSnapshot, agora: QueueSnapshot, threshold_minutes: int) -> TrendAnalysis:
    """Monta a análise a partir das duas pontas da janela."""
    # `is not None` já garantido pelo filtro; a asserção documenta para o tipo.
    assert antes.wait_time_minutes is not None
    assert agora.wait_time_minutes is not None

    variacao = agora.wait_time_minutes - antes.wait_time_minutes
    minutos = (agora.observed_at - antes.observed_at).total_seconds() / 60

    if abs(variacao) < threshold_minutes:
        direcao = Trend.STABLE
    elif variacao < 0:
        direcao = Trend.FALLING
    else:
        direcao = Trend.RISING

    return TrendAnalysis(
        direction=direcao,
        previous_minutes=antes.wait_time_minutes,
        current_minutes=agora.wait_time_minutes,
        span_minutes=minutos,
    )


def analyze_many(
    snapshots: Sequence[QueueSnapshot],
    *,
    now: datetime,
    window_minutes: float = TREND_WINDOW_MINUTES,
    threshold_minutes: int = TREND_THRESHOLD_MINUTES,
) -> dict[str, TrendAnalysis]:
    """A tendência de várias atrações de uma vez, indexada por ID.

    Existe porque a tela mostra oito atrações e o banco devolve o histórico de
    todas numa consulta só. Agrupar aqui evita uma ida ao banco por atração — o
    mesmo motivo de `LiveDataResponse.by_id()`.

    Args:
        snapshots: Histórico de **várias** atrações, misturado.
        now: Instante de referência.
        window_minutes: Quanto olhar para trás.
        threshold_minutes: Variação mínima para não ser estável.

    Returns:
        Um dicionário de ID para análise. Atrações sem histórico suficiente
        simplesmente não aparecem — quem consulta usa `.get()` e trata a ausência
        como `UNKNOWN`.
    """
    por_atracao: dict[str, list[QueueSnapshot]] = {}
    for snapshot in snapshots:
        por_atracao.setdefault(snapshot.attraction_id, []).append(snapshot)

    resultado = {}
    for attraction_id, historico in por_atracao.items():
        analise = analyze(
            historico,
            now=now,
            window_minutes=window_minutes,
            threshold_minutes=threshold_minutes,
        )
        if analise.direction is not Trend.UNKNOWN:
            resultado[attraction_id] = analise

    return resultado

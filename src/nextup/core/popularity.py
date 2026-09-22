"""Popularidade: esta atração é uma das principais do parque?

Nasceu de uma troca. A ideia original do Gabriel era filtrar por **radicalidade**,
mas o catálogo da ThemeParks.wiki traz só `entityType, externalId, id, location,
name, parentId, slug` — não há intensidade, altura mínima nem categoria. Curar 198
parques à mão não escala. A popularidade, ao contrário, sai de dado que já estamos
coletando desde a Fase 6: a fila média histórica.

**O proxy é indireto e vale dizer por quê ele funciona.** Fila comprida não é
popularidade, é o encontro de demanda com capacidade — uma atração de baixa vazão
forma fila com pouca gente. Mas, para o visitante, a pergunta prática não é "qual
é a mais amada?", e sim "qual é daquelas que sempre têm fila?". Para essa, a
média histórica responde direto.

Como todo módulo do `core/`, é função pura: entram médias, saem faixas. Não sabe
o que é banco nem rede.

---

## Os três números vieram de medição

Sobre 1257 snapshots reais do Magic Kingdom (04/09 a 22/09/2026), 30 atrações com
fila medida:

**1. Faixa relativa, nunca valor absoluto.** 59% das medições caíram entre 10h e
13h locais, porque é quando o Render fica acordado e o parque, cheio. A média
absoluta sai inflada — mas o viés atinge *todas* as atrações igualmente, já que o
coletor as fotografa juntas a cada 5 minutos. A **ordem** sobrevive; o **número**
não. Por isso a saída é uma faixa, e a média fica como detalhe de apoio.

**2. O critério é razão contra a mediana do parque, e não tercil por posição.**
Os dois foram medidos partindo o histórico ao meio e conferindo se a faixa se
repetia nas duas metades:

| Critério | Faixa estável entre as metades |
|---|---|
| Tercil por posição | 17/23 (74%) |
| Razão contra a mediana | **19/23 (83%)** |

O tercil ainda erra de um jeito pior: ele *força* um terço das atrações em cada
faixa. Num parque com duas campeãs e trinta medianas, chamaria dez de "principal"
só para preencher a cota. A razão contra a mediana deixa o parque dizer quantas
principais ele tem — no Magic Kingdom, nove.

**3. Abaixo de 12 medições a média é uma foto, não um histórico.** Doze é uma
hora de coleta, ao ritmo de 5 minutos. O corte separou exatamente o grupo certo:
ficaram de fora Country Bear, Hall of Presidents, Tiki Room, Swiss Family
Treehouse, o carrossel e os dois trens — shows e passeios que raramente reportam
fila. Nenhuma atração de fila real foi excluída.

Abaixo do mínimo a faixa é `UNKNOWN`, e isso **não** é o mesmo que "tranquila":
ausência de dado não é dado. Chamar de tranquila uma atração que nunca medimos
mandaria o visitante para uma fila de uma hora com nossa bênção.

---

## Por que ela não reordena o ranking

Mesma regra da tendência e dos alvos. O ranking responde "o que compensa agora",
e popularidade é uma característica da atração, não do momento — dar bônus de
custo a uma principal distorceria o número em vez de assumir a mudança de
critério. Ela entra como **filtro** (quem quer os clássicos, ou quem quer fugir
deles) e como **rótulo**.

O que ela habilita de mais valioso é a comparação entre as duas: uma principal
cuja fila está hoje abaixo da própria média é uma **oportunidade**, e essa é
exatamente a frase que o consultor de parque manda no WhatsApp. Nos dados reais,
8 das 23 atrações estavam numa faixa pelo histórico e noutra pela fila do
momento — ou seja, em um terço dos casos o histórico diz algo que o "agora" não
diz. Se dissesse sempre a mesma coisa, esta feature não precisaria existir.
"""

import statistics
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from nextup.config import (
    POPULARITY_HIGH_RATIO,
    POPULARITY_LOW_RATIO,
    POPULARITY_MIN_MEASUREMENTS,
    POPULARITY_OPPORTUNITY_RATIO,
)


class Popularity(StrEnum):
    """Quão disputada a atração costuma ser, comparada ao resto do parque."""

    HEADLINER = "HEADLINER"
    """Das que sempre têm fila. O visitante de primeira vez veio por estas."""

    MODERATE = "MODERATE"
    """Fila perto da mediana do parque."""

    QUIET = "QUIET"
    """Costuma ter fila curta. Boa para preencher o tempo entre as grandes."""

    UNKNOWN = "UNKNOWN"
    """Histórico curto demais para afirmar qualquer coisa.

    Estado legítimo e frequente: atração recém-aberta, parque que só agora entrou
    na coleta, ou um show que quase nunca reporta fila. É diferente de `QUIET` de
    propósito — ver o cabeçalho do módulo.
    """


@dataclass(frozen=True)
class AttractionPopularity:
    """A faixa, com os números que a sustentam.

    Guarda a média e a contagem pelo mesmo motivo que `TrendAnalysis` guarda as
    duas pontas: sem elas não há como explicar a classificação, e é a explicação
    que faz o visitante confiar nela.
    """

    tier: Popularity

    #: Fila média histórica, em minutos. `None` quando não houve medição alguma.
    average_minutes: float | None = None

    #: Quantas medições com fila entraram na conta.
    measurements: int = 0

    @property
    def is_known(self) -> bool:
        return self.tier is not Popularity.UNKNOWN

    def is_opportunity(self, current_minutes: int | None) -> bool:
        """A fila de agora está bem abaixo do normal desta atração?

        **O motivo desta classe existir.** Uma principal com fila baixa é a hora
        de ir; saber que ela é principal, isolado, não muda a decisão de ninguém.

        Restrito às principais de propósito: uma atração tranquila abaixo da média
        é uma fila de 4 minutos em vez de 7, o que não é notícia. E exige faixa
        conhecida, porque comparar contra uma média de três medições produziria
        "oportunidade" a cada oscilação.
        """
        if self.tier is not Popularity.HEADLINER or self.average_minutes is None:
            return False
        if current_minutes is None:
            return False
        return current_minutes <= self.average_minutes * POPULARITY_OPPORTUNITY_RATIO


def classify(
    averages: Mapping[str, tuple[float, int]],
    *,
    minimum_measurements: int = POPULARITY_MIN_MEASUREMENTS,
) -> dict[str, AttractionPopularity]:
    """Classifica as atrações de **um** parque em faixas de popularidade.

    Args:
        averages: Por ID de atração, o par `(fila média, número de medições)`.
            Vem agregado do banco — ver `storage.average_waits`.
        minimum_measurements: Abaixo disto a atração fica `UNKNOWN`.

    Returns:
        A faixa de cada atração recebida, incluindo as inelegíveis. Devolver todas
        é deliberado: quem chama precisa distinguir "não está no mapa" de "está e
        não sabemos", e omitir as inelegíveis apagaria essa diferença.

    A mediana é calculada **só sobre as elegíveis**. Incluir médias de três
    medições na régua que classifica todas as outras deixaria o ruído de uma
    atração mexer na faixa das vizinhas.
    """
    elegiveis = {
        aid: media
        for aid, (media, n) in averages.items()
        if n >= minimum_measurements and media > 0
    }

    if not elegiveis:
        # Sem régua não há faixa. Acontece no primeiro dia de coleta de um parque
        # novo, e é um resultado correto — não um erro.
        return {
            aid: AttractionPopularity(Popularity.UNKNOWN, average_minutes=media, measurements=n)
            for aid, (media, n) in averages.items()
        }

    mediana = statistics.median(elegiveis.values())
    alto = mediana * POPULARITY_HIGH_RATIO
    baixo = mediana * POPULARITY_LOW_RATIO

    resultado: dict[str, AttractionPopularity] = {}
    for aid, (media, n) in averages.items():
        if aid not in elegiveis:
            faixa = Popularity.UNKNOWN
        elif media >= alto:
            faixa = Popularity.HEADLINER
        elif media <= baixo:
            faixa = Popularity.QUIET
        else:
            faixa = Popularity.MODERATE

        resultado[aid] = AttractionPopularity(
            tier=faixa,
            average_minutes=round(media, 1),
            measurements=n,
        )

    return resultado

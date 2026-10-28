"""Intensidade de uma atração, a partir das etiquetas oficiais da Disney.

A "radicalidade" foi descartada na 7.4 porque a fonte não a informa. Ela volta aqui
sobre dado nosso — a curadoria — e **sem opinião**: a classificação sai das etiquetas
que a própria Disney publica, por uma regra escrita que qualquer um pode conferir.

| Nível | Quando |
|---|---|
| `THRILL` | "Thrill Rides" ou "Big Drops" |
| `MODERATE` | "Small Drops" ou "Scary" |
| `CALM` | nenhuma das anteriores |

"Dark", "Loud" e "Spinning" ficam de fora de propósito. Escuro e barulho são
dimensões sensoriais, não de intensidade: a Haunted Mansion é "Dark, Slow Rides" e não
tem nada de radical. E a Disney marca como "Spinning" tanto a Mad Tea Party quanto o
Buzz Lightyear, que estão em pontas opostas da escala.

Aplicada às 35 atrações do Magic Kingdom (27/10/2026): 5 radicais (TRON, Space
Mountain, Tiana's, Big Thunder, Seven Dwarfs), 3 moderadas (Barnstormer, Peter Pan,
Pirates) e 27 tranquilas. Se uma classificação contrariar o senso comum sobre a
atração, é a regra que está errada, não a atração.
"""

from collections.abc import Iterable
from enum import StrEnum

#: Etiquetas que, sozinhas, fazem uma atração ser radical.
THRILL_TAGS = frozenset({"Thrill Rides", "Big Drops"})

#: Etiquetas que fazem uma atração ser moderada, quando não é radical.
MODERATE_TAGS = frozenset({"Small Drops", "Scary"})


class Intensity(StrEnum):
    CALM = "CALM"
    MODERATE = "MODERATE"
    THRILL = "THRILL"


def classify_intensity(disney_tags: Iterable[str]) -> Intensity:
    """O nível de intensidade de uma atração **já conferida**.

    Recebe só as etiquetas; quem chama garante que a atração foi conferida. Uma
    atração sem curadoria não tem intensidade — e chamá-la de `CALM` por falta de
    etiqueta mandaria quem pediu "só tranquilas" para uma montanha-russa. É a mesma
    regra da 7.4: ausência de dado não é dado.
    """
    etiquetas = {t.strip().casefold() for t in disney_tags}

    if etiquetas & {t.casefold() for t in THRILL_TAGS}:
        return Intensity.THRILL
    if etiquetas & {t.casefold() for t in MODERATE_TAGS}:
        return Intensity.MODERATE
    return Intensity.CALM

"""Num parque com curadoria, as atrações são as da listagem oficial.

A fonte mistura às atrações entradas que não são atração. Em 30/10/2026 eram duas,
da festa de Halloween do Magic Kingdom ("Trick-or-Treat Locations at Mickey's
Not-So-Scary Halloween Party" e a experiência de alergias), com tipo `ATTRACTION` e
coordenada — e por isso apareciam no catálogo de alvos como se fossem brinquedos.

Dois critérios foram testados nos dados e descartados antes deste:

- **Sem `slug`.** TRON e Tiana's Bayou Adventure também vêm sem.
- **Sem fila no `/live`.** Apagaria o Castelo e a área de água do Casey Jr. e,
  pior, atrações de verdade fechadas para reforma — o Carousel of Progress vem sem
  fila enquanto está em `REFURBISHMENT`.

A curadoria foi montada sobre a listagem pública da Disney, e ela é a verdade
externa: as 35 atrações estão no `/live`, e as duas da festa são as únicas que não
estão nela. Parques sem curadoria não têm contra o que comparar, e seguem como a
fonte manda.
"""

from collections.abc import Set

from nextup.models import EntityType, ParkCatalog


def restrict_to_listing(catalog: ParkCatalog, listed: Set[str] | None) -> ParkCatalog:
    """O catálogo só com as atrações listadas; o resto das entidades fica.

    Shows e restaurantes passam intactos: a listagem cobre atrações, e cortar o
    que ela não cobre seria apagar dado por um critério que não se aplica a ele.

    Args:
        catalog: O catálogo como a fonte o entregou.
        listed: IDs da listagem oficial, ou `None` se o parque não tem curadoria.
    """
    if listed is None:
        return catalog

    mantidas = [
        entidade
        for entidade in catalog.children
        if entidade.entity_type is not EntityType.ATTRACTION or entidade.id in listed
    ]
    return catalog.model_copy(update={"children": mantidas})

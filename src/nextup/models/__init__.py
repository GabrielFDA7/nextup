"""Modelos de domínio do NextUp — o idioma comum entre as camadas.

Reexportar aqui permite `from nextup.models import Destination`, sem que quem usa
precise saber em qual arquivo cada modelo mora.
"""

from nextup.models.destination import Destination, DestinationList, Park

__all__ = ["Destination", "DestinationList", "Park"]

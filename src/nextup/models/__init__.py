"""Modelos de domínio do NextUp — o idioma comum entre as camadas.

Reexportar aqui permite `from nextup.models import Destination`, sem que quem usa
precise saber em qual arquivo cada modelo mora.
"""

from nextup.models.attraction import EntityType, Location, ParkCatalog, ParkEntity
from nextup.models.destination import Destination, DestinationList, Park
from nextup.models.live import LiveData, LiveDataResponse, LiveStatus, Queue, StandbyQueue
from nextup.models.snapshot import QueueSnapshot

__all__ = [
    "Destination",
    "DestinationList",
    "EntityType",
    "LiveData",
    "LiveDataResponse",
    "LiveStatus",
    "Location",
    "Park",
    "ParkCatalog",
    "ParkEntity",
    "Queue",
    "QueueSnapshot",
    "StandbyQueue",
]

"""Cache em memória com prazo de validade.

A ThemeParks.wiki é pública, gratuita e mantida por voluntários. Pedir o catálogo
do Magic Kingdom — nome e coordenada de 86 itens que não mudam desde 1971 — a cada
visita seria abusar de um serviço que não cobra nada por isso.

Este cache resolve guardando a resposta por um prazo. O prazo é diferente conforme
a natureza do dado, e a diferença é enorme de propósito:

    catálogo (`/children`)  → 24 horas   → quase nunca muda
    fila (`/live`)          → 60 segundos → muda o tempo todo

Um TTL longo demais no `/live` entregaria fila velha como se fosse atual. Um TTL
curto demais no catálogo geraria milhares de requisições inúteis. Os dois valores
ficam em `config.py`.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class _Entry(Generic[T]):
    """Um valor guardado e o instante em que ele vence."""

    value: T
    expires_at: float


class TTLCache(Generic[T]):
    """Guarda valores por um tempo determinado.

    O relógio é injetável porque testar cache é testar a passagem do tempo. Um
    teste que chamasse `time.sleep(60)` para ver o dado vencer levaria um minuto
    e ainda seria instável. Recebendo o relógio de fora, o teste controla a hora
    e o vencimento acontece na mesma hora, sem esperar nada.
    """

    def __init__(
        self,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Cria um cache.

        Args:
            ttl_seconds: Quantos segundos um valor continua válido depois de guardado.
            clock: Função que devolve o instante atual, em segundos. O padrão é
                `time.monotonic`, e não `time.time`, por um motivo importante:
                `time.time` segue o relógio do sistema, que pode andar para trás
                quando o horário é sincronizado pela rede ou muda o horário de
                verão. Se isso acontecesse, um dado vencido voltaria a parecer
                válido. `time.monotonic` só anda para a frente.

        Raises:
            ValueError: Se o TTL não for positivo.
        """
        if ttl_seconds <= 0:
            raise ValueError(f"TTL deve ser positivo, recebido: {ttl_seconds}")

        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[str, _Entry[T]] = {}

    @property
    def ttl_seconds(self) -> float:
        return self._ttl_seconds

    def get(self, key: str) -> T | None:
        """Devolve o valor guardado, ou `None` se não existir ou já ter vencido.

        Um valor vencido é apagado aqui mesmo, em vez de ficar ocupando memória
        até alguém pedir por ele de novo.
        """
        entry = self._entries.get(key)
        if entry is None:
            return None

        if self._clock() >= entry.expires_at:
            del self._entries[key]
            return None

        return entry.value

    def set(self, key: str, value: T) -> None:
        """Guarda um valor, reiniciando a contagem do prazo."""
        self._entries[key] = _Entry(value=value, expires_at=self._clock() + self._ttl_seconds)

    def invalidate(self, key: str) -> None:
        """Descarta uma chave específica, se existir."""
        self._entries.pop(key, None)

    def clear(self) -> None:
        """Esvazia o cache inteiro."""
        self._entries.clear()

    def __len__(self) -> int:
        """Quantas chaves estão guardadas, vencidas ou não.

        Serve para inspeção e teste. Não confunda com "quantas ainda valem": o
        vencimento só é verificado quando alguém chama `get`.
        """
        return len(self._entries)

    def __contains__(self, key: str) -> bool:
        """Permite `chave in cache`, respeitando o vencimento."""
        return self.get(key) is not None

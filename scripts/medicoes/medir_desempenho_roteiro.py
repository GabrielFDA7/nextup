"""Quanto custa planejar o roteiro no Magic Kingdom real, e quanto a poda economiza?

Origem: 27/10/2026, para escolher `ITINERARY_MAX_STOPS`. Resultado em `config.py` e em
`docs/PROJETO.md`, Fase 8, item 8.2. Não lê o banco. Uso:
    python scripts/medicoes/medir_desempenho_roteiro.py
"""

import itertools
import math
import random
import statistics
import time

from _comum import atracoes_mk

from nextup.core.geo import travel_time_matrix
from nextup.core.itinerary import plan_itinerary

CASOS = [(5, 5), (8, 5), (10, 5), (15, 5), (20, 5), (35, 5), (10, 6), (10, 7)]
REPETICOES = 10


def main() -> None:
    matriz = travel_time_matrix(atracoes_mk())
    ids = sorted(matriz)

    print("alvos  prof  sequências possíveis  avaliadas  média (ms)  pior (ms)")
    for n, k in CASOS:
        tempos, avaliadas = [], []
        for s in range(REPETICOES):
            rnd = random.Random(s)
            alvos = rnd.sample(ids, n)
            origem = rnd.choice(ids)
            filas = {a: rnd.choice([5, 10, 15, 20, 30, 45, 60, 90]) for a in alvos}
            contador = itertools.count()

            def prever(a, _daqui, filas=filas, contador=contador):
                next(contador)
                return filas[a]

            t0 = time.perf_counter()
            plan_itinerary(matriz[origem], matriz, alvos, prever, max_stops=k)
            tempos.append((time.perf_counter() - t0) * 1000)
            avaliadas.append(next(contador))
        print(
            f"{n:5} {k:5} {math.perm(n, k):21,} {statistics.mean(avaliadas):10,.0f}"
            f" {statistics.mean(tempos):11.1f} {max(tempos):10.1f}"
        )


if __name__ == "__main__":
    main()

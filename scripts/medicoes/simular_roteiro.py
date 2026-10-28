"""Planejar as próximas paradas bate o guloso? Backtest do roteiro sobre o histórico.

Origem: 27/10/2026, antes de escrever `core/itinerary.py`. Resultado em
`docs/PROJETO.md`, Fase 8, item 8.2. Próximas rodadas: 30/10 (preliminar) e 03/11/2026
(decisiva), sobre a coleta contínua.

Cenário: o visitante chega à entrada numa hora H do dia D com N alvos e quer concluir
todos no menor tempo. Cada estratégia decide a próxima parada, "anda", "espera a fila
real" e decide de novo. O juiz é a fila medida naquele dia, interpolada entre medições.

    guloso         a menor caminhada + fila agora — o que o ranking faz hoje
    plano+persist  `plan_itinerary` supondo que as filas não mudam (o padrão do produto)
    plano+perfil   `plan_itinerary` com o perfil horário dos outros dias
    oraculo        `plan_itinerary` conhecendo as filas reais do futuro — o teto

**Os planos chamam o otimizador de produção**, e não uma cópia: o backtest mede o código
que vai para o ar.

Uso:
    python scripts/medicoes/simular_roteiro.py [--desde AAAA-MM-DD] [--gap MIN]
                                               [--dur MIN] [--alvos N]

O `--gap` é o maior buraco entre medições que se aceita interpolar. Sobre o histórico
fragmentado de antes de 27/10 foi preciso 240 min; com coleta contínua, use 20.
"""

import argparse
import itertools
import random
import statistics
from collections import defaultdict
from datetime import date

from _comum import atracoes_mk, consultar, fuso_mk, nomes_mk

from nextup.core.geo import travel_time_matrix
from nextup.core.itinerary import plan_itinerary

ENTRADA = "Walt Disney World Railroad - Main Street, U.S.A."
INICIOS = [9 * 60, 11 * 60, 13 * 60, 15 * 60]
SEMENTES = range(8)
JANELA_PERFIL = 30  # min, ± ao redor da hora prevista
MIN_PERFIL = 3
ESTRATEGIAS = ["guloso", "plano+persist", "plano+perfil", "oraculo"]


class ForaDosDadosError(Exception):
    """O juiz não sabe a fila real nesse instante: o cenário sai para TODAS as estratégias."""


class Mundo:
    """As filas reais de cada dia, e o perfil histórico sem o dia avaliado."""

    def __init__(self, args):
        self.args = args
        fuso = fuso_mk()
        pontos = atracoes_mk()
        self.matriz = travel_time_matrix(pontos)
        self.entrada = next(i for i, n in nomes_mk().items() if n == ENTRADA)

        [linhas] = consultar(
            "SELECT attraction_id, observed_at, wait_time_minutes FROM queue_snapshots"
            " WHERE wait_time_minutes IS NOT NULL"
        )
        self.serie = defaultdict(list)  # (atração, dia) -> [(minuto do dia, fila)]
        for a, t, w in linhas:
            lt = t.astimezone(fuso)
            if a in pontos and args.desde <= lt.date() <= args.ate:
                self.serie[(a, lt.date())].append((lt.hour * 60 + lt.minute + lt.second / 60, w))
        for s in self.serie.values():
            s.sort()

        # Somas por faixa de 5 min, no total e por dia, para tirar o dia avaliado da
        # média sem recalcular tudo (leave-one-day-out).
        self.total = defaultdict(lambda: [0.0, 0])
        self.por_dia = defaultdict(lambda: [0.0, 0])
        for (a, d), pts in self.serie.items():
            for m, w in pts:
                f = int(m // 5)
                for chave, tabela in (((a, f), self.total), ((a, d, f), self.por_dia)):
                    tabela[chave][0] += w
                    tabela[chave][1] += 1

    def real(self, a, d, m):
        """A fila verdadeira (interpolada) de `a` no minuto `m` do dia `d`."""
        pts = self.serie.get((a, d))
        if pts:
            if m <= pts[0][0]:
                if pts[0][0] - m <= self.args.borda:
                    return pts[0][1]
            elif m >= pts[-1][0]:
                if m - pts[-1][0] <= self.args.borda:
                    return pts[-1][1]
            else:
                for (m0, w0), (m1, w1) in itertools.pairwise(pts):
                    if m0 <= m <= m1 and m1 - m0 <= self.args.gap:
                        return w0 if m1 == m0 else w0 + (w1 - w0) * (m - m0) / (m1 - m0)
        raise ForaDosDadosError

    def perfil(self, a, d, m):
        f0 = int(m // 5)
        s = n = 0
        for f in range(f0 - JANELA_PERFIL // 5, f0 + JANELA_PERFIL // 5 + 1):
            ts, tn = self.total[(a, f)]
            ds, dn = self.por_dia[(a, d, f)]
            s, n = s + ts - ds, n + tn - dn
        return s / n if n >= MIN_PERFIL else None


def previsor(mundo: Mundo, estrategia: str, d, agora: float):
    """A previsão que cada plano usa, em minutos a partir de `agora`."""
    if estrategia == "plano+persist":
        return lambda a, _daqui: mundo.real(a, d, agora)
    if estrategia == "oraculo":
        return lambda a, daqui: mundo.real(a, d, agora + daqui)

    def perfil(a, daqui):  # sem perfil, cai na persistência, como faria o produto
        p = mundo.perfil(a, d, agora + daqui)
        return mundo.real(a, d, agora) if p is None else p

    return perfil


def executar(mundo: Mundo, estrategia: str, d, inicio: float, alvos: list[str]) -> float:
    """Simula o visitante até concluir todos os alvos; devolve o tempo total em minutos."""
    agora, onde, restantes = inicio, mundo.entrada, set(alvos)
    while restantes:
        if estrategia == "guloso":
            prox = min(
                sorted(restantes),
                key=lambda a: mundo.matriz[onde][a] + mundo.real(a, d, agora),
            )
        else:
            roteiro = plan_itinerary(
                mundo.matriz[onde],
                mundo.matriz,
                sorted(restantes),
                previsor(mundo, estrategia, d, agora),
                ride_minutes=mundo.args.dur,
                max_stops=len(restantes),
            )
            prox = roteiro.next_stop.attraction_id
        agora += mundo.matriz[onde][prox]
        agora += mundo.real(prox, d, agora) + mundo.args.dur  # o juiz: a fila na chegada
        onde = prox
        restantes.discard(prox)
    return agora - inicio


def resumo(sub: list, titulo: str) -> None:
    base = [r["guloso"] for _, _, r in sub]
    print(f"{titulo}  (n={len(sub)}, guloso médio {statistics.mean(base):.1f} min)")
    for e in ESTRATEGIAS[1:]:
        dif = [r[e] - r["guloso"] for _, _, r in sub]
        ganha = sum(x < -0.5 for x in dif)
        perde = sum(x > 0.5 for x in dif)
        media = statistics.mean(dif)
        print(
            f"  {e:14} vs guloso {media:+6.1f} min ({media / statistics.mean(base):+.1%})"
            f"  ganha {ganha:3}  perde {perde:3}  empata {len(dif) - ganha - perde:3}"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--desde", type=date.fromisoformat, default=date(2026, 9, 20))
    ap.add_argument("--ate", type=date.fromisoformat, default=date(2099, 1, 1))
    ap.add_argument("--gap", type=float, default=240, help="maior buraco interpolável (min)")
    ap.add_argument("--borda", type=float, default=30, help="extrapolação nas pontas (min)")
    ap.add_argument("--dur", type=float, default=8, help="minutos dentro de cada atração")
    ap.add_argument("--alvos", type=int, default=5)
    args = ap.parse_args()

    mundo = Mundo(args)
    dias = sorted({d for _, d in mundo.serie})
    resultados, descartados = [], 0
    for d in dias:
        candidatas = sorted(a for (a, dd), pts in mundo.serie.items() if dd == d and len(pts) >= 3)
        if len(candidatas) < args.alvos:
            continue
        for inicio in INICIOS:
            for s in SEMENTES:
                alvos = random.Random(f"{d}-{inicio}-{s}").sample(candidatas, args.alvos)
                try:
                    r = {e: executar(mundo, e, d, inicio, alvos) for e in ESTRATEGIAS}
                except ForaDosDadosError:
                    descartados += 1
                    continue
                resultados.append((d, inicio, r))

    print(f"desde={args.desde} gap={args.gap} borda={args.borda} dur={args.dur} alvos={args.alvos}")
    print(f"dias: {len(dias)}; cenários válidos: {len(resultados)}; descartados: {descartados}\n")
    if not resultados:
        return

    resumo(resultados, "TODOS")
    meio = dias[len(dias) // 2]
    print()
    resumo([x for x in resultados if x[0] < meio], "1a METADE dos dias")
    resumo([x for x in resultados if x[0] >= meio], "2a METADE dos dias")
    print()
    for inicio in INICIOS:
        sub = [x for x in resultados if x[1] == inicio]
        if sub:
            resumo(sub, f"início {inicio // 60:02d}h")


if __name__ == "__main__":
    main()

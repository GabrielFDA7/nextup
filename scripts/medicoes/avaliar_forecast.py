"""O forecast da fonte bate a persistência? E o nosso perfil horário?

Origem: avaliação agendada para 27/09/2026 e feita em 27/10/2026. Resultado em
`docs/PROJETO.md` (Fase 6, bloco da avaliação do forecast) e no cabeçalho de
`core/forecast.py`. Próxima rodada: 03/11/2026, com uma semana de coleta contínua.

Para cada previsão guardada em `queue_forecasts`:
    realizado    = medição da atração mais próxima do horário previsto (até 7,5 min)
    persistência = a última fila conhecida quando vimos a previsão (até 15 min antes)
    perfil       = média da atração, ±30 min da mesma hora, **nos outros dias**
                   (o dia avaliado fica de fora, senão o perfil conheceria a resposta)
Só entram casos em que os três modelos respondem: a mesma amostra para todos.

Uso:
    python scripts/medicoes/avaliar_forecast.py [--desde AAAA-MM-DD]
"""

import argparse
import bisect
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean

from _comum import consultar, fuso_mk

from nextup.core.forecast import Prediction, evaluate

FUSO = fuso_mk()
JANELA_REAL = timedelta(minutes=7.5)
JANELA_PERSIST = timedelta(minutes=15)
FAIXAS = [(0, 0.5), (0.5, 1), (1, 2), (2, 4), (4, 8), (8, 99)]
MODELOS = ("fonte", "persist", "perfil")


def montar_casos(desde: date) -> tuple[list[dict], int]:
    snaps, prevs = consultar(
        "SELECT attraction_id, observed_at, wait_time_minutes FROM queue_snapshots"
        " WHERE wait_time_minutes IS NOT NULL",
        "SELECT attraction_id, forecast_for, predicted_minutes, recorded_at FROM queue_forecasts",
    )
    serie = defaultdict(list)
    for a, t, w in snaps:
        serie[a].append((t, w))
    for s in serie.values():
        s.sort()
    tempos = {a: [t for t, _ in s] for a, s in serie.items()}

    por_dia = defaultdict(list)  # (atração, dia local) -> [(minuto do dia, fila)]
    for a, s in serie.items():
        for t, w in s:
            lt = t.astimezone(FUSO)
            por_dia[(a, lt.date())].append((lt.hour * 60 + lt.minute, w))
    dias_da = defaultdict(set)
    for a, d in por_dia:
        dias_da[a].add(d)

    casos = []
    for a, alvo, previsto, visto in prevs:
        la = alvo.astimezone(FUSO)
        if a not in serie or alvo <= visto or la.date() < desde:
            continue
        ts, s = tempos[a], serie[a]

        i = bisect.bisect_left(ts, alvo)
        perto = [j for j in (i - 1, i) if 0 <= j < len(ts) and abs(ts[j] - alvo) <= JANELA_REAL]
        if not perto:
            continue
        real = s[min(perto, key=lambda j: abs(ts[j] - alvo))][1]

        k = bisect.bisect_right(ts, visto) - 1
        if k < 0 or visto - ts[k] > JANELA_PERSIST:
            continue

        minuto = la.hour * 60 + la.minute
        outros = [
            w
            for d in dias_da[a]
            if d != la.date()
            for m, w in por_dia[(a, d)]
            if abs(m - minuto) <= 30
        ]
        if len(outros) < 3:
            continue

        casos.append(
            {
                "dia": la.date(),
                "lead": (alvo - visto).total_seconds() / 3600,
                "real": real,
                "fonte": previsto,
                "persist": s[k][1],
                "perfil": round(mean(outros)),
            }
        )
    return casos, len(prevs)


def placar(casos: list[dict], titulo: str) -> None:
    if not casos:
        print(f"{titulo:24} sem casos")
        return
    linha = f"{titulo:24} n={len(casos):4}"
    for modelo in MODELOS:
        ev = evaluate([(Prediction(modelo, c[modelo], c["lead"] * 60), c["real"]) for c in casos])
        linha += f"  {modelo}={ev.mean_absolute_error:5.2f}"
    print(linha)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--desde", type=date.fromisoformat, default=date(2026, 9, 20))
    args = ap.parse_args()

    casos, guardadas = montar_casos(args.desde)
    print(
        f"previsões guardadas: {guardadas}; casos avaliáveis: {len(casos)};"
        f" dias: {len({c['dia'] for c in casos})}\n"
    )
    if not casos:
        return

    print("ERRO MÉDIO ABSOLUTO (min), por antecedência:")
    placar(casos, "todos")
    for lo, hi in FAIXAS:
        placar([c for c in casos if lo < c["lead"] <= hi], f"  {lo}-{hi} h")

    print("\nESTABILIDADE: primeira metade x segunda metade dos dias")
    dias = sorted({c["dia"] for c in casos})
    corte = dias[len(dias) // 2]
    for nome, sub in (
        ("1a metade", [c for c in casos if c["dia"] < corte]),
        ("2a metade", [c for c in casos if c["dia"] >= corte]),
    ):
        placar(sub, nome)
        for lo, hi in ((0, 1), (1, 4), (4, 99)):
            placar([c for c in sub if lo < c["lead"] <= hi], f"    {lo}-{hi} h")

    print("\nSÓ OS CASOS EM QUE A FILA MUDOU:")
    placar([c for c in casos if c["real"] != c["persist"]], "mudou")

    print("\nVIÉS (média de previsto - real):")
    for modelo in MODELOS:
        print(f"  {modelo:8} {mean(c[modelo] - c['real'] for c in casos):+.2f}")


if __name__ == "__main__":
    main()

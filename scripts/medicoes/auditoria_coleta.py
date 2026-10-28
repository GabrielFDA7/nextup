"""A coleta está contínua? Conferido no banco, nunca no painel do pinger.

Origem: em 27/10/2026 esta auditoria descobriu o coletor parado ~90% do tempo por um
mês, com o `keep-alive.yml` sempre verde. Detalhes em `docs/PROJETO.md`, Fase 8, 8.0.

Como ler: um ciclo do coletor grava várias linhas com o mesmo `recorded_at`, então
minutos distintos de `recorded_at` contam ciclos. **Ciclo sem medição nova não deixa
linha** (a unicidade descarta a repetição): de madrugada, com o parque fechado, o vazio
é normal. A referência é o horário do parque — ~12 ciclos por hora é coleta contínua.

Uso:
    python scripts/medicoes/auditoria_coleta.py            # o histórico inteiro
    python scripts/medicoes/auditoria_coleta.py --horas 3  # só os ciclos recentes
"""

import argparse
from collections import Counter
from datetime import datetime

from _comum import catalogo_mk, consultar

FUSO = catalogo_mk()["timezone"]
LOCAL_OBS = f"(observed_at AT TIME ZONE '{FUSO}')"
LOCAL_REC = f"(recorded_at AT TIME ZONE '{FUSO}')"
HORAS_DO_PARQUE = range(9, 22)


def recentes(horas: int) -> None:
    [linhas] = consultar(
        f"SELECT date_trunc('minute', {LOCAL_REC}) m, count(*) FROM queue_snapshots"
        f" WHERE recorded_at > now() - interval '{int(horas)} hours' GROUP BY m ORDER BY m"
    )
    print(f"ciclos nas últimas {horas} h (horário do parque):")
    anterior = None
    for m, n in linhas:
        salto = f"  (+{int((m - anterior).total_seconds() // 60)} min)" if anterior else ""
        print(f"  {m:%d/%m %H:%M}  {n:3} linhas{salto}")
        anterior = m
    if not linhas:
        print("  nenhum — o serviço está dormindo, ou o parque fechado")


def historico() -> None:
    por_dia, por_hora, celulas = consultar(
        f"SELECT {LOCAL_REC}::date d, count(*), count(distinct date_trunc('minute', recorded_at)),"
        " count(distinct attraction_id) FROM queue_snapshots GROUP BY d ORDER BY d",
        f"SELECT {LOCAL_REC}::date d, extract(hour from {LOCAL_REC})::int h,"
        " count(distinct date_trunc('minute', recorded_at)) FROM queue_snapshots GROUP BY d, h",
        f"SELECT attraction_id, extract(hour from {LOCAL_OBS})::int,"
        f" count(distinct {LOCAL_OBS}::date) FROM queue_snapshots"
        " WHERE wait_time_minutes IS NOT NULL GROUP BY 1, 2",
    )

    esperado = 12 * len(HORAS_DO_PARQUE)
    print(f"POR DIA (ciclos esperados no horário do parque: ~{esperado})")
    print("dia         linhas  ciclos  atrações")
    for d, n, ciclos, atr in por_dia:
        print(f"{d}  {n:6}  {ciclos:6}  {atr:8}")

    grade: dict = {}
    for d, h, n in por_hora:
        grade.setdefault(d, {})[h] = n
    print("\nCICLOS POR HORA (12 = contínuo)")
    print("dia         " + " ".join(f"{h:>3}" for h in HORAS_DO_PARQUE))
    for d in sorted(grade):
        print(f"{d}  " + " ".join(f"{grade[d].get(h, 0):>3}" for h in HORAS_DO_PARQUE))

    dist = Counter(n for *_, n in celulas)
    total = len(celulas)
    print(f"\nCÉLULAS (atração, hora): quantos dias distintos têm fila medida — {total} células")
    for faixa, (lo, hi) in {
        "1 dia": (1, 1),
        "2-4": (2, 4),
        "5-9": (5, 9),
        "10-19": (10, 19),
        "20+": (20, 10**6),
    }.items():
        k = sum(v for n, v in dist.items() if lo <= n <= hi)
        print(f"  {faixa:6} {k:5}  ({k / total:.0%})")
    print(f"\ngerado em {datetime.now():%d/%m/%Y %H:%M}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--horas", type=int, help="mostrar só os ciclos das últimas N horas")
    args = ap.parse_args()
    recentes(args.horas) if args.horas else historico()

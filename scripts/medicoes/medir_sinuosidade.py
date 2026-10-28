"""O fator de sinuosidade (1,3) confere com as trilhas reais? Verdade externa: OpenStreetMap.

Origem: 27/10/2026, antes de escrever `geo.travel_time_matrix`. Resultado em
`config.py` (comentário de `PATH_WINDING_FACTOR`) e em `docs/PROJETO.md`, Fase 8, 8.1.

Baixa **uma vez** os caminhos de pedestre da área do parque pela Overpass API (fica em
`scripts/medicoes/.cache/osm/`, fora do Git), monta o grafo e calcula a rota a pé mais
curta (Dijkstra) entre cada par de atrações. Compara com linha reta vezes o fator.

Não lê o banco. Uso:
    python scripts/medicoes/medir_sinuosidade.py
"""

import heapq
import itertools
import json
import math
import statistics
import urllib.parse
import urllib.request

from _comum import CACHE, atracoes_mk, nomes_mk

from nextup.config import PATH_WINDING_FACTOR, WALKING_SPEED_MPS
from nextup.core.geo import haversine_distance_m

ARQUIVO = CACHE / "osm" / "trilhas.json"
MARGEM_GRAUS = 0.003  # ~300 m ao redor das atrações
#: Caminhos de pedestre; acesso privado (bastidores) fica de fora.
FILTRO = (
    '["highway"~"^(footway|pedestrian|path|steps|living_street|corridor)$"]'
    '["access"!~"^(private|no)$"]'
)


def hav(p, q):
    return haversine_distance_m(*p, *q)


def baixar(bbox) -> None:
    """Uma consulta só, com User-Agent identificado: a Overpass é pública e gratuita."""
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    consulta = f"[out:json][timeout:90];way{FILTRO}{bbox};out body;>;out skel qt;"
    req = urllib.request.Request(
        "https://overpass-api.de/api/interpreter",
        data=urllib.parse.urlencode({"data": consulta}).encode(),
        headers={"User-Agent": "NextUp/medicao (github.com/GabrielFDA7/nextup)"},
    )
    with urllib.request.urlopen(req, timeout=120) as resposta:
        ARQUIVO.write_bytes(resposta.read())


def grafo_das_trilhas():
    osm = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    nos = {e["id"]: (e["lat"], e["lon"]) for e in osm["elements"] if e["type"] == "node"}
    grafo: dict[int, list[tuple[int, float]]] = {}
    for e in osm["elements"]:
        if e["type"] != "way":
            continue
        ns = [n for n in e["nodes"] if n in nos]
        for a, b in itertools.pairwise(ns):
            d = hav(nos[a], nos[b])
            grafo.setdefault(a, []).append((b, d))
            grafo.setdefault(b, []).append((a, d))
    return nos, grafo


def maior_componente(grafo) -> set:
    """Encaixar uma atração num trecho de trilha solto daria rota infinita."""
    visto, maior = set(), set()
    for s in grafo:
        if s in visto:
            continue
        comp, pilha = {s}, [s]
        while pilha:
            for v, _ in grafo[pilha.pop()]:
                if v not in comp:
                    comp.add(v)
                    pilha.append(v)
        visto |= comp
        maior = max(maior, comp, key=len)
    return maior


def dijkstra(grafo, origem) -> dict:
    dist = {origem: 0.0}
    fila = [(0.0, origem)]
    while fila:
        d, u = heapq.heappop(fila)
        if d > dist[u]:
            continue
        for v, w in grafo[u]:
            if d + w < dist.get(v, math.inf):
                dist[v] = d + w
                heapq.heappush(fila, (d + w, v))
    return dist


def main() -> None:
    pontos = atracoes_mk()
    nome = nomes_mk()
    lats, lons = [p[0] for p in pontos.values()], [p[1] for p in pontos.values()]
    m = MARGEM_GRAUS
    if not ARQUIVO.exists():
        baixar((min(lats) - m, min(lons) - m, max(lats) + m, max(lons) + m))

    nos, grafo = grafo_das_trilhas()
    componente = maior_componente(grafo)
    print(f"nós no grafo: {len(grafo)}; maior componente: {len(componente)}")

    encaixe = {}
    for a, p in pontos.items():
        n = min(componente, key=lambda k, p=p: hav(p, nos[k]))
        encaixe[a] = (n, hav(p, nos[n]))
    print(f"maior distância de encaixe na trilha: {max(d for _, d in encaixe.values()):.0f} m")

    rotas = {a: dijkstra(grafo, encaixe[a][0]) for a in pontos}
    pares = []
    for a, b in sorted((a, b) for a in pontos for b in pontos if a < b):
        reta = hav(pontos[a], pontos[b])
        rota = encaixe[a][1] + rotas[a][encaixe[b][0]] + encaixe[b][1]
        pares.append((nome[a], nome[b], reta, rota))

    def minutos(metros):
        return metros / WALKING_SPEED_MPS / 60

    razoes = sorted(r / s for _, _, s, r in pares if s >= 100)
    q = statistics.quantiles(razoes, n=10)
    print(
        f"\npares: {len(pares)}; razão rota/reta (pares >= 100 m):"
        f" p10={q[0]:.2f} mediana={statistics.median(razoes):.2f} p90={q[8]:.2f}"
    )

    ajuste = sum(s * r for *_, s, r in pares) / sum(s**2 for *_, s, _ in pares)
    print("\nerro médio absoluto por trecho (min):")
    for rotulo, fator in (
        ("linha reta, sem correção", 1.0),
        (f"linha reta x {PATH_WINDING_FACTOR} (config)", PATH_WINDING_FACTOR),
        (f"linha reta x {ajuste:.2f} (melhor fator único)", ajuste),
    ):
        erro = statistics.mean(abs(minutos(s * fator - r)) for *_, s, r in pares)
        print(f"  {rotulo:38} {erro:.2f}")
    media_real = minutos(statistics.mean(p[3] for p in pares))
    print(f"  caminhada real média entre atrações: {media_real:.2f}")

    fator = PATH_WINDING_FACTOR
    print(f"\nos 10 pares em que o fator {fator} mais erra (estimado -> real, min):")
    for a, b, s, r in sorted(pares, key=lambda p: -abs(p[2] * fator - p[3]))[:10]:
        print(f"  {minutos(s * fator):5.1f} -> {minutos(r):5.1f}  {a[:30]} <-> {b[:30]}")


if __name__ == "__main__":
    main()

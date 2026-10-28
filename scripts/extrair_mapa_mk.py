"""Extrai do OpenStreetMap o desenho do Magic Kingdom: trilhas, água, prédios e verde.

Origem: 28/10/2026, Fase 9.3. O redesenho pede um mapa pintado com as cores do tema, e
os tiles do OSM já vêm pintados — não aceitam CSS. Um desenho à mão (como o do Claude
Design) tem a geografia inventada, e quebraria o "tocar no mapa define a posição" e o
ponto do GPS. Então o Leaflet continua com coordenadas reais, mas sem tiles: desenha
este GeoJSON por cima, com as variáveis CSS do tema.

Baixa **uma vez** pela Overpass API (fica em `scripts/.cache/osm/`, fora do Git) e grava
`web/mapas/magic-kingdom.geojson`, que é o que o navegador carrega. O app nunca consulta
a Overpass em tempo real: ela é pública e gratuita, mantida por voluntários.

Dados © OpenStreetMap contributors, licença ODbL — o crédito aparece no mapa.

Uso:
    python scripts/extrair_mapa_mk.py            # usa o cache se existir
    python scripts/extrair_mapa_mk.py --baixar   # força uma nova consulta
"""

import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CATALOGO = RAIZ / "tests" / "fixtures" / "children_magic_kingdom.json"
CACHE = Path(__file__).resolve().parent / ".cache" / "osm" / "mapa_mk.json"
SAIDA = RAIZ / "web" / "mapas" / "magic-kingdom.geojson"

MARGEM_GRAUS = 0.0025  # ~250 m além das atrações: o bastante para a água em volta
#: Tolerância da simplificação. Abaixo de ~1 m o olho não distingue no zoom do celular,
#: e cada ponto a menos é peso a menos no 4G de dentro do parque.
TOLERANCIA_M = 1.0
CASAS = 6  # ~0,1 m de resolução; mais que isso é ruído no arquivo

#: O principal e o espelho oficial listado na wiki do OSM.
SERVIDORES = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
TENTATIVAS = 4
ESPERA_INICIAL_S = 30  # 30, 60, 120: ~3,5 min no pior caso

#: Camada -> filtros Overpass. Trilhas seguem o mesmo filtro da medição de sinuosidade,
#: para o mapa mostrar exatamente os caminhos que sustentam o número da caminhada.
CAMADAS = {
    "trilha": [
        'way["highway"~"^(footway|pedestrian|path|steps|living_street|corridor)$"]'
        '["access"!~"^(private|no)$"]'
    ],
    "agua": ['way["natural"="water"]', 'relation["natural"="water"]', 'way["waterway"]'],
    "predio": ['way["building"]'],
    "verde": [
        'way["leisure"~"^(park|garden)$"]',
        'way["landuse"~"^(grass|forest)$"]',
        'way["natural"~"^(wood|scrub)$"]',
    ],
}


def caixa() -> tuple[float, float, float, float]:
    """Sul, oeste, norte, leste: o retângulo das atrações, com margem."""
    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    pontos = [
        (e["location"]["latitude"], e["location"]["longitude"])
        for e in catalogo["children"]
        if e.get("entityType") == "ATTRACTION" and (e.get("location") or {}).get("latitude")
    ]
    lats, lons = zip(*pontos, strict=True)
    m = MARGEM_GRAUS
    return min(lats) - m, min(lons) - m, max(lats) + m, max(lons) + m


def baixar(bbox) -> None:
    """Uma consulta só, com User-Agent identificado e backoff exponencial.

    Em 28/10/2026 o servidor principal respondeu 502 "at capacity" e pediu exatamente
    isto: esperar e dobrar a espera. O espelho oficial entra na vez seguinte de cada rodada.
    """
    s, w, n, e = bbox
    filtros = "".join(f"{f}({s},{w},{n},{e});" for fs in CAMADAS.values() for f in fs)
    consulta = f"[out:json][timeout:90];({filtros});out geom({s},{w},{n},{e});"
    corpo = urllib.parse.urlencode({"data": consulta}).encode()
    CACHE.parent.mkdir(parents=True, exist_ok=True)

    espera = ESPERA_INICIAL_S
    for tentativa in range(1, TENTATIVAS + 1):
        for servidor in SERVIDORES:
            req = urllib.request.Request(
                servidor,
                data=corpo,
                headers={"User-Agent": "NextUp/mapa (github.com/GabrielFDA7/nextup)"},
            )
            try:
                with urllib.request.urlopen(req, timeout=180) as resposta:
                    CACHE.write_bytes(resposta.read())
                print(f"ok: {servidor}")
                return
            except (urllib.error.URLError, TimeoutError) as erro:
                print(f"tentativa {tentativa}, {servidor}: {erro}")
        if tentativa < TENTATIVAS:
            print(f"esperando {espera} s...")
            time.sleep(espera)
            espera *= 2
    raise SystemExit("a Overpass não respondeu; tente mais tarde")


def camada_de(tags: dict) -> str | None:
    if "highway" in tags:
        return "trilha"
    if tags.get("natural") == "water" or "waterway" in tags:
        return "agua"
    if "building" in tags:
        return "predio"
    if tags.get("leisure") or tags.get("landuse") or tags.get("natural"):
        return "verde"
    return None


def tipo_de_trilha(tags: dict) -> str:
    """Hierarquia do desenho; para a rota, toda trilha vale igual.

    Medido em 28/10/2026: 63% do traçado é `footway` (atalhos e calçadas) e 33% é
    `pedestrian` (as vias largas). Com a mesma espessura, a Fantasyland virava uma
    malha. E 78 trilhas são o contorno de uma praça (`area=yes`): desenhadas como
    linha grossa, cada praça virava um anel. Elas viram área preenchida (camada
    `praca`), e a borda fica só na rede da rota, porque é por ela que se anda.
    """
    if tags.get("area") == "yes":
        return "borda"
    if tags.get("highway") in ("pedestrian", "living_street"):
        return "via"
    return "calcada"


def simplificar(pontos: list[tuple[float, float]], tol_m: float) -> list[tuple[float, float]]:
    """Douglas-Peucker: mantém só os pontos que desviam mais que `tol_m` da reta.

    Em graus, a longitude encolhe com a latitude; por isso a distância é medida numa
    projeção local em metros, e não direto em graus.
    """
    if len(pontos) < 3:
        return pontos
    lat0 = math.radians(pontos[0][1])
    k = 111_320.0

    def xy(p):
        return (p[0] * k * math.cos(lat0), p[1] * k)

    def desvio(p, a, b):
        (px, py), (ax, ay), (bx, by) = xy(p), xy(a), xy(b)
        dx, dy = bx - ax, by - ay
        if dx == dy == 0:
            return math.hypot(px - ax, py - ay)
        return abs(dy * px - dx * py + bx * ay - by * ax) / math.hypot(dx, dy)

    pilha, manter = [(0, len(pontos) - 1)], {0, len(pontos) - 1}
    while pilha:
        i, j = pilha.pop()
        pior, idx = 0.0, None
        for t in range(i + 1, j):
            d = desvio(pontos[t], pontos[i], pontos[j])
            if d > pior:
                pior, idx = d, t
        if idx is not None and pior > tol_m:
            manter.add(idx)
            pilha += [(i, idx), (idx, j)]
    return [pontos[t] for t in sorted(manter)]


def coords(geom) -> list[tuple[float, float]]:
    """GeoJSON é (longitude, latitude) — o contrário do Leaflet. Inverter aqui é bug clássico."""
    return [(round(g["lon"], CASAS), round(g["lat"], CASAS)) for g in geom if g]


def juntar_aneis(trechos: list[list]) -> list[list]:
    """Os contornos de uma relação vêm picados em vários ways; emenda pelas pontas."""
    aneis, soltos = [], [t[:] for t in trechos if len(t) > 1]
    while soltos:
        anel = soltos.pop()
        mudou = True
        while anel[0] != anel[-1] and mudou:
            mudou = False
            for i, t in enumerate(soltos):
                if t[0] == anel[-1]:
                    anel += t[1:]
                elif t[-1] == anel[-1]:
                    anel += t[::-1][1:]
                elif t[-1] == anel[0]:
                    anel = t + anel[1:]
                elif t[0] == anel[0]:
                    anel = t[::-1] + anel[1:]
                else:
                    continue
                soltos.pop(i)
                mudou = True
                break
        if len(anel) >= 4 and anel[0] == anel[-1]:
            aneis.append(anel)
    return aneis


def simplificar_anel(anel: list[tuple[float, float]]) -> list[tuple[float, float]] | None:
    """Anel fechado: o 1º ponto é o último, e a "reta" de referência teria comprimento zero.

    Simplificado direto, um polígono pequeno colapsa em [a, b, a] e deixa de ser
    polígono — foram 28 na primeira extração, e o Leaflet quebrou neles. Partir o anel
    no ponto mais distante do início dá duas linhas abertas, que o algoritmo trata bem.
    Se mesmo assim sobrar menos que um triângulo, a forma é menor que a tolerância.
    """
    meio = max(range(len(anel)), key=lambda i: math.dist(anel[0], anel[i]))
    ida, volta = simplificar(anel[: meio + 1], TOLERANCIA_M), simplificar(anel[meio:], TOLERANCIA_M)
    resultado = ida + volta[1:]
    return resultado if len(resultado) >= 4 else None


def juncoes(osm: dict) -> set[int]:
    """Pontos que pertencem a mais de uma trilha: os cruzamentos da rede."""
    vistos, repetidos = set(), set()
    for e in osm["elements"]:
        if e["type"] == "way" and camada_de(e.get("tags", {})) == "trilha":
            for n in e["nodes"]:
                (repetidos if n in vistos else vistos).add(n)
    return repetidos


def trechos_da_trilha(way: dict, cruzamentos: set[int]) -> list[list[tuple[float, float]]]:
    """Simplifica a trilha sem apagar cruzamento nenhum.

    O navegador traça a rota por esta rede (Dijkstra), e dois caminhos só estão
    ligados se dividem um ponto. Em 28/10/2026, 1054 cruzamentos ficavam no MEIO de
    uma trilha, e a simplificação de ponta a ponta apagaria parte deles, partindo a
    rede. Por isso a trilha é cortada em cada cruzamento, e cada pedaço é simplificado
    sozinho: as pontas de um pedaço nunca saem.

    Pontos fora da caixa vêm nulos da Overpass; eles também cortam a trilha.
    """
    trechos, atual = [], []
    for n, g in zip(way["nodes"], way["geometry"], strict=True):
        if not g:
            trechos.append(atual)
            atual = []
            continue
        atual.append((round(g["lon"], CASAS), round(g["lat"], CASAS)))
        if n in cruzamentos and len(atual) > 1:
            trechos.append(atual)
            atual = [atual[-1]]
    trechos.append(atual)

    linhas, linha = [], []
    for t in trechos:
        if len(t) < 2:
            if linha:
                linhas.append(linha)
            linha = []
            continue
        s = simplificar(t, TOLERANCIA_M)
        if linha and linha[-1] == s[0]:
            linha += s[1:]
        else:
            if linha:
                linhas.append(linha)
            linha = s
    if linha:
        linhas.append(linha)
    return [x for x in linhas if len(x) >= 2]


def feicoes(osm: dict) -> list[dict]:
    saida = []
    cruzamentos = juncoes(osm)
    for e in osm["elements"]:
        camada = camada_de(e.get("tags", {}))
        if not camada:
            continue
        if e["type"] == "way" and camada == "trilha":
            tipo = tipo_de_trilha(e["tags"])
            for linha in trechos_da_trilha(e, cruzamentos):
                geo = {"type": "LineString", "coordinates": linha}
                props = {"c": camada, "t": tipo}
                saida.append({"type": "Feature", "properties": props, "geometry": geo})
            if tipo == "borda":
                anel = simplificar_anel(coords(e["geometry"]))
                if anel and anel[0] == anel[-1]:
                    geo = {"type": "Polygon", "coordinates": [anel]}
                    saida.append({"type": "Feature", "properties": {"c": "praca"}, "geometry": geo})
            continue
        if e["type"] == "way":
            pts = coords(e.get("geometry", []))
            fechado = len(pts) >= 4 and pts[0] == pts[-1]
            if not fechado:
                linha = simplificar(pts, TOLERANCIA_M)
                if len(linha) < 2:
                    continue
                geo = {"type": "LineString", "coordinates": linha}
            else:
                anel = simplificar_anel(pts)
                if not anel:
                    continue
                geo = {"type": "Polygon", "coordinates": [anel]}
        else:  # relação multipolígono (lagos grandes vêm assim)
            externos = [coords(m["geometry"]) for m in e["members"] if m.get("role") == "outer"]
            aneis = [a for a in map(simplificar_anel, juntar_aneis(externos)) if a]
            if not aneis:
                continue
            geo = {"type": "MultiPolygon", "coordinates": [[a] for a in aneis]}
        saida.append({"type": "Feature", "properties": {"c": camada}, "geometry": geo})
    # Ordem de pintura: o que fica embaixo vem primeiro.
    ordem = {"verde": 0, "agua": 1, "praca": 2, "predio": 3, "trilha": 4}
    return sorted(saida, key=lambda f: ordem[f["properties"]["c"]])


def main() -> None:
    bbox = caixa()
    if "--baixar" in sys.argv or not CACHE.exists():
        print("consultando a Overpass (uma vez)...")
        baixar(bbox)
    osm = json.loads(CACHE.read_text(encoding="utf-8"))
    fs = feicoes(osm)

    geojson = {
        "type": "FeatureCollection",
        "attribution": "© OpenStreetMap contributors (ODbL)",
        "bbox": [bbox[1], bbox[0], bbox[3], bbox[2]],
        "features": fs,
    }
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(geojson, separators=(",", ":")), encoding="utf-8")

    def pontos(c) -> int:
        return 1 if isinstance(c[0], int | float) else sum(pontos(x) for x in c)

    bruto = sum(len(e.get("geometry", [])) for e in osm["elements"])
    final = sum(pontos(f["geometry"]["coordinates"]) for f in fs)
    contagem = {c: sum(f["properties"]["c"] == c for f in fs) for c in [*CAMADAS, "praca"]}
    print(f"feições: {contagem}")
    print(f"pontos: {bruto} brutos -> {final} depois da simplificação ({TOLERANCIA_M} m)")
    print(f"arquivo: {SAIDA.relative_to(RAIZ)} ({SAIDA.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()

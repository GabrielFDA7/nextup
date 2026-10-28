// Rota a pé pelas trilhas reais do parque (GeoJSON extraído do OpenStreetMap).
//
// Só desenha: o tempo de caminhada que o app mostra continua vindo da API
// (linha reta × sinuosidade 1,3, medida contra estas mesmas trilhas). Se a rede
// não ligar dois pontos, a rota cai para a linha reta em vez de sumir.

const RAIO_TERRA_M = 6371008.8;

function distanciaM([lat1, lon1], [lat2, lon2]) {
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad, dLon = (lon2 - lon1) * rad;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * RAIO_TERRA_M * Math.asin(Math.sqrt(a));
}

// Pontos iguais em trilhas diferentes são o mesmo cruzamento: a extração preserva
// as coordenadas exatas deles, então a chave de texto basta para ligar a rede.
export function montarRede(geojson) {
  const indice = new Map(), pontos = [], vizinhos = [];
  const no = (lon, lat) => {
    const chave = lon + "," + lat;
    if (!indice.has(chave)) { indice.set(chave, pontos.length); pontos.push([lat, lon]); vizinhos.push([]); }
    return indice.get(chave);
  };
  for (const f of geojson.features) {
    if (f.properties.c !== "trilha") continue;
    const c = f.geometry.coordinates;
    for (let i = 1; i < c.length; i++) {
      const a = no(...c[i - 1]), b = no(...c[i]);
      const d = distanciaM(pontos[a], pontos[b]);
      vizinhos[a].push([b, d]);
      vizinhos[b].push([a, d]);
    }
  }
  return { pontos, vizinhos, naRedePrincipal: maiorPedaco(vizinhos) };
}

// Encaixar alguém num trecho de trilha solto (há 28 pedaços) daria rota impossível.
function maiorPedaco(vizinhos) {
  const pedaco = new Int32Array(vizinhos.length).fill(-1), tamanhos = [];
  for (let s = 0; s < vizinhos.length; s++) {
    if (pedaco[s] !== -1) continue;
    const id = tamanhos.length, pilha = [s];
    pedaco[s] = id;
    let n = 0;
    while (pilha.length) {
      const u = pilha.pop(); n++;
      for (const [v] of vizinhos[u]) if (pedaco[v] === -1) { pedaco[v] = id; pilha.push(v); }
    }
    tamanhos.push(n);
  }
  const maior = tamanhos.indexOf(Math.max(...tamanhos));
  return (i) => pedaco[i] === maior;
}

function maisProximo(rede, ponto) {
  let melhor = -1, menor = Infinity;
  rede.pontos.forEach((p, i) => {
    if (!rede.naRedePrincipal(i)) return;
    const d = distanciaM(ponto, p);
    if (d < menor) { menor = d; melhor = i; }
  });
  return melhor;
}

// Dijkstra com fila de prioridade (heap binário): sempre expande o ponto ainda
// não fechado mais perto da origem, e para ao fechar o destino.
function dijkstra(rede, origem, destino) {
  const dist = new Float64Array(rede.pontos.length).fill(Infinity);
  const anterior = new Int32Array(rede.pontos.length).fill(-1);
  const heap = [[0, origem]];
  dist[origem] = 0;
  const subir = (i) => { while (i > 0) { const p = (i - 1) >> 1; if (heap[p][0] <= heap[i][0]) break; [heap[p], heap[i]] = [heap[i], heap[p]]; i = p; } };
  const descer = (i) => {
    for (;;) {
      const e = 2 * i + 1, d = e + 1; let m = i;
      if (e < heap.length && heap[e][0] < heap[m][0]) m = e;
      if (d < heap.length && heap[d][0] < heap[m][0]) m = d;
      if (m === i) return;
      [heap[m], heap[i]] = [heap[i], heap[m]]; i = m;
    }
  };
  while (heap.length) {
    const [du, u] = heap[0];
    const ultimo = heap.pop();
    if (heap.length) { heap[0] = ultimo; descer(0); }
    if (u === destino) break;
    if (du > dist[u]) continue; // entrada velha: o ponto já foi fechado por um caminho menor
    for (const [v, w] of rede.vizinhos[u]) {
      if (du + w < dist[v]) { dist[v] = du + w; anterior[v] = u; heap.push([dist[v], v]); subir(heap.length - 1); }
    }
  }
  if (dist[destino] === Infinity) return null;
  const caminho = [];
  for (let i = destino; i !== -1; i = anterior[i]) caminho.push(rede.pontos[i]);
  return { pontos: caminho.reverse(), metros: dist[destino] };
}

// Uma perna por par de paradas consecutivas. Cada ponto real liga à trilha mais
// próxima por um traço curto: a atração fica a alguns metros do caminho, não em cima.
export function rotaPelasTrilhas(rede, paradas) {
  const pernas = [];
  for (let i = 1; i < paradas.length; i++) {
    const de = paradas[i - 1], para = paradas[i];
    const trecho = dijkstra(rede, maisProximo(rede, de), maisProximo(rede, para));
    pernas.push(trecho
      ? { pontos: [de, ...trecho.pontos, para], metros: trecho.metros, pelaTrilha: true }
      : { pontos: [de, para], metros: distanciaM(de, para), pelaTrilha: false });
  }
  return pernas;
}

export { distanciaM };

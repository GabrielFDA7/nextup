/* Nomes das paradas no mapa sem sobreposição.
 *
 * Com geografia real não dá para fixar a posição de cada nome: Peter Pan e Seven
 * Dwarfs são vizinhas de verdade, e o que cabe num zoom bate no outro. Cada nome
 * tenta quatro lugares em volta do número e fica no primeiro livre. Se nenhum
 * estiver, ele some e o número fica — a lista abaixo do mapa dá o nome de cada
 * número. Ordem de prioridade: a do ranking, porque a primeira colocada é a que o
 * visitante procura primeiro.
 */

"use strict";

const ROTULOS = (() => {
  const FOLGA = 4; // px entre um nome e o que estiver perto dele
  const LADOS = ["dir", "esq", "cima", "baixo"];

  function retangulo(lado, cx, cy, raio, w, h) {
    const d = raio + 6;
    switch (lado) {
      case "dir": return { x1: cx + d, y1: cy - h / 2, x2: cx + d + w, y2: cy + h / 2 };
      case "esq": return { x1: cx - d - w, y1: cy - h / 2, x2: cx - d, y2: cy + h / 2 };
      case "cima": return { x1: cx - w / 2, y1: cy - d - h, x2: cx + w / 2, y2: cy - d };
      default: return { x1: cx - w / 2, y1: cy + d, x2: cx + w / 2, y2: cy + d + h };
    }
  }

  const bate = (a, b) =>
    a.x1 < b.x2 + FOLGA && b.x1 < a.x2 + FOLGA && a.y1 < b.y2 + FOLGA && b.y1 < a.y2 + FOLGA;

  // Retângulo de um elemento já desenhado, em coordenadas do contêiner do mapa.
  function caixaDe(el, mapa) {
    const r = el.getBoundingClientRect(), base = mapa.getContainer().getBoundingClientRect();
    return { x1: r.left - base.left, y1: r.top - base.top, x2: r.right - base.left, y2: r.bottom - base.top };
  }

  /**
   * paradas: [{ marcador, raio }] na ordem de prioridade; o nome é o `.rotulo` do marcador.
   * obstaculos: elementos que nenhum nome pode cobrir (destaque, "Você", botões do topo).
   */
  function posicionarRotulos(mapa, paradas, obstaculos) {
    const { x: largura, y: altura } = mapa.getSize();
    const ocupados = obstaculos.filter(Boolean).map((el) => caixaDe(el, mapa));

    // Todos os números entram antes de qualquer nome: um nome nunca cobre um número.
    for (const p of paradas) {
      const c = mapa.latLngToContainerPoint(p.marcador.getLatLng());
      p.centro = c;
      ocupados.push({ x1: c.x - p.raio, y1: c.y - p.raio, x2: c.x + p.raio, y2: c.y + p.raio });
    }

    for (const p of paradas) {
      const rotulo = p.marcador.getElement()?.querySelector(".rotulo");
      if (!rotulo) continue;
      rotulo.className = "rotulo dir"; // visível, para poder medir
      const w = rotulo.offsetWidth, h = rotulo.offsetHeight;
      const livre = LADOS.find((lado) => {
        const r = retangulo(lado, p.centro.x, p.centro.y, p.raio, w, h);
        const dentro = r.x1 >= FOLGA && r.y1 >= FOLGA && r.x2 <= largura - FOLGA && r.y2 <= altura - FOLGA;
        return dentro && !ocupados.some((o) => bate(r, o));
      });
      rotulo.className = "rotulo " + (livre || "oculto");
      if (livre) ocupados.push(retangulo(livre, p.centro.x, p.centro.y, p.raio, w, h));
    }
  }

  return { posicionar: posicionarRotulos };
})();

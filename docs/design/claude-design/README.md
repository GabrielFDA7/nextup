# Design da Fase 9.3

Export do **Claude Design** (feito com o prompt de [`../prompt-claude-design.md`](../prompt-claude-design.md))
e o que foi construído sobre ele em 28/10/2026. É referência para a implementação em `web/`,
não código do app.

## Como abrir

Os `.dc.html` carregam os vizinhos por requisição, então não abrem com duplo clique. Da raiz do
projeto:

```bash
python -m http.server 8766
```

E então, no navegador:

- <http://127.0.0.1:8766/docs/design/claude-design/NextUp%20-%20Dire%C3%A7%C3%B5es.dc.html> — as
  três direções originais e o protótipo refinado (rodadas 1 e 2 do Claude Design)
- <http://127.0.0.1:8766/docs/design/claude-design/NextUp%20-%20Algod%C3%A3o%20doce.dc.html> — as
  paletas pastel (rodada 3)
- <http://127.0.0.1:8766/docs/design/claude-design/mapa-real.html> — o mapa real, sem tiles

## O que é cada arquivo

| Arquivo | Origem | O que é |
|---|---|---|
| `NextUp.dc.html` | Claude Design, editado | Protótipo vivo. Ganhou os 6 temas algodão-doce e as variáveis `--glow-ink` / `--on-glow` |
| `NextUp - Direções.dc.html` | Claude Design | As três direções (1a, 1b, 1c) e o refinamento da 1c |
| `NextUpA/B/C.dc.html`, `NextUpComponentes.dc.html` | Claude Design | As telas de cada direção e os componentes isolados |
| `nu-map.js` | Claude Design | O mapa **ilustrado** — geografia inventada, descartado (ver abaixo) |
| `support.js` | Claude Design | Runtime dos `.dc.html` (gerado; não editar) |
| `NextUp - Algodão doce.dc.html` | NextUp | Comparação das paletas 3a, 3b e 3c |
| `mapa-real.html` | NextUp | Leaflet sem tiles, desenhando `web/mapas/magic-kingdom.geojson` |
| `rota.js` | NextUp | Rota pelas trilhas (Dijkstra); só desenha |
| `rotulos.js` | NextUp | Nomes das paradas sem sobreposição |

## O que foi decidido

- **Paleta:** 3c no modo claro (cartão escuro com os pastéis acesos), 3b no escuro (azul-noite).
  Azul é caminhada, rosa é fila, amarelo é destaque. Pastel só em fundo: todo texto usa o tom
  escuro da mesma cor, e os 24 pares de cada tema passam no contraste da WCAG.
- **Mapa:** real, não ilustrado. O desenho do Claude Design quebraria o "tocar no mapa define a
  posição" e o ponto do GPS. O Leaflet fica, sem tiles, pintando o GeoJSON com as variáveis CSS.
- **Rota:** segue as trilhas, mas **só desenha**. O tempo de caminhada continua vindo da API
  (linha reta × 1,3); trocá-lo pela distância das trilhas mudaria o ranking, e isso pede medição.
- **Rótulos:** números sempre; nomes por prioridade do roteiro, no primeiro de quatro lados
  livre, e escondidos se não couberem. Recalculados a cada zoom.

Detalhes e números na seção 10 de [`docs/PROJETO.md`](../../PROJETO.md).

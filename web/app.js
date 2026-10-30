/* NextUp — interface web.
 *
 * Sem framework e sem etapa de build, por decisão registrada na seção 5 do
 * docs/PROJETO.md: a tela é uma lista ordenada e um mapa. React aqui
 * acrescentaria dependências e deploy sem melhorar o produto.
 *
 * O fluxo é sempre o mesmo:
 *
 *     posição do visitante  +  parque escolhido
 *              └──────────────┬──────────────┘
 *                             ▼
 *            GET /api/parks/{id}/recommendations
 *                             ▼
 *                     lista  +  mapa
 *
 * Os três estados que sempre aparecem em app que depende de rede e de GPS estão
 * tratados de propósito: carregando, erro da API e recusa do GPS. Um app que
 * quebra quando o usuário nega a localização não serve para nada.
 */

"use strict";

const PARQUE_PADRAO = "75ea578a-adc8-4116-a54d-dccb60765ef9"; // Magic Kingdom
const LIMITE = 8;

/* A primeira versão é focada no Magic Kingdom — decisão do Gabriel, 28/10/2026: só
 * ele tem curadoria (altura, intensidade) e histórico, e nos outros parques o app
 * seria a "lista de filas" que a Fase 9 critica.
 *
 * O código dos outros parques **fica**, e continua testado: a chave só tira da
 * tela o caminho até eles. Os testes a ligam definindo `NEXTUP_SELETOR_DE_PARQUES`
 * antes de a página carregar. Religar para todo mundo é trocar esta linha.
 */
const MOSTRAR_SELETOR_DE_PARQUES = window.NEXTUP_SELETOR_DE_PARQUES === true;

//: Quanto tempo o "Desfazer" do "Já fui" do cartão fica à mão.
const DESFAZER_MS = 5000;

//: De quanto em quanto tempo as filas se renovam sozinhas. A fonte atualiza a cada
//: ~5 min e o cache do servidor dura 1: dois minutos deixam a tela no máximo um
//: passo atrás da fonte sem gastar a bateria e o 4G de quem está no parque.
const RENOVAR_MS = 2 * 60 * 1000;

//: O relógio que mantém a tela viva: refaz o "há X min" e confere se é hora de
//: renovar. Mais curto que `RENOVAR_MS` para o atraso máximo ser de 30 s, não 2 min.
const TIQUE_MS = 30 * 1000;

//: Dado mais velho que isto deixa de ser "ao vivo". Três vezes o ritmo da fonte:
//: um atraso dela é normal, três seguidos querem dizer que ela parou.
const VELHO_MS = 15 * 60 * 1000;

//: Quanto o visitante anda antes de o ranking ser refeito. Menos que isto some no
//: arredondamento dos minutos de caminhada, e o GPS entre prédios oscila uns
//: 10–20 m com a pessoa parada: refazer a cada oscilação seria gastar à toa.
const PASSO_MINIMO_M = 25;

//: Leitura de GPS menos precisa que isto é ignorada depois da primeira. Pior que
//: um quarteirão, ela confunde mais do que ajuda.
const PRECISAO_MAXIMA_M = 100;

//: Quantas colocadas seguintes o cartão cita abaixo da resposta. Duas cabem numa
//: linha de celular e bastam para "não gostei, e agora?".
const ALTERNATIVAS_NO_CARTAO = 2;

//: Janela do gráfico. Seis horas cobrem meio dia de parque e cabem em ~72 pontos
//: com a coleta de 5 minutos — densidade boa para a largura de um celular.
const HORAS_DE_HISTORICO = 6;

/** Estado da aplicação. Um objeto só, para ficar claro o que muda. */
const estado = {
  posicao: null, // { lat, lon }
  parqueId: PARQUE_PADRAO,
  carregando: false,
  /** Todos os destinos, guardados para a busca filtrar sem ir à rede de novo. */
  destinos: [],
  /** Fuso do parque atual. É o que define quando "hoje" vira "ontem". */
  fusoDoParque: "America/New_York",
  /** IDs marcados como visitados hoje, neste parque. */
  visitadas: new Set(),
  /** IDs que o visitante veio fazer. Sem prazo de validade. */
  alvos: new Set(),
  /** Todas as atrações do parque, para o seletor de alvos. */
  atracoesDoParque: [],
  /** Limites que o visitante impôs. Cortam a lista; não reordenam. */
  filtros: { filaMax: 125, caminhadaMax: 125 },
  /** Se as visitadas estão sendo exibidas em vez de escondidas. */
  mostrandoVisitadas: false,
  /** Quem pergunta: altura da criança mais baixa e gosto do grupo (Fase 9). */
  perfil: { respondido: false, alturaCm: null, intensidade: "tudo" },
  /** Se as atrações escondidas pelo gosto do grupo estão à mostra. */
  mostrandoEscondidas: false,
  /** Última resposta do ranking, para redesenhar sem ir à rede de novo. */
  ultimoRanking: null,
  /** Último panorama (o parque sem posição), pelo mesmo motivo. */
  ultimoPanorama: null,
  /** A melhor escolha da vez — o destino da rota desenhada no mapa. */
  destaque: null,
  /** O que o cartão mostra: "parque" (a melhor de todas) ou "alvos" (das minhas). */
  criterio: "parque",
  /** De onde veio o destaque: "parque", "alvos" ou "sem-alvos" (pediu e não havia). */
  origemDoDestaque: "parque",
  /** A 2ª e a 3ª do mesmo critério do cartão: o plano B sem abrir o painel. */
  alternativas: [],
  /** Os quatro cantos do parque, como a API devolve: o "parque inteiro" do mapa. */
  limitesDoParque: null,
  /** Se a posição está acompanhando o GPS, ou foi marcada à mão no mapa. */
  seguindoGps: false,
  /** Onde o visitante estava no último ranking: é dali que se mede o quanto andou. */
  posicaoDoRanking: null,
  /** Sobe a cada posição escolhida (a primeira do GPS, ou um toque no mapa), nunca
   * ao andar. O mapa só reenquadra quando ela ou a melhor escolha mudam. */
  versaoDaPosicao: 0,
  /** Quando a última busca deu certo, em ms. Zero: ainda não houve. */
  ultimaBusca: 0,
  /** Quando a fonte mediu as filas que estão na tela (ISO). */
  dadoDe: null,
  /** Se a última renovação automática falhou: a tela mostra dado velho, e diz. */
  falhouRenovar: false,
  /** Uma renovação que ficou para depois, porque o visitante estava no meio de algo. */
  renovacaoPendente: false,
};

const el = {
  parque: document.getElementById("parque"),
  buscaParque: document.getElementById("busca-parque"),
  buscaVazia: document.getElementById("busca-vazia"),
  btnLocalizar: document.getElementById("btn-localizar"),
  btnAtualizar: document.getElementById("btn-atualizar"),
  posicaoAtual: document.getElementById("posicao-atual"),
  aviso: document.getElementById("aviso"),
  resumo: document.getElementById("resumo"),
  lista: document.getElementById("lista"),
  atualizado: document.getElementById("atualizado"),
  tituloLista: document.getElementById("titulo-lista"),
  visitadasAviso: document.getElementById("visitadas-aviso"),
  visitadasTexto: document.getElementById("visitadas-texto"),
  btnMostrarVisitadas: document.getElementById("btn-mostrar-visitadas"),
  btnLimparVisitadas: document.getElementById("btn-limpar-visitadas"),
  secaoAlvos: document.getElementById("secao-alvos"),
  listaAlvos: document.getElementById("lista-alvos"),
  alvosResumo: document.getElementById("alvos-resumo"),
  btnLimparAlvos: document.getElementById("btn-limpar-alvos"),
  escolherAlvos: document.getElementById("escolher-alvos"),
  buscaAtracao: document.getElementById("busca-atracao"),
  catalogoAtracoes: document.getElementById("catalogo-atracoes"),
  escolherVazio: document.getElementById("escolher-vazio"),
  filtros: document.getElementById("filtros"),
  filtrosAtivos: document.getElementById("filtros-ativos"),
  filtroFila: document.getElementById("filtro-fila"),
  filtroCaminhada: document.getElementById("filtro-caminhada"),
  filtrosFaixa: document.querySelectorAll(".filtro-faixa"),
  rotuloFila: document.getElementById("rotulo-fila"),
  rotuloCaminhada: document.getElementById("rotulo-caminhada"),
  btnLimparFiltros: document.getElementById("btn-limpar-filtros"),
  btnPerfil: document.getElementById("btn-perfil"),
  perfilResumo: document.getElementById("perfil-resumo"),
  painelPerfil: document.getElementById("painel-perfil"),
  painelPerfilTitulo: document.getElementById("painel-perfil-titulo"),
  btnPularPerfil: document.getElementById("btn-pular-perfil"),
  btnSalvarPerfil: document.getElementById("btn-salvar-perfil"),
  alturaCampo: document.getElementById("altura-campo"),
  altura: document.getElementById("altura"),
  alturaValor: document.getElementById("altura-valor"),
  alturaDica: document.getElementById("altura-dica"),
  btnAlturaMenos: document.getElementById("btn-altura-menos"),
  btnAlturaMais: document.getElementById("btn-altura-mais"),
  perfilAviso: document.getElementById("perfil-aviso"),
  perfilAvisoTexto: document.getElementById("perfil-aviso-texto"),
  btnMostrarEscondidas: document.getElementById("btn-mostrar-escondidas"),
  campoParque: document.getElementById("campo-parque"),
  btnTodasFilas: document.getElementById("btn-todas-filas"),
  todasFilasN: document.getElementById("todas-filas-n"),
  painelFilas: document.getElementById("painel-filas"),
  btnFecharFilas: document.getElementById("btn-fechar-filas"),
  passoSemPosicao: document.getElementById("passo-sem-posicao"),
  passoTitulo: document.getElementById("passo-titulo"),
  frescor: document.getElementById("frescor"),
  passoCriterio: document.getElementById("passo-criterio"),
  passoDestaque: document.getElementById("passo-destaque"),
  desfazer: document.getElementById("desfazer"),
  desfazerTexto: document.getElementById("desfazer-texto"),
  btnDesfazer: document.getElementById("btn-desfazer"),
};

let mapa;
let marcadorVisitante;
let camadaAtracoes;
/** O fundo do mapa: o desenho do parque, ou tiles onde não há desenho. */
let camadaFundo;
/** A rota a pé até a melhor escolha, pelas trilhas. */
let camadaRota;
/** A rede de trilhas do parque atual, para traçar a rota. `null` sem desenho. */
let redeDeTrilhas = null;
/** Entre `movestart` e `moveend`: os nomes estão em trânsito. */
let mapaEmMovimento = false;

/* Os parques que têm desenho próprio, extraído do OpenStreetMap por
 * `scripts/extrair_mapa_mk.py`. Só o Magic Kingdom por enquanto — é o foco da
 * primeira versão, e o único com curadoria e histórico. Os outros seguem com
 * tiles, que funcionam em qualquer lugar do mundo.
 */
const DESENHOS = { [PARQUE_PADRAO]: "mapas/magic-kingdom.geojson" };

/* Quantas colocadas ganham nome e marcador grande no mapa. Com as oito nomeadas, o
 * mapa do celular virava uma sopa de letras em que nada se destacava (Gabriel,
 * 28/10/2026). As três primeiras são as que o visitante compara; a lista completa
 * dá o nome de todos os números.
 */
const NOMES_NO_MAPA = 3;

/** O enquadramento da resposta já feito: só se refaz quando a resposta muda. */
let enquadramentoFeito = null;
/** O visitante e as primeiras colocadas: aonde o botão de recentralizar volta. */
let pontosDaResposta = null;
/** Centro e zoom em que o enquadramento da resposta terminou. */
let vistaDaResposta = null;
/** O parque desenhado. Enquanto houver, o mapa não sai dele. */
let limitesDoDesenho = null;

/* Quanto o mapa deixa passar da borda do parque desenhado, em fração do tamanho
 * dele. Zero cortaria os marcadores da borda pela metade; muito mais deixaria o
 * visitante se perder de novo no estacionamento. */
const FOLGA_DO_PARQUE = 0.12;

// ---------------------------------------------------------------------------
// Avisos
// ---------------------------------------------------------------------------

function mostrarAviso(texto, tipo = "erro") {
  el.aviso.textContent = texto;
  el.aviso.dataset.tipo = tipo;
  el.aviso.hidden = false;
}

function limparAviso() {
  el.aviso.hidden = true;
}

// ---------------------------------------------------------------------------
// Mapa
// ---------------------------------------------------------------------------

const CREDITO_OSM = '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>';

function iniciarMapa() {
  // A vista vem ANTES de qualquer camada vetorial: sem centro e zoom, o Leaflet não
  // sabe recortar as linhas e quebra ("reading 'min'"). Achado no protótipo.
  // Zoom em quartos: com só inteiros, enquadrar a resposta caía um nível inteiro
  // abaixo do que cabia, e o celular voltava a ver o parque todo, miúdo.
  // `maxBoundsViscosity: 1`: o limite do parque é parede, não elástico. Sem limite
  // (parques com tiles), a opção não faz nada.
  mapa = L.map("mapa", { zoomControl: false, zoomSnap: 0.25, maxBoundsViscosity: 1 }).setView(
    [28.4177, -81.5812],
    15
  );
  // O canto esquerdo é da marca, que flutua sobre o mapa.
  L.control.zoom({ position: "topright" }).addTo(mapa);
  // No canto de baixo, onde o polegar alcança — o lugar do "minha localização"
  // em qualquer app de mapa.
  new BotaoRecentralizar({ position: "bottomright" }).addTo(mapa);
  mapa.on("resize", ajustarZoomMinimo);

  // O desenho do parque mora numa camada própria, abaixo da rota (400). Antes ele
  // dividia a camada com a rota e era empurrado para o fundo com `bringToBack()` —
  // que, num grupo, leva cada caminho ao fundo um de cada vez e INVERTE a pilha: o
  // gramado era pintado por cima das trilhas, e o véu, por baixo de tudo.
  mapa.createPane("desenho").style.zIndex = 350;
  // Os nomes das áreas, entre a rota (400) e os marcadores (600): acima do véu
  // sobre o entorno e abaixo de qualquer número.
  mapa.createPane("areas").style.zIndex = 450;
  marcarZoom();

  camadaRota = L.layerGroup().addTo(mapa);
  camadaAtracoes = L.layerGroup().addTo(mapa);
  trocarFundoDoMapa(estado.parqueId);

  // Tocar no mapa define a posição. Resolve dois problemas de uma vez: quem
  // negou o GPS ainda consegue usar o app, e quem está com GPS impreciso
  // (comum entre prédios) pode corrigir na mão — risco previsto na seção 8.
  // O desenho do parque é `interactive: false` justamente para o toque chegar aqui.
  mapa.on("click", (evento) => {
    // Marcar à mão é corrigir o GPS, e o GPS não pode desfazer a correção no
    // segundo seguinte: o acompanhamento para até o visitante pedir de volta.
    pararDeSeguirGps();
    definirPosicao(evento.latlng.lat, evento.latlng.lng, "mapa");
  });

  // Zoom e arrasto mudam o espaço livre: os nomes se reorganizam. Durante a
  // animação eles estão em trânsito, e o atributo sai para dizer isso — é o que
  // os testes esperam, em vez de um tempo fixo que um dia não basta.
  mapa.on("movestart zoomstart", () => {
    mapaEmMovimento = true;
    delete mapa.getContainer().dataset.rotulos;
  });
  mapa.on("zoomend moveend", () => {
    mapaEmMovimento = false;
    marcarZoom();
    posicionarRotulos();
  });
}

/* O traço do Leaflet tem espessura fixa em pixels, e a via que é larga no zoom do
 * parque inteiro vira um fio quando o mapa aproxima. O CSS engrossa pelo zoom. */
function marcarZoom() {
  mapa.getContainer().dataset.zoom = String(Math.round(mapa.getZoom()));
}

/* O nome de uma área do parque, escrito no chão do mapa. */
function nomeDeArea(feicao, posicao) {
  return L.marker(posicao, {
    pane: "areas",
    interactive: false,
    keyboard: false,
    icon: L.divIcon({
      className: "",
      html: `<span class="m-nome-area">${escapar(feicao.properties.nome)}</span>`,
      iconSize: [0, 0],
    }),
  });
}

/* O fundo do mapa, conforme o parque.
 *
 * Com desenho próprio, o Leaflet pinta o GeoJSON com as variáveis CSS do tema —
 * e o mapa troca de cor junto com o resto da tela, o que tile nenhum faz: ele já
 * vem pintado do servidor. Sem desenho, tiles: funcionam em qualquer parque.
 */
async function trocarFundoDoMapa(parqueId) {
  if (camadaFundo) mapa.removeLayer(camadaFundo);
  camadaFundo = null;
  redeDeTrilhas = null;
  camadaRota.clearLayers();
  // Solto até o desenho chegar: preso ao parque anterior, o mapa não deixaria o
  // enquadramento do parque novo acontecer.
  soltarDoParque();

  const arquivo = DESENHOS[parqueId];
  mapa.getContainer().classList.toggle("mapa--desenhado", Boolean(arquivo));

  if (arquivo) {
    try {
      const resposta = await fetch(arquivo);
      if (!resposta.ok) throw new Error("desenho indisponível");
      const desenho = await resposta.json();

      // O visitante pode ter trocado de parque enquanto o arquivo vinha.
      if (estado.parqueId !== parqueId) return;

      // Quatro grupos, na ordem em que são pintados. A casca são as próprias
      // trilhas, mais largas e mais escuras, pintadas antes delas: o contorno que
      // faz um caminho branco aparecer sobre um chão claro. Sem ela, o tema claro
      // perdia as vias de vista (Gabriel, 28/10/2026); o escuro não precisa, e o
      // CSS a apaga lá.
      const so = (...camadas) => ({
        type: "FeatureCollection",
        features: desenho.features.filter((f) => camadas.includes(f.properties.c)),
      });
      const opcoes = {
        style: (f) => ({ className: `m-${f.properties.c}${f.properties.t ? ` m-${f.properties.t}` : ""}` }),
        // Os únicos pontos do desenho são os nomes das áreas.
        pointToLayer: nomeDeArea,
        pane: "desenho",
        interactive: false,
      };
      const casca = {
        ...opcoes,
        style: (f) => ({ className: `m-casco m-casco-${f.properties.t}` }),
      };
      // Criadas NA ORDEM DE PINTURA, uma por linha: o grupo do Leaflet pinta pela
      // ordem em que cada camada nasceu (o id que ela recebe), e não pela ordem da
      // lista. Criar as trilhas antes da casca, para guardar a referência, pintou a
      // casca por cima dos caminhos (29/10/2026, pego por
      // `test_o_contorno_fica_por_baixo_das_trilhas`).
      const chao = L.geoJSON(so("verde", "agua", "praca", "predio"), {
        ...opcoes,
        attribution: CREDITO_OSM,
      });
      const contorno = L.geoJSON(so("trilha"), casca);
      const trilhas = L.geoJSON(so("trilha"), opcoes);
      const entorno = L.geoJSON(so("fora", "area"), opcoes);
      camadaFundo = L.featureGroup([chao, contorno, trilhas, entorno]).addTo(mapa);
      // O limite é o parque desenhado, sem o véu: o véu cobre quilômetros de
      // estacionamento e estrada justamente para não chamar o olho para lá.
      prenderAoParque(L.featureGroup([chao, trilhas]).getBounds());
      redeDeTrilhas = ROTA.montarRede(desenho);
      desenharRota();
      return;
    } catch {
      // Sem o desenho, o mapa ainda precisa existir: cai para os tiles.
      mapa.getContainer().classList.remove("mapa--desenhado");
    }
  }

  if (estado.parqueId !== parqueId) return;
  camadaFundo = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: CREDITO_OSM,
  }).addTo(mapa);
}

/* A rota a pé do visitante até a melhor escolha, pelas trilhas.
 *
 * Só desenha. O número que o app mostra continua vindo da API, e o traçado existe
 * para o visitante ver POR ONDE ir — que a linha reta, atravessando prédios, não
 * diz. Só onde há rede de trilhas; nos outros parques não há o que seguir.
 */
function desenharRota() {
  camadaRota.clearLayers();
  if (!redeDeTrilhas || !estado.posicao || !estado.destaque) return;

  const { latitude, longitude } = estado.destaque.attraction;
  const pernas = ROTA.rotaPelasTrilhas(redeDeTrilhas, [
    [estado.posicao.lat, estado.posicao.lon],
    [latitude, longitude],
  ]);
  const tracado = pernas.map((p) => p.pontos);

  L.polyline(tracado, { className: "m-rota-halo", interactive: false }).addTo(camadaRota);
  L.polyline(tracado, { className: "m-rota", interactive: false }).addTo(camadaRota);
}

/* Os nomes ao lado dos números, sem sobreposição (web/rotulos.js).
 *
 * Prioridade pela ordem do ranking: a primeira colocada é a que o visitante
 * procura primeiro. Nada pode ser coberto por um nome: o "Você", os botões de
 * zoom e o crédito do mapa.
 */
function posicionarRotulos() {
  // Todo marcador entra, com nome ou sem: os sem nome são obstáculo para os outros.
  const paradas = [];
  camadaAtracoes.eachLayer((marcador) => {
    paradas.push({ marcador, raio: marcador.options.raio ?? 15, ordem: marcador.options.ordem ?? 0 });
  });
  paradas.sort((a, b) => a.ordem - b.ordem);

  const container = mapa.getContainer();
  const obstaculos = [
    marcadorVisitante?.getElement(),
    container.querySelector(".leaflet-control-zoom"),
    container.querySelector(".leaflet-control-attribution"),
    // A marca flutua sobre o mapa, fora do contêiner dele.
    document.querySelector(".selo-marca"),
  ];
  ROTULOS.posicionar(mapa, paradas, obstaculos);
  esconderAreasCobertas(container, obstaculos);

  // O ranking pode chegar no meio de uma animação: a conta então vale para uma
  // vista que ainda vai mudar, e o `moveend` refaz e anuncia.
  if (!mapaEmMovimento) container.dataset.rotulos = "prontos";
}

/* Acende no mapa o número do item da lista sob o ponteiro (computador).
 *
 * Vale para a lista do parque e para a dos alvos: o item acende o pino da mesma
 * atração, se ela estiver no mapa. Antes do ranking os marcadores não têm número,
 * e nada acende — não há número para ligar.
 */
function realcarNoMapa(evento) {
  const anterior = mapa.getContainer().querySelector(".pino--realce");
  anterior?.classList.remove("pino--realce");
  if (evento.type === "mouseleave") return;

  // Pela atração, e não pela posição na lista: com "Das minhas" os pinos são os
  // dos alvos, e a terceira da lista do parque não é mais o pino 3.
  const id = evento.target.closest(".item")?.querySelector("[data-atracao]")?.dataset.atracao;
  if (!id) return;
  camadaAtracoes.eachLayer((marcador) => {
    if (marcador.options.atracao === id) {
      marcador.getElement()?.querySelector(".pino")?.classList.add("pino--realce");
    }
  });
}

/* O nome de uma área cede a vez a qualquer coisa que o visitante precise ler.
 *
 * Ele orienta ("estou na Fantasyland"), mas não responde nada: se bate num número,
 * num nome de atração ou no "Você", some. */
function esconderAreasCobertas(container, obstaculos) {
  const caixas = [
    ...container.querySelectorAll(".pino, .rotulo:not(.oculto)"),
    ...obstaculos.filter(Boolean),
  ].map((e) => e.getBoundingClientRect());
  const moldura = container.getBoundingClientRect();

  for (const nome of container.querySelectorAll(".m-nome-area")) {
    nome.classList.remove("oculto");
    const r = nome.getBoundingClientRect();
    // Cortado pela borda, "ADVENTURELAND" vira "TURELAND": pior que nome nenhum.
    const cortado =
      r.left < moldura.left || r.right > moldura.right || r.top < moldura.top || r.bottom > moldura.bottom;
    const coberto = caixas.some(
      (c) => r.left < c.right && c.left < r.right && r.top < c.bottom && c.top < r.bottom
    );
    nome.classList.toggle("oculto", cortado || coberto);
  }
}

/* Marcador numerado, na paleta do app.
 *
 * O alfinete azul padrão do Leaflet destoa do resto e, pior, não diz nada: oito
 * marcadores idênticos não permitem ligar o mapa à lista. Numerado, dá para
 * achar no mapa a atração que está em primeiro sem contar pontinhos.
 */
function marcadorNumerado(posicao, nome) {
  const melhor = posicao === 1;

  // Da quarta em diante: menor e sem nome. Continua no mapa, porque o número liga
  // a atração à lista; só não disputa o olhar com as três que importam agora.
  if (posicao > NOMES_NO_MAPA) {
    return L.divIcon({
      className: "",
      html: `<span class="pino pino--menor">${posicao}</span>`,
      iconSize: [24, 24],
      iconAnchor: [12, 12],
      popupAnchor: [0, -11],
    });
  }

  // O nome vai junto, e quem decide se ele aparece (e de que lado) é
  // `posicionarRotulos`: com geografia real, vizinhas de verdade se sobrepõem.
  return L.divIcon({
    className: "",
    html: `<span class="pino${melhor ? " pino--melhor" : ""}">${posicao}</span><span class="rotulo">${escapar(nome)}</span>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -14],
  });
}

function desenharMapa(recomendacoes) {
  camadaAtracoes.clearLayers();

  recomendacoes.forEach((item, indice) => {
    const { latitude, longitude } = item.attraction;

    L.marker([latitude, longitude], {
      icon: marcadorNumerado(indice + 1, item.attraction.name),
      // Atrações vizinhas ficam a poucos metros, então os marcadores se
      // sobrepõem. Quanto melhor a colocação, mais na frente: a resposta do app
      // não pode ficar escondida atrás de uma opção pior.
      zIndexOffset: (recomendacoes.length - indice) * 10,
      ordem: indice,
      atracao: item.attraction.id,
      raio: indice < NOMES_NO_MAPA ? 15 : 12,
    })
      .bindPopup(`<strong>${indice + 1}. ${escapar(item.attraction.name)}</strong><br>
         ${Math.round(item.total_minutes)} min no total`)
      .addTo(camadaAtracoes);
  });

  posicionarRotulos();
}

/* O ponto do visitante: o padrão dos mapas de celular (ponto azul com halo), que
 * ninguém precisa aprender. Acima de todos os números — é a referência de tudo.
 *
 * Só move a vista se o ponto ficou fora dela. Quem enquadra é a resposta
 * (`enquadrarResposta`): dois saltos seguidos, um para o visitante e outro para as
 * atrações, desorientavam mais do que ajudavam.
 */
function marcarVisitante(lat, lon, { centralizar = true } = {}) {
  if (marcadorVisitante) {
    marcadorVisitante.setLatLng([lat, lon]);
  } else {
    marcadorVisitante = L.marker([lat, lon], {
      icon: L.divIcon({
        className: "",
        html: '<span class="voce"></span>',
        iconSize: [22, 22],
        iconAnchor: [11, 11],
        popupAnchor: [0, -10],
      }),
      zIndexOffset: 2000,
      keyboard: false,
    }).addTo(mapa);
    marcadorVisitante.bindPopup("Você está aqui");
  }
  // Ao andar, o ponto se move e o mapa fica: puxar a vista a cada passo tiraria o
  // mapa das mãos de quem está olhando outra parte do parque.
  if (centralizar && !mapa.getBounds().contains([lat, lon])) mapa.setView([lat, lon], 17);
}

/* Aproxima o mapa do que o visitante está decidindo: ele e as primeiras colocadas.
 *
 * Antes o mapa mostrava o parque inteiro, e no celular os oito números cabiam
 * num punhado de centímetros sobre um desenho miúdo. Só se refaz quando a
 * resposta muda (outra posição ou outra melhor escolha): reenquadrar a cada
 * atualização puxaria o mapa das mãos de quem está arrastando.
 */
function enquadrarResposta(recomendacoes) {
  if (!estado.posicao || recomendacoes.length === 0) return;

  // Guardados sempre, mesmo quando o enquadramento não se refaz: são o destino
  // do botão de recentralizar.
  // O destaque entra sempre: com "Das minhas", ele pode estar longe das primeiras
  // do ranking, e a rota até ele sairia da tela.
  const destaque = estado.destaque ? [estado.destaque] : [];
  pontosDaResposta = [
    [estado.posicao.lat, estado.posicao.lon],
    ...[...destaque, ...recomendacoes.slice(0, NOMES_NO_MAPA)].map((r) => [
      r.attraction.latitude,
      r.attraction.longitude,
    ]),
  ];

  // A versão da posição, e não a coordenada: andar pelo GPS muda a coordenada a
  // cada passo, e reenquadrar a cada passo puxaria o mapa das mãos de quem olha.
  const chave = `${estado.versaoDaPosicao},${estado.destaque?.attraction.id}`;
  if (chave === enquadramentoFeito) return;
  enquadramentoFeito = chave;

  // Pedido no meio de uma animação de zoom, o enquadramento é DESCARTADO em
  // silêncio pelo Leaflet (`_tryAnimatedZoom` responde "já movi" sem mover). Na
  // abertura o mapa anima até o parque inteiro, e um GPS rápido caía bem nessa
  // janela: o mapa ficava longe, sem erro nenhum. Esperar o fim da animação resolve.
  if (mapaEmMovimento) mapa.once("moveend", () => enquadrarPontos(pontosDaResposta));
  else enquadrarPontos(pontosDaResposta);
}

/** O visitante e as primeiras colocadas, com folga maior no topo, onde a marca flutua. */
function enquadrarPontos(pontos) {
  // A vista só é conhecida quando o movimento termina — e é ela, e não os pontos,
  // que o botão de recentralizar compara: o limite do parque pode ter cortado o
  // enquadramento pedido.
  mapa.once("moveend", () => {
    vistaDaResposta = { centro: mapa.getCenter(), zoom: mapa.getZoom() };
  });
  mapa.fitBounds(pontos, {
    paddingTopLeft: [36, 76],
    paddingBottomRight: [36, 44],
    maxZoom: 18,
  });
}

/* Enquadra o parque inteiro, em vez de centralizar num ponto.
 *
 * Centralizar exigiria adivinhar o zoom, e o zoom certo para o Magic Kingdom é o
 * errado para um parque três vezes maior. Com os quatro cantos que a API devolve,
 * o Leaflet calcula o zoom sozinho.
 *
 * Isto conserta um comportamento que era quase um bug: escolher Disneyland Paris
 * deixava o mapa parado na Flórida, sem nenhuma pista de que o parque tinha
 * mudado.
 */
function enquadrarParque(limites) {
  if (!limites) return;

  mapa.fitBounds(
    [
      [limites.south, limites.west],
      [limites.north, limites.east],
    ],
    // Sem folga, as atrações da borda encostam na moldura do mapa e os
    // marcadores ficam cortados pela metade.
    { padding: [30, 30], maxZoom: 17 }
  );
}

/* O mapa preso ao parque (Gabriel, 29/10/2026).
 *
 * Na versão só do Magic Kingdom, arrastar para fora dele não mostra nada útil — e
 * quem se perde no estacionamento não sabe voltar. O limite é o parque desenhado
 * com uma folga, e o zoom mínimo é o que mostra esse retângulo inteiro: mais
 * longe que isso, o parque só encolheria no meio de um vazio.
 *
 * Só onde há desenho. Nos parques com tiles (atrás da chave do seletor) o mapa
 * continua livre, como sempre foi.
 */
function prenderAoParque(limites) {
  limitesDoDesenho = limites.pad(FOLGA_DO_PARQUE);
  mapa.setMaxBounds(limitesDoDesenho);
  ajustarZoomMinimo();
}

function soltarDoParque() {
  limitesDoDesenho = null;
  mapa.setMaxBounds(null);
  mapa.setMinZoom(0);
}

/* O zoom mínimo depende do tamanho da tela: girar o celular, ou a coluna do
 * computador, muda quanto do parque cabe. Por isso ele se refaz no `resize`. */
function ajustarZoomMinimo() {
  if (!limitesDoDesenho) return;
  mapa.setMinZoom(mapa.getBoundsZoom(limitesDoDesenho));
}

/* Volta o mapa para o que importa, alternando entre dois destinos.
 *
 * O primeiro toque traz de volta o visitante e as primeiras colocadas — a vista
 * que o app monta sozinho. Se o mapa já está nela, o toque mostra o parque
 * inteiro. Sem posição, só existe o parque inteiro. É o comportamento do botão
 * de localização dos apps de mapa, que o visitante já conhece.
 */
function recentralizar() {
  if (pontosDaResposta && estado.posicao && !mapaNaVista(vistaDaResposta)) {
    enquadrarPontos(pontosDaResposta);
    return;
  }
  enquadrarParque(estado.limitesDoParque);
}

/** Se o mapa está parado na vista dada — com tolerância de uns metros. */
function mapaNaVista(vista) {
  return (
    vista !== null &&
    Math.abs(mapa.getZoom() - vista.zoom) < 0.01 &&
    mapa.getCenter().distanceTo(vista.centro) < 5
  );
}

/* O botão, como controle do Leaflet: assim ele mora dentro do mapa e acompanha a
 * pilha de controles do canto, sem posicionamento à mão. */
const BotaoRecentralizar = L.Control.extend({
  onAdd() {
    const botao = L.DomUtil.create("button", "recentralizar");
    botao.id = "btn-recentralizar";
    botao.type = "button";
    botao.innerHTML = ICONE.mira;
    botao.setAttribute("aria-label", "Recentralizar o mapa");
    botao.title = "Volta para você. Toque de novo para ver o parque inteiro.";
    // Sem isto o toque atravessaria o botão e chegaria ao mapa, que o leria como
    // "estou aqui" e moveria o visitante para o canto da tela.
    L.DomEvent.disableClickPropagation(botao);
    L.DomEvent.on(botao, "click", recentralizar);
    return botao;
  },
});

/* Marcador discreto para quando ainda não há ranking.
 *
 * Numerar exigiria uma ordem, e ordem é exatamente o que não existe antes de o
 * visitante dizer onde está. Um ponto neutro mostra o parque sem fingir que
 * respondeu a pergunta do app.
 */
function marcadorSimples(fila) {
  const texto = fila === null ? "—" : String(fila);

  return L.divIcon({
    className: "",
    html: `<span class="pino pino--neutro">${texto}</span>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -14],
  });
}

/** Desenha o parque sem ranking: as atrações e suas filas de agora. */
function desenharParque(atracoes) {
  camadaAtracoes.clearLayers();

  atracoes.forEach((item) => {
    const fila = item.queue_minutes;
    const descricao = fila === null ? "sem fila medida" : `${fila} min de fila`;

    L.marker([item.latitude, item.longitude], { icon: marcadorSimples(fila) })
      .bindPopup(`<strong>${escapar(item.name)}</strong><br>${descricao}`)
      .addTo(camadaAtracoes);
  });
}

// ---------------------------------------------------------------------------
// Posição
// ---------------------------------------------------------------------------

/* Uma posição nova e escolhida: a primeira do GPS, ou um toque no mapa.
 *
 * Andar não passa por aqui — passa por `andarPeloGps`, que move o ponto sem
 * reenquadrar o mapa nem mostrar o carregamento. */
function definirPosicao(lat, lon, origem) {
  estado.posicao = { lat, lon };
  estado.versaoDaPosicao += 1;
  descreverPosicao(origem);
  marcarVisitante(lat, lon);
  buscarRecomendacoes();
}

/* Frase, e não coordenada: "28.41707, -81.58104" não diz nada a quem está no
 * parque. O número continua no `title`, para quem precisar conferir. */
function descreverPosicao(origem) {
  const { lat, lon } = estado.posicao;
  // Quem marcou à mão precisa de um caminho de volta para o GPS, e ele mora
  // aqui: o botão "Usar minha localização" sumiu quando a posição foi dada.
  const voltar = navigator.geolocation
    ? ' · <button type="button" class="link voltar-gps">Usar o GPS</button>'
    : "";
  el.posicaoAtual.innerHTML =
    origem === "gps"
      ? '<span aria-hidden="true">📍</span> Seguindo você pelo GPS'
      : `<span aria-hidden="true">📍</span> Posição marcada no mapa${voltar}`;
  el.posicaoAtual.title = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
  el.posicaoAtual.hidden = false;
}

/** O id do `watchPosition`, para parar de acompanhar. */
let vigiaDoGps = null;

/* Acompanha o visitante pelo GPS, e não só uma leitura (30/10/2026).
 *
 * Até aqui a posição era lida uma vez: quem andava pelo parque continuava vendo o
 * ranking calculado a partir de onde estava ao abrir o app — "o mais perto" de dez
 * minutos atrás. A primeira leitura posiciona e enquadra; as seguintes movem o
 * ponto e, quando o visitante andou o bastante, refazem o ranking em silêncio.
 */
function localizar() {
  if (!navigator.geolocation) {
    mostrarAviso(
      "Este navegador não oferece localização. Toque no mapa para marcar onde você está."
    );
    return;
  }

  pararDeSeguirGps();
  el.btnLocalizar.disabled = true;
  el.btnLocalizar.textContent = "Localizando…";
  mostrarAviso("Procurando sua posição…", "info");

  let primeira = true;
  vigiaDoGps = navigator.geolocation.watchPosition(
    (posicao) => {
      const { latitude, longitude, accuracy } = posicao.coords;
      if (primeira) {
        primeira = false;
        estado.seguindoGps = true;
        restaurarBotaoLocalizar();
        limparAviso();
        definirPosicao(latitude, longitude, "gps");
        return;
      }
      if (accuracy > PRECISAO_MAXIMA_M) return;
      andarPeloGps(latitude, longitude);
    },
    (erro) => {
      if (primeira) {
        restaurarBotaoLocalizar();
        mostrarAviso(explicarErroDeGps(erro));
        pararDeSeguirGps();
        return;
      }
      // Depois da primeira, perder o sinal por um instante é rotina — entre
      // prédios, numa fila coberta. Só a recusa da permissão muda alguma coisa.
      if (erro.code === erro.PERMISSION_DENIED) {
        pararDeSeguirGps();
        descreverPosicao("mapa");
      }
    },
    // `enableHighAccuracy` pede o GPS de verdade em vez da posição aproximada
    // por antena — necessário para diferenciar atrações a 50 m uma da outra.
    { enableHighAccuracy: true, timeout: 20000, maximumAge: 10000 }
  );
}

function pararDeSeguirGps() {
  if (vigiaDoGps !== null) navigator.geolocation.clearWatch(vigiaDoGps);
  vigiaDoGps = null;
  estado.seguindoGps = false;
}

/* O visitante andou. O ponto e a rota acompanham sempre; o ranking só quando a
 * distância desde o último já muda a conta (`PASSO_MINIMO_M`). */
function andarPeloGps(lat, lon) {
  estado.posicao = { lat, lon };
  el.posicaoAtual.title = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
  marcarVisitante(lat, lon, { centralizar: false });
  desenharRota();

  const desde = estado.posicaoDoRanking;
  if (!desde || metrosEntre(desde, estado.posicao) >= PASSO_MINIMO_M) {
    renovar();
  }
}

/** Distância curta em metros. Plana, e não Haversine: em centenas de metros a
 * curvatura da Terra não aparece no terceiro algarismo. */
function metrosEntre(a, b) {
  const rad = Math.PI / 180;
  const x = (b.lon - a.lon) * rad * Math.cos(((a.lat + b.lat) / 2) * rad);
  const y = (b.lat - a.lat) * rad;
  return Math.hypot(x, y) * 6371000;
}

function restaurarBotaoLocalizar() {
  el.btnLocalizar.disabled = false;
  el.btnLocalizar.textContent = "Usar minha localização";
}

/** Transforma o código de erro do navegador em instrução para o usuário. */
function explicarErroDeGps(erro) {
  const alternativa = "Toque no mapa para marcar onde você está.";

  switch (erro.code) {
    case erro.PERMISSION_DENIED:
      return `Você negou o acesso à localização. ${alternativa}`;
    case erro.POSITION_UNAVAILABLE:
      return `Não foi possível obter sua posição agora. ${alternativa}`;
    case erro.TIMEOUT:
      return `O GPS demorou demais para responder. ${alternativa}`;
    default:
      return `Não consegui usar o GPS. ${alternativa}`;
  }
}

// ---------------------------------------------------------------------------
// Dados
// ---------------------------------------------------------------------------

async function carregarParques() {
  try {
    const resposta = await fetch("/api/destinations");
    if (!resposta.ok) throw new Error("falha ao listar parques");

    const dados = await resposta.json();
    estado.destinos = ordenarDestinos(dados.destinations);
    preencherSeletor(estado.destinos);
  } catch {
    // Não é motivo para travar o app: o parque padrão continua funcionando.
    el.parque.innerHTML = '<option value="">Magic Kingdom (padrão)</option>';
    el.parque.disabled = true;
    el.buscaParque.disabled = true;
  }
}

/* Resorts grandes primeiro, depois alfabético.
 *
 * Alfabético puro põe "Aquatica" acima de "Walt Disney World Resort", que é o
 * oposto do que a maioria procura. O número de parques é o melhor sinal de porte
 * que a API nos dá sem inventar dado: um destino com quatro parques é um resort
 * grande, e quem quer um específico agora tem a busca.
 */
function ordenarDestinos(destinos) {
  return destinos
    .slice()
    .sort(
      (a, b) =>
        b.parks.length - a.parks.length || a.name.localeCompare(b.name, "pt-BR")
    );
}

function preencherSeletor(destinos) {
  el.parque.innerHTML = "";

  destinos.forEach((destino) => {
    const grupo = document.createElement("optgroup");
    grupo.label = destino.name;

    destino.parks.forEach((parque) => {
      const opcao = document.createElement("option");
      opcao.value = parque.id;
      opcao.textContent = parque.name;
      opcao.selected = parque.id === estado.parqueId;
      grupo.appendChild(opcao);
    });

    el.parque.appendChild(grupo);
  });

  el.parque.disabled = false;
}

/* Filtra a lista pelo que foi digitado.
 *
 * Casa contra o nome do parque **e** o do destino: quem digita "disney" espera
 * ver o Magic Kingdom, embora a palavra não apareça no nome dele.
 */
function filtrarParques(termo) {
  const busca = termo.trim().toLowerCase();

  if (!busca) {
    preencherSeletor(estado.destinos);
    el.buscaVazia.hidden = true;
    return;
  }

  const filtrados = estado.destinos
    .map((destino) => {
      const destinoCasa = destino.name.toLowerCase().includes(busca);
      const parques = destinoCasa
        ? destino.parks
        : destino.parks.filter((p) => p.name.toLowerCase().includes(busca));

      return { ...destino, parks: parques };
    })
    .filter((destino) => destino.parks.length > 0);

  preencherSeletor(filtrados);

  // Some com o vazio silencioso: um seletor em branco parece app quebrado.
  el.buscaVazia.hidden = filtrados.length > 0;
}

/* Troca o parque ativo e atualiza tudo que depende dele.
 *
 * Existe como função própria porque dois caminhos levam aqui — escolher no
 * seletor e apertar Enter na busca — e eles precisam fazer exatamente a mesma
 * coisa. Duplicar essa sequência é como um dos dois acaba divergindo do outro.
 */
function trocarParque(novoId) {
  const parqueId = novoId || PARQUE_PADRAO;

  // Sair e voltar ao mesmo parque não deveria custar duas requisições.
  if (parqueId === estado.parqueId) return;

  estado.parqueId = parqueId;

  // Cada parque tem sua própria lista de visitadas: ter feito o Space Mountain
  // não diz nada sobre o EPCOT. Zerar aqui evita o estado do parque anterior
  // vazar para a primeira renderização do novo.
  estado.visitadas = new Set();
  estado.alvos = new Set();
  estado.atracoesDoParque = [];
  estado.mostrandoVisitadas = false;
  estado.mostrandoEscondidas = false;
  estado.ultimoRanking = null;
  estado.ultimoPanorama = null;
  estado.destaque = null;
  el.visitadasAviso.hidden = true;
  el.perfilAviso.hidden = true;
  trocarFundoDoMapa(parqueId);
  el.buscaAtracao.value = "";
  el.escolherAlvos.open = false;

  // Sempre reenquadra o mapa; o ranking só vem se houver posição.
  carregarParque({ trocaDeParque: true });
  buscarRecomendacoes();
}

/* Carrega o parque sem depender da posição do visitante.
 *
 * É o que faz o app mostrar alguma coisa antes de o GPS ser liberado — até aqui,
 * quem recusasse a localização via uma tela vazia e nenhuma razão para confiar
 * no resto.
 */
async function carregarParque({ trocaDeParque = false, silencioso = false } = {}) {
  try {
    const resposta = await fetch(`/api/parks/${estado.parqueId}/attractions`);
    if (!resposta.ok) {
      if (silencioso) return falhaAoRenovar();
      mostrarAviso(await explicarErroDaApi(resposta));
      return;
    }

    const dados = await resposta.json();
    registrarBusca(dados.data_updated_at);

    // O fuso do parque decide quando "hoje" vira "ontem" para as visitadas. Só a
    // rota de atrações o informa, e por isso a leitura acontece aqui.
    estado.fusoDoParque = dados.timezone || estado.fusoDoParque;
    estado.limitesDoParque = dados.bounds;
    estado.visitadas = VISITADAS.doParque(estado.parqueId, estado.fusoDoParque);
    // Alvos não dependem do fuso: valem até o visitante mudar de ideia.
    estado.alvos = ALVOS.doParque(estado.parqueId);

    // O catálogo alimenta o seletor de alvos, que funciona **sem** posição: dá
    // para montar a lista de desejos a caminho do parque.
    estado.atracoesDoParque = [...dados.attractions].sort((a, b) =>
      a.name.localeCompare(b.name, "pt-BR")
    );
    // Com o catálogo aberto, redesenhar o reordenaria sob o dedo de quem escolhe.
    if (!(silencioso && el.escolherAlvos.open)) desenharCatalogo(el.buscaAtracao.value);
    desenharAlvos(estado.ultimoRanking ? estado.ultimoRanking.recommendations : []);

    // Na primeira visita o painel do perfil abre antes de o catálogo chegar, e a
    // dica da altura depende dele.
    if (el.painelPerfil.open) definirAltura(Number(el.altura.value));

    // Duas chamadas assíncronas disputam o mapa: esta e a do ranking. Se o
    // visitante liberar o GPS enquanto esta ainda está no ar, a resposta chega
    // atrasada e jogaria a vista para longe de onde ele está. Numa troca de
    // parque o enquadramento é o que ele pediu; na abertura, não.
    if (trocaDeParque || (!estado.posicao && !silencioso)) {
      enquadrarParque(dados.bounds);
    }

    // Com posição, o ranking manda: quem desenha o mapa é `buscarRecomendacoes`.
    if (!estado.posicao) {
      desenharParque(dados.attractions);
      mostrarPanoramaDoParque(dados);
    }
  } catch {
    if (silencioso) return falhaAoRenovar();
    mostrarAviso("Não foi possível falar com o servidor. Verifique sua conexão.");
  }
}

// ---------------------------------------------------------------------------
// Tempo real: renovação automática e frescor
// ---------------------------------------------------------------------------

/* O relógio da tela. A cada `TIQUE_MS`: o "há X min" e a hora de entrada andam, e,
 * se já passou `RENOVAR_MS` desde a última busca, as filas se renovam.
 *
 * Com a aba escondida não renova nada — celular no bolso não gasta 4G. Ao voltar,
 * o `visibilitychange` chama o tique na hora, e o visitante não vê fila velha nem
 * pelos 30 s até o próximo. */
function tique() {
  atualizarFrescor();
  atualizarHoraDeEntrada();
  if (document.hidden) return;
  if (estado.renovacaoPendente || Date.now() - estado.ultimaBusca >= RENOVAR_MS) renovar();
}

function renovar() {
  if (estado.carregando) return;
  // No meio de algo, a renovação espera: redesenhar a lista fecharia o gráfico
  // que o visitante abriu, e o painel aberto perderia o lugar da rolagem.
  if (!podeRedesenhar()) {
    estado.renovacaoPendente = true;
    return;
  }
  estado.renovacaoPendente = false;
  if (estado.posicao) buscarRecomendacoes({ silencioso: true });
  else carregarParque({ silencioso: true });
}

function podeRedesenhar() {
  const graficoAberto = document.querySelector(".item[data-expandido='true']");
  const painelModal = el.painelFilas.open && el.painelFilas.matches(":modal");
  return !graficoAberto && !painelModal;
}

function registrarBusca(dadoDe) {
  estado.ultimaBusca = Date.now();
  estado.dadoDe = dadoDe || estado.dadoDe;
  estado.falhouRenovar = false;
  atualizarFrescor();
}

function falhaAoRenovar() {
  estado.falhouRenovar = true;
  // Tentar de novo no próximo tique, e não em dois minutos: quem perdeu o sinal
  // numa fila coberta quer o dado de volta assim que ele voltar.
  estado.renovacaoPendente = true;
  atualizarFrescor();
}

/* "Ao vivo · filas medidas há 2 min". A idade é a da MEDIÇÃO da fonte, e não a da
 * nossa busca: buscar de novo um dado que a fonte não atualizou não o torna novo.
 * Três estados, e o indicador nunca finge: ao vivo, fonte parada (de madrugada, o
 * normal) e sem conexão. */
function atualizarFrescor() {
  if (!estado.dadoDe) {
    el.frescor.hidden = true;
    return;
  }

  const idade = Date.now() - new Date(estado.dadoDe).getTime();
  const minutos = Math.max(0, Math.floor(idade / 60000));
  let quando = `há ${minutos} min`;
  if (minutos < 1) quando = "agora";
  if (idade > VELHO_MS) quando = `às ${formatarHora(estado.dadoDe)}`;

  let situacao;
  let texto;
  if (estado.falhouRenovar) {
    situacao = "sem-conexao";
    texto = `Sem conexão · filas medidas ${quando}`;
  } else if (idade > VELHO_MS) {
    situacao = "parado";
    texto = `Filas medidas ${quando} · a fonte não atualizou desde então`;
  } else {
    situacao = "ao-vivo";
    texto = `Ao vivo · filas medidas ${quando}`;
  }

  el.frescor.dataset.estado = situacao;
  el.frescor.textContent = texto;
  el.frescor.hidden = false;
}

/* "entra às 21:51" envelhece a cada minuto entre uma renovação e outra. Mexe só no
 * texto, e não no cartão: redesenhá-lo faria o leitor de tela o anunciar inteiro. */
function atualizarHoraDeEntrada() {
  const chegada = el.passoDestaque.querySelector(".passo__chegada");
  if (!chegada || !estado.destaque) return;
  chegada.textContent = `entra às ${horaDaqui(estado.destaque.total_minutes)}`;
}

/* `silencioso`: a renovação automática e o andar pelo GPS. Sem esqueleto, que
 * faria a tela piscar a cada dois minutos; e, se falhar, a tela **fica** com o que
 * tinha — uma oscilação do 4G no parque não pode apagar uma resposta boa. O
 * indicador de frescor diz que o dado envelheceu. */
async function buscarRecomendacoes({ silencioso = false } = {}) {
  if (!estado.posicao || estado.carregando) return;

  estado.carregando = true;
  if (!silencioso) mostrarEsqueleto();
  const posicaoPedida = { ...estado.posicao };

  // `limit=0` pede o ranking INTEIRO, e quem corta é a exibição.
  //
  // Pedir só oito parecia econômico e escondia um bug: marcar as oito como "já
  // fui" esvaziava a tela, porque as outras dezoito nunca haviam sido enviadas.
  // Pior, o app então anunciava "você já passou por todas as atrações
  // disponíveis" — uma mentira, com vinte atrações livres a poucos metros.
  //
  // É a terceira vez que este projeto tropeça no mesmo padrão: pedir a lista já
  // cortada e depois tentar raciocinar sobre ela. A regra registrada no CLAUDE.md
  // é justamente esta — **peça tudo, corte na exibição**.
  const parametros = new URLSearchParams({
    lat: estado.posicao.lat,
    lon: estado.posicao.lon,
    limit: 0,
  });

  try {
    const resposta = await fetch(
      `/api/parks/${estado.parqueId}/recommendations?${parametros}`
    );

    if (!resposta.ok) {
      if (silencioso) return falhaAoRenovar();
      mostrarAviso(await explicarErroDaApi(resposta));
      el.lista.innerHTML = "";
      el.resumo.hidden = true;
      estado.destaque = null;
      desenharPasso();
      return;
    }

    const dados = await resposta.json();
    limparAviso();
    renderizar(dados);
    registrarBusca(dados.data_updated_at);
    estado.posicaoDoRanking = posicaoPedida;
  } catch {
    if (silencioso) return falhaAoRenovar();
    mostrarAviso("Não foi possível falar com o servidor. Verifique sua conexão.");
    el.lista.innerHTML = "";
    estado.destaque = null;
    desenharPasso();
  } finally {
    estado.carregando = false;
    el.btnAtualizar.hidden = false;
  }
}

/** Cada código HTTP vira uma instrução diferente — é para isso que eles existem. */
async function explicarErroDaApi(resposta) {
  if (resposta.status === 404) return "Parque não encontrado. Escolha outro na lista.";
  if (resposta.status === 503) return "A fonte de dados está fora do ar. Tente em instantes.";
  if (resposta.status === 502) return "A fonte de dados respondeu em formato inesperado.";
  if (resposta.status === 422) return "Posição inválida. Toque no mapa para marcar de novo.";
  return "Algo deu errado ao buscar as recomendações.";
}

// ---------------------------------------------------------------------------
// Tela
// ---------------------------------------------------------------------------

function mostrarEsqueleto() {
  el.lista.innerHTML = Array.from(
    { length: 4 },
    () => '<li class="esqueleto"></li>'
  ).join("");

  el.passoSemPosicao.hidden = true;
  el.passoDestaque.innerHTML = '<div class="esqueleto esqueleto--passo"></div>';
  el.passoDestaque.hidden = false;
}

/* A tela antes de haver posição: filas do parque, sem ranking.
 *
 * Ordenada pela menor fila — que é a pergunta errada do projeto, e por isso o
 * texto diz explicitamente o que falta. Prometer "para onde ir" sem saber onde o
 * visitante está seria repetir justamente o erro que o NextUp existe para evitar.
 */
function mostrarPanoramaDoParque(dados) {
  desenharPanorama(dados);
  // Depois de desenhar, porque conta o que foi desenhado — e o desenho tem três
  // saídas antecipadas (lista vazia), em que o número certo é zero.
  atualizarContagemDeFilas();
}

function desenharPanorama(dados) {
  estado.ultimoPanorama = dados;
  desenharPasso();
  el.tituloLista.textContent = dados.park_name;
  // O modo fica no DOM, e não só na cabeça de quem leu o código: a lista tem dois
  // significados muito diferentes — "as menores filas" e "o que compensa mais" —
  // e confundi-los é exatamente o erro que o projeto inteiro existe para evitar.
  el.lista.dataset.modo = "panorama";

  // A ressalva não é modéstia, é a tese do projeto.
  //
  // Esta lista está ordenada pela **menor fila** — exatamente a pergunta que o
  // NextUp existe para contestar. Sem ela, o primeiro item aqui seria lido como
  // recomendação, e no Disneyland Paris os primeiros colocados são playgrounds
  // com fila zero: verdadeiros e inúteis.
  el.resumo.innerHTML = `
    ${dados.available} de ${dados.total_attractions} atrações com fila medida.
    <strong>Ordenado pela menor fila</strong>, que raramente é a melhor escolha.
    Diga onde você está para somar a caminhada.
  `;
  el.resumo.hidden = false;

  const medidas = dados.attractions.filter((a) => a.queue_minutes !== null);
  atualizarAvisoDoPerfil(medidas);

  if (medidas.length === 0) {
    el.lista.innerHTML = "";
    mostrarAviso("Nenhuma atração com fila agora. O parque pode estar fechado.", "info");
    el.atualizado.hidden = true;
    return;
  }

  const comFila = medidas.filter(passaNoPerfil).sort((a, b) => a.queue_minutes - b.queue_minutes);

  if (comFila.length === 0) {
    el.lista.innerHTML = "";
    mostrarAviso(avisoDePerfilApertado(), "info");
    el.atualizado.hidden = true;
    return;
  }

  el.lista.innerHTML = comFila.slice(0, LIMITE).map(criarItemSimples).join("");

  el.atualizado.textContent = `Dado da fonte às ${formatarHora(dados.data_updated_at)}.`;
  el.atualizado.hidden = false;
}

function criarItemSimples(item) {
  // O histórico também aparece aqui: saber como a fila se comportou hoje não
  // depende de o visitante ter dito onde está.
  return `
    <li class="item item--sem-posicao" data-expandido="false">
      <div class="custo">
        <strong>${item.queue_minutes}</strong>
        <span>min</span>
      </div>
      <div class="corpo">
        <p class="nome">${escapar(item.name)}</p>
        <p class="conta">
          <span class="parcela">${ICONE.fila} só a fila, sem a caminhada</span>
        </p>
        ${criarRestricao(item)}
      </div>
      <button type="button" class="ver-historico"
              data-atracao="${escapar(item.id)}"
              aria-expanded="false">
        ${ICONE.grafico}
        <span>Histórico</span>
      </button>
    </li>
  `;
}

/* Uma resposta do ranking vira três coisas na tela: a lista (no painel), o
 * cartão do próximo passo e o número no botão do painel. O cartão depende da
 * lista — a melhor escolha é decidida lá —, e por isso vem depois. */
function renderizar(dados) {
  renderizarLista(dados);
  desenharPasso();
  atualizarContagemDeFilas();
}

function renderizarLista(dados) {
  estado.ultimoRanking = dados;
  // Sem destaque até prova em contrário: numa lista vazia, a rota apontaria para
  // uma atração que já não é resposta de nada.
  estado.destaque = null;
  estado.origemDoDestaque = "parque";
  estado.alternativas = [];
  desenharRota();

  el.tituloLista.textContent = dados.park_name;
  el.lista.dataset.modo = "ranking";

  el.resumo.textContent = `${dados.available} de ${dados.total_attractions} atrações disponíveis agora.`;
  el.resumo.hidden = false;

  if (dados.recommendations.length === 0) {
    el.lista.innerHTML = "";
    mostrarAviso(
      "Nenhuma atração disponível agora. O parque pode estar fechado.",
      "info"
    );
    el.atualizado.hidden = true;
    return;
  }

  desenharAlvos(dados.recommendations);

  const visiveis = escolherVisiveis(dados.recommendations);
  atualizarAvisoDeVisitadas(dados.recommendations);
  atualizarAvisoDoPerfil(
    dados.recommendations
      .filter((r) => !estado.visitadas.has(r.attraction.id))
      .map((r) => r.attraction)
  );

  if (visiveis.length === 0) {
    el.lista.innerHTML = "";

    // Quatro motivos diferentes para uma lista vazia, e dizer o errado é pior que
    // não dizer nada: "você já passou por todas" para quem só apertou um filtro
    // esconde a causa e faz o app parecer quebrado.
    const livres = dados.recommendations.filter(
      (r) => !estado.visitadas.has(r.attraction.id) && !estado.alvos.has(r.attraction.id)
    );

    if (livres.length > 0 && !livres.some(passaNosFiltros)) {
      mostrarAviso(
        "Nenhuma atração cabe nos seus filtros agora. Afrouxe os limites para ver mais.",
        "info"
      );
    } else if (livres.length > 0) {
      // Passam nos filtros e mesmo assim não aparecem: só sobrou o perfil.
      mostrarAviso(avisoDePerfilApertado(), "info");
    } else {
      // Esta frase agora é verdade. Antes ela aparecia com oito marcadas de vinte
      // e oito disponíveis, porque a lista pedida ao servidor já vinha cortada.
      mostrarAviso(
        "Você já passou por todas as atrações disponíveis agora. Nada mal.",
        "info"
      );
    }
    return;
  }

  limparAviso();

  // A etiqueta vai para a melhor **ainda não feita**, e não para a primeira da
  // lista. Com as visitadas à mostra, a primeira posição pode ser uma que o
  // visitante já fez — e aí ninguém receberia o destaque, justamente na tela em
  // que ele está decidindo para onde ir.
  //
  // Nem para uma só dos adultos: o destaque responde "para onde vamos agora?" e o
  // grupo inclui a criança. A atração continua na lista, marcada — pelo Rider
  // Switch os adultos ainda vão, revezando. Decisão do Gabriel, Fase 9.
  const serveAoGrupo = (r) =>
    !estado.visitadas.has(r.attraction.id) && !PERFIL.soAdultos(r.attraction, estado.perfil);
  const doParque = visiveis.filter(serveAoGrupo);
  const melhorDisponivel = doParque[0];
  const idDaMelhor = melhorDisponivel ? melhorDisponivel.attraction.id : null;

  // A etiqueta da lista continua sendo do ranking; quem muda com a chave é o
  // cartão. Dos alvos, a recomendação inteira e não `visiveis`: alvo escapa do
  // filtro, como na seção "Você veio por estas".
  const dosAlvos = dados.recommendations.filter(
    (r) => estado.alvos.has(r.attraction.id) && serveAoGrupo(r)
  );
  const querAlvos = estado.criterio === "alvos" && estado.alvos.size > 0;
  // Pedir as marcadas sem nenhuma disponível não pode esvaziar o cartão: ele cai
  // para a melhor do parque e diz por quê.
  const fonte = querAlvos && dosAlvos.length > 0 ? dosAlvos : doParque;
  estado.origemDoDestaque = querAlvos ? (dosAlvos.length > 0 ? "alvos" : "sem-alvos") : "parque";
  estado.destaque = fonte[0] || null;
  estado.alternativas = fonte.slice(1, 1 + ALTERNATIVAS_NO_CARTAO);

  el.lista.innerHTML = visiveis.map((item) => criarItem(item, idDaMelhor)).join("");
  // O mapa mostra o conjunto do CARTÃO: com "Das minhas", os alvos, numerados na
  // ordem deles. Antes ficavam os números do parque, e a rota até o alvo terminava
  // num lugar sem pino nenhum (Gabriel, 30/10/2026). O 1 é o fim da rota; o 2 e o
  // 3 são os da linha "Ou então".
  const noMapa = estado.origemDoDestaque === "alvos" ? dosAlvos : visiveis;
  desenharMapa(noMapa);
  desenharRota();
  enquadrarResposta(noMapa);

  el.atualizado.textContent = `Dado da fonte às ${formatarHora(dados.data_updated_at)}.`;
  el.atualizado.hidden = false;
}

/* Quais recomendações vão para a tela, a partir do ranking inteiro.
 *
 * O corte acontece **depois** de tirar as visitadas, e é essa ordem que conserta
 * o bug: cortar antes deixaria a tela vazia assim que as oito primeiras fossem
 * marcadas, escondendo as vinte seguintes.
 *
 * No modo "Mostrar", as visitadas voltam **sem empurrar as outras para fora**. Se
 * o corte fosse aplicado à lista já misturada, revelar oito visitadas expulsaria
 * as oito sugestões — e o visitante perderia de vista justamente o que precisa
 * decidir. Aqui as duas coisas convivem: as melhores disponíveis, mais o que já
 * foi feito, reordenadas pelo custo.
 */
/* Aplica os limites do visitante.
 *
 * **Corta, não reordena.** A ordem continua sendo por custo total, que é a tese do
 * projeto; o filtro só decide o que nem entra na lista.
 *
 * Os alvos escapam de propósito: quem marcou uma atração como "vim por esta" está
 * dizendo que vai nela de qualquer jeito. Escondê-la por causa de um limite geral
 * seria o app discutindo com uma escolha explícita do visitante.
 */
function passaNosFiltros(recomendacao) {
  if (estado.alvos.has(recomendacao.attraction.id)) return true;

  return (
    recomendacao.queue_minutes <= estado.filtros.filaMax &&
    recomendacao.walking_minutes <= estado.filtros.caminhadaMax &&
    passaNaPopularidade(recomendacao)
  );
}

/* O filtro de popularidade, que tem uma armadilha própria.
 *
 * Sem banco — ou antes de o coletor rodar — a API devolve `popularity: null` em
 * TODAS as atrações. Tratar ausente como faixa reprovada esvaziaria a tela
 * inteira num ambiente que funciona perfeitamente, e o visitante não teria como
 * adivinhar o motivo: ele não pediu nada, e o app pararia de responder.
 *
 * Por isso ausência de dado libera a atração. É o mesmo princípio que faz
 * `_tendencias()` engolir a falha do banco no servidor: o histórico enriquece a
 * recomendação, nunca decide se ela existe.
 */
function passaNaPopularidade(recomendacao) {
  if (!recomendacao.popularity) return true;

  return estado.filtros.faixas.includes(recomendacao.popularity.tier);
}

/* O gosto do grupo, aplicado depois dos filtros e com o mesmo contrato: corta,
 * não reordena, e quem corta avisa quantas (`atualizarAvisoDoPerfil`).
 *
 * Recebe a atração crua — a do ranking (`r.attraction`) ou a do panorama — porque
 * as duas trazem `id` e `intensity` no mesmo formato. Os alvos escapam pelo
 * mesmo motivo de escaparem dos filtros: "vim por esta" vence uma preferência
 * geral.
 */
function passaNoPerfil(atracao) {
  const a = atracao.attraction || atracao;
  if (estado.alvos.has(a.id) || estado.mostrandoEscondidas) return true;
  return !PERFIL.escondida(a, estado.perfil);
}

function escolherVisiveis(recomendacoes) {
  // Os alvos já têm seção própria acima. Repeti-los aqui gastaria as oito vagas
  // do ranking com coisas que o visitante acabou de ver.
  const semAlvos = recomendacoes.filter((r) => !estado.alvos.has(r.attraction.id));
  const dentroDoLimite = semAlvos.filter(passaNosFiltros).filter(passaNoPerfil);
  const disponiveis = dentroDoLimite.filter((r) => !estado.visitadas.has(r.attraction.id));
  const proximas = disponiveis.slice(0, LIMITE);

  if (!estado.mostrandoVisitadas) return proximas;

  const marcadas = dentroDoLimite.filter((r) => estado.visitadas.has(r.attraction.id));

  return [...proximas, ...marcadas].sort((a, b) => a.total_minutes - b.total_minutes);
}

/* Os controles de filtro e o selo que denuncia que eles estão ligados.
 *
 * O selo é a parte que não pode faltar. Um filtro esquecido é indistinguível de
 * um parque vazio: o visitante vê três sugestões onde havia trinta e conclui que
 * o app quebrou, ou pior, que o parque está lotado.
 */
function atualizarControlesDeFiltro() {
  const { filaMax, caminhadaMax } = estado.filtros;

  el.filtroFila.value = filaMax;
  el.filtroCaminhada.value = caminhadaMax;
  el.rotuloFila.textContent = rotularLimite(filaMax);
  el.rotuloCaminhada.textContent = rotularLimite(caminhadaMax);

  for (const caixa of el.filtrosFaixa) {
    caixa.checked = estado.filtros.faixas.includes(caixa.value);
  }

  const ligados = FILTROS.ativos(estado.filtros);
  el.filtrosAtivos.hidden = !ligados;
  el.filtrosAtivos.textContent = ligados ? "ativos" : "";
}

function rotularLimite(valor) {
  return valor >= FILTROS.SEM_LIMITE ? "Sem limite" : `Até ${valor} min`;
}

/** Guarda o filtro, redesenha e mantém o rótulo em dia. */
function aplicarFiltros() {
  estado.filtros = FILTROS.salvar({
    filaMax: Number(el.filtroFila.value),
    caminhadaMax: Number(el.filtroCaminhada.value),
    // Desmarcar tudo esconderia a tela inteira, e o visitante quase sempre quer
    // dizer "volte ao normal" — não "não me mostre nada". Trata-se como limpar.
    faixas: [...el.filtrosFaixa].filter((c) => c.checked).map((c) => c.value),
  });

  if (estado.filtros.faixas.length === 0) {
    estado.filtros = FILTROS.salvar({ ...estado.filtros, faixas: [...FILTROS.FAIXAS] });
  }

  atualizarControlesDeFiltro();
  if (estado.ultimoRanking) renderizar(estado.ultimoRanking);
}

/* A seção "Você veio por estas".
 *
 * Fica fora do ranking porque responde outra pergunta. O ranking diz o que
 * compensa mais *agora*; esta lista diz **quando ir naquilo que o visitante veio
 * fazer** — e para isso ela precisa mostrar o alvo mesmo quando ele está caro.
 *
 * Um alvo com 90 minutos de fila não deve sumir da tela: é justamente essa a
 * informação que faz o visitante decidir esperar, voltar mais tarde, ou desistir.
 * Enterrá-lo em décimo quinto lugar do ranking seria esconder a única coisa que
 * ele veio saber.
 *
 * Entre si, os alvos são ordenados por custo total — a mesma régua do resto do
 * app. A tese não muda; muda o conjunto sobre o qual ela é aplicada.
 */
function desenharAlvos(recomendacoes) {
  el.btnLimparAlvos.hidden = estado.alvos.size === 0;

  if (estado.alvos.size === 0) {
    // Convite, e não vazio. Escondida, a seção faria a funcionalidade não existir
    // para quem nunca tropeçou nela por acaso.
    el.listaAlvos.innerHTML = "";
    el.alvosResumo.textContent =
      "Marque o que você veio fazer e o NextUp mostra o melhor momento de cada uma.";
    return;
  }

  const meus = recomendacoes
    .filter((r) => estado.alvos.has(r.attraction.id))
    .sort((a, b) => a.total_minutes - b.total_minutes);

  if (meus.length === 0) {
    // Marcadas, mas nenhuma no ranking: fechadas, em manutenção, sem fila medida —
    // ou o visitante ainda não disse onde está. Dizer isso é melhor que mostrar
    // uma lista vazia e deixar o visitante achar que o app perdeu as marcações.
    el.listaAlvos.innerHTML = "";
    el.alvosResumo.textContent = estado.posicao
      ? `Nenhuma das suas ${estado.alvos.size} marcadas está disponível agora.`
      : `${estado.alvos.size} marcadas. Diga onde você está para ver o custo de cada uma.`;
    return;
  }

  const feitos = meus.filter((r) => estado.visitadas.has(r.attraction.id)).length;
  el.alvosResumo.textContent =
    feitos > 0
      ? `${feitos} de ${meus.length} já feitas hoje.`
      : `${meus.length} ${meus.length === 1 ? "atração" : "atrações"} na sua lista.`;

  // Sem `idDaMelhor`: a etiqueta "melhor escolha agora" pertence ao ranking, que
  // compara o parque inteiro. Repeti-la aqui, sobre um recorte de três atrações,
  // diria algo diferente com as mesmas palavras.
  el.listaAlvos.innerHTML = meus.map((item) => criarItem(item, null)).join("");
}

/* O catálogo completo do parque, para escolher alvos.
 *
 * Existe porque marcar alvos só no ranking era um mecanismo falho: a tela mostra
 * oito de trinta e cinco, e as outras vinte e sete eram inalcançáveis. Quem veio
 * pelo Space Mountain não conseguia dizer isso ao app até o Space Mountain,
 * por acaso, aparecer entre as oito melhores.
 *
 * A lista sai de `/attractions`, que **não** exige posição — então dá para montar
 * a lista de desejos a caminho do parque, antes de liberar o GPS.
 */
function desenharCatalogo(termo = "") {
  const busca = termo.trim().toLowerCase();
  const encontradas = busca
    ? estado.atracoesDoParque.filter((a) => a.name.toLowerCase().includes(busca))
    : estado.atracoesDoParque;

  el.escolherVazio.hidden = encontradas.length > 0;

  // Marcadas primeiro, para remover ser tão fácil quanto adicionar: quem abriu a
  // lista para tirar algo não deveria ter de procurar entre trinta e cinco.
  const marcadas = encontradas.filter((a) => estado.alvos.has(a.id));
  const resto = encontradas.filter((a) => !estado.alvos.has(a.id));

  const grupos = [{ titulo: "Na sua lista", atracoes: marcadas.sort(porPopularidade) }];

  if (resto.some((a) => a.popularity)) {
    for (const { faixa, titulo } of GRUPOS_DO_CATALOGO) {
      const daFaixa = resto.filter((a) => (a.popularity?.tier ?? "UNKNOWN") === faixa);
      grupos.push({ titulo, atracoes: daFaixa.sort(porPopularidade) });
    }
  } else {
    // Sem banco não há faixa, e um título "Sem histórico" sobre o parque inteiro
    // diria algo verdadeiro e inútil. Sem faixa, volta a ordem alfabética.
    grupos.push({
      titulo: marcadas.length > 0 ? "Todas as atrações" : null,
      atracoes: resto.sort((a, b) => a.name.localeCompare(b.name, "pt-BR")),
    });
  }

  el.catalogoAtracoes.innerHTML = grupos
    .filter((g) => g.atracoes.length > 0)
    .map(criarGrupoDoCatalogo)
    .join("");
}

/* Os grupos do catálogo, na ordem em que aparecem.
 *
 * Por popularidade, e não alfabética nem por fila (Gabriel, 29/10/2026): quem
 * monta a lista de desejos procura as principais do parque, e a faixa é estável.
 * A fila de agora muda a cada minuto e repetiria o trabalho do ranking — alvo é
 * desejo, não oportunidade. O título diz por que a atração está ali; a ordem,
 * sozinha, não explicaria.
 */
const GRUPOS_DO_CATALOGO = [
  { faixa: "HEADLINER", titulo: "As principais do parque" },
  { faixa: "MODERATE", titulo: "Também procuradas" },
  { faixa: "QUIET", titulo: "Costumam ter fila curta" },
  { faixa: "UNKNOWN", titulo: "Sem histórico suficiente" },
];

/** Maior fila média primeiro; sem média, pelo nome. */
function porPopularidade(a, b) {
  const mediaA = a.popularity?.average_minutes ?? -1;
  const mediaB = b.popularity?.average_minutes ?? -1;
  return mediaB - mediaA || a.name.localeCompare(b.name, "pt-BR");
}

function criarGrupoDoCatalogo({ titulo, atracoes }) {
  const cabecalho = titulo ? `<p class="catalogo__titulo">${titulo}</p>` : "";
  return `
    <li class="catalogo__grupo">
      ${cabecalho}
      <ul class="catalogo__linhas">${atracoes.map(criarLinhaDoCatalogo).join("")}</ul>
    </li>
  `;
}

function criarLinhaDoCatalogo(atracao) {
  const marcada = estado.alvos.has(atracao.id);

  // A fila de agora ajuda a escolher, mas nem toda atração tem uma — fechada ou
  // sem medida. Dizer "—" é mais honesto que omitir a linha ou inventar um zero.
  const fila =
    atracao.queue_minutes === null ? "—" : `${atracao.queue_minutes} min`;

  // A caixa nativa continua lá, transparente e cobrindo a linha: o teclado, o
  // leitor de tela e o "marcar" do formulário vêm dela. O círculo é só desenho.
  return `
    <li>
      <label class="catalogo__item${marcada ? " catalogo__item--marcada" : ""}">
        <input type="checkbox" data-atracao="${escapar(atracao.id)}"
               ${marcada ? "checked" : ""} />
        <span class="catalogo__marca" aria-hidden="true">${ICONE.check}</span>
        <span class="catalogo__nome">${escapar(atracao.name)}</span>
        <span class="catalogo__fila">${fila}</span>
      </label>
    </li>
  `;
}

/** Marca ou desmarca um alvo e redesenha, sem ir à rede de novo. */
function alternarAlvo(attractionId) {
  estado.alvos = ALVOS.alternar(estado.parqueId, attractionId);

  if (estado.ultimoRanking) {
    renderizar(estado.ultimoRanking);
  } else {
    // Sem ranking ainda: a seção de alvos se atualiza sozinha, para marcar
    // funcionar antes de o visitante liberar o GPS.
    desenharAlvos([]);
  }

  // O catálogo **não** é redesenhado aqui: quem chamou já cuida da própria
  // aparência, e redesenhar reordenaria a lista sob o dedo de quem está
  // escolhendo. Ver o ouvinte de `toggle` em `iniciar`.
}

/* Um clique em qualquer das duas listas.
 *
 * Delegação: o ouvinte fica na lista, não nos botões. As listas são apagadas e
 * redesenhadas a cada marcação, e ouvintes presos aos botões antigos morreriam
 * junto — ou pior, ficariam vivos segurando nós que já saíram da página.
 */
function aoClicarNumItem(evento) {
  const alvo = evento.target.closest(".marcar-alvo");
  if (alvo) {
    alternarAlvo(alvo.dataset.atracao);
    return;
  }

  const visitada = evento.target.closest(".marcar-visitada");
  if (visitada) {
    alternarVisitada(visitada.dataset.atracao);
    return;
  }

  const historico = evento.target.closest(".ver-historico");
  if (!historico) return;

  const item = historico.closest(".item");
  const expandido = item.dataset.expandido === "true";

  historico.setAttribute("aria-expanded", String(!expandido));
  alternarHistorico(item, historico.dataset.atracao);
}

/* O aviso das visitadas: quantas são e como revê-las.
 *
 * Existe porque esconder coisas sem dizer que está escondendo é a diferença entre
 * um app que ajuda e um que parece quebrado. A pessoa marcou três atrações, a
 * lista encolheu — ela precisa saber que foi ela quem causou isso.
 */
function atualizarAvisoDeVisitadas(recomendacoes) {
  const marcadas = recomendacoes.filter((r) => estado.visitadas.has(r.attraction.id));

  if (marcadas.length === 0) {
    el.visitadasAviso.hidden = true;
    return;
  }

  const plural = marcadas.length === 1 ? "atração já visitada" : "atrações já visitadas";
  el.visitadasTexto.textContent = `${marcadas.length} ${plural} hoje.`;

  el.btnMostrarVisitadas.textContent = estado.mostrandoVisitadas ? "Ocultar" : "Mostrar";
  el.btnMostrarVisitadas.setAttribute("aria-pressed", String(estado.mostrandoVisitadas));
  el.visitadasAviso.hidden = false;
}

/** Marca ou desmarca uma atração e redesenha, sem ir à rede de novo. */
function alternarVisitada(attractionId) {
  estado.visitadas = VISITADAS.alternar(
    estado.parqueId,
    estado.fusoDoParque,
    attractionId
  );

  if (estado.ultimoRanking) renderizar(estado.ultimoRanking);
}

/* Ícones em SVG, desenhados inline.
 *
 * Poderiam ser emoji, que seria mais curto — mas emoji muda de desenho conforme
 * o sistema, não herda a cor do texto e desalinha com a linha de base. O SVG
 * escala sem borrar e acompanha a cor de quem o contém.
 */
const ICONE = {
  caminhada: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="13" cy="4" r="2" />
      <path d="m13.5 9-2.5 4 3 2.5 1 6.5" />
      <path d="M8 21l2-5.5-2-3 1-4.5 3-1 3 2.5 2.5 1" />
    </svg>`,
  fila: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.5 2" />
    </svg>`,
  estrela: `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="m12 2 2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.3 5.9 20.6l1.4-6.8L2.2 9.1l6.9-.8L12 2Z" />
    </svg>`,
  // Duas pessoas, para a linha de popularidade. O ícone marca o assunto — quanta
  // gente costuma haver ali — e quem distingue a faixa é o texto, como nas
  // parcelas da conta. A primeira versão reaproveitava o alvo, e ele já significa
  // "vim por esta" no botão a dois centímetros: o mesmo símbolo dizendo duas
  // coisas na mesma linha.
  pessoas: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="9" cy="7" r="3" />
      <path d="M3 20v-1a5 5 0 0 1 5-5h2a5 5 0 0 1 5 5v1" />
      <path d="M16.5 4.3a3 3 0 0 1 0 5.4" />
      <path d="M18 14.2a5 5 0 0 1 3 4.6V20" />
    </svg>`,
  caindo: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M12 5v14" /><path d="m19 12-7 7-7-7" />
    </svg>`,
  subindo: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M12 19V5" /><path d="m5 12 7-7 7 7" />
    </svg>`,
  grafico: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M3 3v16a2 2 0 0 0 2 2h16" />
      <path d="m7 14 3.5-4 3 2.5L18 7" />
    </svg>`,
  check: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>`,
  mira: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"
      stroke-linecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="7" />
      <circle cx="12" cy="12" r="2.5" fill="currentColor" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
    </svg>`,
  alvo: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.4" fill="currentColor" />
    </svg>`,
  // Uma régua com a seta de altura: o assunto é "até onde a criança alcança".
  altura: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M7 3v18" /><path d="m4 6 3-3 3 3" /><path d="m4 18 3 3 3-3" />
      <path d="M14 4h6v16h-6" /><path d="M14 9h3" /><path d="M14 14h3" />
    </svg>`,
};

/* A marca de altura, na linha abaixo da conta.
 *
 * **Marca, não esconde** (decisão do Gabriel): pelo Rider Switch da Disney, um
 * adulto vai enquanto o outro espera com a criança, e depois trocam sem refazer a
 * fila. Esconder tiraria dos adultos a informação de que dá para revezar.
 *
 * Com criança no grupo e atração sem curadoria, diz que não sabe — em vez de
 * calar, que seria ler "não sabemos" como "pode ir".
 */
function criarRestricao(atracao) {
  if (PERFIL.soAdultos(atracao, estado.perfil)) {
    return `
      <p class="restricao">
        ${ICONE.altura}
        <span>
          <strong>A partir de ${atracao.min_height_cm} cm · só os adultos</strong>
          <span class="restricao__dica">Rider Switch: um adulto vai, o outro espera com a
          criança, e depois trocam sem refazer a fila.</span>
        </span>
      </p>
    `;
  }

  if (estado.perfil.alturaCm !== null && PERFIL.semCuradoria(atracao)) {
    return `
      <p class="restricao restricao--desconhecida">
        ${ICONE.altura} Altura mínima não conferida. Confira na entrada
      </p>
    `;
  }

  return "";
}

/* O aviso do que o gosto do grupo escondeu.
 *
 * Recebe as atrações ainda em jogo (sem as visitadas), no formato cru da API.
 * Conta só as que o perfil esconde de fato: alvos escapam, e atração sem
 * intensidade nunca é escondida — contá-las seria anunciar um corte que não houve.
 */
const NOMES_DO_PERFIL = {
  tranquilas: { rotulo: "Tranquilas", uma: "radical", varias: "radicais" },
  emocao: { rotulo: "Quero emoção", uma: "tranquila", varias: "tranquilas" },
};

function atualizarAvisoDoPerfil(atracoes) {
  const escondidas = atracoes.filter(
    (a) => !estado.alvos.has(a.id) && PERFIL.escondida(a, estado.perfil)
  );

  if (escondidas.length === 0) {
    el.perfilAviso.hidden = true;
    return;
  }

  const nomes = NOMES_DO_PERFIL[estado.perfil.intensidade];
  const n = escondidas.length;
  const quais = n === 1 ? `1 ${nomes.uma}` : `${n} ${nomes.varias}`;

  el.perfilAvisoTexto.textContent = estado.mostrandoEscondidas
    ? `${quais} à mostra, apesar de “${nomes.rotulo}”.`
    : `${quais} ${n === 1 ? "escondida" : "escondidas"} por “${nomes.rotulo}”.`;
  el.btnMostrarEscondidas.textContent = estado.mostrandoEscondidas ? "Ocultar" : "Mostrar";
  el.btnMostrarEscondidas.setAttribute("aria-pressed", String(estado.mostrandoEscondidas));
  el.perfilAviso.hidden = false;
}

/** A frase da lista vazia quando a causa é o perfil — e como desfazer. */
function avisoDePerfilApertado() {
  const nomes = NOMES_DO_PERFIL[estado.perfil.intensidade];
  return `Nenhuma atração combina com “${nomes.rotulo}” agora. Toque em Mostrar para ver as ${nomes.varias}.`;
}

/** Redesenha a tela que estiver à vista, sem ir à rede de novo. */
function redesenhar() {
  if (estado.ultimoRanking) {
    renderizar(estado.ultimoRanking);
  } else if (estado.ultimoPanorama) {
    mostrarPanoramaDoParque(estado.ultimoPanorama);
  }
}

// ---------------------------------------------------------------------------
// Painel do perfil
// ---------------------------------------------------------------------------

const RESUMO_DA_INTENSIDADE = { tranquilas: "Tranquilas", tudo: "De tudo", emocao: "Emoção" };

/** O botão "Seu grupo": o perfil à vista, porque ele muda a resposta do app. */
function atualizarResumoDoPerfil() {
  const { alturaCm, intensidade } = estado.perfil;

  el.perfilResumo.textContent =
    alturaCm === null && intensidade === "tudo"
      ? "Sem restrições"
      : // Curto, porque divide a linha com "Seu próximo passo" no cartão. O botão
        // se anuncia como "Seu grupo" ao leitor de tela, e o contexto diz o resto.
        `${alturaCm === null ? "Sem crianças" : `${alturaCm} cm`} · ${
          RESUMO_DA_INTENSIDADE[intensidade]
        }`;
}

/* Abre o painel com as respostas guardadas.
 *
 * Duas caras, um painel só: na primeira visita ele convida ("Antes do primeiro
 * passo", "Pular"); depois ele edita ("Seu grupo", "Cancelar"). Dois painéis
 * fariam duas cópias das mesmas perguntas, e uma delas acabaria desatualizada.
 */
function abrirPerfil({ primeiraVez = false } = {}) {
  const { respondido, alturaCm, intensidade } = estado.perfil;

  el.painelPerfil.dataset.primeiraVez = String(primeiraVez);
  el.painelPerfilTitulo.textContent = primeiraVez ? "Antes do primeiro passo" : "Seu grupo";
  el.btnPularPerfil.textContent = primeiraVez ? "Pular" : "Cancelar";
  el.btnSalvarPerfil.textContent = primeiraVez ? "Ver meu próximo passo" : "Salvar";

  // Nenhuma das duas marcada na primeira vez: pré-marcar "Sem crianças" seria
  // responder pelo visitante, e a pergunta deixaria de ser pergunta.
  for (const opcao of el.painelPerfil.querySelectorAll("input[name='criancas']")) {
    opcao.checked = respondido && opcao.value === (alturaCm === null ? "nao" : "sim");
  }
  for (const opcao of el.painelPerfil.querySelectorAll("input[name='intensidade']")) {
    opcao.checked = opcao.value === intensidade;
  }

  definirAltura(alturaCm ?? PERFIL.ALTURA.padrao);
  el.alturaCampo.hidden = alturaCm === null;

  el.painelPerfil.showModal();
}

/** Ajusta a altura nos três lugares que a mostram e reescreve a consequência. */
function definirAltura(cm) {
  const altura = Math.min(PERFIL.ALTURA.max, Math.max(PERFIL.ALTURA.min, Math.round(cm)));
  el.altura.value = altura;
  el.alturaValor.textContent = `${altura} cm`;
  el.alturaDica.textContent = consequenciaDaAltura(altura);
}

/* "Com 95 cm, fica de fora: TRON, Space Mountain..."
 *
 * Calculada sobre o catálogo do parque, que chega sem exigir posição — então
 * funciona na primeira abertura, antes do GPS. As mais exigentes vêm primeiro,
 * porque são as que o visitante mais provavelmente veio procurar.
 */
function consequenciaDaAltura(cm) {
  // Catálogo ainda a caminho: calar é melhor que afirmar "não conferimos" por
  // engano. `carregarParque` reescreve a dica quando ele chega.
  if (estado.atracoesDoParque.length === 0) return "";

  const conferidas = estado.atracoesDoParque.filter((a) => !PERFIL.semCuradoria(a));
  if (conferidas.length === 0) {
    return "Neste parque ainda não conferimos as alturas mínimas.";
  }

  const deFora = conferidas
    .filter((a) => a.min_height_cm != null && a.min_height_cm > cm)
    .sort((a, b) => b.min_height_cm - a.min_height_cm)
    .map((a) => a.name);

  if (deFora.length === 0) return `Com ${cm} cm, a criança pode ir em todas.`;
  return `Com ${cm} cm, fica de fora: ${deFora.join(", ")}. Os adultos ainda podem ir, revezando.`;
}

function salvarPerfil() {
  const criancas = el.painelPerfil.querySelector("input[name='criancas']:checked");
  const intensidade = el.painelPerfil.querySelector("input[name='intensidade']:checked");

  estado.perfil = PERFIL.salvar({
    alturaCm: criancas && criancas.value === "sim" ? Number(el.altura.value) : null,
    intensidade: intensidade ? intensidade.value : "tudo",
  });
  fecharPerfil();
}

/* Pular também é resposta: o painel não volta sozinho na próxima visita.
 * Perguntar de novo a cada abertura seria insistir com quem já disse "agora não". */
function pularPerfil() {
  if (el.painelPerfil.dataset.primeiraVez === "true") {
    estado.perfil = PERFIL.salvar({ alturaCm: null, intensidade: "tudo" });
  }
  fecharPerfil();
}

function fecharPerfil() {
  el.painelPerfil.close();
  // Perfil novo, contexto novo: o "Mostrar" valia para o corte anterior.
  estado.mostrandoEscondidas = false;
  atualizarResumoDoPerfil();
  redesenhar();
}

// ---------------------------------------------------------------------------
// Cartão do próximo passo (Fase 9.3)
// ---------------------------------------------------------------------------

const NOME_DA_INTENSIDADE = { CALM: "Tranquila", MODERATE: "Moderada", THRILL: "Radical" };

/* O cartão que responde a pergunta do app — "para onde eu vou agora?".
 *
 * Sem posição, ele pede a localização: prometer um próximo passo sem saber onde o
 * visitante está repetiria o erro que o projeto existe para evitar (a menor fila
 * do outro lado do parque). Com posição, ele mostra a melhor escolha **do grupo**:
 * a mesma de `renderizar`, que já pulou as visitadas e as só dos adultos.
 *
 * Sem melhor escolha (lista vazia), o cartão some e o aviso diz por quê — ele
 * distingue as quatro causas, e o cartão repetiria só uma delas.
 */
function desenharPasso() {
  const temPosicao = Boolean(estado.posicao);
  el.passoSemPosicao.hidden = temPosicao;

  // A chave só existe com alvos marcados: sem eles, "das minhas" seria uma opção
  // que não leva a lugar nenhum.
  el.passoCriterio.hidden = !temPosicao || estado.alvos.size === 0;
  el.passoCriterio.querySelector(`input[value='${estado.criterio}']`).checked = true;
  el.passoTitulo.textContent =
    estado.destaque && estado.origemDoDestaque === "alvos"
      ? "Próxima da sua lista"
      : "Seu próximo passo";

  if (!temPosicao || !estado.destaque) {
    // Esvaziar, e não só esconder: o esqueleto do carregamento ficaria lá dentro,
    // e numa falha da API o cartão "carregaria" para sempre se reaparecesse.
    // Pego pelo teste que garante que o esqueleto some quando dá erro.
    el.passoDestaque.innerHTML = "";
    el.passoDestaque.hidden = true;
    ultimoPasso = null;
    return;
  }

  // O cartão é `aria-live`: substituí-lo inteiro a cada renovação faria o leitor
  // de tela o anunciar a cada dois minutos, igual. Só a hora de entrada muda
  // sozinha, e ela fica de fora da comparação (`atualizarHoraDeEntrada`).
  const html = criarPasso(estado.destaque);
  const chave = html.replace(/entra às \d\d:\d\d/, "");
  if (chave !== ultimoPasso || el.passoDestaque.hidden) {
    el.passoDestaque.innerHTML = html;
    ultimoPasso = chave;
  }
  el.passoDestaque.hidden = false;
}

/** O último cartão desenhado, sem a hora de entrada. Ver `desenharPasso`. */
let ultimoPasso = null;

/* O conteúdo do cartão.
 *
 * O total é o maior número da tela, e logo abaixo ele se abre em caminhada e fila:
 * é a soma que o visitante não faz de cabeça, e é a tese do projeto. A barra
 * desenha a proporção — pontilhado para quem anda, cápsula para quem espera —, a
 * mesma linguagem do mapa.
 */
function criarPasso(item) {
  const a = item.attraction;
  const pe = Math.round(item.walking_minutes);
  const fila = item.queue_minutes;
  const total = Math.round(item.total_minutes);

  const perfilAtivo = estado.perfil.alturaCm !== null || estado.perfil.intensidade !== "tudo";
  const criterio = {
    alvos: "A menor soma de caminhada e fila entre as que você veio fazer.",
    // Pediu as marcadas e nenhuma está disponível: dizer, em vez de trocar o
    // critério calado — o visitante leria a sugestão como uma das dele.
    "sem-alvos": "Nenhuma das suas está disponível agora. Esta é a melhor do parque.",
    parque: perfilAtivo
      ? "A menor soma de caminhada e fila entre as que servem para o seu grupo."
      : "A menor soma de caminhada e fila do parque agora.",
  }[estado.origemDoDestaque];
  const porque =
    estado.origemDoDestaque === "sem-alvos"
      ? `<p class="passo__porque">${criterio}</p>`
      : criarTendencia(item.trend) + criarPopularidade(item.popularity) ||
        `<p class="passo__porque">${criterio}</p>`;

  const intensidade = NOME_DA_INTENSIDADE[a.intensity];
  const selo = intensidade ? `<span class="passo__selo">${intensidade}</span>` : "";

  return `
    <div class="passo__linha">
      <p class="passo__nome">${escapar(a.name)}</p>
      <p class="passo__total"><strong>${total}</strong><span>min</span></p>
    </div>
    <div class="passo__barra" role="img" aria-label="${pe} min a pé e ${fila} min de fila">
      <span class="passo__pe" style="flex-grow: ${Math.max(pe, 1)}"></span>
      <span class="passo__fila" style="flex-grow: ${Math.max(fila, 1)}"></span>
    </div>
    <p class="passo__conta">
      <span>${ICONE.caminhada} ${pe} min a pé</span>
      <span>${ICONE.fila} ${fila} min de fila</span>
      <span class="passo__chegada" aria-live="off">entra às ${horaDaqui(item.total_minutes)}</span>
    </p>
    ${porque}
    ${selo}
    ${criarAlternativas(estado.alternativas)}
    <button type="button" class="botao-ja-fui" data-atracao="${escapar(a.id)}"
            data-nome="${escapar(a.name)}">
      ${ICONE.check} Já fui
    </button>
  `;
}

/* A 2ª e a 3ª, numa linha: o plano B de quem não gostou da sugestão, sem abrir o
 * painel (29/10/2026). Mesmo critério do cartão — com "Das minhas", as seguintes
 * também são das marcadas. */
function criarAlternativas(alternativas) {
  if (alternativas.length === 0) return "";

  const itens = alternativas
    .map(
      (r) => `
        <li>
          <span class="passo__outra-nome">${escapar(r.attraction.name)}</span>
          <strong>${Math.round(r.total_minutes)} min</strong>
        </li>`
    )
    .join("");
  return `<div class="passo__outras"><p>Ou então</p><ul>${itens}</ul></div>`;
}

/** A hora em que o visitante entra na atração, no fuso do PARQUE. */
function horaDaqui(minutos) {
  try {
    return new Date(Date.now() + minutos * 60000).toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: estado.fusoDoParque,
    });
  } catch {
    return formatarHora(new Date(Date.now() + minutos * 60000).toISOString());
  }
}

let temporizadorDesfazer;

/* "Já fui" pelo cartão, com 5 s para desfazer.
 *
 * O cartão troca de atração na hora — é o que torna o botão útil —, e por isso
 * mesmo um toque errado de quem usa o celular com uma mão só passaria sem volta:
 * quando ele percebe, a atração já saiu da tela. */
function jaFuiPeloCartao(attractionId, nome) {
  alternarVisitada(attractionId);

  el.desfazerTexto.textContent = `“${nome}” marcada como feita hoje.`;
  el.btnDesfazer.dataset.atracao = attractionId;
  el.desfazer.hidden = false;

  clearTimeout(temporizadorDesfazer);
  temporizadorDesfazer = setTimeout(() => {
    el.desfazer.hidden = true;
  }, DESFAZER_MS);
}

/* O número no botão do painel: quantas atrações há lá dentro.
 *
 * Contado na lista desenhada, e não em `available`: o painel mostra as oito
 * primeiras, e a barra dizia "· 26" sobre um painel de oito (29/10/2026). É a
 * lição nº 3 ao contrário — o número tem de ser o do que está na tela. */
function atualizarContagemDeFilas() {
  const n = el.lista.querySelectorAll(":scope > .item").length;
  el.todasFilasN.textContent = n > 0 ? ` · ${n}` : "";
}

/* A tendência, na linha da conta.
 *
 * É a frase que explica **por que agora** — a diferença entre um número e um
 * conselho. A seta e a cor existem porque o olho lê "caindo" antes de ler o
 * texto, e num app usado de pé, no meio do parque, isso conta.
 *
 * Só aparece para quem se moveu: "estável" ocupa espaço para dizer que nada
 * mudou, e a fila fica parada quase dois terços do tempo.
 */
function criarTendencia(trend) {
  if (!trend || trend.direction === "STABLE") return "";

  const caindo = trend.direction === "FALLING";
  const icone = caindo ? ICONE.caindo : ICONE.subindo;
  const classe = caindo ? "tendencia tendencia--caindo" : "tendencia tendencia--subindo";

  return `
    <p class="${classe}">
      ${icone}
      ${escapar(trend.description)}
    </p>
  `;
}

/* A popularidade, na linha abaixo da conta.
 *
 * Mostra **faixa**, nunca o número da média. A coleta é mais densa no pico do
 * meio-dia, o que infla a média absoluta — mas infla todas as atrações juntas,
 * então a comparação entre elas sobrevive e o valor isolado não. Exibir "fila
 * média: 52,6 min" convidaria a comparar com a fila de agora, que é outra
 * pergunta, e cuja resposta já está a dois centímetros dali.
 *
 * Duas faixas ficam em silêncio, e é decisão de produto:
 *
 * - `MODERATE` é o meio da tabela. Um selo dizendo "mediana" em metade das
 *   atrações vira ruído, e ruído gasta a atenção que o selo de principal precisa.
 * - `UNKNOWN` é ausência de dado. Anunciá-la faria o app falar sobre si mesmo em
 *   vez de falar sobre o parque — e ela ainda aparece no filtro, para quem quiser
 *   justamente as que ainda não conhecemos.
 */
function criarPopularidade(popularidade) {
  if (!popularidade) return "";

  // A oportunidade vem primeiro porque é a única que muda a decisão de agora:
  // uma das principais do parque com fila abaixo da média dela.
  if (popularidade.opportunity) {
    return `
      <p class="popularidade popularidade--oportunidade">
        ${ICONE.pessoas}
        Principal do parque, e hoje abaixo da média dela
        (${Math.round(popularidade.average_minutes)} min)
      </p>
    `;
  }

  if (popularidade.tier === "HEADLINER") {
    return `<p class="popularidade">${ICONE.pessoas} Uma das principais do parque</p>`;
  }

  if (popularidade.tier === "QUIET") {
    return `<p class="popularidade">${ICONE.pessoas} Costuma ter fila curta</p>`;
  }

  return "";
}

function criarItem(item, idDaMelhor) {
  const id = item.attraction.id;
  const visitada = estado.visitadas.has(id);
  const ehAlvo = estado.alvos.has(id);

  // Uma atração já visitada não é "a melhor escolha agora", por melhor que seja
  // o número. Quem decide qual recebe a etiqueta é `renderizar`.
  const ehMelhor = id === idDaMelhor;

  const etiqueta = ehMelhor
    ? `<span class="etiqueta">${ICONE.estrela} Melhor escolha agora</span>`
    : "";

  const classes = ["item"];
  if (ehMelhor) classes.push("item--melhor");
  if (visitada) classes.push("item--visitada");
  if (ehAlvo) classes.push("item--alvo");
  if (PERFIL.soAdultos(item.attraction, estado.perfil)) classes.push("item--adultos");

  return `
    <li class="${classes.join(" ")}" data-expandido="false">
      <div class="custo">
        <strong>${Math.round(item.total_minutes)}</strong>
        <span>min</span>
      </div>
      <div class="corpo">
        <p class="nome">${escapar(item.attraction.name)}</p>
        <p class="conta">
          <span class="parcela">
            ${ICONE.caminhada} ${Math.round(item.walking_minutes)} min a pé
          </span>
          <span class="parcela">
            ${ICONE.fila} ${item.queue_minutes} min de fila
          </span>
        </p>
        ${criarTendencia(item.trend)}
        ${criarPopularidade(item.popularity)}
        ${criarRestricao(item.attraction)}
        ${etiqueta}
      </div>
      <!-- Botões de verdade, e não <div> clicáveis: já vêm com foco pelo teclado,
           papel anunciado ao leitor de tela e acionamento por Enter e Espaço.
           Refazer isso à mão num div dá errado silenciosamente. -->
      <div class="acoes">
        <button type="button" class="marcar-alvo"
                data-atracao="${escapar(id)}"
                aria-pressed="${ehAlvo}"
                title="${ehAlvo ? "Tirar da minha lista" : "Vim por esta"}">
          ${ICONE.alvo}
          <span>${ehAlvo ? "Na lista" : "Vim por"}</span>
        </button>
        <button type="button" class="marcar-visitada"
                data-atracao="${escapar(id)}"
                aria-pressed="${visitada}"
                title="${visitada ? "Desmarcar" : "Marcar como já visitada"}">
          ${ICONE.check}
          <span>${visitada ? "Fui" : "Já fui"}</span>
        </button>
        <button type="button" class="ver-historico"
                data-atracao="${escapar(id)}"
                aria-expanded="false">
          ${ICONE.grafico}
          <span>Histórico</span>
        </button>
      </div>
    </li>
  `;
}

// ---------------------------------------------------------------------------
// Gráfico do histórico
// ---------------------------------------------------------------------------

/* Desenhado em SVG à mão, sem biblioteca.
 *
 * Não é teimosia: uma biblioteca de gráficos custa 50–200 KB para desenhar uma
 * linha e alguns eixos, num app cuja decisão registrada é não ter etapa de build.
 * O SVG escala sem borrar, herda a cor do tema e sai pronto no HTML.
 *
 * As coordenadas são calculadas num sistema de 0–100 em vez de pixels: assim o
 * `viewBox` cuida do redimensionamento e o mesmo desenho serve do celular ao
 * desktop sem recalcular nada.
 */
const GRAFICO = { largura: 100, altura: 34, topo: 3, base: 31 };

/* O eixo vertical começa em ZERO, e não no menor valor da série.
 *
 * Começar no mínimo é o padrão de muitas bibliotecas e está errado para este
 * dado. Com escala truncada, uma fila que oscila entre 5 e 10 minutos desenha a
 * mesma queda dramática que uma que despencou de 90 para 5 — e a informação que
 * o visitante mais quer, *o tamanho da fila*, desaparece do desenho.
 *
 * Com base zero, a altura da linha É a fila. Inclinação responde "está
 * melhorando?", altura responde "está grande?", e as duas perguntas convivem no
 * mesmo gráfico sem uma mentir sobre a outra.
 */
function escalaVertical(filas) {
  // Folga no topo para o pico não encostar na borda e virar uma linha cortada.
  // O mínimo de 10 evita que uma série toda de filas curtas — 0 e 5 minutos —
  // vire um gráfico de picos gigantes sobre nada.
  return Math.max(Math.max(...filas) * 1.15, 10);
}

function pontosDaLinha(pontos, teto) {
  const passo = pontos.length > 1 ? GRAFICO.largura / (pontos.length - 1) : 0;

  return pontos.map((ponto, indice) => {
    const x = pontos.length > 1 ? indice * passo : GRAFICO.largura / 2;
    // O eixo Y do SVG cresce para baixo, então o valor é invertido — sem isso o
    // gráfico sairia de cabeça para baixo, com as filas maiores no chão.
    const proporcao = ponto.minutes / teto;
    const y = GRAFICO.base - proporcao * (GRAFICO.base - GRAFICO.topo);
    return { x, y, ponto };
  });
}

function desenharGrafico(dados) {
  const pontos = dados.points;

  if (pontos.length < 2) {
    return `<p class="grafico-vazio">
      Ainda não há histórico suficiente para esta atração. O NextUp coleta a cada
      5 minutos. Volte mais tarde.
    </p>`;
  }

  const filas = pontos.map((p) => p.minutes);
  const minimo = Math.min(...filas);
  const maximo = Math.max(...filas);
  const coords = pontosDaLinha(pontos, escalaVertical(filas));

  const linha = coords.map((c) => `${c.x.toFixed(2)},${c.y.toFixed(2)}`).join(" ");
  // A área sob a linha dá peso visual à curva; sozinha, uma linha de 1px some
  // numa tela de celular ao sol.
  const area = `0,${GRAFICO.altura} ${linha} ${GRAFICO.largura},${GRAFICO.altura}`;
  const ultimo = coords[coords.length - 1];

  const resumo = dados.summary;
  const legenda = resumo
    ? `<div class="grafico-numeros">
         <span><strong>${resumo.min_minutes}</strong> mín</span>
         <span><strong>${resumo.average_minutes}</strong> média</span>
         <span><strong>${resumo.max_minutes}</strong> máx</span>
       </div>`
    : "";

  return `
    <figure class="grafico">
      <figcaption>
        Últimas ${dados.hours}h · ${pontos.length} medições
      </figcaption>
      <svg viewBox="0 0 ${GRAFICO.largura} ${GRAFICO.altura}"
           preserveAspectRatio="none"
           role="img"
           aria-label="${escapar(descreverGrafico(dados, minimo, maximo))}">
        <polygon class="grafico-area" points="${area}" />
        <polyline class="grafico-linha" points="${linha}" />
        <circle class="grafico-agora" cx="${ultimo.x.toFixed(2)}"
                cy="${ultimo.y.toFixed(2)}" r="1.6" />
      </svg>
      <div class="grafico-eixo">
        <span>${formatarHora(pontos[0].at)}</span>
        <span>${formatarHora(ultimo.ponto.at)}</span>
      </div>
      ${legenda}
    </figure>
  `;
}

/* O texto alternativo do gráfico.
 *
 * Um `<svg>` sem rótulo é invisível para leitor de tela — e aqui não há
 * alternativa textual em lugar nenhum, porque os números da legenda não contam a
 * forma da curva. Esta frase é a única versão acessível do gráfico.
 */
function descreverGrafico(dados, minimo, maximo) {
  const inicio = dados.points[0].minutes;
  const fim = dados.points[dados.points.length - 1].minutes;

  return (
    `Fila nas últimas ${dados.hours} horas: começou em ${inicio} minutos, ` +
    `está em ${fim}. Variou entre ${minimo} e ${maximo}.`
  );
}

async function alternarHistorico(item, attractionId) {
  const aberto = item.querySelector(".historico");

  if (aberto) {
    aberto.remove();
    item.dataset.expandido = "false";
    return;
  }

  const caixa = document.createElement("div");
  caixa.className = "historico";
  caixa.innerHTML = '<p class="grafico-vazio">Carregando histórico…</p>';
  item.appendChild(caixa);
  item.dataset.expandido = "true";

  try {
    const resposta = await fetch(
      `/api/parks/${estado.parqueId}/attractions/${attractionId}/history?hours=${HORAS_DE_HISTORICO}`
    );

    if (!resposta.ok) {
      caixa.innerHTML = `<p class="grafico-vazio">${
        resposta.status === 503
          ? "O histórico está indisponível no momento."
          : "Não foi possível carregar o histórico."
      }</p>`;
      return;
    }

    caixa.innerHTML = desenharGrafico(await resposta.json());
  } catch {
    caixa.innerHTML = '<p class="grafico-vazio">Não foi possível falar com o servidor.</p>';
  }
}

/* No fuso do PARQUE, como a hora de entrada do cartão. Antes saía no fuso do
 * celular: num aparelho brasileiro, "Dado da fonte às 22:41" convivia na mesma
 * tela com "entra às 21:51", uma hora de diferença sem explicação. */
function formatarHora(iso) {
  if (!iso) return "—";
  const opcoes = { hour: "2-digit", minute: "2-digit" };
  try {
    return new Date(iso).toLocaleTimeString("pt-BR", {
      ...opcoes,
      timeZone: estado.fusoDoParque,
    });
  } catch {
    // Fuso desconhecido: a hora do aparelho é melhor que nenhuma.
    return new Date(iso).toLocaleTimeString("pt-BR", opcoes);
  }
}

/** Impede que um nome vindo da API seja interpretado como HTML.
 *
 * Os nomes vêm de uma fonte externa. Sem escapar, um nome contendo `<script>`
 * executaria no navegador de quem abrisse a página — a falha conhecida como XSS.
 */
function escapar(texto) {
  const no = document.createElement("span");
  no.textContent = texto;
  return no.innerHTML;
}

// ---------------------------------------------------------------------------
// Início
// ---------------------------------------------------------------------------

function iniciar() {
  iniciarMapa();

  // A primeira versão é só o Magic Kingdom: sem a chave, a lista de destinos
  // nem é pedida — o seletor não aparece, e buscá-la seria rede à toa.
  if (MOSTRAR_SELETOR_DE_PARQUES) {
    el.campoParque.hidden = false;
    carregarParques();
  }

  // A largura de cada nome no mapa muda quando a fonte chega; medir com a fonte
  // reserva deixaria as caixas erradas e os nomes se tocando.
  document.fonts?.ready.then(posicionarRotulos);

  // Antes de qualquer desenho: os filtros são globais e sobrevivem entre visitas,
  // então a primeira lista já precisa sair respeitando o que ficou guardado.
  estado.filtros = FILTROS.ler();
  atualizarControlesDeFiltro();

  // O perfil também vem antes de qualquer desenho, pelo mesmo motivo.
  estado.perfil = PERFIL.ler();
  atualizarResumoDoPerfil();
  estado.criterio = CARTAO.ler();

  // Carrega o parque padrão já na abertura: o app passa a mostrar algo útil
  // antes de qualquer permissão de GPS.
  carregarParque();

  el.btnLocalizar.addEventListener("click", localizar);
  el.btnAtualizar.addEventListener("click", () => {
    if (estado.posicao) {
      buscarRecomendacoes();
    } else {
      carregarParque();
    }
  });

  el.buscaParque.addEventListener("input", (evento) => {
    filtrarParques(evento.target.value);
  });

  // Delegação: um ouvinte na lista, e não um por botão. A lista é reapagada e
  // redesenhada a cada atualização, e ouvintes presos aos botões antigos
  // morreriam junto — ou pior, ficariam vivos segurando nós que já saíram da
  // página.
  // O mesmo tratador serve às duas listas — ranking e alvos —, porque os itens
  // são idênticos. Um tratador por lista faria dois caminhos para o mesmo clique,
  // e um deles acabaria esquecido numa mudança futura.
  [el.lista, el.listaAlvos].forEach((lista) => {
    lista.addEventListener("click", aoClicarNumItem);
  });

  el.btnLimparAlvos.addEventListener("click", () => {
    ALVOS.limpar(estado.parqueId);
    estado.alvos = new Set();
    if (estado.ultimoRanking) {
      renderizar(estado.ultimoRanking);
    } else {
      desenharAlvos([]);
    }
    desenharCatalogo(el.buscaAtracao.value);
  });

  // Delegação também aqui: a lista é redesenhada a cada marcação, e ouvintes
  // presos às caixas antigas morreriam junto.
  el.catalogoAtracoes.addEventListener("change", (evento) => {
    const caixa = evento.target.closest("input[type='checkbox']");
    if (!caixa) return;

    alternarAlvo(caixa.dataset.atracao);

    // Só a linha muda de aparência. Redesenhar a lista aqui a reordenaria **sob o
    // dedo do visitante** — ele marca uma atração, ela salta para o topo, e quem
    // estava escolhendo várias perde o lugar. A reordenação espera o painel
    // fechar e abrir de novo.
    caixa.closest(".catalogo__item").classList.toggle(
      "catalogo__item--marcada",
      caixa.checked
    );
  });

  // Reordenar ao ABRIR: aí as marcadas estão no topo para quem veio remover
  // alguma, sem que a lista tenha se mexido enquanto ele escolhia.
  el.escolherAlvos.addEventListener("toggle", () => {
    if (el.escolherAlvos.open) desenharCatalogo(el.buscaAtracao.value);
  });

  el.buscaAtracao.addEventListener("input", (evento) => {
    desenharCatalogo(evento.target.value);
  });

  // Enter num campo de busca dentro de `<details>` fecharia o painel em alguns
  // navegadores. Aqui não há o que submeter: a lista já filtra a cada tecla.
  el.buscaAtracao.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter") evento.preventDefault();
  });

  // `input` e não `change`: o rótulo acompanha o dedo enquanto arrasta, em vez de
  // só revelar o valor quando o visitante solta — e aí ele arrastaria às cegas.
  [el.filtroFila, el.filtroCaminhada].forEach((controle) => {
    controle.addEventListener("input", aplicarFiltros);
  });

  // Caixas usam `change`: `input` dispara igual aqui, mas `change` é o evento que
  // descreve o que aconteceu — e é o que o teclado emite ao marcar com Espaço.
  el.filtrosFaixa.forEach((caixa) => {
    caixa.addEventListener("change", aplicarFiltros);
  });

  el.btnLimparFiltros.addEventListener("click", () => {
    estado.filtros = FILTROS.limpar();
    atualizarControlesDeFiltro();
    if (estado.ultimoRanking) renderizar(estado.ultimoRanking);
  });

  el.btnMostrarVisitadas.addEventListener("click", () => {
    estado.mostrandoVisitadas = !estado.mostrandoVisitadas;
    if (estado.ultimoRanking) renderizar(estado.ultimoRanking);
  });

  el.btnLimparVisitadas.addEventListener("click", () => {
    VISITADAS.limpar(estado.parqueId);
    estado.visitadas = new Set();
    estado.mostrandoVisitadas = false;
    if (estado.ultimoRanking) renderizar(estado.ultimoRanking);
  });

  el.parque.addEventListener("change", (evento) => {
    trocarParque(evento.target.value);
  });

  // Enter na busca aplica o parque que o seletor está mostrando.
  //
  // Sem isto havia uma mentira na tela: filtrar reconstrói o `<select>`, e o
  // navegador passa a exibir a primeira opção — mas **exibir não é selecionar**.
  // Nenhum `change` dispara, então quem digitasse "epcot" e desse Enter veria
  // "EPCOT" escrito no seletor enquanto o app continuava no Magic Kingdom.
  el.buscaParque.addEventListener("keydown", (evento) => {
    if (evento.key !== "Enter") return;

    // Impede o Enter de submeter e recarregar a página, o que perderia a posição
    // que o visitante já tinha informado.
    evento.preventDefault();

    if (el.parque.value) {
      trocarParque(el.parque.value);
      // Tira o teclado da frente do mapa no celular — que é justamente o que o
      // visitante quer ver depois de escolher o parque.
      el.buscaParque.blur();
    }
  });

  el.btnPerfil.addEventListener("click", () => abrirPerfil());
  el.btnSalvarPerfil.addEventListener("click", salvarPerfil);
  el.btnPularPerfil.addEventListener("click", pularPerfil);

  // Esc fecha o `<dialog>` sozinho. Interceptar é o que faz o Esc da primeira
  // visita valer como "Pular" — senão o painel voltaria na próxima abertura.
  el.painelPerfil.addEventListener("cancel", (evento) => {
    evento.preventDefault();
    pularPerfil();
  });

  el.painelPerfil.addEventListener("change", (evento) => {
    if (evento.target.name !== "criancas") return;
    el.alturaCampo.hidden = evento.target.value !== "sim";
    definirAltura(Number(el.altura.value));
  });

  el.altura.addEventListener("input", () => definirAltura(Number(el.altura.value)));
  el.btnAlturaMenos.addEventListener("click", () => definirAltura(Number(el.altura.value) - 1));
  el.btnAlturaMais.addEventListener("click", () => definirAltura(Number(el.altura.value) + 1));

  el.btnTodasFilas.addEventListener("click", () => el.painelFilas.showModal());
  // Uma renovação que esperou o painel fechar acontece assim que ele fecha.
  el.painelFilas.addEventListener("close", () => {
    if (estado.renovacaoPendente) renovar();
  });
  el.posicaoAtual.addEventListener("click", (evento) => {
    if (evento.target.closest(".voltar-gps")) localizar();
  });
  setInterval(tique, TIQUE_MS);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) tique();
  });
  el.passoCriterio.addEventListener("change", (evento) => {
    estado.criterio = CARTAO.salvar(evento.target.value);
    if (estado.ultimoRanking) renderizar(estado.ultimoRanking);
  });
  for (const lista of [el.lista, el.listaAlvos]) {
    lista.addEventListener("mouseover", realcarNoMapa);
    lista.addEventListener("mouseleave", realcarNoMapa);
  }
  el.btnFecharFilas.addEventListener("click", () => el.painelFilas.close());

  el.passoDestaque.addEventListener("click", (evento) => {
    const botao = evento.target.closest(".botao-ja-fui");
    if (botao) jaFuiPeloCartao(botao.dataset.atracao, botao.dataset.nome);
  });

  el.btnDesfazer.addEventListener("click", () => {
    clearTimeout(temporizadorDesfazer);
    el.desfazer.hidden = true;
    alternarVisitada(el.btnDesfazer.dataset.atracao);
  });

  el.btnMostrarEscondidas.addEventListener("click", () => {
    estado.mostrandoEscondidas = !estado.mostrandoEscondidas;
    redesenhar();
  });

  el.btnAtualizar.hidden = false;

  // A primeira visita abre com as duas perguntas, por cima do parque já carregado
  // — e não numa página de cadastro antes dele (decisão "uma tela, dois estados").
  if (!estado.perfil.respondido) abrirPerfil({ primeiraVez: true });
}

iniciar();

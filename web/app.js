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
  /** Se as visitadas estão sendo exibidas em vez de escondidas. */
  mostrandoVisitadas: false,
  /** Última resposta do ranking, para redesenhar sem ir à rede de novo. */
  ultimoRanking: null,
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
};

let mapa;
let marcadorVisitante;
let camadaAtracoes;

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

function iniciarMapa() {
  mapa = L.map("mapa").setView([28.4177, -81.5812], 15);

  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(mapa);

  camadaAtracoes = L.layerGroup().addTo(mapa);

  // Tocar no mapa define a posição. Resolve dois problemas de uma vez: quem
  // negou o GPS ainda consegue usar o app, e quem está com GPS impreciso
  // (comum entre prédios) pode corrigir na mão — risco previsto na seção 8.
  mapa.on("click", (evento) => {
    definirPosicao(evento.latlng.lat, evento.latlng.lng, "escolhida no mapa");
  });
}

/* Marcador numerado, na paleta do app.
 *
 * O alfinete azul padrão do Leaflet destoa do resto e, pior, não diz nada: oito
 * marcadores idênticos não permitem ligar o mapa à lista. Numerado, dá para
 * achar no mapa a atração que está em primeiro sem contar pontinhos.
 */
function marcadorNumerado(posicao) {
  const melhor = posicao === 1;

  return L.divIcon({
    className: "",
    html: `<span class="pino${melhor ? " pino--melhor" : ""}">${posicao}</span>`,
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
      icon: marcadorNumerado(indice + 1),
      // Atrações vizinhas ficam a poucos metros, então os marcadores se
      // sobrepõem. Quanto melhor a colocação, mais na frente: a resposta do app
      // não pode ficar escondida atrás de uma opção pior.
      zIndexOffset: (recomendacoes.length - indice) * 10,
    })
      .bindPopup(`<strong>${indice + 1}. ${escapar(item.attraction.name)}</strong><br>
         ${Math.round(item.total_minutes)} min no total`)
      .addTo(camadaAtracoes);
  });
}

function marcarVisitante(lat, lon) {
  if (marcadorVisitante) {
    marcadorVisitante.setLatLng([lat, lon]);
  } else {
    marcadorVisitante = L.circleMarker([lat, lon], {
      radius: 9,
      color: "#fff",
      weight: 3,
      fillColor: "#0b6bcb",
      fillOpacity: 1,
    }).addTo(mapa);
    marcadorVisitante.bindPopup("Você está aqui");
  }
  mapa.setView([lat, lon], 16);
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

function definirPosicao(lat, lon, origem) {
  estado.posicao = { lat, lon };

  el.posicaoAtual.textContent = `Posição ${origem}: ${lat.toFixed(5)}, ${lon.toFixed(5)}`;
  el.posicaoAtual.hidden = false;

  marcarVisitante(lat, lon);
  buscarRecomendacoes();
}

function localizar() {
  if (!navigator.geolocation) {
    mostrarAviso(
      "Este navegador não oferece localização. Toque no mapa para marcar onde você está."
    );
    return;
  }

  el.btnLocalizar.disabled = true;
  el.btnLocalizar.textContent = "Localizando…";
  mostrarAviso("Procurando sua posição…", "info");

  navigator.geolocation.getCurrentPosition(
    (posicao) => {
      restaurarBotaoLocalizar();
      limparAviso();
      definirPosicao(posicao.coords.latitude, posicao.coords.longitude, "do GPS");
    },
    (erro) => {
      restaurarBotaoLocalizar();
      mostrarAviso(explicarErroDeGps(erro));
    },
    // `enableHighAccuracy` pede o GPS de verdade em vez da posição aproximada
    // por antena — necessário para diferenciar atrações a 50 m uma da outra.
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
  );
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
  estado.ultimoRanking = null;
  el.visitadasAviso.hidden = true;
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
async function carregarParque({ trocaDeParque = false } = {}) {
  try {
    const resposta = await fetch(`/api/parks/${estado.parqueId}/attractions`);
    if (!resposta.ok) {
      mostrarAviso(await explicarErroDaApi(resposta));
      return;
    }

    const dados = await resposta.json();

    // O fuso do parque decide quando "hoje" vira "ontem" para as visitadas. Só a
    // rota de atrações o informa, e por isso a leitura acontece aqui.
    estado.fusoDoParque = dados.timezone || estado.fusoDoParque;
    estado.visitadas = VISITADAS.doParque(estado.parqueId, estado.fusoDoParque);
    // Alvos não dependem do fuso: valem até o visitante mudar de ideia.
    estado.alvos = ALVOS.doParque(estado.parqueId);

    // O catálogo alimenta o seletor de alvos, que funciona **sem** posição: dá
    // para montar a lista de desejos a caminho do parque.
    estado.atracoesDoParque = [...dados.attractions].sort((a, b) =>
      a.name.localeCompare(b.name, "pt-BR")
    );
    desenharCatalogo(el.buscaAtracao.value);
    desenharAlvos(estado.ultimoRanking ? estado.ultimoRanking.recommendations : []);

    // Duas chamadas assíncronas disputam o mapa: esta e a do ranking. Se o
    // visitante liberar o GPS enquanto esta ainda está no ar, a resposta chega
    // atrasada e jogaria a vista para longe de onde ele está. Numa troca de
    // parque o enquadramento é o que ele pediu; na abertura, não.
    if (trocaDeParque || !estado.posicao) {
      enquadrarParque(dados.bounds);
    }

    // Com posição, o ranking manda: quem desenha o mapa é `buscarRecomendacoes`.
    if (!estado.posicao) {
      desenharParque(dados.attractions);
      mostrarPanoramaDoParque(dados);
    }
  } catch {
    mostrarAviso("Não foi possível falar com o servidor. Verifique sua conexão.");
  }
}

async function buscarRecomendacoes() {
  if (!estado.posicao || estado.carregando) return;

  estado.carregando = true;
  mostrarEsqueleto();

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
      mostrarAviso(await explicarErroDaApi(resposta));
      el.lista.innerHTML = "";
      el.resumo.hidden = true;
      return;
    }

    limparAviso();
    renderizar(await resposta.json());
  } catch {
    mostrarAviso("Não foi possível falar com o servidor. Verifique sua conexão.");
    el.lista.innerHTML = "";
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
}

/* A tela antes de haver posição: filas do parque, sem ranking.
 *
 * Ordenada pela menor fila — que é a pergunta errada do projeto, e por isso o
 * texto diz explicitamente o que falta. Prometer "para onde ir" sem saber onde o
 * visitante está seria repetir justamente o erro que o NextUp existe para evitar.
 */
function mostrarPanoramaDoParque(dados) {
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
    <strong>Ordenado pela menor fila</strong> — que raramente é a melhor escolha.
    Diga onde você está para somar a caminhada.
  `;
  el.resumo.hidden = false;

  const comFila = dados.attractions
    .filter((a) => a.queue_minutes !== null)
    .sort((a, b) => a.queue_minutes - b.queue_minutes);

  if (comFila.length === 0) {
    el.lista.innerHTML = "";
    mostrarAviso("Nenhuma atração com fila agora. O parque pode estar fechado.", "info");
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
          <span class="parcela">${ICONE.fila} só a fila — falta a caminhada</span>
        </p>
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

function renderizar(dados) {
  estado.ultimoRanking = dados;

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

  if (visiveis.length === 0) {
    el.lista.innerHTML = "";
    // Agora esta frase é verdade. Antes ela aparecia com oito marcadas de vinte e
    // oito disponíveis, porque a lista pedida ao servidor já vinha cortada.
    mostrarAviso(
      "Você já passou por todas as atrações disponíveis agora. Nada mal.",
      "info"
    );
    return;
  }

  limparAviso();

  // A etiqueta vai para a melhor **ainda não feita**, e não para a primeira da
  // lista. Com as visitadas à mostra, a primeira posição pode ser uma que o
  // visitante já fez — e aí ninguém receberia o destaque, justamente na tela em
  // que ele está decidindo para onde ir.
  const melhorDisponivel = visiveis.find((r) => !estado.visitadas.has(r.attraction.id));
  const idDaMelhor = melhorDisponivel ? melhorDisponivel.attraction.id : null;

  el.lista.innerHTML = visiveis.map((item) => criarItem(item, idDaMelhor)).join("");
  desenharMapa(visiveis);

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
function escolherVisiveis(recomendacoes) {
  // Os alvos já têm seção própria acima. Repeti-los aqui gastaria as oito vagas
  // do ranking com coisas que o visitante acabou de ver.
  const semAlvos = recomendacoes.filter((r) => !estado.alvos.has(r.attraction.id));
  const disponiveis = semAlvos.filter((r) => !estado.visitadas.has(r.attraction.id));
  const proximas = disponiveis.slice(0, LIMITE);

  if (!estado.mostrandoVisitadas) return proximas;

  const marcadas = semAlvos.filter((r) => estado.visitadas.has(r.attraction.id));

  return [...proximas, ...marcadas].sort((a, b) => a.total_minutes - b.total_minutes);
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
  const ordenadas = [...encontradas].sort((a, b) => {
    const marcadaA = estado.alvos.has(a.id);
    const marcadaB = estado.alvos.has(b.id);
    if (marcadaA !== marcadaB) return marcadaA ? -1 : 1;
    return a.name.localeCompare(b.name, "pt-BR");
  });

  el.catalogoAtracoes.innerHTML = ordenadas.map(criarLinhaDoCatalogo).join("");
}

function criarLinhaDoCatalogo(atracao) {
  const marcada = estado.alvos.has(atracao.id);

  // A fila de agora ajuda a escolher, mas nem toda atração tem uma — fechada ou
  // sem medida. Dizer "—" é mais honesto que omitir a linha ou inventar um zero.
  const fila =
    atracao.queue_minutes === null ? "—" : `${atracao.queue_minutes} min`;

  return `
    <li>
      <label class="catalogo__item${marcada ? " catalogo__item--marcada" : ""}">
        <input type="checkbox" data-atracao="${escapar(atracao.id)}"
               ${marcada ? "checked" : ""} />
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
  alvo: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.4" fill="currentColor" />
    </svg>`,
};

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
      5 minutos — volte mais tarde.
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

function formatarHora(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });
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
  carregarParques();

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

  el.btnAtualizar.hidden = false;

  mostrarAviso(
    "Toque em “Usar minha localização” ou marque sua posição no mapa para ver o que compensa mais.",
    "info"
  );
}

iniciar();

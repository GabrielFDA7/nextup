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

/** Estado da aplicação. Um objeto só, para ficar claro o que muda. */
const estado = {
  posicao: null, // { lat, lon }
  parqueId: PARQUE_PADRAO,
  carregando: false,
  /** Todos os destinos, guardados para a busca filtrar sem ir à rede de novo. */
  destinos: [],
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

  const parametros = new URLSearchParams({
    lat: estado.posicao.lat,
    lon: estado.posicao.lon,
    limit: LIMITE,
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
  return `
    <li class="item item--sem-posicao">
      <div class="custo">
        <strong>${item.queue_minutes}</strong>
        <span>min</span>
      </div>
      <div>
        <p class="nome">${escapar(item.name)}</p>
        <p class="conta">
          <span class="parcela">${ICONE.fila} só a fila — falta a caminhada</span>
        </p>
      </div>
    </li>
  `;
}

function renderizar(dados) {
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

  el.lista.innerHTML = dados.recommendations.map(criarItem).join("");
  desenharMapa(dados.recommendations);

  el.atualizado.textContent = `Dado da fonte às ${formatarHora(dados.data_updated_at)}.`;
  el.atualizado.hidden = false;
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
};

function criarItem(item, indice) {
  const ehMelhor = indice === 0;

  // A etiqueta responde à pergunta do app: entre 26 atrações, é esta.
  const etiqueta = ehMelhor
    ? `<span class="etiqueta">${ICONE.estrela} Melhor escolha agora</span>`
    : "";

  return `
    <li class="item${ehMelhor ? " item--melhor" : ""}">
      <div class="custo">
        <strong>${Math.round(item.total_minutes)}</strong>
        <span>min</span>
      </div>
      <div>
        <p class="nome">${escapar(item.attraction.name)}</p>
        <p class="conta">
          <span class="parcela">
            ${ICONE.caminhada} ${Math.round(item.walking_minutes)} min a pé
          </span>
          <span class="parcela">
            ${ICONE.fila} ${item.queue_minutes} min de fila
          </span>
        </p>
        ${etiqueta}
      </div>
    </li>
  `;
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

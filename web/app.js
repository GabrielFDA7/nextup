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
};

const el = {
  parque: document.getElementById("parque"),
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
    preencherSeletor(dados.destinations);
  } catch {
    // Não é motivo para travar o app: o parque padrão continua funcionando.
    el.parque.innerHTML = '<option value="">Magic Kingdom (padrão)</option>';
    el.parque.disabled = true;
  }
}

function preencherSeletor(destinos) {
  el.parque.innerHTML = "";

  destinos
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name, "pt-BR"))
    .forEach((destino) => {
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

function renderizar(dados) {
  el.tituloLista.textContent = dados.park_name;

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

  el.btnLocalizar.addEventListener("click", localizar);
  el.btnAtualizar.addEventListener("click", buscarRecomendacoes);

  el.parque.addEventListener("change", (evento) => {
    estado.parqueId = evento.target.value || PARQUE_PADRAO;
    buscarRecomendacoes();
  });

  mostrarAviso(
    "Toque em “Usar minha localização” ou marque sua posição no mapa para começar.",
    "info"
  );
}

iniciar();

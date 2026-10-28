# NextUp — Contexto para o Claude Code

Este arquivo é lido automaticamente ao abrir o projeto. Ele existe para que qualquer
sessão, em qualquer máquina, continue de onde a anterior parou.

---

## O projeto em um parágrafo

NextUp responde em tempo real "para qual atração eu devo ir agora?", cruzando o tempo de
fila de cada atração com a distância até ela. Automatiza o serviço que hoje consultores de
parque fazem manualmente por WhatsApp. Fonte de dados: ThemeParks.wiki (API pública,
gratuita, sem chave).

**A decisão de produto mais importante:** ranquear por `custo_total = caminhada + fila`,
**nunca** pela menor fila isolada. A menor fila pode ficar a 900 metros — o visitante
andaria 15 minutos para economizar 10. Esse detalhe é o diferencial do projeto.

Contexto completo, arquitetura, roadmap e registro de decisões em
[docs/PROJETO.md](docs/PROJETO.md). **Leia antes de trabalhar no projeto.**

---

## Como trabalhar com o Gabriel

- **Fale português.**
- Conhecimento **intermediário** em programação, mas **primeiro projeto consumindo APIs**.
- Ele pediu explicitamente para **ser ensinado enquanto construímos**: explique o *porquê*
  de cada decisão, não só entregue o código pronto. Conceito novo vai para o glossário
  (seção 9 do `docs/PROJETO.md`).
- Evite despejar blocos grandes de código sem contexto. O objetivo dele inclui aprender.

**Restrição que molda todas as decisões:** este é o **projeto principal de portfólio** dele
para conseguir emprego (alvo: full-stack). Testes, CI/CD, Docker, deploy, commits limpos e
documentação de decisões **fazem parte da entrega** — não são extras opcionais.

---

## Estado atual

> 🧭 **ONDE PARAMOS (28/10/2026) — leia primeiro.**
>
> **Frentes abertas:**
> - **Fases 9.2 e 9.3 — implementação começando (28/10).** O design está fechado em
>   [`docs/design/claude-design/`](docs/design/claude-design/) (o README diz como abrir):
>   **3c no claro, 3b no escuro** (paleta algodão-doce), estrutura de **uma tela, dois
>   estados** (painel do perfil sobre o parque; depois próximo passo → roteiro → mapa →
>   lista de filas). O **mapa é real, sem tiles**: Leaflet pintando
>   `web/mapas/magic-kingdom.geojson` com as variáveis CSS; o protótipo está em
>   `mapa-real.html`, com `rota.js` (rota pelas trilhas, só desenho) e `rotulos.js`.
>   Revisar cada elemento do design **contra o que a API realmente entrega** ao portar.
>   ⚠️ O design usa dados de mentira (horários, minutos): nada dele vira constante.
> - **Primeira versão focada no Magic Kingdom** (decisão do Gabriel). Em consideração:
>   tirar o seletor de parques ou limitá-lo a parques igualmente famosos.
>
> **Agenda:**
> - **30/10 (sex)** — preliminar: `python scripts/medicoes/simular_roteiro.py --desde
>   2026-10-28 --gap 20`. Antes, `auditoria_coleta.py` para conferir a coleta.
> - **03/11 (ter)** — decisiva, com o fim de semana: o simulador e `avaliar_forecast.py
>   --desde 2026-10-28`. Ela libera (ou mata) a tela do roteiro (8.4). O horário de verão
>   acaba em 01/11 — os scripts já usam o fuso do catálogo.
> - **Início de novembro** — conferir se "à noite as filas são baratas" sobrevive ao fim
>   da temporada de Halloween (era de noites de festa, com público reduzido).
>
> **Máquina nova? O que NÃO vem pelo Git:**
> - O **`.env`**, com a `NEXTUP_DATABASE_URL` do Neon (copiar do painel do Neon, sem
>   editar — o `config.py` normaliza). Sem ele, os scripts de medição leem um SQLite vazio.
> - O **Python 3.13**, se a máquina só tiver o 3.14: `py install 3.13`, e então
>   `py -V:3.13 -m venv .venv`.
> - `pip install -e ".[dev,e2e]"` (traz o `tzdata`) e `playwright install chromium`.
> - Para ativar a venv no PowerShell (`.venv\Scripts\Activate.ps1`), o Windows bloqueia
>   scripts por padrão: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, uma vez.
> - A memória do Claude Code (`~/.claude/projects/...`) é local; **este arquivo é a
>   memória que viaja**. O cron-job.org é conta do Gabriel e segue funcionando sozinho.

**Todas as 6 fases do roadmap original estão concluídas** (20/09/2026). O histórico é
coletado, persistido, analisado, exposto pela API e desenhado na tela.

O **6.6 terminou com um resultado negativo medido**: prever a fila por extrapolação erra
mais que usar a fila atual, em todo horizonte. O ranking não mudou — mas agora há número
para sustentar a escolha. Detalhes na seção 7 de `docs/PROJETO.md`.

**818 testes passando**: 722 na suíte rápida (~9s; 272 são do roteiro, a maioria
instâncias aleatórias conferidas contra força bruta) e 96 de interface em navegador (~130s).
CI verde em Python 3.11, 3.12 e 3.13, com job separado para o E2E.

Já existe e funciona:
- Estrutura completa em `src/nextup/` com as 4 camadas
- `config.py` com toda a configuração centralizada
- `core/geo.py` — Haversine, sinuosidade (1,3, medido contra o OSM) e tempo de caminhada;
  `travel_time_matrix` dá o tempo entre todos os pares de atrações (Fase 8.1)
- `core/itinerary.py` — **o otimizador do roteiro** (Fase 8.2, núcleo). `plan_itinerary`
  ordena os alvos por *branch and bound* exato, até 5 paradas, com a previsão de fila
  **injetada** (`persistence` é o padrão). Ainda sem rota na API nem tela
- `core/intensity.py` — tranquila / moderada / radical a partir das **etiquetas oficiais
  da Disney**, por regra escrita (Fase 9.1)
- `data/` — **dado conferido à mão**, empacotado com o código: a curadoria de altura
  mínima e etiquetas das 35 atrações do Magic Kingdom (`curadoria_magic_kingdom.json`).
  `models/curation.py` traduz as chaves em português para os nomes do código. A API devolve
  `min_height_cm` e `intensity` em toda atração
- `models/` — `Destination`, `ParkCatalog` (com coordenadas GPS) e `LiveData`
- `clients/cache.py` — cache com TTL, relógio injetável
- `clients/themeparks.py` — cliente assíncrono, backoff exponencial, erros próprios
- `core/recommender.py` — **o coração**: ranqueia por `custo_total = caminhada + fila`
- `core/trends.py` — tendência da fila (subindo/caindo/estável), função pura
- `cli.py` — comando `nextup`. Sem coordenadas lista filas; com `--lat/--lon` recomenda.
  `nextup --parks` lista os IDs de parque
- `core/history.py` — resumo de uma série de filas (mín, média, máx, amplitude)
- `core/popularity.py` — faixa de popularidade a partir da fila média histórica. Função
  pura; os três números do algoritmo saíram de medição sobre 1257 snapshots reais
- `core/forecast.py` — modelos de previsão e a régua que os compara. **Medido: extrapolar
  tendência erra mais que usar a fila atual**, então o ranking não usa previsão
- `api/` — FastAPI com 5 rotas sob `/api`: `health`, `destinations`,
  `parks/{id}/attractions` (o parque **sem** exigir posição, com `bounds` para o mapa),
  `parks/{id}/attractions/{id}/history?hours` e
  `parks/{id}/recommendations?lat&lon&limit`. Docs automáticas em `/docs`
- `web/preferencias.js` — `VISITADAS` (por dia, com fuso do parque) e `ALVOS` (sem prazo).
  Os alvos se escolhem num catálogo completo do parque, que funciona sem GPS.
  `FILTROS` (globais) limitam fila e caminhada
- `web/` — interface em HTML/CSS/JS puro, servida pelo próprio FastAPI. Geolocation,
  mapa Leaflet, e **tocar no mapa define a posição** (saída para quem nega o GPS).
  Abre mostrando o parque antes de qualquer permissão; busca no seletor; o mapa
  reenquadra ao trocar de parque
- `storage/` — persistência (Fase 6). Duas tabelas: `queue_snapshots` (o que foi medido)
  e `queue_forecasts` (o que a fonte previu, para auditá-la). `tables.py` (desenho),
  `engine.py` (conexão) e `snapshots.py` (gravar, consultar, limpar). SQLAlchemy Core,
  assíncrono, SQLite no desenvolvimento e Postgres na produção
- `migrations/` — Alembic com template assíncrono. A URL vem do ambiente, **nunca** do
  `alembic.ini`, que é versionado num repositório público. O contêiner aplica
  `alembic upgrade head` no start, antes do uvicorn
- `collector.py` — **o coletor** (Fase 6.2). Sobe como tarefa de fundo no `lifespan`,
  coleta a cada 5 min, guarda só atrações e compartilha o cliente com as rotas. Nível do
  `cli.py` porque orquestra `clients/` + `storage/`
- `tests/test_arquitetura.py` — a regra de dependência é verificada automaticamente
- `tests/test_migracoes.py` — aplica as migrações e compara com `tables.py`
- `tests/test_web_e2e.py` — 82 testes em Chromium real (`pytest -m e2e`)
- Fixtures reais da API em `tests/fixtures/`; nenhum teste toca a internet
- `.venv` local com **Python 3.13**, mesma versão mais alta testada no CI

**Como rodar o app inteiro:** `uvicorn nextup.api.main:app --reload` e abrir
`http://127.0.0.1:8000` — a interface e a API sobem juntas.

**Testes:** `pytest -m "not e2e"` para o ciclo rápido; `pytest` roda tudo. Os de
interface exigem `pip install -e ".[dev,e2e]"` e `playwright install chromium`.

**Fase 5 concluída — o projeto está no ar:**
<https://nextup-rcux.onrender.com> (API em `/api`, docs em `/docs`).

`Dockerfile`, `docker-compose.yml`, `.dockerignore` e `render.yaml` existem, e o job
`imagem-docker` do CI constrói a imagem, sobe o contêiner e confere que a API responde,
que não roda como root e que respeita a variável `PORT`. **Docker não está instalado na
máquina** — a validação é toda pelo CI. Todo push na `main` republica no Render sozinho.

**Limitação do plano gratuito:** hiberna após ~15 min sem acesso. Mitigado por um job no
**cron-job.org** (conta do Gabriel) que chama `/api/health` a cada 5 min, com alerta de
falha. O `keep-alive.yml` do GitHub fica só como reserva: medido em 27/10/2026, ele rodava a
cada ~4 h, e não a cada 10 min. O ping usa `/api/health` porque essa rota não consulta a
ThemeParks.wiki.

**Refino visual feito (13/09/2026).** Direção escolhida pelo Gabriel: "personalidade de
parque" — paleta de pôr do sol (coral, âmbar, roxo profundo), fonte Outfit, cantos
arredondados, ícones SVG e marcadores numerados no mapa. Tema escuro revisado: os fundos
quentes clareiam nele, então a tinta por cima inverte via `--sobre-quente` — sem isso, o
botão principal ficaria branco sobre coral claro.

**Fase 7 — Personalização CONCLUÍDA (21/09/2026).** Nasceu das ideias do Gabriel, não do
roadmap original: 7.1 ("já fui hoje"), 7.2 (brinquedos alvo), 7.3 (filtros) e 7.4
(popularidade). Detalhes na seção 7 de `docs/PROJETO.md`.

**Os filtros (7.3) cortam, nunca reordenam.** São de **fila** e **caminhada**, e não de
custo total: filtrar por custo é redundante com o ranking, mas as parcelas não são
intercambiáveis — 5 min a pé + 35 de fila é o mesmo total que 20 + 20, e experiência
oposta para quem empurra um carrinho.

> ⚠️ **Os alvos escapam do filtro**, e o selo "ativos" não é enfeite: filtro esquecido é
> indistinguível de parque vazio. A lista vazia distingue três causas — filtro apertado,
> tudo visitado, ou parque fechado — porque dizer a frase errada esconde o motivo.

**A popularidade (7.4) é o primeiro recurso construído sobre dado NOSSO.** Substituiu a
"radicalidade", que a fonte não fornece, pela **fila média histórica** — e a verdade
externa confere: as primeiras colocadas são TRON, Seven Dwarfs, Peter Pan e Space
Mountain. Os três números do algoritmo saíram de 1257 snapshots reais, não de intuição:

- **Faixa relativa ao parque, nunca limiar em minutos.** 59% das medições caem entre 10h e
  13h, o que infla a média absoluta — mas infla todas as atrações juntas, porque o coletor
  as fotografa a cada 5 min. A ordem sobrevive; o número não.
- **Razão contra a mediana, não tercil.** Medido: 83% de estabilidade contra 74%. E o
  tercil *força* um terço em cada faixa, promovendo dez medianas a "principal" num parque
  que tem duas.
- **Mínimo de 12 medições** (uma hora de coleta). O corte excluiu exatamente os shows e
  trens, e nenhuma atração de fila real.

> ⚠️ **`UNKNOWN` não é `QUIET`.** Ausência de dado não é dado. Chamar de tranquila uma
> atração que nunca medimos mandaria o visitante para uma fila de uma hora com a nossa
> bênção. Ela tem caixa própria no filtro.

> ⚠️ **A popularidade não reordena o ranking**, como a tendência e os alvos — e por uma
> razão a mais: ela descreve a **atração**, e o ranking responde sobre o **momento**.

> ⚠️ **Ausência de `popularity` LIBERA a atração no filtro.** Sem banco, a API devolve
> `null` em todas; reprovar esvaziaria a tela num ambiente que funciona perfeitamente.
> Mesmo princípio de `_tendencias()` engolir a falha do banco.

**A "oportunidade" é a razão de a feature existir:** uma das principais do parque com fila
hoje abaixo da média dela. Saber que uma atração é principal, isolado, não muda decisão
nenhuma. Em 8 de 23 atrações medidas, o histórico discorda do "agora" — se concordasse
sempre, não haveria o que dizer. Vale só para as principais: uma tranquila abaixo da média
é 4 min em vez de 7.

**`storage.average_waits` agrega no banco, e é exceção consciente à lição nº 3.** Agregar
não descarta linha nenhuma — a lição é sobre *cortar listas* antes de raciocinar sobre
elas. Aqui são ~70 mil linhas (7 dias × 35 atrações) que não fazem sentido arrastar do
Neon para calcular uma média.

> ⚠️ **Parque sem histórico não entra no cache** de popularidade (1h, por parque). Guardar
> o vazio prenderia o resultado justamente enquanto o coletor começa a preencher.
**Com a Fase 7 fechada, a fundação do roteiro do dia existe** (evolução 3 da seção 4): já
se sabe onde o visitante esteve, aonde ele quer chegar, que limites ele impõe e quais
atrações são as principais. Essa é a frente que mais diferencia tecnicamente — otimização
combinatória, parente do Caixeiro Viajante. **É o próximo passo natural do projeto.**

**Fase 8 — em investigação.** Desenho atual (seção 7, Fase 8): roteiro de **3–4 paradas
replanejadas a cada conclusão**, porque previsão de horas erra ~9–10 min por parada. O 8.2
é um *Orienteering Problem* com custo dependente do tempo, não TSP. **Situação em
27/10/2026:** o 8.0 (consertar a coleta) teve a causa corrigida; falta confirmar uma
semana de coleta contínua e então **repetir a avaliação forecast × perfil horário** para
escolher qual previsão o roteiro usa — preliminar na sexta 30/10, decisiva em 03/11, com o
fim de semana. ⚠️ O horário de verão americano acaba em 01/11: a próxima avaliação precisa
de fuso de verdade, não de UTC−4 fixo (`_comum.fuso_mk()` já resolve). O **8.1 (matriz
de caminhada) está pronto**, e o **núcleo do 8.2 também** (`core/itinerary.py`).

> ⚠️ **O roteiro ganha do guloso pela GEOGRAFIA, não pela previsão.** Backtest de
> 27/10/2026, 5 alvos: plano supondo filas paradas -4,1%; plano com perfil horário
> -2,7% (pior!); oráculo que conhece o futuro -7,6% (o teto). Por isso o padrão é a
> persistência. **Foi ensaio sobre histórico fragmentado (85% dos cenários
> descartados): repetir sobre a coleta contínua antes de construir a tela (8.4).**

**Fase 9 — Perfil do visitante (iniciada em 27/10/2026).** Nasceu de uma crítica do
Gabriel: *ver a fila não resolve nada que a fonte já não resolva*. Com filas niveladas, o
ranking vira "o mais perto". O app sabe o que a atração **custa**, não o que ela **vale**
para quem pergunta. Decisões dele: o perfil é **perguntado, não inferido**; **só duas
perguntas** (altura da criança mais baixa; tranquilas / de tudo / emoção), ambas
puláveis; a altura **marca** ("só os adultos", pelo *Rider Switch*), não esconde, e a
atração marcada não ganha o destaque de "melhor escolha". **9.1 (curadoria) pronta**;
faltam 9.2 (as perguntas, no `localStorage`) e 9.3 (o redesenho da tela, que começou pelo
design — ver o bloco "Onde paramos" no topo).

> ⚠️ **Nada no design pode imitar a marca Disney** (logotipo, personagens, orelhas,
> castelo, tipografia). Projeto independente; portfólio público não pode parecer oficial.

> ⚠️ **A curadoria nunca vem de memória nem de resumo de busca.** Os dois erraram: a
> memória e os sites de terceiros dizem 102 cm para a Big Thunder, a busca disse 102
> para a Magic Carpets. A listagem oficial diz 97 e "Any Height". Altura errada manda
> criança para fila em que ela não entra.

> ⚠️ **Não tente o endpoint interno da Disney** (`/finder/api/...`). Ele não responde a
> cliente automatizado — proteção contra robôs —, e disfarçar a requisição seria burlar
> um bloqueio. Para revisar a curadoria: capturas de tela da listagem pública. O site
> abre em português; a tradução das etiquetas está no próprio JSON (`como_preencher`).

> ⚠️ **Só linha conferida conta** (`conferido_em` + `conferido_por`), e **atração sem
> curadoria não tem intensidade** — nunca vire `CALM` por falta de etiqueta.
> `tests/test_curadoria.py` recusa linha com dado e sem conferência.

**As medições estão versionadas em `scripts/medicoes/`** (README com a agenda): auditoria
da coleta, avaliação do forecast, simulador do roteiro, sinuosidade contra o OSM e
desempenho do otimizador. Leem o banco de produção só por `_comum.consultar`, que recusa
qualquer comando que não seja leitura. O simulador chama o `plan_itinerary` de produção.
**Rodadas marcadas:** 30/10 (preliminar) e 03/11 (decisiva), com os comandos no README.

**A personalização mora no `localStorage`** (`web/preferencias.js`), sem conta de usuário: o
app é usado no celular dentro do parque por algumas horas, e exigir cadastro antes de
responder "para onde vou agora" mataria o produto. O arquivo tem uma base comum e dois
namespaces, `VISITADAS` e `ALVOS`.

> ⚠️ **As duas marcações têm regras OPOSTAS.** Visitadas valem por **dia** e carregam
> carimbo de data; alvos valem **até o visitante mudar de ideia**. Alvo é desejo, não
> acontecimento — uma lista de desejos que se apaga à meia-noite é um app que esquece.

> ⚠️ **"Já fui hoje" carimba a data DO PARQUE, não a do celular.** Quem está em Orlando às
> 23h ainda está no mesmo dia de visita. Sem o carimbo, o visitante voltaria na semana
> seguinte com metade das atrações escondidas e nenhuma pista do porquê.

> ⚠️ **Os alvos ficam em seção própria e NÃO reordenam o ranking.** São perguntas
> diferentes: o ranking diz o que compensa agora, a lista de alvos diz quando ir naquilo
> que o visitante veio fazer. Dar bônus de custo a um alvo distorceria o número em vez de
> assumir a mudança de critério.

> ⚠️ **O catálogo de alvos não se reordena enquanto está aberto.** As marcadas sobem ao
> topo só quando o painel é reaberto — reordenar sob o dedo faz quem está escolhendo
> várias perder o lugar. `alternarAlvo` de propósito **não** chama `desenharCatalogo`.

> ⚠️ **Todo acesso ao `localStorage` precisa de `try/catch`.** Em aba anônima ou com
> cookies bloqueados ele **lança**, não devolve vazio.

> ⚠️ **Não remova `[hidden] { display: none !important }` do CSS.** A regra do navegador
> para `[hidden]` perde para qualquer classe com `display`, e sete elementos da página
> dependem do atributo. Foi bug real, encontrado por teste.

**A previsão (6.6) foi medida e descartada.** `core/forecast.py` guarda os modelos e a
régua, e `tests/test_forecast.py` fixa a conclusão. Extrapolar tendência erra mais que
usar a fila atual: 3,97 contra 2,50 min em dez minutos, e a diferença cresce com o
horizonte. A causa é que a direção não persiste.

> ⚠️ **Não troque o modelo do ranking por previsão sem repetir o backtest.** A ideia já
> foi tentada e medida; os números estão no cabeçalho de `core/forecast.py`.

**O `forecast` da fonte agora é gravado** (tabela `queue_forecasts`), porque era o único
candidato que não dava para avaliar sem histórico dele. Guarda a **primeira** aparição de
cada previsão — sobrescrever destruiria a medida de antecedência, que é o que dá valor a
uma previsão.

**O forecast da fonte foi avaliado (27/10/2026) e também não entra no ranking.** No
horizonte de uma caminhada erra 9,52 min contra 2,03 da fila atual. Em horizontes de
**horas** a persistência desaba (~14 min) e o forecast e o nosso perfil horário empatam em
~9–10 min — sem vencedor estável entre os dois. Isso é matéria-prima do roteiro (Fase 8),
não do ranking. Tabela no cabeçalho de `core/forecast.py`.

**O histórico na API e na tela (6.4 e 6.5).** A rota de histórico é o primeiro endpoint
que serve **dado nosso**. O gráfico é SVG escrito à mão — sem biblioteca, coerente com a
decisão de não ter etapa de build.

> ⚠️ **A regra de falha se inverte entre as duas rotas.** Na recomendação, banco fora do
> ar é engolido e a resposta sai sem tendência. Na rota de histórico, banco fora do ar dá
> **503** — ali o histórico *é* a resposta, e série vazia mentiria dizendo que a fila
> ficou parada.

> ⚠️ **O eixo vertical do gráfico começa em zero**, e não no menor valor da série. Escala
> truncada exagera variação pequena e apaga magnitude; para fila, a altura da linha tem de
> *ser* a fila. Isso foi um bug real, percebido só ao olhar a captura de tela.

**A tendência (6.3).** `core/trends.py`, função pura. Os dois números do algoritmo vieram
de **medição sobre dados reais**, não de intuição: o limiar é 5 min porque 218 de 218
medições são múltiplos de 5, e a janela é de 30 min porque 118 de 189 variações
consecutivas eram zero — comparar com a medição anterior diria "estável" quase sempre.
Ela **não reordena** o ranking, só enriquece a justificativa.

> ⚠️ **O histórico nunca pode derrubar a recomendação.** `_tendencias()` em `routes.py`
> engole falha de banco de propósito: sem banco, com o Postgres fora do ar, ou antes da
> migração, o ranking sai igual — só sem a frase. `tests/test_api_tendencia.py` vigia os
> três cenários.

**O coletor (6.2).** Ligado por padrão (`NEXTUP_COLLECTOR_ENABLED`), a cada 5 min, só
Magic Kingdom. A suíte o desliga no `conftest.py`, e o CI também — bater na ThemeParks.wiki
a cada build seria má educação com uma API pública mantida por voluntários.

> ⚠️ **O Render hiberna após ~15 min sem acesso *de entrada*.** As requisições que o
> coletor faz para fora **não** contam como atividade. Com o serviço dormindo não há
> coleta, então o pinger externo é o que mantém o histórico contínuo.

> ⚠️ **A saúde da coleta se confere NO BANCO, nunca no painel do job.** Entre 22/09 e
> 27/10/2026 o coletor gravou 7–23 ciclos por dia, contra ~156 esperados (~10%), enquanto o
> `keep-alive.yml` exibia 100% de sucesso — ele não falhava, só não rodava. Antes de
> qualquer medição sobre o histórico, contar ciclos por hora **com o parque aberto**
> (`recorded_at` distintos por minuto): ~12 por hora é coleta contínua. Ciclo sem
> medição nova não deixa linha — a unicidade descarta a repetição —, então de
> madrugada o vazio é normal e não prova nada.

**O banco (Fase 6).** Produção é um **Postgres no Neon** — projeto
`mute-forest-48970873`, branch `production`, região `sa-east-1` — com a migração já
aplicada. O Postgres do Render foi descartado porque o plano gratuito expira, e SQLite
dentro do contêiner perderia tudo a cada push (disco efêmero).

A URL vem de `NEXTUP_DATABASE_URL`; o `config.py` **carrega o `.env` sozinho**
(`override=False`, então variável do ambiente vence o arquivo). O padrão sem configuração
é um SQLite na raiz. Migrações: `alembic upgrade head`.

**Cole a connection string do painel sem editar.** `normalize_database_url` põe o
`+asyncpg` e remove `sslmode`/`channel_binding`, que são da libpq e o `asyncpg` recusa; o
TLS é configurado pelo `connect_args_for`, com verificação completa de certificado.

> ⚠️ **A suíte tem uma trava no `conftest.py`** que força SQLite em memória antes de
> qualquer `import nextup`. Sem ela, com o `.env` carregado, um teste distraído
> escreveria no banco de produção. Não remova — `tests/test_trava_de_seguranca.py` vigia.

> ⚠️ **A CLI do Neon (`neon login`, `neon.ts`, `neon deploy`) não é usada aqui.** É um
> fluxo Node/TypeScript; o NextUp é Python e faz deploy pelo Render. Do Neon o projeto
> precisa só da connection string.

**Cinco lições dos dados reais, que valem para as próximas fases:**
1. `OPERATING` **não** garante tempo de fila — 9 das 35 atrações do Magic Kingdom
   estavam abertas sem fila medida. Use sempre `is_rankable`.
2. Validar **antes** de guardar no cache. O contrário já causou bug aqui.
3. **Peça tudo, corte na exibição.** O mesmo padrão já mordeu **quatro vezes**: três como
   contagem errada (`available` refletindo o `limit`), no CLI, na API e quase no frontend;
   e a quarta, em 20/09/2026, como uma **tela vazia** — marcar as 8 recomendações como
   visitadas esvaziava a lista, porque a tela pedia 8 e filtrava depois. O app chegava a
   anunciar "você já passou por todas as atrações" com 20 livres. Pedir a lista já cortada
   e depois raciocinar sobre ela dá errado de um jeito novo a cada vez.
4. **Todo instante vai para o banco em UTC, com fuso.** O Postgres guarda o fuso, o
   SQLite não — sem normalizar na entrada, o histórico fica deslocado em horas entre os
   dois ambientes e nenhum teste reclama.
5. **Medição duplicada não dá erro, só envenena a média.** Por isso a unicidade é
   `(attraction_id, observed_at)`, usando o `lastUpdated` da fonte e não a hora em que
   gravamos. O coletor roda num ritmo que escolhemos; a fonte atualiza no dela.
6. **As fixtures são todas do Magic Kingdom, e isso esconde bugs.** Lá 86 de 86 entidades
   têm coordenada; em outros parques não. Um bug que deixou o **Disneyland Paris
   inacessível desde a Fase 1** sobreviveu a 261 testes e só apareceu ao abrir o app e
   clicar. Ao mexer em parsing de catálogo, teste contra um parque que **não** seja o MK.

> ⚠️ **A fonte tem duas formas de dizer "não sei onde isto fica":** omitir `location` ou
> mandá-lo com `null` dentro. `ParkEntity` trata as duas como ausência — não reverta isso,
> `tests/test_models_coordenada_ausente.py` vigia. Uma atração sem GPS não pode derrubar
> o parque inteiro, pelo mesmo motivo do `EntityType._missing_`.

---

## Arquitetura — a regra que não se quebra

```
api  →  core  →  models  ←  clients
                       ↖
                        storage
```

A dependência é **unidirecional**:

- **`core/`** é o cérebro (distância, score, ranking) e **não importa nada de rede nem de
  banco**. Recebe objetos, devolve ordenação. Por isso seus testes rodam offline, em
  milissegundos. *Se você sentir vontade de importar `httpx` — ou `sqlalchemy` — dentro de
  `core/`, o desenho está errado.*
- **`clients/`** é o único lugar que sabe que a ThemeParks.wiki existe. Trocar de fonte de
  dados deve afetar só essa pasta.
- **`storage/`** é o único lugar que sabe que existe um banco. Irmã de `clients/`, e a
  diferença importa: `clients/` busca dado **de fora**, que não controlamos; `storage/`
  guarda dado **nosso**, acumulado ao longo do tempo.
- **`models/`** é o idioma comum. Depois que o JSON vira `Attraction`, ninguém mais precisa
  conhecer o formato original da API.
- **`api/`** só traduz HTTP em chamadas ao `core`. **Zero regra de negócio aqui.**

---

## Convenções

**Código**
- Docstrings e comentários em **português**; nomes de variáveis e funções em **inglês**.
- Comentário explica *por que*, não *o que*. O código já diz o que faz.
- Nada de número mágico espalhado: vai para `config.py`, com sobrescrita por variável de
  ambiente.
- Linha de até 100 caracteres (`ruff`, configurado no `pyproject.toml`).

**Testes**
- Testes de `core/` **nunca** tocam a rede.
- Um teste bom compara contra uma **verdade externa**, não repete a conta do código — se
  repetir, os dois erram juntos e o teste não detecta nada. Veja `tests/test_geo.py`:
  usa Paris–Londres, um grau de latitude e coordenadas reais do Magic Kingdom.
- Respostas reais da API ficam em `tests/fixtures/` e alimentam os mocks do `respx`.
- Teste que usa o banco chama o app pelo **`httpx.ASGITransport`**, nunca pelo
  `TestClient`: este roda o app em outro event loop, e o SQLAlchemy 2.1 recusa a conexão
  usada pelos dois. Só o `test_collector` usa `TestClient`, porque precisa do `lifespan`.

**Commits**
- Conventional Commits com descrição em português: `feat:`, `fix:`, `docs:`, `chore:`,
  `ci:`, `test:`, `refactor:`.
- **Commits pequenos e temáticos.** O histórico é avaliado por recrutador — ele conta a
  evolução do projeto.

**Documentação — obrigatório**
- Toda decisão técnica entra na tabela da **seção 10** de `docs/PROJETO.md`.
- Conclusão de fase atualiza a **seção 7** e o cabeçalho de status.
- **Ao final de cada sessão, registrar os prompts do Gabriel na íntegra em
  `docs/PROMPTS.md`** — sem corrigir digitação, com o contexto e o que resultou. É
  exigência explícita dele.

---

## Setup do ambiente

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Verificar que tudo está de pé:

```bash
pytest -m "not e2e"    # esperado: 722 testes, ~9s
ruff check .
ruff format --check .
```

Preparar o banco local (SQLite; cria o arquivo na primeira vez):

```bash
alembic upgrade head
```

Subir a aplicação inteira (API + interface):

```bash
uvicorn nextup.api.main:app --reload     # http://127.0.0.1:8000
```

Testes de interface (exigem `pip install -e ".[dev,e2e]"` e `playwright install chromium`):

```bash
pytest -m e2e          # esperado: 96 testes, ~130s
```

---

## Referência rápida da API

Base: `https://api.themeparks.wiki/v1` — sem autenticação.

| Endpoint | Retorna | Natureza | TTL de cache |
|---|---|---|---|
| `/destinations` | Destinos e seus parques | Estático | 24h |
| `/entity/{id}/children` | Catálogo: nomes, tipos, **coordenadas GPS** | Estático | 24h |
| `/entity/{id}/live` | Fila e status **agora** | Dinâmico | 60s |
| `/entity/{id}/schedule` | Horários do parque | Semi-estático | 24h |

Campos importantes do `/live`: `queue.STANDBY.waitTime` (minutos), `status`
(`OPERATING` / `CLOSED` / `DOWN` / `REFURBISHMENT`), `operatingHours`, `lastUpdated`.

Magic Kingdom (parque padrão do MVP): `75ea578a-adc8-4116-a54d-dccb60765ef9`.
Demais IDs na seção 3 de `docs/PROJETO.md`.

**Boa cidadania com a API:** ela é pública e gratuita. Sempre enviar o `User-Agent` do
projeto, usar cache agressivo e aplicar backoff exponencial nas tentativas. Nunca
martelar o endpoint em laço.

# NextUp — Assistente Inteligente de Filas em Parques

> Documento vivo. Nasceu em 11/09/2026 e é atualizado a cada decisão tomada.
> Registro de contexto, decisões e arquitetura. Se algo mudar, muda aqui primeiro.
>
> **Status atual: Fases 0 a 5 concluídas.** O projeto está no ar em
> <https://nextup-rcux.onrender.com>.
>
> **Fase 6 quase fechada** — passos 6.1 a 6.5 concluídos: o histórico é coletado,
> persistido, analisado, exposto pela API e desenhado na tela. Falta só o **6.6, previsão
> da fila na chegada**. 326 testes na suíte rápida, 38 de interface em navegador.

---

## 1. O Problema

Parques de grande porte — Walt Disney World, Disneyland, Universal, SeaWorld — concentram
a experiência do visitante em um punhado de atrações muito procuradas. O resultado é
previsível: o cliente paga caro por um ingresso e gasta boa parte do dia **parado numa
fila**, não vivendo a experiência mágica que comprou.

O tempo de espera é altamente volátil. Uma atração com 90 minutos às 11h pode estar com
15 minutos às 11h40, porque um show terminou do outro lado do parque e a multidão migrou.
Quem não acompanha esse movimento em tempo real toma decisões ruins o dia inteiro.

### A solução que já existe hoje (e é manual)

Surgiu um serviço informal, hoje vendido por consultores e guias de viagem:

1. Uma pessoa fica em casa, ou no hotel, monitorando um site de tempos de espera.
2. Ela acompanha onde o cliente está dentro do parque.
3. Por WhatsApp, avisa: *"corre pro Space Mountain agora, caiu pra 20 minutos"*.

Funciona. Mas é um humano executando, em tempo real, um algoritmo simples:
**cruzar tempo de fila com distância até o visitante e recomendar o melhor destino.**

### A tese do projeto

Esse trabalho é automatizável. Não é uma tarefa que exige julgamento humano — é uma
consulta a uma API, um cálculo de distância e uma ordenação. O que o consultor entrega é
latência de reação e disciplina de monitoramento, e software faz as duas coisas melhor,
24 horas por dia, para milhares de usuários ao mesmo tempo.

**Este projeto substitui esse serviço manual por um algoritmo.**

---

## 2. Objetivos

### Objetivo de produto
Entregar ao visitante, em tempo real, a resposta para uma única pergunta:
**"Para qual atração eu devo ir agora?"** — considerando fila atual, distância a
percorrer, status de operação e as preferências dele.

### Objetivo de carreira (igualmente importante)
Este é o **projeto principal de portfólio** do Gabriel — a peça central do LinkedIn e das
candidaturas na área. Isso impõe exigências que um projeto pessoal comum não teria:

- Código organizado em camadas, com responsabilidades separadas.
- Testes automatizados de verdade, não um `print` conferindo saída.
- CI/CD rodando a cada commit (GitHub Actions).
- Containerização (Docker) e deploy público acessível por link.
- README que um recrutador entende em 30 segundos, com screenshot ou GIF.
- Histórico de commits limpo, contando a evolução do projeto.
- Documentação de decisões técnicas — este próprio arquivo é parte da entrega.

> Um projeto que funciona impressiona pouco. Um projeto que funciona, é testado, roda em
> produção e tem as decisões documentadas é o que diferencia candidato júnior de pleno.

### Objetivo de aprendizado
Gabriel tem conhecimento intermediário em programação, mas **nunca trabalhou com APIs e
dados dessa forma**. Cada etapa é construída com explicação do *porquê*, não só do *como*.
Conceitos novos entram no glossário (seção 9).

---

## 3. Viabilidade — Veredito: VIÁVEL

Validado tecnicamente em 11/09/2026, com chamadas reais à API. Não é estimativa.

### Fonte de dados: ThemeParks.wiki

- **Base:** `https://api.themeparks.wiki/v1`
- **Autenticação:** nenhuma. Endpoints públicos, sem chave de API.
- **Custo:** gratuito.
- **Cobertura:** dezenas de destinos globais — Walt Disney World, Disneyland Resort,
  Universal, SeaWorld, parques europeus.

### Evidências coletadas

| Verificação | Resultado |
|---|---|
| `GET /destinations` | HTTP 200 — lista completa de destinos e parques |
| Magic Kingdom `/live` | 71 entidades, sendo **35 atrações** com fila |
| Campo de fila | `queue.STANDBY.waitTime`, em minutos |
| Status operacional | `OPERATING`, `CLOSED`, `DOWN`, `REFURBISHMENT` |
| Horários | `operatingHours` por atração, com fuso do parque |
| Frescor do dado | `lastUpdated` em ISO-8601 |
| **Coordenadas GPS** | **35 de 35 atrações** com `location.latitude` / `longitude` |

A última linha é a mais importante. **Sem coordenadas não existiria o "mais próximo de
você"** — o projeto viraria só mais uma lista de filas, que é o que já existe por aí.
Com elas, o diferencial do projeto está de pé.

### IDs de referência (Walt Disney World)

| Parque | ID |
|---|---|
| Magic Kingdom | `75ea578a-adc8-4116-a54d-dccb60765ef9` |
| EPCOT | `47f90d2c-e191-4239-a466-5892ef59a88b` |
| Hollywood Studios | `288747d1-8b4f-4a64-867e-ea7c9b27bad8` |
| Animal Kingdom | `1c84a229-8862-4648-9c71-378ddd2c7693` |
| Destino WDW (pai) | `e957da41-3552-4cf6-b636-5babc5cbc4e5` |

### Endpoints que vamos usar

| Endpoint | Serve para |
|---|---|
| `/destinations` | Descobrir destinos e seus parques |
| `/entity/{id}/children` | Catálogo do parque: atrações, **coordenadas**, tipos |
| `/entity/{id}/live` | Filas e status **em tempo real** |
| `/entity/{id}/schedule` | Horários de funcionamento do parque |

O `/children` é dado **estático** (muda raramente) e o `/live` é **dinâmico** (muda a cada
minuto). Essa distinção define toda a estratégia de cache — veja a seção 5.

### É factível para o nível do Gabriel?

Sim, e por um motivo estrutural: **a parte difícil já está resolvida pela API.** Coletar,
normalizar e manter dados de fila de dezenas de parques seria um projeto de meses. A
ThemeParks.wiki entrega isso pronto, em JSON limpo.

O que resta é exatamente o terreno de conhecimento intermediário:

- Consumir HTTP e tratar JSON → `httpx`
- Modelar os dados → `pydantic`
- Calcular distância geográfica → fórmula de Haversine, ~10 linhas
- Ordenar por um score → lógica de negócio pura, testável
- Expor via API → `FastAPI`

O que será **novo** para ele — e é justamente o valor de aprendizado — é o redor: cache
com TTL, tratamento de falha de rede, testes com mock de API, containerização, CI/CD e
deploy. São habilidades de engenharia, não de algoritmo, e são exatamente as que aparecem
nas descrições de vaga.

**Avaliação de risco: baixo.** O risco real não é técnico, é de escopo — querer entregar
tudo de uma vez. Mitigação: o roadmap em fases da seção 7.

---

## 4. O Algoritmo — O Coração do Projeto

Tudo que o projeto tem de original mora aqui. É a tradução em código do que o consultor
humano faz de cabeça.

### A pergunta errada e a pergunta certa

**Errada:** "qual atração tem a menor fila?" — pode ser uma atração a 900 metros, do outro
lado do parque. O visitante gasta 15 minutos andando para economizar 10.

**Certa:** "qual atração me custa menos tempo total até eu estar sentado no brinquedo?"

### Custo Total Estimado

```
custo_total = tempo_de_caminhada + tempo_de_fila_previsto
```

**Tempo de caminhada** — distância de Haversine entre o visitante e a atração, dividida
pela velocidade média a pé. Duas correções importantes:

- Velocidade em parque lotado é menor que a de rua: usar ~1,1 m/s, não 1,4 m/s.
- Linha reta subestima o trajeto real, porque ninguém atravessa um lago ou um prédio.
  Aplicar um **fator de sinuosidade** de ~1,3 sobre a distância.

**Tempo de fila previsto** — na primeira versão, o `waitTime` atual da API. Numa fase
posterior, o valor projetado para o momento em que o visitante *chegar lá* (Fase 6).

### Filtros eliminatórios

Descartados antes de qualquer cálculo:

- Atração com status diferente de `OPERATING`
- Atração fora do horário de funcionamento
- Atração fora dos filtros do usuário (altura mínima, intensidade, já visitada hoje)

### Ranking

Ordenar as sobreviventes por `custo_total` crescente e devolver o topo — com justificativa
legível: *"Big Thunder Mountain — 4 min de caminhada + 20 min de fila = 24 min. Caiu de 45
para 20 nos últimos 30 minutos."*

A justificativa não é enfeite. É o que torna a resposta confiável, do mesmo jeito que a
mensagem do consultor no WhatsApp explica o motivo.

### Evoluções previstas do algoritmo

1. **Tendência** — comparar a fila atual com a de 15/30 minutos atrás. Fila caindo vale
   mais que fila estável no mesmo patamar.
2. **Previsão na chegada** — estimar a fila no instante em que o visitante chega, não a de
   agora. Exige histórico.
3. **Roteiro do dia** — deixar de responder "próxima atração" e passar a montar a sequência
   ótima para o dia inteiro. É um problema de otimização combinatória, parente do Caixeiro
   Viajante. Território avançado e **excelente** material de portfólio.

---

## 5. Arquitetura e Stack

### Princípios

1. **Nunca chamar a API externa a cada requisição do usuário.** Cache com TTL curto para
   dado vivo (~60s) e TTL longo para catálogo (~24h). Isso protege a fonte, reduz latência
   e mantém o app de pé se a API cair.
2. **Lógica de negócio isolada de I/O.** O cálculo de score não sabe o que é HTTP nem o que
   é banco. Assim ele é testável sem rede — e teste que depende de internet é teste ruim.
3. **Camadas explícitas.** Cliente da API → normalização → regra de negócio → exposição.
   Cada camada com uma responsabilidade só.
4. **Falhar com elegância.** API externa fora do ar deve devolver o último dado conhecido,
   com aviso de idade — nunca um erro 500 na cara do usuário.

### Stack proposta

| Camada | Escolha | Por quê |
|---|---|---|
| Linguagem | Python 3.14 | Já instalado, e é o padrão da área de dados |
| HTTP | `httpx` | Suporte nativo a async, sucessor natural do `requests` |
| Validação | `pydantic v2` | Transforma JSON solto em objetos tipados e validados |
| API | `FastAPI` | Padrão de mercado atual, docs automáticas, async nativo |
| Testes | `pytest` + `respx` | `respx` simula a API externa; testes rodam offline |
| Qualidade | `ruff` | Lint e formatação num binário só, muito rápido |
| Container | Docker | Roda igual na sua máquina e no servidor |
| CI | GitHub Actions | Lint + testes a cada push, selo verde no repositório |
| Frontend | HTML + CSS + JS puro | Sem build, sem `node_modules`; usa a Geolocation API do navegador |
| Mapa | Leaflet | Leve, gratuito, sem chave de API — mostra você e as atrações |

**Por que frontend sem framework?** React ou Vue aqui adicionariam uma etapa de build,
dependências e complexidade de deploy sem melhorar o produto. A tela é uma lista ordenada
e um mapa. JavaScript moderno dá conta, e o recrutador consegue ler o código em dois
minutos. Se o projeto crescer a ponto de justificar um framework, migramos — e essa
migração vira, ela mesma, uma boa história técnica.

### Fluxo de uma requisição

```
Usuário (lat, lon, filtros)
        │
        ▼
   API FastAPI  ──▶  Cache  ──(expirado)──▶  ThemeParks.wiki
        │              │
        │         (válido)
        ▼              │
   Normalização ◀──────┘
        │
        ▼
   Motor de Ranking   ◀── Haversine + filtros + score
        │
        ▼
   Top N atrações, com justificativa
```

---

## 6. Estrutura de Pastas

> **Status: definida em 11/09/2026.** Escopo confirmado: API + web app, com perfil
> full-stack. Esta seção é o mapa do repositório para quem chega de fora — inclusive o
> recrutador — e precisa ser mantida em dia.
>
> Nome definido em 12/09/2026: **NextUp**, pacote Python `nextup`.

```
nextup/
│
├── .github/
│   └── workflows/
│       └── ci.yml              # Lint + testes a cada push
│
├── docs/
│   ├── PROJETO.md              # Este documento
│   └── PROMPTS.md              # Registro de prompts
│
├── src/
│   └── nextup/
│       ├── __init__.py
│       ├── config.py           # Constantes e configuração (TTLs, velocidade a pé)
│       │
│       ├── clients/            # CAMADA 1 — conversa com o mundo externo
│       │   ├── themeparks.py   # Cliente HTTP da ThemeParks.wiki
│       │   └── cache.py        # Cache com TTL
│       │
│       ├── models/             # CAMADA 2 — o formato dos nossos dados
│       │   ├── park.py         # Parque, destino
│       │   └── attraction.py   # Atração, fila, coordenada, status
│       │
│       ├── core/               # CAMADA 3 — regra de negócio (SEM rede, SEM I/O)
│       │   ├── geo.py          # Haversine, tempo de caminhada
│       │   ├── scoring.py      # Cálculo do custo total
│       │   └── recommender.py  # Filtros + ranking + justificativa
│       │
│       ├── api/                # CAMADA 4 — exposição HTTP
│       │   ├── main.py         # App FastAPI
│       │   ├── routes.py       # Endpoints
│       │   └── schemas.py      # Contratos de entrada e saída
│       │
│       └── cli.py              # Interface de linha de comando (útil nas Fases 1 e 2)
│
├── web/                        # Frontend — servido estaticamente pelo FastAPI
│   ├── index.html
│   ├── app.js                  # Geolocation + fetch na API + render
│   └── style.css
│
├── tests/
│   ├── conftest.py             # Configuração compartilhada dos testes
│   ├── fixtures/               # Respostas reais da API, salvas para os mocks
│   ├── test_geo.py
│   ├── test_scoring.py
│   ├── test_recommender.py
│   └── test_themeparks_client.py
│
├── .env.example                # Modelo de variáveis de ambiente
├── .gitattributes              # Normaliza quebras de linha Windows/Linux
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml              # Dependências e config do ruff/pytest
├── LICENSE
└── README.md                   # A vitrine — é o que o recrutador lê primeiro
```

### A lógica por trás dessa organização

O ponto central é a separação em **quatro camadas com dependência em sentido único**:

```
api  →  core  →  models  ←  clients
```

- `core/` é o cérebro e **não importa nada de rede**. Ele recebe objetos e devolve uma
  ordenação. Por isso seus testes rodam em milissegundos, sem internet, sem depender de o
  Magic Kingdom estar aberto.
- `clients/` é o único lugar que sabe que a ThemeParks.wiki existe. Se um dia trocarmos de
  fonte de dados, só essa pasta muda.
- `models/` é o idioma comum. Depois que o JSON vira um objeto `Attraction`, ninguém mais
  no sistema precisa saber o formato original da API.
- `api/` só traduz HTTP para chamadas ao `core`. Não contém regra de negócio.

**Isso não é burocracia.** É o que permite testar o algoritmo sem rede e trocar qualquer
peça sem quebrar as outras — e é exatamente o tipo de organização que um avaliador
técnico procura quando abre um repositório.

---

## 7. Roadmap

Cada fase entrega algo que **funciona e é demonstrável**. Nada de fase que só faz sentido
quando a próxima terminar.

### Fase 0 — Fundação ✅ *concluída em 12/09/2026*
Repositório Git, estrutura de pastas em 4 camadas, `pyproject.toml` com dependências e
configuração de `ruff`/`pytest`, `.gitignore`, `.gitattributes`, `.env.example`, licença
MIT, README e pipeline de CI.

Entregou também o primeiro módulo funcional, `core/geo.py`: Haversine, correção de
sinuosidade e conversão em minutos — **17 testes passando**, validados contra referências
externas conhecidas (Paris–Londres, um grau de latitude, pontos antipodais) e coordenadas
reais do Magic Kingdom.

Histórico em 5 commits, seguindo Conventional Commits.

> **Nota de ambiente:** o ambiente virtual **não** foi criado nesta etapa, por restrição da
> máquina corporativa onde o projeto nasceu. Consequência: `ruff` não rodou localmente — a
> validação de lint ficou por conta do CI.
>
> **Resultado do primeiro CI (12/09/2026): sucesso.** Lint, formatação e os 17 testes
> passaram em Python 3.11, 3.12 e 3.13, no commit `b33c3b6`.
>
> **Ambiente local criado (12/09/2026), na máquina pessoal.** Só havia Python 3.14
> instalado, versão que o CI ainda não testa — para não validar contra algo sem garantia,
> foi instalado Python 3.13 (`winget install Python.Python.3.13`) e a `.venv` foi criada
> com ele. `pytest`, `ruff check` e `ruff format --check` rodaram localmente pela primeira
> vez, com o mesmo resultado do CI. Fase 0 agora está concluída de ponta a ponta.

### Fase 1 — Cliente da API ✅ *concluída em 12/09/2026*
Módulo que conversa com a ThemeParks.wiki: busca parques, catálogo e dados ao vivo.
Modelos `pydantic`, cache com TTL, tratamento de timeout e erro. Testes com `respx`.
**Entrega:** script de linha de comando que imprime as filas de um parque, ordenadas.

Entregou, em quatro peças:
- `models/` — `Destination`, `ParkCatalog` (com as coordenadas GPS) e `LiveData`
- `clients/cache.py` — cache com TTL e relógio injetável
- `clients/themeparks.py` — cliente assíncrono com backoff exponencial e erros próprios
- `cli.py` — o comando `nextup`, que imprime as filas ordenadas

**93 testes novos**, nenhum tocando a internet: as respostas reais da API foram
capturadas em `tests/fixtures/` e o `respx` as devolve nos testes.

> **Duas descobertas dos dados reais**, que mudaram o desenho:
>
> 1. **Estar `OPERATING` não significa ter fila.** Das 35 atrações do Magic Kingdom,
>    9 estavam abertas sem tempo de espera — o Castelo da Cinderela não é brinquedo.
>    Daí a existência de `LiveData.is_rankable`, que exige as duas condições.
> 2. **Guardar no cache antes de validar é bug.** Um teste pegou: resposta malformada
>    ficava memorizada por 24h e toda chamada seguinte falhava sem nem tentar a rede.
>    Hoje o cache guarda o modelo já validado.

### Fase 2 — Motor de Recomendação ✅ *concluída em 12/09/2026*
Haversine, filtros eliminatórios, cálculo de custo total, ranking e justificativa. Lógica
pura, sem rede, com cobertura de testes alta.
**Entrega:** dada uma posição no parque, o programa responde para onde ir.

Entregou:
- `core/recommender.py` — `recommend()` e `Recommendation`, com `explain()` gerando a
  justificativa legível: *"Prince Charming Regal Carrousel — 2 min de caminhada +
  5 min de fila = 7 min"*
- `cli.py --lat/--lon` — o modo que responde para onde ir; sem as coordenadas, o
  comando mantém a listagem por fila da Fase 1
- `tests/test_arquitetura.py` — transforma a regra do `CLAUDE.md` em teste: o `core`
  não pode importar `httpx`, `asyncio` nem `clients`. Verificado com uma violação
  proposital, que o teste acusou.

**28 testes novos.** O mais importante do projeto é
`test_fila_menor_perde_para_atracao_mais_perto`: fila de 10 min a 900 m perde para
fila de 20 min a 50 m. Se algum dia alguém "simplificar" o algoritmo para ordenar só
por `waitTime`, é esse teste que vai acusar.

> **Fora do escopo desta fase**, por dependerem de dados que o MVP ainda não busca:
> filtro por horário de funcionamento (exige `/schedule`) e filtros do usuário
> (altura mínima, intensidade, já visitada).

### Fase 3 — API HTTP ✅ *concluída em 12/09/2026*
FastAPI expondo os endpoints, documentação automática em `/docs`, tratamento de erros e
CORS configurado.
**Entrega:** API navegável, respondendo recomendações por HTTP.

Três rotas, sob o prefixo `/api`:

| Rota | O que faz |
|---|---|
| `GET /api/health` | Diz se o serviço está de pé. Não consulta a fonte externa de propósito |
| `GET /api/destinations` | Destinos e parques, com os IDs usados nas demais rotas |
| `GET /api/parks/{id}/recommendations?lat=&lon=&limit=` | O ranking por caminhada + fila |

Decisões da camada:
- **Schemas separados dos modelos internos** (`api/schemas.py`): o contrato público não
  muda porque a ThemeParks.wiki renomeou um campo.
- **Um cliente por processo**, criado no `lifespan`. Um cliente por requisição faria o
  cache nascer vazio toda vez — o TTL de 24h só existe se o cache sobreviver.
- **Erros viram códigos HTTP** em um só lugar; nenhuma rota tem `try/except`.
  404 (não existe) · 502 (contrato mudou) · 503 (fonte fora do ar, com `Retry-After`).

**27 testes novos.** A suíte da API caiu de 22s para 4,4s ao parar de disparar o
`lifespan` nos testes que substituem a dependência — cada disparo montava um contexto
SSL de 0,7s sem necessidade.

> **O mesmo bug de contagem apareceu de novo aqui.** `available` devolvia o valor de
> `limit` em vez do total disponível, exatamente como no CLI. Pior: o primeiro teste que
> escrevi **afirmava o comportamento errado**, porque foi escrito olhando o que o código
> fazia em vez do que deveria fazer.

### Fase 4 — Interface Web ✅ *concluída em 12/09/2026*
Página que pega a localização pelo navegador (Geolocation API), consulta nossa API e
mostra o ranking com mapa Leaflet. Responsiva — vai ser usada no celular, dentro do
parque, andando. Estado de carregamento, tratamento de erro e recusa de GPS resolvidos.
**Entrega:** o produto funcionando de verdade, na tela.

Entregou `web/` (HTML + CSS + JS puro, sem build), servido pelo próprio FastAPI —
o app inteiro cabe num contêiner só. Seletor com os 198 parques da API, mapa Leaflet
com o visitante e as atrações, e a primeira colocada destacada.

**Tocar no mapa define a posição.** Resolve de uma vez os dois problemas previstos na
seção 8: quem nega o GPS continua usando o app, e quem está com GPS impreciso (comum
entre prédios) corrige na mão.

**21 testes de ponta a ponta**, em Chromium de verdade (`pytest -m e2e`), cobrindo o
que nenhum teste de API alcança:

| Verificado | Por que importa |
|---|---|
| O Leaflet carrega e desenha | Se falhasse, o mapa seria um retângulo vazio e nada acusaria |
| Negar o GPS não quebra o app | É o caminho mais provável de um usuário real |
| Clicar no mapa funciona sem GPS | A alternativa oferecida precisa realmente existir |
| 503 e 404 viram frase compreensível | O código HTTP não serve para o visitante ler |
| Nome com `<script>` não executa | Os nomes vêm de fonte externa — seria XSS |
| Sem rolagem horizontal a 390px | Sintoma clássico de layout quebrado no celular |

O CI ganhou um **segundo job** para eles, separado porque baixa um navegador e não faz
sentido repetir isso em três versões do Python. A suíte rápida continua em ~7s.

#### Refino visual — 13/09/2026

A primeira versão funcionava e era genérica. Direção escolhida entre três propostas:
**"personalidade de parque"** — paleta de pôr do sol (coral queimado, âmbar, roxo
profundo), fonte **Outfit**, cantos arredondados, ícones SVG e marcadores numerados.

O objetivo não foi enfeitar: foi não parecer mais um painel corporativo azul. Num
portfólio, ser lembrado conta.

Três problemas reais encontrados e corrigidos no caminho:

| Problema | Por que importava |
|---|---|
| Botão principal e etiqueta com **texto branco** no tema escuro | Os fundos quentes clareiam no escuro; branco por cima perdia o contraste. Resolvido com `--sobre-quente`, que inverte junto com o tema |
| Marcadores azuis genéricos e **todos iguais** | Oito alfinetes idênticos não deixavam ligar o mapa à lista. Viraram numerados, na paleta do app |
| O marcador **nº 1 ficava escondido** atrás de outro | Atrações vizinhas se sobrepõem no mapa; a resposta do app não pode ficar atrás de uma opção pior. Resolvido com `zIndexOffset` proporcional à colocação |

As três regras funcionais foram preservadas e continuam verificadas por teste: contraste
alto, alvos de toque grandes e nada de rolagem horizontal no celular.

### Fase 5 — Produção ✅ *concluída em 13/09/2026*

**No ar em <https://nextup-rcux.onrender.com>** — verificado em produção: interface
carregando, 198 parques no seletor, mapa com tiles, ranking com dados ao vivo e nenhum
erro de console.

Docker, CI no GitHub Actions, deploy público, README com GIF de demonstração.
**Entrega:** link que qualquer pessoa — ou recrutador — abre e usa.

Já entregue:
- `Dockerfile` em duas etapas, rodando como usuário sem privilégios, com `HEALTHCHECK`
  apontando para `/api/health`
- `docker-compose.yml` e `.dockerignore`
- `render.yaml` — configuração do deploy versionada junto do código
- README renovado: captura da interface real, instruções de Docker, tabela de rotas da
  API com exemplo de resposta
- **Job `imagem-docker` no CI** — constrói, sobe, espera ficar saudável, confere que a
  API e a interface respondem, que o processo não roda como root e que a imagem respeita
  a variável `PORT`

> **Docker não foi instalado na máquina do Gabriel.** A imagem é construída e testada
> pelo CI a cada push, o que na prática é uma garantia mais forte que "funcionou na minha
> máquina" — mas significa que ele não consegue depurar o contêiner localmente.

> **Armadilha evitada:** o `CMD` fixava a porta 8000. O Render — como quase toda
> plataforma — escolhe a porta e a informa por variável de ambiente (`PORT`, padrão
> 10000). O serviço subiria saudável e **nunca receberia uma requisição**. É o tipo de
> falha que só aparece depois do deploy; virou passo de CI.

**Publicado em 13/09/2026.** O Render leu o `render.yaml`, construiu a imagem e subiu o
serviço; todo push na `main` republica sozinho.

**Limitação e mitigação:** o plano gratuito hiberna após ~15 min sem acesso. O workflow
`keep-alive.yml` chama `/api/health` a cada 10 minutos para evitar isso — intervalo de 10
e não 14 porque o GitHub atrasa agendamentos, e a margem cobre o atraso.

Detalhes que valem lembrar: o ping usa `/api/health` de propósito, porque essa rota **não**
consulta a ThemeParks.wiki — acordar nosso serviço não pode virar tráfego numa API pública
de terceiros a cada 10 minutos. E o GitHub desativa agendamentos em repositórios públicos
parados há 60 dias, então o workflow para sozinho se o projeto ficar esse tempo sem
commits.

> As Fases 3 a 5 formam o MVP completo. É o ponto em que o projeto já pode ir para o
> LinkedIn.

### Fase 6.5 — Correções de UX e um bug de três fases ✅ *20/09/2026*

Rodada intercalada na Fase 6, a partir de ideias trazidas pelo Gabriel. Duas entregas de
produto e **um bug sério encontrado ao rodar o app de verdade** — não pelos testes.

#### O bug: o Disneyland Paris nunca funcionou

Ao trocar de parque na interface, o app respondeu **502**. A causa:

```
34 validation errors for ParkCatalog
children.11.location.latitude
  Input should be a valid number [input_value=None]
```

A ThemeParks.wiki tem **duas** formas de dizer que não sabe onde algo fica: omitir o campo
`location`, ou mandá-lo preenchido com `null` dentro. O projeto só entendia a primeira.

O estrago era desproporcional à causa. O `pydantic` valida a lista inteira de uma vez,
então **uma** atração sem GPS invalidava as outras oitenta e o parque inteiro sumia. O
NextUp respondia "a fonte respondeu em formato inesperado" — culpando a fonte por um
limite nosso.

> **Por que isso sobreviveu a seis fases e 261 testes:** todas as fixtures são do Magic
> Kingdom, onde 86 de 86 entidades têm coordenada. O bug era invisível para a suíte
> inteira e só aparecia em parques que ninguém testava — que são 197 dos 198 do seletor.
> Nenhum teste unitário o encontraria; **encontrá-lo exigiu abrir o app e clicar.**

A correção é a mesma degradação graciosa do `EntityType._missing_`: coordenada incompleta
vira ausência, a entidade continua no catálogo com nome e tipo, e só fica de fora do
ranking — onde de fato não haveria distância a calcular. Verificado depois: Disneyland
Paris responde 200, com 38 atrações e 29 filas.

#### Ver o parque antes de dar a localização

Até aqui, quem não liberasse o GPS via uma tela em branco. A rota nova
`GET /api/parks/{id}/attractions` responde *"como está o parque?"*, que é pergunta
legítima e não precisa saber onde o visitante está.

Ela devolve também `bounds`, o retângulo que contém as atrações — e é o que conserta um
comportamento que era quase um bug: escolher Disneyland Paris deixava o mapa parado na
Flórida, sem nenhuma pista de que o parque tinha mudado. Enquadrar é melhor que
centralizar, porque o zoom sai junto.

> **A armadilha da tela nova, percebida só ao olhar a captura.** A lista sem posição é
> ordenada pela menor fila — exatamente a pergunta que o projeto existe para contestar. No
> Disneyland Paris os primeiros colocados eram *playgrounds com fila zero*: verdadeiros e
> inúteis. Sem qualificação, seriam lidos como recomendação. O resumo agora diz, com
> todas as letras, que aquilo está ordenado pela menor fila e que isso raramente é a
> melhor escolha. A ressalva não é modéstia — é a tese do produto.

O modo da lista virou atributo no DOM (`data-modo="panorama"` / `"ranking"`), porque os
dois significados são diferentes demais para conviverem sem rótulo. Os testes E2E que
falharam ao introduzir o panorama falharam **por estarem certos**: procuravam `.item` e
encontravam o item errado.

#### Seletor de parques

Busca por nome, casando contra parque **e** destino — quem digita "disney" espera ver o
Magic Kingdom, embora a palavra não apareça no nome dele. E os destinos passaram a ser
ordenados por número de parques: alfabético punha "Aquatica" acima de "Walt Disney World
Resort", que é o oposto do que a maioria procura.

#### Radicalidade: descartada por falta de dado

O catálogo inteiro traz apenas `entityType, externalId, id, location, name, parentId,
slug`. Não há intensidade, altura mínima ou categoria. Filtrar por radicalidade exigiria
curar 35 atrações à mão — dado nosso, que não escala para 198 parques. Decisão do Gabriel:
trocar por **popularidade**, derivada da fila média histórica, que é dado real e já está
sendo coletado. Fica para quando houver histórico suficiente.

---

### Fase 6 — Inteligência Histórica *em andamento*
Persistir snapshots de fila ao longo do tempo. Com histórico vêm as análises que mais
valorizam o projeto: detecção de tendência, melhor horário por atração e previsão da fila
no momento em que o visitante chega.
**Entrega:** gráficos e previsão — o que eleva o projeto de "consome uma API" para
"produz conhecimento próprio a partir de dados".

**O que esta fase muda de fundamental:** até a Fase 5 o NextUp era *stateless* — consulta,
responde, esquece. Daqui em diante ele acumula história própria, o que exige duas coisas
novas: **estado persistente** e **um processo que roda sozinho**, gravando a fila mesmo
sem ninguém acessando o site.

E uma consequência de cronograma que decide a ordem de tudo: **previsão precisa de dados
que ainda não existem.** Não dá para construir o modelo e testá-lo no mesmo dia. Por isso
o coletor vem cedo — ele enche o banco enquanto o resto é construído.

| # | Entrega | Situação |
|---|---|---|
| 6.1 | `QueueSnapshot`, pasta `storage/`, SQLAlchemy, Alembic | ✅ 15/09/2026 |
| — | Banco de produção provisionado no Neon, migração aplicada | ✅ 15/09/2026 |
| 6.2 | Coletor periódico gravando o Magic Kingdom | ✅ 20/09/2026 |
| 6.3 | `core/trends.py` — tendência como função pura | ✅ 20/09/2026 |
| 6.4 | Rota `GET /api/.../history` | ✅ 20/09/2026 |
| 6.5 | Gráfico da fila na interface | ✅ 20/09/2026 |
| 6.6 | Previsão da fila **na chegada** | pendente |

O 6.3 torna verdadeira uma frase que a seção 4 deste documento promete desde o começo e
que o app ainda não cumpre: *"caiu de 45 para 20 nos últimos 30 minutos"*. E o 6.6 fecha a
tese do projeto — hoje o algoritmo soma a fila de **agora** a uma atração onde o visitante
só chega em 12 minutos, o que é uma aproximação, não a resposta certa.

#### 6.1 — Fundação do storage ✅ *concluída em 15/09/2026*

- `models/snapshot.py` — `QueueSnapshot`, Pydantic puro, com `from_live()`
- `storage/tables.py`, `engine.py`, `snapshots.py` — tabela, conexão e acesso
- `migrations/` — Alembic com template assíncrono e a primeira migração
- 28 testes novos, em SQLite na memória; a suíte rápida foi de 173 para **201**

Três armadilhas encontradas e fechadas no caminho:

1. **O SQLite não autoincrementa `BIGINT`.** Só `INTEGER PRIMARY KEY` vira *rowid*; com
   `BIGINT` a chave sai nula e a inserção falha. No Postgres funciona normalmente.
   Resolvido com `BigInteger().with_variant(Integer, "sqlite")` — a mesma classe de
   problema da porta fixa da Fase 5: some no ambiente onde se testa, aparece no outro.
2. **O SQLite não guarda fuso horário**, mesmo com a coluna declarada `timezone=True`.
   A data volta ingênua e o histórico ficaria deslocado em horas entre desenvolvimento e
   produção, sem erro nenhum. Resolvido normalizando tudo para UTC na entrada e
   reanexando o fuso na leitura.
3. **Medição duplicada não dá erro** — só envenena a média. O coletor roda num ritmo que
   escolhemos, a fonte atualiza num ritmo que não controlamos; quando o primeiro é mais
   rápido, a mesma medição chega de novo. A restrição de unicidade em
   `(attraction_id, observed_at)` faz o banco recusá-la, e o `ON CONFLICT DO NOTHING`
   impede que uma repetida derrube o lote inteiro.

> **Uma quarta armadilha, prevenida:** alterar `tables.py` e esquecer de gerar a migração
> passa em *todos* os testes locais — eles criam as tabelas a partir do próprio
> `tables.py` — e quebra só no deploy. `tests/test_migracoes.py` aplica as migrações num
> banco vazio e compara o resultado com o desenho declarado. Foi verificado que ele
> realmente falha quando os dois divergem; teste que nunca falha não protege nada.

#### Banco de produção — Neon ✅ *15/09/2026*

Projeto `mute-forest-48970873`, branch `production`, região `sa-east-1` (São Paulo — a
mais próxima, embora a latência importe pouco aqui: quem espera pelo banco é o coletor,
não o visitante). A migração está aplicada e a tabela existe, vazia.

**A quinta armadilha, encontrada na hora de conectar.** A connection string que o Neon
manda copiar termina em `?sslmode=require&channel_binding=require`. Esses são parâmetros
da **libpq**, a biblioteca C oficial do Postgres que o `psycopg` usa por baixo. O
`asyncpg` não é libpq — implementa o protocolo por conta própria e tem API própria para
TLS — então recusa os dois:

```
TypeError: connect() got an unexpected keyword argument 'sslmode'
```

A correção fácil seria editar a string à mão. É também a errada: editar à mão é o passo
que alguém esquece no dia do deploy. `normalize_database_url` remove os parâmetros, e
`ssl_is_required` preserva a **intenção** deles antes que sumam.

Essa separação é o ponto importante. O pior resultado possível não seria o erro acima —
erro alto se conserta. Seria o NextUp descartar o `sslmode` e conectar em **texto plano**,
funcionando perfeitamente enquanto a senha do banco viaja aberta pela rede.

E a solução ficou mais forte que o pedido original. Passar `ssl=verify-full` na URL não
serve: o `asyncpg` então exige um `~/.postgresql/root.crt` em cada máquina — funcionaria
aqui e quebraria no contêiner. O engine monta um `ssl.create_default_context()`, que já
vem com verificação de cadeia **e** de hostname, usando as autoridades certificadoras do
sistema. Verificado contra o Neon real, inclusive com um caso de controle: um contexto que
não confia em nenhuma CA precisa ser recusado, senão a verificação seria decorativa.

> **Uma armadilha criada e fechada na mesma sessão.** Fazer o `config.py` carregar o
> `.env` é conveniente — mas a partir daí a URL padrão numa máquina de desenvolvimento
> passou a apontar para o **banco de produção**. Bastaria um teste criar um engine sem URL
> explícita para apagar dados reais. O `conftest.py` sobrescreve a URL para SQLite em
> memória antes de qualquer `import nextup`, e `tests/test_trava_de_seguranca.py` existe
> para que remover essa trava quebre a suíte em vez de passar em silêncio.

#### 6.2 — O coletor ✅ *concluída em 20/09/2026*

`src/nextup/collector.py`, no mesmo nível do `cli.py`. A posição é deliberada: o coletor
*orquestra* — pede ao `clients/` e entrega ao `storage/`. Não é `core/`, porque não é
lógica pura; não é `api/`, porque não traduz HTTP.

Sobe como tarefa de fundo no `lifespan` do FastAPI e **compartilha o cliente com as
rotas**, de propósito: os dois passam a dividir o mesmo cache, e uma coleta que caia
dentro dos 60 segundos do `/live` reaproveita o que uma visita ao site acabou de buscar.

Verificado contra a API ao vivo e o Neon real: 35 atrações lidas, 35 gravadas, e a segunda
coleta imediata gravou **zero** — a defesa contra duplicata funcionando em produção, não
só em teste. Das 35, sete estavam abertas sem fila medida, confirmando de novo a primeira
lição do projeto.

**Quatro decisões que um processo de fundo erra com frequência**, e que aqui estão
resolvidas explicitamente:

1. **A primeira coleta acontece antes da primeira espera.** Parece detalhe e não é: o
   Render hiberna, e o serviço só acorda quando chega uma requisição. Esperar o intervalo
   antes de agir faria cada despertar render menos dado — num dia de pouco acesso, quase
   nenhum.
2. **Nenhuma falha derruba o laço.** A fonte é de terceiros e gratuita; vai cair algum
   dia. Um coletor que morre na primeira falha só é descoberto semanas depois, quando
   alguém repara no buraco do gráfico.
3. **O cancelamento atravessa intacto.** `CancelledError` herda de `BaseException`
   justamente para não ser pega por um `except Exception` distraído — mas o `except`
   explícito documenta a intenção. Engolir o cancelamento faria o servidor travar ao
   desligar.
4. **Só atrações entram no histórico.** O `/live` devolve o parque inteiro, shows e
   restaurantes junto. Guardar o Castelo da Cinderela — sempre aberto, nunca com fila —
   seriam dezenas de milhares de linhas idênticas. O tipo vem do catálogo, que tem cache
   de 24h: o filtro custa uma requisição por dia, não uma por coleta.

**A armadilha que pegou quem a escreveu.** O primeiro teste do laço procurou os snapshots
numa janela ao redor do relógio de teste e não achou nada. Motivo: `observed_at` vem do
`lastUpdated` da fonte — e as fixtures foram capturadas em 12/09, não no dia do teste. É a
distinção entre as duas datas se provando real logo na primeira vez que importou. Virou o
teste `test_o_instante_gravado_e_o_da_fonte`.

**Migrações passaram a ser aplicadas no deploy.** O `CMD` do contêiner agora roda
`alembic upgrade head && exec uvicorn ...`. O `&&` importa: migração que falha impede o
servidor de subir, o que é falhar alto — e muito melhor que subir consultando uma coluna
que ainda não existe. Isso exigiu copiar `migrations/` e `alembic.ini` para a imagem (o
Alembic lê os scripts do disco, não do pacote instalado) e dar ao usuário sem privilégios
a posse de `/app`, senão o SQLite padrão do CI não poderia ser criado.

> **Duas coisas que não valem para o CI.** O coletor sobe **desligado** lá
> (`NEXTUP_COLLECTOR_ENABLED=false`): verificar a imagem não justifica gerar tráfego numa
> API pública mantida por voluntários a cada build. E dois passos novos conferem que a
> migração rodou de fato — sem eles, alguém poderia remover `migrations/` da imagem e nada
> quebraria, porque o servidor subiria igual.

**Um risco investigado e descartado: `asyncpg` + pooler.** A URL do Neon aponta para um
host terminado em `-pooler`, que é o PgBouncer deles. Existe uma incompatibilidade
clássica aí: o `asyncpg` cria *prepared statements* com nomes fixos
(`__asyncpg_stmt_N__`), e um pooler em modo transação pode entregar a mesma conexão do
servidor a clientes diferentes, fazendo os nomes colidirem.

O que torna essa falha perigosa é ela **não aparecer numa chamada isolada** — só sob
reuso de conexão. Um teste ingênuo passa e a produção quebra semanas depois, de forma
intermitente. Por isso a verificação forçou o cenário: 60 queries parametrizadas em
rodadas concorrentes, com `dispose()` do pool no meio para provocar o reaproveitamento.
Nenhuma colisão. O PgBouncer passou a suportar prepared statements em modo transação, e o
comportamento observado confirma.

> Se algum dia aparecer `prepared statement "__asyncpg_stmt_N__" already exists` nos logs,
> a cura é uma linha em `connect_args_for`: `statement_cache_size=0`. Não está lá hoje
> porque não há problema para corrigir, e configuração preventiva sem evidência é código
> que ninguém sabe por que existe.

#### 6.3 — Tendência ✅ *concluída em 20/09/2026*

A frase que a seção 4 deste documento promete desde 11/09/2026 finalmente existe:

> Swiss Family Treehouse — 3 min de caminhada + 5 min de fila = 8 min.
> **Caiu de 45 para 20 nos últimos 30 min.**

`core/trends.py` é lógica pura — entra lista de `QueueSnapshot`, sai uma direção. Não
conhece banco nem rede, e o `test_arquitetura.py` garante que continue assim.

**Os dois números do algoritmo saíram de medição, não de intuição.** Sobre os 228
snapshots reais já coletados:

| Achado | Consequência no desenho |
|---|---|
| **218 de 218** medições são múltiplos de 5 | O limiar é 5 — o menor passo que a fonte reporta |
| **118 de 189** variações consecutivas são **zero** | A janela é de 30 min, não "a medição anterior" |

A segunda descoberta é a que decidiu tudo. A intuição mandaria comparar a medição atual
com a anterior — e isso devolveria "estável" em quase dois terços dos casos, inclusive
sobre uma fila que caiu de 60 para 20 ao longo da manhã. A comparação é contra o **início
da janela**.

O primeiro achado desmonta a tentação oposta: filtrar variações de ±5 como ruído. Elas são
**53 das 71** variações não-nulas — três de cada quatro movimentos reais. Descartá-las
faria a tendência viver dizendo que nada muda.

**A tendência não reordena o ranking.** Uma fila caindo rápido ainda pode custar mais
tempo total que uma parada ao lado; deixar a tendência mandar seria trocar a tese do
projeto por uma heurística, sem ninguém decidir isso. Ela enriquece a justificativa e
para por aí.

**Degradação graciosa, verificada.** O ranking existe desde a Fase 2 e não podia passar a
depender do banco. Sem banco configurado, com o Postgres fora do ar, ou antes de a
migração rodar, a recomendação sai igual — só sem a frase. Três testes cobrem exatamente
esses três cenários.

Na tela, a tendência ganha seta e cor. A cor **não carrega a informação sozinha**: a seta
aponta e o texto diz por extenso, então quem não distingue verde de vermelho lê a mesma
coisa. E "estável" não aparece — ocupar uma linha para dizer que nada mudou é ruído numa
tela usada de pé, no meio do parque.

> **Onde isso ainda é fraco:** com poucas horas de histórico, apenas 2 das 8 atrações
> exibidas têm tendência calculável. Não é defeito do algoritmo — é o banco enchendo. A
> cobertura melhora sozinha a cada dia de coleta, e é exatamente por isso que o coletor
> veio antes.

#### 6.4 e 6.5 — Histórico exposto e desenhado ✅ *concluídas em 20/09/2026*

`GET /api/parks/{id}/attractions/{id}/history?hours=6` é o **primeiro endpoint do NextUp
que serve dado nosso**. Todos os outros são a ThemeParks.wiki reempacotada; este só existe
porque o coletor rodou — e é exatamente o que o objetivo da Fase 6 promete: sair de
"consome uma API" para "produz conhecimento próprio".

Devolve a série de pontos, um resumo (mín, média, máx, atual, amplitude) e a tendência
recalculada sobre a janela pedida — quem pede 24h quer o movimento do dia, não o do último
quarto de hora.

**Uma regra se inverte aqui.** Na recomendação, o histórico é enfeite e a falha do banco é
engolida de propósito: melhor um ranking sem a frase "caiu de 45 para 20" do que erro
nenhum. Nesta rota o histórico **é** a resposta, então banco fora do ar devolve 503.
Servir uma série vazia seria pior que falhar — diria que a fila ficou parada.

O nome da atração vem do catálogo em cache, e não do banco: guardá-lo em cada snapshot
seriam centenas de milhares de cópias da mesma string.

**O gráfico é SVG escrito à mão**, sem biblioteca. Não é teimosia: uma biblioteca de
gráficos custa 50–200 KB para desenhar uma linha e alguns eixos, num projeto cuja decisão
registrada é não ter etapa de build. As coordenadas são calculadas num sistema de 0–100 e
o `viewBox` cuida do resto.

> **O erro de visualização que só apareceu ao olhar a captura de tela.** A primeira versão
> escalava o eixo vertical do **menor** ao maior valor da série — o padrão de muitas
> bibliotecas. O resultado: a linha de uma atração cuja fila foi de 10 a 5 minutos ficava
> colada no fundo, e uma oscilação de cinco minutos desenhava a mesma queda dramática que
> um desabamento de 90 para 5.
>
> Escala truncada **exagera variação pequena e apaga magnitude**. Para fila, que é um dado
> de grandeza, o eixo tem de começar em zero: assim a altura da linha *é* a fila.
> Inclinação responde "está melhorando?", altura responde "está grande?", e as duas
> perguntas convivem sem uma mentir sobre a outra.

Detalhes de acessibilidade que valem registro: o `<svg>` leva `aria-label` com uma frase
que descreve a curva, porque um gráfico sem rótulo é **invisível** para leitor de tela — e
aqui não há alternativa textual em lugar nenhum, já que os números do resumo não contam a
forma da linha. E o gatilho é um `<button>` de verdade, que já vem com foco pelo teclado e
acionamento por Enter e Espaço; refazer isso num `<div>` clicável dá errado em silêncio.

**Limitação conhecida, herdada do plano gratuito:** o Render hiberna após ~15 min sem
acesso **de entrada**, e requisições que o coletor faz para fora não contam como
atividade. Com o serviço dormindo, não há coleta. O `keep-alive.yml`, que existia para o
link de portfólio não abrir em tela branca, passou a ser o que mantém o histórico contínuo
— uma responsabilidade bem maior que a original. Se o GitHub desativar o agendamento por
inatividade do repositório, o histórico ganha buracos silenciosos.

---

## 8. Riscos e Limitações

| Risco | Impacto | Mitigação |
|---|---|---|
| API externa fora do ar ou instável | Alto | Cache persistente + degradação graciosa com aviso de idade do dado |
| Mudança de contrato da API | Médio | Camada de normalização isolada; `pydantic` falha alto e cedo |
| Uso abusivo derrubar nosso acesso | Médio | Cache agressivo, backoff exponencial, `User-Agent` identificando o projeto |
| GPS impreciso dentro do parque | Médio | Permitir escolha manual da área onde o visitante está |
| Cobertura de dados varia por parque | Baixo | Focar em Walt Disney World no MVP, onde a cobertura foi verificada |
| Escopo crescer sem controle | **Alto** | Roadmap em fases; nada da Fase N+1 antes da Fase N estar pronta |

### Aspectos legais e éticos
- Dados públicos, consumidos por API pública, sem burlar autenticação ou bloqueio.
- Projeto sem vínculo com a The Walt Disney Company. Aviso explícito no README.
- Crédito à ThemeParks.wiki como fonte, no README e na interface.
- Se o projeto for monetizado no futuro, revisar os termos de uso da fonte antes.

---

## 9. Glossário

Conceitos novos, registrados conforme aparecem no projeto.

| Termo | O que é |
|---|---|
| **API REST** | Um serviço que responde a URLs devolvendo dados (JSON) em vez de páginas |
| **Endpoint** | Uma URL específica da API, com uma função própria (`/live`, `/children`) |
| **JSON** | Formato de texto para dados estruturados; vira dicionário em Python |
| **Cache** | Guardar uma resposta para reusar, evitando pedir de novo a mesma coisa |
| **TTL** | *Time To Live* — prazo de validade do cache antes de buscar de novo |
| **Haversine** | Fórmula que dá a distância entre dois pontos GPS sobre a esfera terrestre |
| **Mock** | Resposta falsa da API usada em teste, para o teste não depender de internet |
| **CI/CD** | Automação que testa (e publica) o código a cada commit |
| **Pydantic** | Biblioteca que valida JSON e transforma em objetos Python tipados |
| **Async** | Modelo em que o programa faz outra coisa enquanto espera a rede responder |
| **ISO-8601** | Padrão de data/hora: `2026-09-11T22:30:25Z` |
| **Lint** | Ferramenta que lê o código e aponta erros e desvios de estilo sem executá-lo |
| **Fixture** | Dado de apoio para teste — aqui, respostas reais da API salvas em arquivo |
| **Conventional Commits** | Padrão de mensagem de commit: `feat:`, `fix:`, `docs:`, `chore:`, `ci:` |
| **src layout** | Código dentro de `src/`, separado dos testes; evita importar o pacote errado |
| **Ambiente virtual (venv)** | Pasta isolada com as dependências de um projeto, sem afetar o Python do sistema |
| **Validação** | Conferir, na entrada, se o dado tem a forma esperada — e recusar logo se não tiver |
| **Modelo (schema)** | Classe que descreve a forma de um dado: quais campos existem e de que tipo são |
| **Envelope** | Camada externa da resposta da API — `{"destinations": [...]}` em vez da lista solta |
| **UUID** | Identificador único de 36 caracteres, como `75ea578a-adc8-...`; não se repete no mundo |
| **Slug** | Apelido legível e sem espaços de um recurso: `waltdisneyworldresort` |
| **Imutável (frozen)** | Objeto que não pode ser alterado depois de criado; para mudar, cria-se outro |
| **Enum** | Lista fechada de valores possíveis, como `ATTRACTION`/`SHOW`/`RESTAURANT` |
| **Alias** | Apelido de campo: a API manda `entityType`, nosso código lê `entity_type` |
| **camelCase / snake_case** | Convenções de nome: `waitTime` (padrão da API) vs. `wait_time` (padrão do Python) |
| **Degradação graciosa** | Perder uma parte do resultado em vez de falhar inteiro quando um dado vem ruim |
| **Propriedade (`@property`)** | Método que se lê como se fosse um campo: `item.is_rankable`, sem parênteses |
| **Fila standby** | A fila comum, de quem não pagou para furar (no Disney, o oposto do Lightning Lane) |
| **Índice (dicionário)** | Estrutura que acha um item pela chave de uma vez, em vez de varrer a lista toda |
| **Fake (dublê)** | Substituto simples de uma dependência real no teste — aqui, um relógio controlado |
| **Injeção de dependência** | Receber de fora o que se usa (o relógio), em vez de criar por dentro; é o que torna o código testável |
| **Relógio monotônico** | Contador que só anda para a frente, imune a acerto de hora e horário de verão |
| **Cache hit / miss** | *Hit*: achou no cache e não precisou pedir à API. *Miss*: não achou, vai ter que buscar |
| **Backoff exponencial** | Esperar cada vez mais entre as retentativas (0,5s → 1s → 2s), para dar folga a um servidor em dificuldade |
| **HTTP 4xx vs 5xx** | 4xx é erro de quem pede (não adianta repetir); 5xx é erro do servidor (costuma passar) |
| **Gerenciador de contexto** | O bloco `with` / `async with`: garante que o recurso seja fechado mesmo se der erro no meio |
| **Interceptar rede (respx)** | Fingir ser a API dentro do teste, para provocar falhas impossíveis de causar de propósito na API real |
| **CORS** | Permissão que o servidor dá para uma página de outro endereço poder ler sua resposta |
| **OpenAPI / Swagger** | Descrição da API em formato padrão; é o que gera a página `/docs` sozinha |
| **Middleware** | Camada que envolve toda requisição, antes e depois da rota — aqui, o CORS |
| **Lifespan** | Código que roda ao ligar e ao desligar a aplicação; monta e desmonta recursos |
| **HTTP 422** | "Entendi seu pedido, mas os dados estão inválidos" — latitude 91, por exemplo |
| **DTO / schema de saída** | Objeto que define o que a API devolve, separado do modelo interno |
| **Geolocation API** | Recurso do navegador que informa a posição do usuário, só com permissão dele |
| **XSS** | Falha em que texto de terceiros vira código executável na página de quem abre |
| **Teste E2E** | Teste que usa o app como um usuário usaria — navegador real, clique real |
| **Esqueleto (skeleton)** | Bloco cinza que ocupa o lugar do conteúdo enquanto ele carrega |
| **Responsivo** | Layout que se adapta ao tamanho da tela, do celular ao desktop |
| **Viewport** | Área visível da página; a `meta` que a declara evita o celular fingir ser desktop |
| **Imagem / contêiner** | A *imagem* é a receita congelada; o *contêiner* é uma execução dela, descartável |
| **Build em etapas** | Construir numa imagem e copiar só o resultado para outra, deixando as ferramentas para trás |
| **Healthcheck** | Comando que o orquestrador roda para saber se o contêiner está vivo e são |
| **Blueprint (render.yaml)** | Configuração de deploy escrita em arquivo e versionada, em vez de cliques num painel |
| **Serverless** | Modelo em que a função acorda por requisição e some depois — sem memória entre chamadas |
| **Hibernação (cold start)** | Serviço gratuito que dorme sem uso; a primeira visita paga a espera de subir |
| **Stateless / stateful** | Sem ou com memória entre execuções. O NextUp era o primeiro; com o histórico virou o segundo |
| **Disco efêmero** | Sistema de arquivos recriado a cada deploy — o que for gravado nele some sozinho |
| **ORM** | Biblioteca que traduz linhas de tabela em objetos da linguagem, e vice-versa |
| **SQLAlchemy Core vs. ORM** | *Core* descreve tabelas e monta SQL; *ORM* mapeia classes para linhas. O NextUp usa só o Core |
| **Migração (migration)** | Script versionado que transforma o banco de uma forma para outra, sem perder o que já está lá |
| **Alembic** | Ferramenta de migrações do SQLAlchemy; guarda no próprio banco em que versão ele está |
| **Autogenerate** | Comparação entre o desenho declarado e o banco real, que escreve a migração da diferença. Sugere, não decide |
| **Schema drift** | Código e banco discordarem sobre a forma da tabela; passa em todo teste local e quebra no deploy |
| **Restrição de unicidade** | Regra do banco que recusa duas linhas com a mesma combinação de colunas |
| **ON CONFLICT DO NOTHING** | "Se essa linha já existe, siga em frente" — em vez de abortar a transação inteira |
| **Índice** | Estrutura que evita varrer a tabela toda para achar poucas linhas; o custo é ocupar espaço e deixar a escrita um pouco mais lenta |
| **Transação** | Bloco de comandos que vale inteiro ou não vale nada; impede gravar metade de uma coleta |
| **Pool de conexões** | Conjunto de conexões abertas e reaproveitadas, porque abrir uma custa caro |
| **Driver** | Biblioteca que fala o protocolo de um banco específico (`asyncpg` para Postgres, `aiosqlite` para SQLite) |
| **UTC** | Hora de referência mundial, sem fuso nem horário de verão; o único formato seguro para guardar instante |
| **Datetime ingênuo (naive)** | Data sem fuso horário — parece funcionar até dois ambientes a interpretarem diferente |
| **TIMESTAMPTZ** | Tipo do Postgres que guarda o instante junto com o fuso; o SQLite não tem equivalente |
| **Retenção** | Por quanto tempo se guarda um dado antes de apagar; decisão de produto, não de faxina |
| **Lote (batch)** | Enviar muitas linhas num comando só, em vez de uma ida ao banco por linha |
| **libpq** | A biblioteca C oficial do Postgres. O `psycopg` a usa; o `asyncpg` não — daí os parâmetros incompatíveis |
| **Connection string** | A URL que contém tudo para conectar: usuário, senha, host, banco e opções. **Contém segredo** |
| **TLS / SSL** | Cifra a conexão. Cifrar não é o mesmo que verificar com quem se está falando |
| **`sslmode=require` vs. `verify-full`** | `require` só cifra; `verify-full` confere a cadeia do certificado e o hostname, e é o que barra um intermediário |
| **Autoridade certificadora (CA)** | Quem assina certificados; o sistema já confia num conjunto delas, e é contra esse conjunto que se valida |
| **Pooler** | Intermediário que reaproveita conexões do banco; o `-pooler` no host do Neon indica que se está falando com ele |
| **Variável de ambiente** | Configuração que vem de fora do código, o jeito padrão de entregar segredo a uma aplicação |
| **`.env`** | Arquivo local com as variáveis de ambiente do projeto. **Nunca vai para o git** |
| **Tarefa de fundo** | Trabalho que roda em paralelo ao servidor, sem ninguém ter pedido por requisição |
| **`asyncio.Task`** | Uma corrotina posta para rodar sozinha; dá para cancelar e esperar terminar |
| **Cancelamento** | Pedido para uma tarefa parar. Só tem efeito no próximo ponto em que ela espera por algo |
| **`CancelledError`** | O aviso de cancelamento. Herda de `BaseException` de propósito, para não ser pega por engano |
| **`BaseException` vs. `Exception`** | Quase todo erro é `Exception`; o que não deve ser pego por acidente fica fora dela |
| **Idempotência** | Repetir a operação não muda o resultado — é o que a unicidade dá ao coletor |
| **Entrypoint / `CMD`** | O comando que o contêiner roda ao subir; onde encadear migração e servidor |
| **`sync: false`** | No Render, declara que a variável existe mas o valor vem do painel — jeito de declarar segredo |
| **PgBouncer** | O pooler mais comum do Postgres; é o que responde no host terminado em `-pooler` |
| **Prepared statement** | Consulta enviada uma vez e reutilizada com parâmetros diferentes; mais rápida, mas fica presa à conexão |
| **Modo transação (pooler)** | O pooler devolve a conexão ao fim de cada transação, então clientes diferentes dividem a mesma conexão do servidor |
| **Janela deslizante** | Olhar só para os últimos N minutos, descartando o que é velho demais para dizer algo sobre agora |
| **Limiar (threshold)** | A variação mínima para algo contar como mudança, em vez de ruído |
| **Série temporal** | Sequência de medições do mesmo valor ao longo do tempo — é o que o histórico de filas é |
| **Degradação graciosa** | Perder um enfeite quando uma dependência cai, em vez de perder a resposta inteira |
| **Acessibilidade de cor** | Não deixar a cor ser o único portador da informação; ~8% dos homens não distinguem verde de vermelho |
| **SVG** | Desenho descrito por coordenadas, não por pixels; escala sem borrar e herda a cor do texto |
| **`viewBox`** | O sistema de coordenadas interno do SVG; permite desenhar em 0–100 e exibir em qualquer tamanho |
| **Escala truncada** | Eixo que não começa em zero. Exagera variações pequenas — erro clássico de gráfico |
| **`aria-label`** | Rótulo que só o leitor de tela lê; é a única versão acessível de um gráfico |
| **`aria-expanded`** | Diz ao leitor de tela se o botão abriu ou fechou algo, em vez de deixá-lo adivinhar |
| **Delegação de evento** | Um ouvinte no elemento pai em vez de um por filho; sobrevive à lista ser redesenhada |
| **Amplitude (spread)** | Pico menos vale. Mede se vale a pena escolher a hora de ir |

---

## 10. Registro de Decisões

| Data | Decisão | Motivo |
|---|---|---|
| 11/09/2026 | ThemeParks.wiki como fonte de dados | Pública, gratuita, sem chave, com GPS das atrações |
| 11/09/2026 | Walt Disney World como escopo do MVP | Cobertura verificada: 35/35 atrações com coordenadas |
| 11/09/2026 | Custo total = caminhada + fila, não só fila | É o que o consultor humano realmente faz |
| 11/09/2026 | MVP = API FastAPI + web app | Recrutador testa pelo link em segundos; mostra backend e frontend |
| 11/09/2026 | Posicionamento full-stack | Alvo de vaga escolhido: backend sólido + interface bem feita |
| 11/09/2026 | Frontend sem framework (HTML/CSS/JS + Leaflet) | Sem etapa de build; a tela é lista + mapa, não justifica React |
| 11/09/2026 | Arquitetura em 4 camadas, dependência unidirecional | Permite testar o algoritmo sem rede e trocar a fonte de dados sem quebrar o resto |
| 12/09/2026 | Nome do projeto: **NextUp** | Curto, memorável, em inglês e diz o que o app faz: *o próximo* |
| 12/09/2026 | Sem venv na máquina corporativa | Restrição de ambiente; será criado ao clonar na máquina pessoal |
| 12/09/2026 | Commits pequenos e temáticos (Conventional Commits) | Histórico legível conta a evolução do projeto — critério de avaliação de portfólio |
| 12/09/2026 | `geo.py` sem dependências externas | Mantém o `core` testável offline e permitiu validar a lógica sem instalar nada |
| 12/09/2026 | `.venv` local em Python 3.13, não no 3.14 já instalado | 3.14 não é testado pelo CI; usar a mesma versão mais alta do CI evita "passa aqui, falha lá" |
| 12/09/2026 | Modelar só os campos que o projeto usa | `pydantic` ignora o resto; a API pode crescer sem quebrar o NextUp |
| 12/09/2026 | Tipo e status desconhecidos viram `UNKNOWN`, não erro | Um valor novo na API não pode derrubar o catálogo inteiro de um parque |
| 12/09/2026 | Cache guarda o modelo validado, não o JSON cru | Resposta malformada ficaria memorizada por 24h; bug encontrado por teste |
| 12/09/2026 | Retentativa só em 5xx e falha de rede | 404 e 4xx não se consertam sozinhos; insistir gasta requisição de uma API gratuita |
| 12/09/2026 | `User-Agent` e timeout por requisição, não na conexão | Continuam valendo quando a Fase 3 injetar uma conexão compartilhada |
| 12/09/2026 | Relógio e `sleep` injetáveis | Testar tempo sem esperar: suíte roda em segundos e não fica instável |
| 12/09/2026 | Regra de arquitetura virou teste automatizado | Regra que só vive na documentação se perde na terceira pressa |
| 12/09/2026 | `Recommendation` guarda as parcelas, não só o total | Sem elas não há justificativa — e é a justificativa que faz o usuário confiar |
| 12/09/2026 | Posição do visitante é opcional no CLI | Sem GPS ainda dá para ver as filas; com GPS vem a recomendação de verdade |
| 12/09/2026 | O CLI pede o ranking completo e corta na exibição | Caso contrário a contagem exibida seria a do `--limit`, não a de atrações disponíveis |
| 12/09/2026 | Schemas da API separados dos modelos internos | O contrato público não pode mudar porque a fonte externa renomeou um campo |
| 12/09/2026 | Um `ThemeParksClient` por processo, criado no `lifespan` | Um por requisição faria o cache nascer vazio toda vez, anulando o TTL |
| 12/09/2026 | Erros do projeto viram códigos HTTP num só lugar | Nenhuma rota precisa de `try/except`; o código diz de quem é o problema e se vale repetir |
| 12/09/2026 | `/health` não consulta a ThemeParks.wiki | Instabilidade da fonte faria o orquestrador reiniciar um contêiner saudável |
| 12/09/2026 | `Annotated` em vez de `Depends` no valor padrão | Forma recomendada hoje pelo FastAPI, e evita o alerta B008 do `ruff` |
| 12/09/2026 | Frontend servido pelo próprio FastAPI | Um contêiner só, um deploy só; a tela é estática e não justifica um segundo servidor |
| 12/09/2026 | Tocar no mapa define a posição | Resolve recusa de GPS e imprecisão de GPS com o mesmo gesto |
| 12/09/2026 | Playwright num job separado do CI | Baixa um navegador; repetir isso em 3 versões do Python seria desperdício |
| 12/09/2026 | E2E interceptam a API dentro do navegador | Teste de tela não pode depender da ThemeParks.wiki estar no ar |
| 12/09/2026 | Escapar nomes vindos da API antes de inserir no HTML | Nome com `<script>` viraria XSS no navegador de quem abrisse a página |
| 12/09/2026 | Actions atualizadas para `@v7` | As `@v4`/`@v5` usavam Node 20, marcado como descontinuado pelo GitHub |
| 13/09/2026 | Imagem Docker validada pelo CI, não localmente | Docker Desktop não instalado; build verificado a cada push é garantia mais forte que "funciona aqui" |
| 13/09/2026 | Build em duas etapas | O compilador não viaja para o servidor: imagem menor e menos superfície de ataque |
| 13/09/2026 | Contêiner roda como usuário sem privilégios | Root é o padrão do Docker e é má ideia: quem escapar da aplicação já entra com o usuário mais poderoso |
| 13/09/2026 | O código não é copiado para a imagem final | Já vem instalado dentro do venv; copiar de novo seria peso morto |
| 13/09/2026 | `CMD` respeita `${PORT:-8000}` com `exec` | Plataformas escolhem a porta; o `exec` mantém o uvicorn como processo principal para receber o sinal de desligamento |
| 13/09/2026 | **Netlify descartado** como plataforma | Não roda Python nem servidor de longa duração — e sem processo persistente o cache de 24h nasceria vazio a cada requisição |
| 13/09/2026 | Render como plataforma de deploy | Plano gratuito sem cartão, lê o Dockerfile do repositório; hibernação de ~50s é o preço aceito |
| 13/09/2026 | Configuração do deploy em `render.yaml` | Versionada junto do código, em vez de existir só como cliques num painel |
| 13/09/2026 | Ping a cada 10 min para evitar a hibernação | Link de portfólio não pode abrir em tela branca por um minuto; decisão consciente do Gabriel, ciente de que contorna o limite do plano gratuito |
| 13/09/2026 | O ping usa `/api/health`, não a rota de recomendação | Acordar o nosso serviço não pode gerar tráfego na API pública de terceiros a cada 10 minutos |
| 13/09/2026 | Identidade visual "personalidade de parque" | Painel azul corporativo não é lembrado; num portfólio, ser lembrado conta |
| 13/09/2026 | Tinta sobre fundos quentes é variável (`--sobre-quente`) | No tema escuro o coral e o âmbar clareiam, e texto branco por cima perderia o contraste |
| 13/09/2026 | Ícones em SVG, não emoji | Emoji muda de desenho conforme o sistema, não herda a cor do texto e desalinha com a linha de base |
| 13/09/2026 | Marcadores numerados, com o 1º na frente | Permite ligar mapa e lista; e a resposta do app não pode ficar escondida atrás de uma opção pior |
| 15/09/2026 | **Postgres gerenciado externo** para o histórico | O disco do plano gratuito do Render é efêmero: um SQLite no contêiner perderia tudo no próximo push — e todo push republica |
| 15/09/2026 | Postgres do Render descartado | O plano gratuito dele tem prazo de expiração; é o mesmo risco de perder o histórico, só adiado |
| 15/09/2026 | SQLite no desenvolvimento, Postgres na produção | Quem clona o repositório roda a suíte sem instalar banco nenhum, e os testes continuam em milissegundos |
| 15/09/2026 | `storage/` como pasta irmã de `clients/` | `clients/` busca dado de fora, que não controlamos; `storage/` guarda dado nosso. Quebram por motivos diferentes |
| 15/09/2026 | `core/` proibido de importar `sqlalchemy` | Mesma regra do `httpx`: se o algoritmo consultar o banco, seus testes passam a exigir um banco de pé |
| 15/09/2026 | Tabelas em SQLAlchemy Core, sem ORM declarativo | O idioma comum já são os modelos Pydantic; um segundo conjunto de classes de domínio criaria duas verdades sobre o que é um snapshot |
| 15/09/2026 | **Duas datas por snapshot** (`observed_at` e `recorded_at`) | Uma é quando a fonte mediu, a outra quando gravamos. Só a primeira identifica a medição |
| 15/09/2026 | Unicidade em `(attraction_id, observed_at)` + `ON CONFLICT DO NOTHING` | Coletar mais rápido que a fonte atualiza duplicaria medições e enviesaria a média histórica **sem dar erro** |
| 15/09/2026 | Snapshot de atração fechada é guardado, com fila nula | "Esteve fechada às 14h" é história; descartar criaria buracos que pareceriam falha do coletor |
| 15/09/2026 | Todo instante normalizado para UTC na entrada | O Postgres guarda fuso, o SQLite não. Sem normalizar, o histórico ficaria deslocado em horas entre os dois ambientes |
| 15/09/2026 | Alembic desde a primeira tabela | `create_all` só cria o que falta; migrar um banco que já tem dados exige o passo a passo versionado |
| 15/09/2026 | `alembic.ini` com `sqlalchemy.url` vazia | O arquivo é versionado num repositório público; senha de produção no histórico do git não sai mais de lá |
| 15/09/2026 | Teste compara o banco migrado com `tables.py` | Esquecer de gerar a migração passa em todo teste local e só quebra no deploy |
| 15/09/2026 | Driver assíncrono obrigatório (`+asyncpg` / `+aiosqlite`) | Um driver síncrono travaria o event loop do FastAPI a cada gravação do coletor |
| 15/09/2026 | Retenção de 90 dias configurável | ~6 mil linhas por dia por parque; guardar para sempre um dado que ninguém consulta é conta crescendo |
| 15/09/2026 | **Neon** como provedor do Postgres | Free tier sem prazo de expiração, região `sa-east-1`; projeto `mute-forest-48970873`, branch `production` |
| 15/09/2026 | `sslmode` e `channel_binding` removidos da URL | São parâmetros da libpq; o `asyncpg` tem API própria de TLS e recusa os dois. Permite colar a string do painel sem editar |
| 15/09/2026 | TLS por `SSLContext` do Python, não por `ssl=verify-full` na URL | O `asyncpg` exigiria um `~/.postgresql/root.crt` em cada máquina — funcionaria aqui e quebraria no contêiner |
| 15/09/2026 | A verificação de certificado é **completa**, não só cifra | `require` cifra mas não confere com quem se está falando; o contexto padrão valida cadeia e hostname |
| 15/09/2026 | `config.py` carrega o `.env` com `override=False` | Evita exportar variável na mão a cada comando, e variável do ambiente continua vencendo o arquivo em produção |
| 15/09/2026 | Trava no `conftest.py` forçando SQLite na suíte | Com o `.env` carregado, a URL padrão passou a apontar para produção — um teste distraído apagaria dados reais |
| 15/09/2026 | CLI do Neon e `neon.ts` **descartados** | Fluxo Node/TypeScript; o NextUp é Python e faz deploy pelo Render. Do Neon o projeto só precisa da connection string |
| 20/09/2026 | Coletor em `collector.py`, nível do `cli.py` | Ele orquestra `clients/` + `storage/`; não é lógica pura nem tradução de HTTP |
| 20/09/2026 | Coletor como tarefa de fundo do FastAPI | Mais simples que agendador externo, e o `keep-alive` já mantém o serviço acordado. Cron do Render é plano pago |
| 20/09/2026 | Coletor **compartilha o cliente** com as rotas | Os dois dividem o cache: coleta dentro dos 60s reaproveita o que uma visita ao site buscou |
| 20/09/2026 | Coletor **ligado por padrão** | Desligado pareceria seguro, mas troca falha barulhenta por silenciosa — histórico não coletado não se recupera |
| 20/09/2026 | Intervalo de 5 minutos | Acompanha o ritmo da fonte; mais rápido traria a mesma medição, que a unicidade recusaria |
| 20/09/2026 | Primeira coleta antes da primeira espera | O Render hiberna; esperar o intervalo faria cada despertar render menos dado |
| 20/09/2026 | Só atrações entram no histórico | Shows e restaurantes nunca têm fila; guardá-los seriam dezenas de milhares de linhas idênticas |
| 20/09/2026 | `attraction_ids()` ignora a coordenada | Coordenada é requisito para *ranquear*, não para *ter histórico* — e passado descartado não volta |
| 20/09/2026 | Migrações aplicadas no `CMD` do contêiner | Passo manual antes de cada deploy é passo que alguém esquece; com `&&`, migração ruim impede o servidor de subir |
| 20/09/2026 | Coletor **desligado** no CI | Verificar a imagem não justifica gerar tráfego numa API pública a cada build |
| 20/09/2026 | `NEXTUP_DATABASE_URL` com `sync: false` no `render.yaml` | Declara que a variável existe sem pôr a senha num repositório público |
| 20/09/2026 | Conectar pelo endpoint **`-pooler`** do Neon | Verificado que a colisão clássica entre `asyncpg` e PgBouncer não ocorre; o pooler aguenta mais conexões que o endpoint direto |
| 20/09/2026 | **`location` com nulos vira "sem coordenada"** | Uma atração sem GPS derrubava o catálogo inteiro; o Disneyland Paris estava inacessível desde a Fase 1 |
| 20/09/2026 | Rota `/parks/{id}/attractions`, sem exigir posição | "Como está o parque?" e "para onde eu vou?" são perguntas diferentes, e só a segunda precisa de GPS |
| 20/09/2026 | `bounds` na resposta, e `fitBounds` no mapa | Centralizar exigiria adivinhar o zoom; o certo para o Magic Kingdom é errado para um parque maior |
| 20/09/2026 | O modo da lista vai no DOM (`data-modo`) | "Menores filas" e "o que compensa mais" são coisas diferentes; confundi-las é o erro que o projeto combate |
| 20/09/2026 | O panorama **diz** que ordena pela menor fila | Sem a ressalva, os primeiros colocados seriam playgrounds com fila zero, lidos como recomendação |
| 20/09/2026 | Busca no seletor de parques | Com 198 parques, digitar "magic" é mais curto que rolar até o M |
| 20/09/2026 | Destinos ordenados por número de parques | Alfabético punha "Aquatica" acima de "Walt Disney World"; o porte é o melhor sinal que a API dá sem inventar dado |
| 20/09/2026 | Radicalidade **descartada**; popularidade em seu lugar | O catálogo não traz intensidade nem altura mínima. Fila média histórica é dado real que já coletamos |
| 20/09/2026 | Tendência compara com o **início da janela**, não com a medição anterior | 118 de 189 variações consecutivas medidas eram zero; comparar consecutivas diria "estável" sobre uma queda de dois terços |
| 20/09/2026 | Limiar de tendência = **5 minutos** | 218 de 218 medições são múltiplos de 5; exigir mais descartaria 3 de cada 4 movimentos reais |
| 20/09/2026 | A tendência **não reordena** o ranking | Fila caindo rápido ainda pode custar mais tempo total; reordenar trocaria a tese do projeto por uma heurística |
| 20/09/2026 | `UNKNOWN` não vira campo na API — vira ausência | Contrato público não deve ter estado que significa "não sei"; quem consome checa se o campo existe |
| 20/09/2026 | Histórico indisponível **nunca** derruba a recomendação | O ranking existe desde a Fase 2 e não pode passar a depender do banco estar de pé |
| 20/09/2026 | O engine do banco nasce sempre, não junto com o coletor | Amarrar os dois faria a tendência sumir sempre que alguém desligasse a coleta |
| 20/09/2026 | `park_history()` em vez de um `history()` por atração | 35 idas ao banco para montar uma resposta; num Postgres remoto, cada ida custa a latência inteira |
| 20/09/2026 | "Estável" não aparece na tela | Ocupar uma linha para dizer que nada mudou é ruído num app usado de pé |
| 20/09/2026 | A cor da tendência não carrega a informação sozinha | Seta e texto dizem o mesmo; quem não distingue verde de vermelho lê igual |
| 20/09/2026 | Banco fora do ar dá **503** na rota de histórico | Aqui o histórico *é* a resposta; série vazia mentiria dizendo que a fila ficou parada |
| 20/09/2026 | Teto de 168h na janela de histórico | Sem limite, `?hours=99999` pediria a tabela inteira e montaria um JSON de megabytes |
| 20/09/2026 | Nome da atração vem do catálogo, não do banco | Guardá-lo em cada snapshot seriam centenas de milhares de cópias da mesma string |
| 20/09/2026 | **Gráfico em SVG à mão**, sem biblioteca | 50–200 KB para desenhar uma linha, num projeto sem etapa de build |
| 20/09/2026 | Eixo vertical do gráfico **começa em zero** | Escala truncada exagera variação pequena e apaga magnitude; para fila, altura da linha tem de ser a fila |
| 20/09/2026 | O `<svg>` leva `aria-label` descrevendo a curva | Gráfico sem rótulo é invisível para leitor de tela, e os números do resumo não contam a forma |
| 20/09/2026 | O gatilho do gráfico é um `<button>`, não um `<div>` | Foco por teclado e acionamento por Enter/Espaço vêm de graça; refazer num div falha em silêncio |

---

*Mantido por Gabriel de Angelis, com Claude Code. Última atualização: 15/09/2026.*

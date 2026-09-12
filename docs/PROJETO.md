# NextUp — Assistente Inteligente de Filas em Parques

> Documento vivo. Nasceu em 11/09/2026 e é atualizado a cada decisão tomada.
> Registro de contexto, decisões e arquitetura. Se algo mudar, muda aqui primeiro.
>
> **Status atual: Fase 0 concluída** (12/09/2026). Próximo passo: Fase 1 — cliente da API.

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

### Fase 1 — Cliente da API
Módulo que conversa com a ThemeParks.wiki: busca parques, catálogo e dados ao vivo.
Modelos `pydantic`, cache com TTL, tratamento de timeout e erro. Testes com `respx`.
**Entrega:** script de linha de comando que imprime as filas de um parque, ordenadas.

### Fase 2 — Motor de Recomendação
Haversine, filtros eliminatórios, cálculo de custo total, ranking e justificativa. Lógica
pura, sem rede, com cobertura de testes alta.
**Entrega:** dada uma posição no parque, o programa responde para onde ir.

### Fase 3 — API HTTP
FastAPI expondo os endpoints, documentação automática em `/docs`, tratamento de erros e
CORS configurado.
**Entrega:** API navegável, respondendo recomendações por HTTP.

### Fase 4 — Interface Web
Página que pega a localização pelo navegador (Geolocation API), consulta nossa API e
mostra o ranking com mapa Leaflet. Responsiva — vai ser usada no celular, dentro do
parque, andando. Estado de carregamento, tratamento de erro e recusa de GPS resolvidos.
**Entrega:** o produto funcionando de verdade, na tela.

### Fase 5 — Produção
Docker, CI no GitHub Actions, deploy público, README com GIF de demonstração.
**Entrega:** link que qualquer pessoa — ou recrutador — abre e usa.

> As Fases 3 a 5 formam o MVP completo. É o ponto em que o projeto já pode ir para o
> LinkedIn.

### Fase 6 — Inteligência Histórica
Persistir snapshots de fila ao longo do tempo. Com histórico vêm as análises que mais
valorizam o projeto: detecção de tendência, melhor horário por atração e previsão da fila
no momento em que o visitante chega.
**Entrega:** gráficos e previsão — o que eleva o projeto de "consome uma API" para
"produz conhecimento próprio a partir de dados".

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

---

*Mantido por Gabriel de Angelis, com Claude Code. Última atualização: 11/09/2026.*

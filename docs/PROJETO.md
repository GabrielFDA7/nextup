# NextUp — Assistente Inteligente de Filas em Parques

> Documento vivo. Nasceu em 11/09/2026 e é atualizado a cada decisão tomada.
> Registro de contexto, decisões e arquitetura. Se algo mudar, muda aqui primeiro.
>
> **Status atual: Fases 0 a 5 concluídas.** O projeto está no ar em
> <https://nextup-rcux.onrender.com>.
>
> **Fase 6 concluída (20/09/2026).** O histórico é coletado, persistido, analisado,
> exposto pela API e desenhado na tela. O passo 6.6 terminou com um **resultado negativo
> medido**: prever a fila por extrapolação erra mais que usar a fila atual, então o
> ranking não mudou — mas agora sabemos por quê, com número.
>
> **Fase 7 — Personalização concluída (21/09/2026).** Nasceu das ideias do Gabriel, não
> do roadmap original: "já fui hoje" (7.1), brinquedos alvo (7.2), filtros de fila e
> caminhada (7.3) e popularidade (7.4). A última fecha o ciclo da Fase 6 — é a primeira
> feature construída **sobre o histórico que nós mesmos coletamos**, e não sobre a API.
>
> **Todas as seis fases do roadmap original estão entregues**, mais a Fase 7. **876
> testes**: 722 na suíte rápida (272 do roteiro, a maioria instâncias aleatórias
> conferidas contra força bruta) e 154 de interface em navegador.
>
> **Fase 9 — Perfil do visitante: iniciada (27/10/2026).** Nasceu de uma crítica do
> Gabriel: ver a fila não resolve nada que a fonte já não resolva. O app passa a saber
> **quem pode entrar** e **quão intensa** é cada atração, com uma curadoria conferida na
> listagem oficial da Disney (9.1). Faltam as perguntas do perfil e o redesenho da tela,
> que começou pelo design (prompt em `docs/design/`). A primeira versão será focada no
> Magic Kingdom.
>
> **Fase 8 — Roteiro do dia: em investigação (27/10/2026).** A auditoria da coleta (8.0)
> descobriu o coletor parado ~90% do tempo por um mês — o cron do GitHub rodava a cada
> ~4 h, não a cada 10 min, e sempre verde. Corrigido com pinger externo. A avaliação do
> forecast da fonte, agendada para 27/09, foi feita: ele **não** entra no ranking (erra
> 9,52 min contra 2,03 da fila atual no horizonte de uma caminhada), mas em horizontes de
> horas empata com o nosso perfil horário e ambos batem a persistência — a matéria-prima do
> roteiro. A **matriz de caminhada (8.1)** está pronta, com o fator 1,3 medido contra o
> OpenStreetMap. O **núcleo do otimizador (8.2)** também: um backtest mostrou que planejar
> ganha do guloso em ~4%, e que o ganho vem da geografia, não da previsão.

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

### Quem mais resolve isso — levantamento de 29/10/2026

O projeto nasceu olhando para o consultor de WhatsApp, e por sete semanas tratou
`caminhada + fila` como "o diferencial". Um levantamento feito depois, a partir de uma
pergunta do Gabriel sobre o app **Lines**, mostrou que a ideia não é inédita. O
levantamento veio de lojas de apps, blogs e fóruns — **nenhum dos apps foi testado à
mão ainda**, e boa parte das fontes é marketing do próprio fornecedor.

| Grupo | Exemplos | O que faz | Frente ao NextUp |
|---|---|---|---|
| **Oficial** | My Disney Experience + Disney Genie | Roteiro do dia a partir de interesses, atualizado ao longo do dia; pontua por distância a pé e **espalha os visitantes** entre as recomendações; filas previstas; **rota a pé** ("Get Directions", desde 2016) | O mais forte, e gratuito. Tem dado que nunca teremos (reservas, ingressos, posição de todos). Exige conta e ingresso vinculado; críticas de travamento e confusão. ⚠️ *A confirmar:* se o roteiro do Genie sobreviveu à troca do Genie+ pelo Lightning Lane, em 2024 |
| **Planejadores** | Lines (TouringPlans) | Roteiros com botão "Optimize" que replaneja durante o dia, controle de "caminhar × esperar", previsão própria | Já pesa caminhada contra fila há mais de dez anos. Em inglês, parte por assinatura |
| **Só filas** | Wait Times for Disney World, Wait Times for Disney Parks, MouseWait, LineTime, Undercover Tourist | Lista de esperas, às vezes com tempos enviados pelos usuários | Categoria lotada. É onde o NextUp estaria se parasse no ranking — a crítica que originou a Fase 9 |
| **No Brasil** | consultores e agências por WhatsApp | O serviço manual da seção anterior | **Nenhum app em português** com essa proposta foi encontrado |

**O que muda na forma de apresentar o projeto.** `custo_total = caminhada + fila`
continua sendo a decisão de produto mais importante — sem ela o NextUp seria mais uma
lista de filas —, mas não é o que o separa de tudo o que existe. Também não é verdade
que "ninguém mais tem mapa e rota": o app oficial tem. O que sustenta o projeto diante
dos concorrentes é:

1. **Para o visitante brasileiro, em português** — o espaço sem concorrente direto.
2. **Resposta imediata, sem conta nem ingresso vinculado.** "Para onde vou agora?" ao
   abrir, em vez de um plano a montar.
3. **O mapa como parte da resposta**, com rota pelas trilhas reais — diferença de
   execução, não de existência.
4. **O perfil do visitante** (altura e intensidade) com curadoria conferida na fonte
   oficial.
5. **Decisões medidas e publicadas**, inclusive as negativas. Nenhum dos concorrentes
   diz quanto erra.

A praticidade e a beleza da tela parecem vantagens reais, mas por enquanto foram
avaliadas só por quem construiu o app. Viram argumento quando visitantes de fora
disserem o mesmo.

**Limitação conhecida, aprendida com o Genie:** se muita gente seguisse a mesma
recomendação ao mesmo tempo, o NextUp criaria a fila que mandou evitar. O Genie espalha
os visitantes porque vê todos eles; o NextUp, sem conta e sem servidor de estado, não
vê. Irrelevante com poucos usuários, real com muitos.

### Se um dia for cobrar — estudo de 29/10/2026 (não é decisão)

**Recomendação: validar antes de monetizar.** Cobrar exige usuários, e para o objetivo
de carreira "150 usuários reais e três consultores interessados" vale mais que um botão
de pagamento.

| Caminho | Como seria | Avaliação |
|---|---|---|
| **B2B — consultores e agências** | Mensalidade para o consultor oferecer o app aos clientes dele, com a marca dele | **O preferido.** É o público que já cobra por esse serviço; poucos clientes, valor maior, venda por conversa. O app segue gratuito e sem conta para o visitante. Valida-se com cinco conversas, antes de qualquer código |
| Passe por viagem (B2C) | Pagamento único por viagem (~R$ 20–40), via Pix; ranking grátis, roteiro e perfil completo pagos | Assinatura mensal não combina com 4–10 dias de uso por ano. O atrito é cobrar de quem está no parque, com pressa |
| Afiliados | Comissão sobre ingresso, seguro, chip, aluguel de carro | Essas compras acontecem **antes** da viagem; o app é usado **durante**. Só complementar |
| Anúncios | — | Descartado: volume pequeno, retorno quase nulo, e estraga uma tela que é ponto forte |

**Antes de cobrar qualquer coisa:**

1. **Termos de uso comercial da ThemeParks.wiki** — o risco mais sério, porque o projeto
   inteiro depende dela. O código do backend é MIT, mas isso não cobre o uso comercial
   da API hospedada, e os termos não foram encontrados. Confirmar no site, no GitHub ou
   com o mantenedor.
2. **Marca Disney.** Apps comerciais independentes existem (o Lines é um); a regra de
   não imitar nada da marca passa a ser também jurídica.
3. **Infraestrutura sem hibernação e formalização** (CNPJ — MEI deve bastar no começo —,
   termos de uso, LGPD).

**Custo de sair do plano gratuito** (pesquisado em 29/10/2026, quase tudo em fontes
secundárias — conferir nas páginas oficiais antes de contratar):

| Item | Opção | Custo aproximado |
|---|---|---|
| Hospedagem sem hibernação | Render Starter (512 MB, nada muda no deploy) | US$ 7/mês |
| | Fly.io (máquina compartilhada, 256 MB, cobrança por segundo) | ~US$ 2–3/mês |
| | VPS gerenciado por nós (Hetzner, DigitalOcean) | ~US$ 4–5/mês |
| Banco | Neon, plano gratuito — já usado, não muda | US$ 0 |
| Domínio | `.com.br` no Registro.br | R$ 40/ano |

Domínio próprio **não exige sair do Render**: o plano gratuito já aceita domínio
personalizado. São duas decisões independentes.

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

> **Revisto em 29/10/2026:** "o que já existe por aí" era mais do que listas de filas.
> Planejadores e o app oficial da Disney já pesam caminhada contra fila — ver
> "Quem mais resolve isso", na seção 1.

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
sendo coletado. **Entregue em 21/09/2026** (Fase 7.4), assim que o histórico ficou
suficiente.
---

### Fase 6 — Inteligência Histórica ✅ *concluída em 20/09/2026*
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
| 6.6 | Previsão da fila **na chegada** | ✅ 20/09/2026 — *medida e descartada* |

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

#### 6.6 — Previsão na chegada: medida, e **descartada** ✅ *20/09/2026*

O objetivo era fechar a lacuna que a seção 4 aponta desde o primeiro dia: o NextUp soma a
fila de **agora** a uma atração onde o visitante só chega dez ou quinze minutos depois.

**O resultado foi negativo, e é a entrega mais valiosa da fase.**

Antes de implementar qualquer modelo, um backtest sobre 315 medições reais comparou a
previsão contra o baseline óbvio — **persistência**, que é "a fila daqui a N minutos é a
fila de agora", exatamente o que o app já fazia:

| Horizonte | Persistência | Tendência extrapolada | Amortecida |
|---|---|---|---|
| 5 min | **1,86** | 2,66 | 2,25 |
| 10 min | **2,50** | 3,97 | 3,18 |
| 20 min | **3,44** | 6,13 | 4,60 |
| 30 min | **4,65** | 9,02 | 6,70 |

*(erro médio absoluto em minutos; menor é melhor)*

Extrapolar a tendência **piora** a previsão em todos os horizontes, e piora mais quanto
mais longe — justamente onde prever seria mais útil.

A primeira suspeita foi viés: a fila fica parada na maior parte do tempo, o que daria
vantagem de graça à persistência. Isolando **só os casos em que a fila mudou**, ela
continua ganhando — 6,42 contra 7,72 em dez minutos, 8,23 contra 13,19 em trinta.

A razão é que **a direção não persiste**. Uma fila que subiu nos últimos trinta minutos
tem chance parecida de cair nos próximos, e extrapolar amplifica ruído em vez de projetar
sinal.

> **A decisão:** não trocar o modelo do ranking. O que o NextUp faz desde a Fase 2 é o
> melhor disponível — e agora sabemos *por quê*, com número. Implementar a previsão
> assim mesmo teria piorado o produto e ficado bonito no roadmap, que é o pior par
> possível.

**O que foi construído, então:**

- `core/forecast.py` — os dois modelos e a régua que os compara, para a medição poder ser
  repetida. Um baseline ruim **documentado** vale mais que um ausente: sem ele, a próxima
  pessoa tentaria a mesma ideia do zero.
- `tests/test_forecast.py` — fixa a conclusão em teste, para ela não sobreviver apenas
  como parágrafo que ninguém lê.
- **A tabela `queue_forecasts`** e o coletor gravando nela.

Esta última é a parte que olha para a frente. Sobrou **um candidato não testado**: a
previsão horária que a própria ThemeParks.wiki publica, e que o backtest não pôde avaliar
porque ninguém a estava guardando. Ela tem chance real justamente onde a extrapolação
falha — captura o padrão do dia, que uma janela de trinta minutos não enxerga.

A tabela guarda a **primeira** aparição de cada previsão, e é isso que faz `recorded_at`
significar "quando a fonte se comprometeu com esse número". Sem essa deduplicação, a
republicação a cada consulta viraria 288 linhas idênticas por dia e a antecedência — que é
o que dá valor a uma previsão — seria sempre de alguns minutos.

Verificado em produção: 158 previsões guardadas, 26 atrações, cobrindo sete horas à frente.

##### ✅ Avaliar o forecast da fonte — agendado para 27/09, **feito em 27/10/2026**

*O resultado está no fim deste bloco. O plano original fica como foi escrito, porque o
contraste entre o que se planejou e o que se encontrou é parte da história.*

Uma semana de coleta a partir de 20/09. O prazo não é arredondamento: **filas de sábado
não se parecem com as de terça**, e o `forecast` é exatamente um perfil de padrão do dia.
Avaliar só com dias úteis mediria metade do fenômeno.

**O que fazer nesse dia:**

1. Conferir a continuidade da coleta antes de qualquer conclusão. O Render hiberna, e se o
   `keep-alive` falhou em alguma madrugada há buracos no histórico — que enviesariam a
   medição sem avisar.
2. Cruzar `queue_forecasts` com `queue_snapshots` pelo horário, formando pares
   *(previsto, realizado)*.
3. Medir com `core/forecast.evaluate`, separando por **antecedência**: previsão de três
   horas antes é um feito; de quinze minutos, quase persistência disfarçada.
4. Comparar contra a persistência, com o mesmo método do backtest de 20/09.

**A decisão que sai daí:** se o forecast bater a persistência com antecedência real, o
`custo_total` passa a usar a fila prevista para o instante da chegada, e a Fase 6.6 ganha
a implementação que hoje não se justifica. Se não bater, fica registrado que **as duas
alternativas foram medidas** — o que é uma conclusão bem mais forte que nunca ter testado.

##### O que a avaliação encontrou (27/10/2026)

**Primeiro, o passo 1 do roteiro reprovou a coleta.** O coletor gravou de **7 a 23 ciclos
por dia** desde 22/09, contra ~156 esperados só no horário do parque — cerca de 10%. O padrão é sempre o
mesmo: o Render acorda, coleta 3 ou 4 vezes nos 15 minutos de tolerância e volta a dormir
por horas. A causa foi o `keep-alive.yml`: **244 execuções em 37 dias**, quando deveriam ser
~5.300, com intervalo mediano de **4 horas**. Todas terminaram verdes. Detalhes e correção
na Fase 8, item 8.0.

Mesmo assim havia o que medir, porque os buracos vêm do cron do GitHub, e não do nível da
fila: não há motivo para enviesarem o erro de um modelo contra outro. Cada previsão
guardada foi cruzada com a medição mais próxima do horário previsto (até 7,5 min), e
comparada com dois concorrentes **sobre exatamente os mesmos casos**:

- **persistência** — a fila conhecida quando vimos a previsão pela primeira vez;
- **perfil horário** — a média da mesma atração, ±30 min da mesma hora, **nos outros dias**
  (o dia avaliado fica de fora, senão o perfil conheceria a resposta).

605 casos, 22 atrações, 30 dias:

| Antecedência | Casos | Forecast da fonte | Persistência | Perfil horário |
|---|---|---|---|---|
| até 30 min | 102 | 9,52 | **2,03** | 6,74 |
| 30 min – 1 h | 22 | 10,45 | **4,77** | 8,68 |
| 1 – 2 h | 33 | 7,27 | 7,94 | **6,88** |
| 2 – 4 h | 38 | **10,13** | 14,18 | 11,18 |
| 4 – 8 h | 260 | **9,23** | 14,75 | 9,83 |
| mais de 8 h | 150 | **8,90** | 13,11 | 9,43 |

*(erro médio absoluto em minutos; menor é melhor)*

**Para o ranking, nada muda — agora por medição dupla.** No horizonte de uma caminhada a
persistência erra 2,03 min, e o forecast da fonte, 9,52. O 2,03 também confere com o 2,50
do backtest de 20/09, feito sobre outros dados e com outro método: dois experimentos
independentes concordando é a verificação de que a régua está certa. As duas alternativas
à fila atual — extrapolar a tendência e usar a previsão da fonte — foram medidas, e as duas
perderam.

**Para a Fase 8, há resultado novo.** Em horizontes de horas a persistência desaba
(~14 min: a fila da manhã não diz nada da tarde), e **tanto o forecast quanto o perfil
horário erram cerca de 35% menos**. É exatamente a pergunta que o roteiro precisa responder.

O que a tabela não diz sozinha:

- **Fonte e perfil empatam.** Partindo os dias ao meio, a fonte ganha na primeira metade
  (7,69 contra 9,37 acima de 4 h) e o perfil na segunda (9,97 contra 10,42). Não há
  vencedor estável.
- **A fonte superestima**, em média **+5,3 min**. A persistência subestima (−6,3), porque a
  medição da manhã é menor que a da tarde.
- **A fonte atualiza o perfil**: a mesma atração na mesma hora recebeu em média 3,2 valores
  diferentes ao longo dos dias. Não é uma tabela fixa.
- Só nos casos em que a fila mudou, o placar acima de 4 h fica em 9,97 (fonte) contra
  17,37 (persistência).

> ⚠️ **Amostra parcial.** Com a coleta a ~10%, os casos se concentram nas janelas em que o
> Render estava acordado. A medição deve ser repetida com coleta contínua antes de escolher
> entre fonte e perfil no 8.2.

**Limitação conhecida, herdada do plano gratuito:** o Render hiberna após ~15 min sem
acesso **de entrada**, e requisições que o coletor faz para fora não contam como
atividade. Com o serviço dormindo, não há coleta. O `keep-alive.yml`, que existia para o
link de portfólio não abrir em tela branca, passou a ser o que mantém o histórico contínuo
— uma responsabilidade bem maior que a original. Se o GitHub desativar o agendamento por
inatividade do repositório, o histórico ganha buracos silenciosos.

*Atualização de 27/10/2026:* os buracos vieram, e não pela desativação — o agendamento
rodou o tempo todo, só que a cada ~4 horas. O ping principal passou para o cron-job.org;
ver Fase 8, item 8.0.

### Fase 7 — Personalização ✅ *concluída em 21/09/2026*

A partir das ideias trazidas pelo Gabriel em 20/09/2026. O roadmap original acabou na
Fase 6; esta é a primeira fase que nasce do uso, e não do plano inicial.

**A tese da fase:** até aqui o NextUp responde igual para todo mundo que está no mesmo
lugar. Mas dois visitantes lado a lado querem coisas diferentes — um já foi no Space
Mountain hoje, o outro veio ao parque só por causa dele. Sem saber disso, a recomendação
é boa no geral e errada no particular.

| # | Entrega | Situação |
|---|---|---|
| 7.1 | **"Já fui hoje"** — marcar visitadas e tirá-las do ranking | ✅ 20/09/2026 |
| 7.2 | **Brinquedos alvo** — a lista do que o visitante veio fazer | ✅ 20/09/2026 |
| 7.3 | Filtros — fila máxima e caminhada máxima | ✅ 21/09/2026 |
| 7.4 | Popularidade, derivada da fila média histórica | ✅ 21/09/2026 |

A ordem não é arbitrária. **7.1 e 7.2 são a fundação do roteiro do dia** (evolução 3 da
seção 4): não dá para montar uma sequência ótima sem saber onde o visitante já esteve e
aonde ele quer chegar. Elas parecem as mais simples da lista e são as mais estruturais.

#### A decisão que molda a fase: onde mora a personalização

Três caminhos, e a escolha define o produto:

| Onde | Custo | O que se ganha | O que se perde |
|---|---|---|---|
| **`localStorage`** | baixo | Funciona na hora, sem cadastro, sem dado pessoal nosso | Preso a um navegador; trocar de aparelho zera tudo |
| Conta de usuário | alto | Sincroniza entre aparelhos | Login, senha, recuperação, LGPD — e uma barreira antes do primeiro uso |
| Link com estado na URL | médio | Compartilhável, sem servidor | URLs enormes; some ao fechar a aba |

**Escolhido: `localStorage`.** O NextUp é usado *dentro do parque*, no celular, por
algumas horas — o cenário em que trocar de aparelho não acontece. E exigir cadastro antes
de responder "para onde vou agora" mataria o produto: a graça é abrir o link e usar.

> **A consequência que precisa ficar explícita na tela:** o que o visitante marcar fica no
> aparelho dele. Não some por mágica, mas também não segue para outro navegador — e um app
> que perde dados sem avisar é pior que um que nunca os guardou.

**"Já fui hoje" precisa de data, não só de uma lista.** Marcar uma atração como visitada
vale para *hoje*; amanhã ela volta ao ranking. Sem carimbo de data, o visitante voltaria
ao parque na semana seguinte com metade das atrações escondidas e nenhuma pista do porquê.
O reset acompanha o dia **do parque**, não o do navegador — quem está em Orlando às 23h
ainda está no mesmo dia de visita, mesmo que no fuso do celular já seja outro.

#### 7.1 — "Já fui hoje" ✅ *concluída em 20/09/2026*

`web/visitadas.js`, módulo próprio. Marcar uma atração a tira do ranking — que é o que o
consultor de parque faz: ele não manda você de volta para onde acabou de ir.

**Três decisões que parecem detalhe e não são:**

1. **Sai do ranking, não da existência.** Um aviso diz quantas foram escondidas, com
   "Mostrar" e "Limpar". Esconder sem avisar é a diferença entre um app que ajuda e um que
   parece quebrado — a pessoa marcou três atrações, a lista encolheu, e ela precisa saber
   que foi ela quem causou isso.
2. **A etiqueta "melhor escolha" vai para a melhor ainda não feita.** Com as visitadas à
   mostra, a primeira posição pode ser uma já visitada, e aí ninguém receberia o destaque
   — justamente na tela em que o visitante está decidindo aonde ir.
3. **Cada parque tem sua lista.** Ter feito o Space Mountain não diz nada sobre o EPCOT.

Todo acesso ao `localStorage` passa por `try/catch`: em aba anônima, com cookies
bloqueados ou cota estourada, ele **lança** em vez de devolver vazio. Um app que quebra
porque não conseguiu lembrar de uma preferência é pior que um app sem preferência nenhuma.
E registros de dias anteriores são descartados na escrita, senão cada dia de uso deixaria
uma entrada morta para sempre.

> **Um bug de CSS que o teste encontrou, e que valia para a página inteira.** O aviso
> aparecia mesmo com o atributo `hidden`. Causa: o navegador aplica `display: none` a
> `[hidden]` pela **folha de estilo padrão**, que perde para qualquer regra de autor — e
> `.visitadas-aviso { display: flex }` a sobrescrevia.
>
> É uma armadilha silenciosa: o HTML diz uma coisa, a tela mostra outra, e o `hidden` do
> JavaScript vira decorativo. O projeto tinha **sete** elementos usando o atributo e
> nenhuma regra `[hidden]` no CSS — a correção (`[hidden] { display: none !important }`,
> presente em todo reset moderno) protege todos eles.

##### A quarta vez do mesmo bug — encontrada pelo Gabriel usando o app

Marcando as oito recomendações como visitadas e clicando em "Atualizar", a lista ficava
**vazia** — e o app anunciava *"você já passou por todas as atrações disponíveis"*, com
vinte atrações livres a poucos metros.

A causa é o padrão que a seção de lições do `CLAUDE.md` já registra, agora pela **quarta
vez**: a tela pedia `limit=8` ao servidor e só depois escondia as visitadas. As outras
vinte nunca chegaram a existir para o navegador.

> Pedir a lista **já cortada** e depois raciocinar sobre ela. A regra é sempre a mesma:
> **peça tudo, corte na exibição.** As três primeiras vezes foram contagens erradas; esta
> foi uma tela vazia e uma mensagem falsa.

**A alternativa que foi considerada e recusada:** mandar os IDs visitados para a API
filtrar. Resolveria, e custaria caro — acoplaria o servidor ao estado do navegador e
contradiria a decisão desta mesma fase, de a personalização não sair do aparelho.

**O custo medido da solução escolhida:** a resposta foi de **3,5 KB para 12,5 KB** (8 para
29 recomendações). Nove kilobytes a mais por atualização, contra um app que declarava o
parque esgotado. Não há dúvida no balanço.

Duas consequências finas, resolvidas junto:

- **Marcar não encolhe mais a lista.** A nona colocada sobe. A tela mostra oito porque
  oito é o que cabe, não porque oito é o que existe.
- **No modo "Mostrar", as visitadas se somam às sugestões** em vez de tomar a vaga delas.
  Se tomassem, revelar o que já foi feito custaria uma sugestão — e quanto mais o visitante
  andasse pelo parque, menos o app teria a dizer.

#### 7.2 — Brinquedos alvo ✅ *concluída em 20/09/2026*

Uma seção **"Você veio por estas"**, acima do ranking e separada dele por uma linha.

**A decisão de produto que molda tudo:** o que um alvo faz com o ranking?

| Alternativa | Por que não |
|---|---|
| Alvos sobem no topo | Quebra a tese do projeto — a ordem deixa de ser por custo total |
| Alvos ganham bônus no custo | Pior ainda: distorce o número em vez de assumir a mudança de critério |
| Alvos só destacados na lista | Não resolve nada — o alvo continua enterrado em décimo quinto lugar |

O que se escolheu foi reconhecer que são **perguntas diferentes**:

- O ranking responde *"o que compensa mais agora?"*
- A lista de alvos responde *"quando devo ir naquilo que eu vim fazer?"*

Cada uma ganha seu espaço, e nenhuma precisa mentir. Entre si, os alvos são ordenados por
custo total — a régua não muda; muda o conjunto sobre o qual ela é aplicada.

**O caso que justifica a seção existir**, verificado com dados reais: marcando como alvo a
**pior colocada de trinta** — Peter Pan's Flight, 58 minutos de custo total —, ela aparece
no topo da tela. Enterrada no ranking, seria invisível justamente para quem veio por ela.
E é essa informação que faz o visitante decidir esperar, voltar mais tarde ou desistir.

**Alvos não têm prazo de validade**, ao contrário das visitadas. A diferença vale registro:

```
VISITADAS  valem por DIA.   Amanhã o parque está inteiro de novo.
ALVOS      valem até mudar. São desejo, não acontecimento.
```

Uma lista de desejos que se apaga sozinha à meia-noite seria um app que esquece o que você
quer.

Detalhes que caíram do desenho:

- **O alvo sai do ranking.** Repeti-lo nas duas listas gastaria uma das oito vagas com algo
  que o visitante acabou de ver — e a lista não encolhe, a nona colocada sobe.
- **A etiqueta "melhor escolha agora" não vaza para os alvos.** Ela compara o parque
  inteiro; repeti-la sobre um recorte de três atrações diria outra coisa com as mesmas
  palavras.
- **Um alvo pode ser marcado como feito**, e o resumo passa a contar "1 de 3 já feitas".

O armazenamento foi reorganizado em `web/preferencias.js`, com uma base comum para as duas
marcações. Duplicar o `try/catch` do `localStorage` em dois arquivos seria pedir para um
deles esquecê-lo.

> **Uma armadilha de tema escuro, evitada por verificação.** O botão de alvo usa o roxo
> `--profundo` como fundo. No tema claro ele é `#4c2a6b` e pede texto branco; no escuro
> vira `#c9a6e8`, um lilás claro — e o branco sumiria. Foi preciso criar
> `--sobre-profundo`, exatamente como o projeto já fizera com `--sobre-quente` para o
> âmbar e o coral. É a segunda vez que a mesma armadilha aparece; o padrão agora tem nome.

##### O mecanismo de seleção estava falho — crítica do Gabriel, no mesmo dia

A primeira versão só deixava marcar alvos **pelo ranking**. Como a tela mostra oito de
trinta e cinco, as outras vinte e sete eram inalcançáveis: quem veio pelo Space Mountain
não conseguia dizer isso ao app até o Space Mountain, por acaso, aparecer entre as oito
melhores. E a seção ficava escondida enquanto vazia, então a funcionalidade **não existia**
para quem nunca tropeçasse nela.

A correção tem três partes:

1. **A seção é sempre visível**, e quando vazia traz um convite em vez de nada.
2. **Um `<details>` com o catálogo completo** do parque: busca, a fila atual de cada
   atração e uma caixa de seleção por linha. Marcar e desmarcar pelo mesmo lugar.
3. **Funciona antes do GPS.** A rota `/attractions` não exige posição, então dá para montar
   a lista de desejos a caminho do parque.

O `<details>` nativo foi escolhido em vez de um painel feito à mão: abrir e fechar, foco
pelo teclado, Enter e Espaço e o anúncio ao leitor de tela vêm de graça. Refazer isso com
`div` e JavaScript dá errado em silêncio — o mesmo raciocínio que fez o gatilho do gráfico
ser um `<button>`.

> **Um problema de UX que só apareceu escrevendo o teste.** A primeira versão redesenhava
> o catálogo a cada marcação, e como as marcadas sobem para o topo, a lista **se reordenava
> sob o dedo do visitante**: ele marcava uma atração, ela saltava para cima, e quem estava
> escolhendo várias perdia o lugar.
>
> Agora a linha só muda de aparência, e a reordenação espera o painel fechar e abrir de
> novo. As marcadas no topo servem a quem veio **remover** algo — e esse é outro momento,
> não o mesmo.

#### 7.3 — Filtros ✅ *concluída em 21/09/2026*

**Fila máxima** e **caminhada máxima**. Dois, e não uma lista de opções.

A pergunta que definiu quais filtros fazem sentido: *o ranking já ordena por custo total —
o que sobra para um filtro fazer?* Filtrar **por custo** seria redundante, já que basta
olhar o topo da lista.

O que o ranking não resolve é que ele **soma as parcelas**. Cinco minutos de caminhada mais
trinta e cinco de fila dá o mesmo total que vinte mais vinte — e são experiências opostas
para quem empurra um carrinho, está com uma criança no colo ou já andou oito quilômetros
naquele dia. Os filtros úteis são exatamente os que separam de volta o que o custo juntou.

**O filtro corta; não reordena.** A ordem continua sendo por custo total, que é a tese do
projeto. Mudar o critério de ordenação não seria um filtro — seria outro produto.

Três decisões que não são óbvias:

1. **Os alvos escapam do filtro.** Quem marcou "vim por esta" vai nela de qualquer jeito;
   escondê-la por um limite geral seria o app discutindo com uma escolha explícita.
2. **Os filtros são globais, não por parque.** "Não quero andar muito" é sobre a pessoa,
   não sobre o Magic Kingdom — ao contrário de visitadas e alvos, que são por parque.
3. **Um selo "ativos" no cabeçalho.** Esta é a parte que não pode faltar: um filtro
   esquecido é **indistinguível de um parque vazio**. O visitante vê três sugestões onde
   havia trinta e conclui que o app quebrou, ou que o parque está lotado.

Pela mesma razão, a lista vazia agora distingue três causas. Dizer *"você já passou por
todas as atrações"* a quem apenas apertou um controle esconderia o motivo e faria o app
parecer quebrado.

> **Um teste que fingia testar.** A primeira versão do teste "filtro esconde tudo" tinha um
> `if` que **nunca entrava**: com fila ≤ 5 e caminhada ≤ 5 ainda sobrava uma atração no
> Magic Kingdom. Um teste que sempre passa e nunca verifica é pior que teste nenhum, porque
> dá confiança falsa.
>
> Foi preciso medir a fixture para descobrir isso, e o cenário do teste virou um realista:
> apertar o filtro ao mínimo **e** marcar como visitada a única que ainda passa.


#### 7.4 — Popularidade: o proxy que a fonte não dá, mas o histórico dá

A radicalidade foi descartada acima por falta de dado. A popularidade ocupa o lugar dela
usando o que **nós** acumulamos desde a Fase 6: a fila média histórica de cada atração.

**O proxy é indireto, e vale ser honesto sobre isso.** Fila comprida não é popularidade —
é o encontro da demanda com a capacidade, e uma atração de baixa vazão forma fila com
pouca gente. Mas a pergunta prática do visitante não é "qual é a mais amada?", e sim
"qual é daquelas que sempre têm fila?". Para essa, a média histórica responde direto.

A verdade externa confirma o proxy: as primeiras colocadas pela média medida são TRON,
Seven Dwarfs Mine Train, Peter Pan's Flight e Space Mountain — exatamente as que qualquer
guia do Magic Kingdom lista como principais. Nenhuma linha de código foi escrita para
chegar a esse resultado; ele saiu dos dados.

##### Os três números vieram de medição, não de intuição

Sobre **1257 snapshots reais** do Magic Kingdom (04/09 a 22/09/2026), 30 atrações com fila
medida:

**1. Faixa relativa, nunca valor absoluto.** 59% das medições caíram entre 10h e 13h
locais — é quando o Render fica acordado e o parque, cheio. A média absoluta sai inflada.
Mas o viés atinge *todas* as atrações igualmente, porque o coletor as fotografa juntas a
cada 5 minutos: a **ordem** sobrevive, o **número** não. Por isso a tela mostra faixa, e a
média só aparece na frase de oportunidade, onde o que importa é a comparação com ela
mesma.

**2. Razão contra a mediana do parque, e não tercil por posição.** Os dois critérios foram
medidos partindo o histórico ao meio e conferindo se a faixa se repetia nas duas metades:

| Critério | Faixa estável entre as metades |
|---|---|
| Tercil por posição | 17/23 (74%) |
| **Razão contra a mediana** | **19/23 (83%)** |

O tercil ainda erra de um jeito pior: ele *força* um terço das atrações em cada faixa. Num
parque com duas campeãs e trinta medianas, chamaria dez de "principal" só para preencher a
cota. A razão contra a mediana deixa o parque dizer quantas principais ele tem — no Magic
Kingdom, nove. E classifica Big Thunder Mountain como principal, que é o correto e o
tercil errava.

> O teste de estabilidade divide o histórico em duas metades **temporais**, e a coleta
> cobre essencialmente um domingo e uma segunda. Ou seja, 83% é a concordância entre dois
> **dias de semana diferentes**, que têm perfis de multidão distintos — não ruído amostral.
> Visto assim, é um resultado melhor do que o número sugere.

**3. Abaixo de 12 medições a média é uma foto, não um histórico.** Doze é uma hora de
coleta ao ritmo de 5 minutos. O corte separou exatamente o grupo certo: ficaram de fora
Country Bear, Hall of Presidents, Tiki Room, Swiss Family Treehouse, o carrossel e os dois
trens — shows e passeios que raramente reportam fila. Nenhuma atração de fila real foi
excluída.

##### `UNKNOWN` não é `QUIET`

Abaixo do mínimo a faixa é desconhecida, e isso é uma faixa de verdade — não a ausência de
uma. Chamar de "tranquila" uma atração que nunca medimos mandaria o visitante para uma
fila de uma hora com a nossa bênção. Ela tem caixa própria no filtro, para quem quiser
justamente as que ainda não conhecemos.

##### A oportunidade: a razão de a feature existir

Saber que uma atração é principal, isolado, não muda a decisão de ninguém. O que muda é a
combinação: **uma das principais do parque com fila hoje abaixo da média dela**. É
literalmente a frase que o consultor de parque manda no WhatsApp.

Nos dados reais, **8 das 23 atrações** estavam numa faixa pelo histórico e noutra pela fila
do momento. Em um terço dos casos o histórico diz algo que o "agora" não diz — e se
dissesse sempre a mesma coisa, esta feature não precisaria existir.

Rodando contra o banco de produção em 21/09/2026, três oportunidades apareceram de uma vez:
Jungle Cruise (média 31, fila 5), Space Mountain (média 30, fila 10) e Tiana's Bayou
Adventure (média 29, fila 10).

##### Ela não reordena o ranking

Mesma regra da tendência e dos alvos, e por uma razão a mais: popularidade descreve a
**atração**, e o ranking responde sobre o **momento**. Dar bônus de custo a uma principal
distorceria o número em vez de assumir a mudança de critério.

Uma observação de produto que caiu do uso real: com o filtro desligado, as oito primeiras
sugestões **nunca** incluem uma principal, porque elas custam mais. O filtro "só as
principais" é o que torna essa parte do parque alcançável — a feature não é enfeite do
ranking, é uma porta para o que o ranking naturalmente empurra para baixo.

##### A agregação roda no banco, e é exceção deliberada à lição nº 3

O projeto aprendeu a "pedir tudo e cortar na exibição" — quatro bugs vieram de violar isso.
`storage.average_waits` faz o oposto: pede ao Postgres a média já calculada. A distinção
importa e está registrada no código: a lição é sobre **descartar linhas** antes de
raciocinar sobre elas, o que apaga informação. Isto é uma **agregação** — nenhuma atração
some, nenhuma medição é ignorada, e o resultado é idêntico a somar na memória.

O que muda é o volume: sete dias de janela, 35 atrações a cada 5 minutos, cerca de 70 mil
linhas. Arrastá-las do Neon a cada recomendação seria pagar megabytes por uma média que o
banco calcula sem sair do lugar.

##### O cache não é otimização prematura

É o que torna a feature viável. A consulta roda a cada recomendação, o Neon fica em
`sa-east-1`, e a resposta se move na escala de **dias**. Uma hora de TTL troca uma ida ao
banco por recomendação por uma ida por hora. O cache é por parque e global ao processo,
porque popularidade é propriedade do parque: dois visitantes lado a lado recebem o mesmo
número.

> ⚠️ **Parque sem histórico não entra no cache.** Guardar o mapa vazio prenderia o resultado
> por uma hora justamente enquanto o coletor começa a preencher, e o visitante não veria
> faixa nenhuma até o TTL vencer.

##### Dois bugs que só apareceram rodando o app

Nenhum dos dois foi pego pelos 499 testes:

1. **A frase saía grudada.** Sem tendência, a conta não termina em ponto, então a
   justificativa virava `"= 10 min Uma das principais do parque"`. Agora há teste.
2. **O ícone caiu na segunda linha.** `align-items: center` num texto que quebra em duas
   linhas centraliza o ícone verticalmente — ele aparecia colado na segunda linha, como se
   pertencesse a ela. Só a captura de tela mostrou.

E um terceiro, de clareza: a primeira versão reaproveitava o ícone de alvo para "uma das
principais", e ele já significa "vim por esta" no botão a dois centímetros. O mesmo símbolo
dizendo duas coisas na mesma linha. Virou um ícone de pessoas, que marca o assunto — quanta
gente costuma haver ali — deixando o texto distinguir a faixa.

---

### Fase 8 — Roteiro do dia 🔍 *investigação preliminar, 21/09/2026*

> **Nada foi implementado.** O que segue é a medição que precede a decisão de escopo, feita
> antes de escrever qualquer código — e o resultado dela **muda o desenho da fase**. A
> estrutura definitiva ainda precisa do aval do Gabriel.

#### A diferença entre ranking e roteiro

O ranking de hoje é **guloso**: escolhe o melhor agora e nunca se arrepende. Um roteiro é
**global** — aceita uma escolha pior agora para ganhar depois. *"Vá na Jungle Cruise agora
e deixe a TRON para as 19h, quando a fila cai."*

Repare no que essa frase exige: **saber qual será a fila às 19h**. O ranking não prevê
nada; o roteiro não existe sem previsão. É essa dependência que estrutura a fase inteira —
e é exatamente onde o projeto já tem um resultado negativo medido (6.6).

#### O que foi medido

A 6.6 descartou **extrapolar a tendência**. A investigação de agora testou o caminho que
ela não cobriu: o **perfil horário** ("a Space Mountain costuma ter 40 min às 14h"), que é
média histórica por faixa do dia, e não extrapolação de direção.

**1. O dado ainda não existe.** Apenas **2 dias** de coleta (20 e 21/09). Das 298 células
(atração, hora), **33% têm uma única medição** e 47% têm menos de três. Há buracos às 8h,
15h e 17h — consequência da hibernação do Render.

**2. O perfil não se repete entre dias.** Comparando a **mesma atração, na mesma hora**, em
dias consecutivos — 28 pares comparáveis, com ao menos duas medições de cada lado:

| Medida | Valor |
|---|---|
| Erro médio absoluto entre os dois dias | **13,58 min** |
| Baseline de persistência da 6.6 (10 min à frente) | 2,50 min |

Os horizontes são diferentes, então não é comparação direta. Mas 13,58 min num dado cuja
média é ~20 min é erro da ordem de dois terços do valor.

**3. Há estrutura no erro, e ela não basta.** Em **25 dos 28 pares** o segundo dia foi
maior — não é ruído, é um deslocamento do dia inteiro (fator 1,54×). Testando a hipótese
natural, *"a forma do dia se repete e só o nível muda; calibre o nível pela manhã e preveja
a tarde"*:

| | Erro |
|---|---|
| Sem corrigir o nível do dia | 13,58 min |
| Corrigindo por um fator único | **10,98 min** |
| Redução | apenas 19% |

A forma do perfil também muda. Com 28 pares e 2 dias isso é **indicativo, não conclusivo**
— mas indica o bastante para decidir o desenho.

> ⚠️ **Cuidado metodológico que quase produziu a conclusão errada.** A primeira comparação
> usou a *média do parque* entre dias, e deu 18,1 contra 31,9 ao meio-dia. Só que a coleta
> não cobriu as mesmas atrações nos dois dias: a média se move sem a fila ter mudado. A
> comparação honesta é sempre do mesmo par (atração, janela).

#### A consequência no desenho

Um plano do dia inteiro feito às 9h precisa prever 8 horas à frente. Com ~11 min de erro
por atração, acumulado em dez paradas, o plano vira ficção — e **ficção confiante é pior
que nenhum plano**, porque o visitante a segue.

A saída é operar no horizonte em que a previsão já funciona. A 6.6 mediu isso: persistência
erra 1,86 min a 5 minutos e 2,50 a 10.

> **O roteiro sugere as próximas 3–4 atrações e se replaneja a cada uma concluída.** Não é
> limitação disfarçada: é o formato honesto dado o que sabemos prever, e é também como o
> app é usado — de pé, no parque, decidindo a próxima parada.

#### Estrutura proposta

| # | Entrega | Por que nesta ordem |
|---|---|---|
| 8.0 | **Consertar a coleta** — cobertura horária e continuidade 🔧 *27/10: causa achada e corrigida; falta confirmar uma semana contínua* | Pré-requisito de tudo; hoje há 2 dias e 47% das células com menos de 3 medições |
| 8.1 | **Matriz de caminhada** atração→atração ✅ *27/10/2026* | `geo.py` só sabe visitante→atração; o roteiro precisa dos 1225 pares |
| 8.2 | **O otimizador** — sequência de 3–4 paradas 🔧 *27/10: backtest de ensaio e núcleo prontos; falta confirmar na coleta contínua e a rota da API* | O coração técnico da fase |
| 8.3 | **Replanejamento** a cada conclusão | Um roteiro rígido morre no primeiro desvio |
| 8.4 | **Interface** — linha do tempo | Mostrar um plano é diferente de mostrar uma lista |

O 8.0 é infraestrutura e não gera tela nova, mas sem ele o 8.2 seria otimização sobre dado
inventado. Ele também é pré-requisito da avaliação do forecast agendada para 27/09 — as
duas coisas pedem a mesma correção.

#### 8.0 — A auditoria da coleta 🔧 *27/10/2026*

Um mês depois da investigação, a expectativa era ter cinco semanas de histórico contínuo.
**A auditoria mostrou outra coisa: o coletor esteve parado ~90% do tempo.**

| Medida | Esperado | Medido |
|---|---|---|
| Ciclos de coleta por dia | ~156 (a cada 5 min, ~13 h de parque aberto) | **7 a 23** |
| Execuções do `keep-alive.yml` em 37 dias | ~5.300 (a cada 10 min) | **244** |
| Intervalo entre execuções do `keep-alive` | 10 min | mediana de **4 h**; nenhum abaixo de 12 min |
| Execuções com falha | — | **0** |

Um dia típico (24/10, horário de Orlando) mostra o mecanismo: gravações às 08:04, 08:09 e
08:14; depois só às 11:53, 11:58 e 12:03; depois às 14:41… O Render acorda com um ping
tardio, fica de pé os 15 minutos de tolerância, o coletor roda três ou quatro vezes, e o
serviço volta a dormir por horas.

> ⚠️ **A lição: um job verde não prova que o trabalho aconteceu.** O `keep-alive` nunca
> falhou — ele simplesmente não rodava. O comentário do arquivo dizia que o GitHub atrasa
> agendamentos "em minutos"; foram horas. A suposição era razoável e nunca tinha sido
> medida. O que detectou o problema foi olhar **o efeito** (ciclos gravados no banco), e
> não **a causa** (o painel do Actions).

**A correção:** o ping principal passou para o **cron-job.org**, chamando `/api/health` a
cada **5 minutos**, com notificação de falha ligada. Serviços desse tipo existem para ser
pontuais, que é justamente o que o cron do GitHub não promete. O `keep-alive.yml` fica como
reserva, com o cabeçalho corrigido pelos números medidos. Cinco minutos, e não dez ou
quinze, porque a hibernação é aos 15: o intervalo curto tolera até duas falhas seguidas.
O plano gratuito do Render dá 750 h por mês, o que cobre um serviço ligado o mês inteiro.

**O que se salvou do histórico:** para o *perfil por hora*, mais do que parece — 59% das
células (atração, hora) têm 10 dias distintos ou mais, porque as poucas medições diárias se
espalharam por cinco semanas. Para qualquer coisa de *horizonte curto*, pouco: só existem
pares de medições dentro das janelas de 15 minutos.

**O perfil horário, remedido.** Com 2 dias de dado, a investigação de 21/09 achou 13,58 min
de erro. Com cinco semanas, deixando o dia avaliado de fora, o perfil erra **~9–10 min**
acima de 2 horas de antecedência — e empata com o forecast da própria fonte (tabela
completa na Fase 6, bloco da avaliação do forecast). Melhorou, e continua grande demais para
um plano do dia inteiro: **a decisão das 3–4 paradas replanejadas se mantém**, agora sobre
cinco semanas e não sobre dois dias.

**A pergunta que fica para o 8.2:** qual previsão usar para "mais tarde". A fonte funciona em
qualquer parque desde o primeiro dia; o perfil é dado nosso, mas exige semanas de coleta
por parque. Decidir depois de repetir a medição com uma semana de coleta contínua.

#### 8.1 — Matriz de caminhada ✅ *27/10/2026*

`geo.travel_time_matrix`: o tempo a pé entre **todos os pares** de atrações, calculado uma
vez e lido muitas. O ranking só precisava de *visitante → atração*; o roteiro precisa de
*atração → atração*, porque escolher a segunda parada exige saber quanto se anda saindo da
primeira. Função pura, simétrica, zero na diagonal, e identificador desconhecido levanta
`KeyError` — um tempo inventado seria usado pelo otimizador sem desconfiar.

**Antes de escrever, o fator de sinuosidade foi medido.** O 1,3 nasceu como estimativa na
seção 4 e nunca tinha sido conferido. No ranking isso pesava pouco — o erro é parecido para
todas as atrações e a ordem sobrevive. No roteiro pesa mais: trechos encadeados somam erros,
e o erro não é uniforme (o rio do Magic Kingdom aproxima na linha reta o que está longe a
pé).

A verdade externa foi o **OpenStreetMap**: os caminhos de pedestre do parque, baixados numa
consulta única, viraram um grafo, e a rota mais curta (Dijkstra) foi calculada entre os 595
pares de atrações do Magic Kingdom.

| Modelo | Erro médio por trecho |
|---|---|
| Linha reta, sem correção | 1,70 min |
| **Linha reta × 1,3 (o que já existia)** | **0,58 min** |
| Linha reta × 1,33 (o melhor fator único possível) | 0,59 min |

*(caminhada média real entre duas atrações: 6,43 min)*

**A estimativa estava certa** — o melhor fator possível é 1,33. A razão real varia de 1,20 a
1,65 (p10 a p90) e passa de 2 onde há água no caminho: Big Thunder ↔ Haunted Mansion são
174 m em linha reta e 417 m a pé. Em 7 das 35 atrações, a vizinha mais próxima pela linha
reta não é a mais próxima pelas trilhas.

**Por que não usar as trilhas reais, então?** Porque o erro de caminhada (0,58 min por
trecho) é pequeno diante do erro da previsão de fila (~9 min em horizontes de horas). Um
roteador sobre o OSM traria dependência nova, um processo de dados por parque e cobertura
desigual fora da Disney — esforço gasto na parcela do erro que já é pequena. Se um dia a
previsão de fila melhorar muito, a conta se inverte.

Os testes (`tests/test_geo_matriz.py`) comparam contra os números do OSM, verificam a
desigualdade triangular — uma matriz que a violasse daria ao otimizador "atalhos" que só
existem na conta — e **documentam a limitação do rio** como teste, para ela não ser
esquecida.

#### 8.2 — O otimizador: backtest primeiro, núcleo depois ✅ *27/10/2026 (núcleo)*

**A pergunta que veio antes do código:** planejar bate o guloso? O ranking de hoje já é
um guloso replanejado a cada parada — o roteiro só se justifica se planejar à frente der
ganho *medido* sobre isso. Com ~9 min de erro na previsão de horas, havia motivo real para
duvidar.

**O backtest.** Cenário: o visitante chega à entrada numa hora do dia com 5 alvos e quer
concluir todos no menor tempo. Quatro estratégias, todas replanejando a cada parada, com a
fila real (interpolada) como juiz:

| Estratégia | Contra o guloso | Vence | Perde |
|---|---|---|---|
| **Plano supondo filas paradas** (persistência) | **-7,7 min (-4,1%)** | 136 de 178 | 28 |
| Plano com o perfil horário | -5,0 min (-2,7%) | 119 | 47 |
| Oráculo — conhece as filas futuras (teto) | -14,2 min (-7,6%) | 170 | 0 |

A conclusão se manteve variando a duração das atrações (5, 8 e 15 min), com 4 alvos em vez
de 5, e nas duas metades dos dias (-7,4 e -8,0 min).

O que a tabela ensina:

- **O ganho vem da geografia, não da previsão.** A estratégia vencedora supõe que nada
  muda; o que ela faz melhor é a **ordem** — o guloso persegue a fila mais curta,
  atravessa o parque e depois atravessa de volta. É a melhor notícia possível para o
  produto: essa versão não precisa de histórico, e funciona em qualquer parque desde o
  primeiro dia.
- **O perfil horário atrapalha.** Planejar com ele rende *menos* que supor filas paradas —
  coerente com a avaliação do forecast, em que nenhuma previsão nossa vale a troca na
  escala de uma ou duas horas.
- **O oráculo mede o prêmio que falta.** Nem uma previsão perfeita passaria de ~14 min em
  cinco alvos. A geografia já captura metade do teto. O roteiro economiza uma fila a cada
  três horas e acerta em três de cada quatro vezes — real, e modesto.

> ⚠️ **Ensaio sobre histórico fragmentado.** A fila real entre medições foi interpolada
> através de buracos de até 4 h, o que suaviza o mundo, e 85% dos cenários foram
> descartados por falta de dado (com buracos de até 2 h, sobraram 4). **Repetir sobre a
> coleta contínua antes da interface (8.4).** Se o ganho sumir, o núcleo fica como
> resultado negativo documentado, como o `forecast.py`.

**O núcleo — `core/itinerary.py`.** `plan_itinerary` devolve as próximas paradas na ordem
que termina mais cedo. Três decisões de desenho:

- **Busca exata por *branch and bound*.** As ordens crescem com o fatorial (5 alvos são
  120; 10 são 3,6 milhões). A busca monta as sequências parada a parada e abandona um
  ramo quando o começo dele já passa do melhor roteiro completo. O resultado é o mesmo da
  força bruta — e os testes conferem isso em 210 instâncias aleatórias.
- **Profundidade máxima de 5 paradas** (`ITINERARY_MAX_STOPS`), coerente com o desenho de
  replanejar a cada parada. Medido no Magic Kingdom real:

  | Alvos | Profundidade | Sequências possíveis | Avaliadas | Tempo médio |
  |---|---|---|---|---|
  | 10 | 5 | 30.240 | 5.952 | 2 ms |
  | 35 | 5 | 39 milhões | 340 mil | 70 ms |
  | 10 | 7 | 604.800 | 137 mil | 52 ms |

  A poda corta 99% do trabalho. Profundidade 7 custaria 25 vezes mais sem ganho que o
  backtest justifique.
- **A previsão é injetada** (`WaitPredictor`), com a persistência como padrão. Trocar de
  previsor não toca no otimizador — e só deve acontecer depois de um backtest.

O tempo é sempre **minutos a partir de agora**: o `core/` continua sem saber de fuso. A
duração de cada atração (`RIDE_DURATION_MINUTES`, 8 min) é estimativa, porque a fonte não
a informa; a sensibilidade foi testada e não muda a conclusão.

**Falta para fechar o 8.2:** confirmar o ganho na coleta contínua e expor o roteiro numa
rota da API.

#### O problema não é o Caixeiro Viajante

A seção 4 supôs TSP. É um problema mais rico: **Orienteering Problem com custos dependentes
do tempo**. As diferenças importam:

- Não se visita tudo — **escolhe-se um subconjunto**, porque não dá tempo
- Há **janela de tempo**: o parque fecha
- O custo de cada nó **muda conforme a hora da chegada** — é o que o TSP clássico não tem
- Os nós têm **prêmios diferentes**: um alvo (7.2) vale mais que uma atração qualquer

A arquitetura segue a regra da casa: `core/itinerary.py`, função pura, com a previsão
injetada como `trends` e `popularity` já são hoje. O otimizador não sabe o que é banco.

### Fase 9 — Perfil do visitante 🔧 *iniciada em 27/10/2026*

#### A crítica que originou a fase

O Gabriel, ao pedir um redesenho do site, colocou o dedo na ferida:

> *"Simplesmente ver o tempo de fila dos brinquedos não resolve o maior problema, isso é
> facilmente resolvido pela api que usamos [...] qualquer um consegue calcular mentalmente
> uma estimativa de qual o próximo brinquedo."*

Os dados confirmaram na hora. Na noite de 27/10 (festa de Halloween, filas baixas), as 8
primeiras do ranking a partir da entrada tinham **todas 5 min de fila**: com as filas
niveladas, o ranking vira "o que está mais perto" — o que qualquer um vê no mapa. **O
ranking sabe o que cada atração *custa*, e não o que ela *vale* para quem pergunta.**

Quatro cenários, rodados com o código de produção sobre as filas reais:

| Cenário | O que o app fazia | O que falta |
|---|---|---|
| Quem já tem os favoritos | Lista os alvos pelo custo de agora; segui-la é zigue-zague: **173 min**, 33 a pé | O roteiro (8.2) faz os mesmos 5 em **162 min**, 22 a pé |
| Criança pequena | Saindo do Dumbo, sugeria a Space Mountain (112 cm) em 4º lugar | O app não sabe altura mínima |
| Quando focar nas principais | — | Medido: todas as faixas são baratas às 9h e às 21h e caras entre 12h e 17h, mas a TRON oscila ~23 min e uma tranquila ~8. **Principais nas pontas do dia, tranquilas no pico** |
| Quem quer (ou evita) emoção | Space Mountain e Magic Carpets lado a lado, como equivalentes | O app não sabe intensidade |

> ⚠️ O padrão do horário tem um viés conhecido: setembro e outubro são temporada da festa
> de Halloween, cujas noites têm público reduzido. Parte do "à noite é barato" pode ser
> artefato. Conferir com os dados de novembro.

**A consequência para o produto:** o `custo_total` continua sendo o critério, mas passa a
responder outra pergunta — de *"qual a mais barata?"* para *"entre as que valem a pena
**para mim**, qual a mais barata **agora**?"*. Quem define "valer a pena" é o perfil.

#### Decisões de produto do Gabriel

- **Perguntar, não adivinhar.** Inferir o perfil pelo comportamento erra, e um filtro
  silencioso repete a lição da 7.3 (filtro esquecido é indistinguível de parque vazio). A
  inferência pode vir depois, como **sugestão visível**.
- **Só as perguntas essenciais**: a altura da criança mais baixa do grupo e o tipo de
  atração preferido (tranquilas / de tudo / emoção). Ambas puláveis, com o comportamento de
  hoje como padrão.
- **Altura marca, não esconde.** A atração aparece com *"a partir de 122 cm — só os
  adultos"*, pensando no *Rider Switch* da Disney. E não ganha o destaque de "melhor
  escolha", que é para o grupo todo.

#### 9.1 — A curadoria ✅ *27/10/2026*

A fonte não informa altura mínima nem intensidade — foi por isso que a "radicalidade"
caiu na 7.4. A solução é **dado nosso, conferido à mão**, para as 35 atrações do Magic
Kingdom: `src/nextup/data/curadoria_magic_kingdom.json`.

**Nada veio de memória nem de resumo de busca.** Os dois erraram, e a fonte oficial os
desmentiu:

| Atração | Memória / terceiros / busca | Listagem oficial |
|---|---|---|
| Big Thunder Mountain | 102 cm (memória e sites de terceiros) | **97 cm** |
| The Magic Carpets of Aladdin | 102 cm (resumo de busca) | **Any Height** |

Como o dado foi obtido está na seção 8 (aspectos legais e éticos): capturas de tela da
listagem pública, feitas pelo Gabriel e transcritas. O site estava em português, e a
tradução das etiquetas para os nomes da Disney em inglês **não foi suposta**: as cinco
atrações lidas antes na versão americana aparecem nas capturas, e cada par confirmou uma
tradução ("PERCURSO LENTO, GIROS" ↔ "Slow Rides, Spinning", e assim por diante).

**A intensidade sai das etiquetas oficiais por uma regra escrita** (`core/intensity.py`),
não por opinião: radical = "Thrill Rides" ou "Big Drops"; moderada = "Small Drops" ou
"Scary"; o resto, tranquila. "Dark" e "Spinning" ficam de fora: escuro é dimensão
sensorial, e a Disney marca como "Spinning" tanto o Buzz Lightyear quanto a Mad Tea Party.

| Nível | Atrações |
|---|---|
| Radical (5) | TRON (122 cm), Space Mountain (112), Tiana's (102), Big Thunder (97), Seven Dwarfs (97) |
| Moderada (3) | Barnstormer (89), Peter Pan, Pirates of the Caribbean |
| Tranquila (27) | todas as outras |

Três casos revistos com o Gabriel, e mantidos: **Peter Pan moderada** (a Disney marca
"Small Drops"; refinar a regra para deixá-la tranquila arrastaria junto a Pirates, que tem
uma queda de verdade no escuro); **Haunted Mansion tranquila** (nenhuma atração do Magic
Kingdom é marcada "Scary"; sustos são outra dimensão, a tratar se fizer falta); **Seven
Dwarfs radical** (a Disney a marca "Thrill Rides", e o selo de 97 cm já avisa a família).

**Três garantias no código:**

- **Só a linha conferida chega ao visitante.** Sem `conferido_em` e `conferido_por`, a
  atração é desconhecida — uma altura errada manda uma criança para uma fila em que ela não
  entra.
- **Sem curadoria não há intensidade.** Chamar de tranquila uma atração não conferida
  mandaria quem pediu "só tranquilas" para uma montanha-russa (a regra do `UNKNOWN` da 7.4).
- **A API descreve, não decide.** `min_height_cm` e `intensity` saem nas rotas de atrações
  e de recomendações; nada some e nada é reordenado. O perfil, na tela, decide.

A curadoria mora em `data/`, um terceiro tipo de pasta: `clients/` busca dado de fora,
`storage/` guarda dado acumulado, `data/` guarda dado **conferido** — que muda por revisão,
com commit e autor. O teste de arquitetura proíbe `core/` e `models/` de importá-la.

#### Próximos passos

| # | Entrega |
|---|---|
| 9.2 | As duas perguntas do perfil, no `localStorage`, como os filtros da 7.3 ✅ |
| 9.3 | O redesenho da tela em torno do perfil: perfil → próximo passo → roteiro → "ver todas as filas" ✅ *(sem o roteiro, que espera 03/11)* |

#### 9.2 — As duas perguntas ✅ *28/10/2026*

O perfil mora no `localStorage` (`PERFIL`, em `web/preferencias.js`), **global** como os
filtros: "a criança tem 95 cm" é sobre o grupo, não sobre o parque. As regras ficam ali
como funções puras (`soAdultos`, `escondida`, `semCuradoria`), e a tela só pergunta.

| Resposta | O que muda |
|---|---|
| Criança de N cm | Atração que pede mais que N ganha **"A partir de X cm · só os adultos"** e a dica do *Rider Switch*. Continua na lista; **não** ganha o destaque de "melhor escolha" |
| Tranquilas | Esconde as **5 radicais**; as 3 moderadas ficam (decisão do Gabriel) |
| Quero emoção | Esconde as **tranquilas** — 27 das 35 do Magic Kingdom (decisão do Gabriel) |

O que esconde, avisa: *"5 radicais escondidas por "Tranquilas""*, com **Mostrar** — o
contrato da 7.3, porque "Emoção" sem aviso pareceria um parque com três quartos a menos.
A lista vazia ganhou a quarta causa ("nada combina com o seu perfil"). Atração sem
intensidade nunca é escondida, e com criança no grupo a sem curadoria diz *"altura mínima
não conferida"* — a regra do `UNKNOWN`. Os alvos escapam, como escapam dos filtros.

**O painel** é um `<dialog>` que abre sozinho na primeira visita, por cima do parque já
carregado, e depois pelo botão **"Seu grupo"**, sempre à vista. Ao ajustar a altura, a
consequência aparece antes de confirmar, calculada no catálogo real (*"Com 95 cm, fica de
fora: TRON, Space Mountain…"*). Nada vem pré-marcado; **pular também é resposta**, e o Esc
da primeira visita vale como pular.

**16 testes de interface.** Uma armadilha evitada: na fixture, as 8 primeiras do ranking
são todas tranquilas e sem altura mínima, e "Tranquilas esconde as radicais" passaria sem
esconder nada. Um helper promove uma radical a mais barata, com a conta fechando, e o
par 95 cm / 97 cm prova que foi o perfil, e não o acaso, que tirou a Seven Dwarfs do
destaque.

#### 9.3 — O redesenho começou pelo design 🎨 *27–28/10/2026*

O Gabriel decidiu desenhar antes de codificar, usando o **Claude Design**. O prompt está
versionado em [`docs/design/prompt-claude-design.md`](design/prompt-claude-design.md) e
carrega a tese do produto, os dados reais da API e as regras de comportamento que o código
já garante (filtro visível, `UNKNOWN` que não é tranquila, as três causas de lista vazia,
dado velho sinalizado). Assim o design já nasce respeitando o que a implementação exige.

**Estrutura: uma tela, dois estados** — e não duas páginas. A primeira abertura mostra o
parque com um painel leve por cima (as duas perguntas, puláveis); a tela principal em uso
tem, nesta ordem, o **próximo passo** (uma atração, com o porquê), o **roteiro** (os alvos
em linha do tempo), o **mapa** e, rebaixada, a **lista de todas as filas**. Uma página de
cadastro separada faria o visitante, no meio do parque, preencher formulário antes de ver
qualquer resposta — e o app abre mostrando o parque desde a Fase 5.

**Restrição de marca**: nada de logotipo, personagem, orelhas, castelo ou tipografia que
imite a Disney. O projeto é independente, e um portfólio público não pode parecer produto
oficial.

**Primeira rodada (28/10):** o Gabriel não gostou tanto do resultado, mas vai aproveitar
muita coisa. Próximo passo: revisar o que voltar contra o que a API realmente entrega.

**Primeira versão focada no Magic Kingdom** — decisão do Gabriel, porque só ele tem
curadoria e histórico; nos outros parques o app seria a "lista de filas" que a Fase 9
critica. Decidido em 28/10: o seletor sai da tela, mas o código dos outros parques fica,
atrás de uma chave, e continua testado.

#### 9.3 — A implementação ✅ *28/10/2026* (sem o roteiro, que espera a medição de 03/11)

Em três etapas, cada uma com commit e testes, para o app no ar nunca ficar pela metade:

| Etapa | O que entrou |
|---|---|
| 1. Paleta e fonte | Algodão-doce: 3c no claro, 3b no escuro; Bricolage Grotesque. Os componentes não mudaram, só os valores dos tokens — cada par medido pela WCAG (o mais apertado, 5,3:1) |
| 2. Mapa real | O GeoJSON no lugar dos tiles, pintado pelo CSS; rota até a melhor escolha pelas trilhas; nomes nos marcadores sem sobreposição. Os outros parques seguem com tiles |
| 3. Layout | Mapa no topo, de borda a borda; o cartão **"Seu próximo passo"**; a lista inteira num painel aberto por "Todas as filas · 26" |

**O cartão** tem três estados — sem posição (pede a localização), carregando, e com a
melhor escolha do grupo. O total é o maior número da tela, aberto em caminhada e fila numa
barra com a linguagem do mapa (pontilhado para quem anda, cápsula para quem espera), mais
"entra às HH:MM" no fuso do parque. O "Já fui" do cartão tem 5 s para desfazer. Sem
melhor escolha, o cartão some e o aviso explica, porque é o aviso que distingue as quatro
causas de lista vazia. O cartão é escuro nos dois temas, e redefine dentro dele os tokens
pensados para fundo claro.

**O que os testes pegaram no caminho:**

- Os tiles eram baixados de verdade em todo teste — furando "nenhum teste toca a
  internet" desde a Fase 5. Agora são interceptados com um PNG de 1×1 (gerado com CRC
  conferido: o primeiro, escrito de memória, estava errado).
- Durante a animação de zoom, os nomes do mapa ficam em trânsito (até 45 px fora). O app
  anuncia quando terminou de posicioná-los (`data-rotulos="prontos"`, por eventos
  públicos do Leaflet), e os testes esperam o anúncio em vez de um tempo fixo.
- Numa falha da API, o cartão era escondido com o esqueleto de carregamento dentro.
- Um teste intermitente (o clique no mapa sem GPS) media o mapa no meio da troca de um
  aviso acima dele; agora espera o aviso final.

**Fica para depois:** o **roteiro** (o espaço dele é "Você veio por estas", logo abaixo do
cartão) espera a medição de 03/11; os nomes da 1ª e da 2ª colocadas às vezes não cabem no
mapa quando o visitante está no meio delas — a regra esconde em vez de sobrepor, e o
cartão já diz o nome da primeira.

#### 9.3 — Revisão: mapa legível e layout de computador ✅ *28/10/2026*

No mesmo dia, testando no celular, o Gabriel achou o mapa **difícil de entender** e o
computador **com o layout do celular esticado**. As causas do mapa, achadas uma a uma em
capturas de tela:

1. **A pilha de pintura estava invertida — bug real.** O desenho era empurrado para baixo
   da rota com `bringToBack()`, que num grupo leva cada caminho ao fundo um de cada vez:
   o último a ir fica embaixo de todos, e a pilha inteira vira de cabeça para baixo. O
   gramado era pintado **por cima** das trilhas. Conserto: uma camada (*pane*) só do
   desenho, abaixo da rota, sem reordenar nada. Os 135 testes passavam com o bug — nenhum
   olhava a ordem; agora um olha (e falha se o `bringToBack()` voltar: conferido).
2. **Tudo era lilás.** Caminho branco sobre chão quase branco, prédio, gramado e chão na
   mesma mancha. Agora cada coisa tem sua convenção: chão mais escuro para o caminho
   saltar, gramado verde, água azul, prédio sem contorno.
3. **Nada orientava.** Uma segunda consulta (pequena, em cache) à Overpass traz o
   **contorno do parque** — o entorno fica sob um véu — e as **seis áreas**, escritas no
   chão em caixa alta. O nome vai no ponto de dentro mais longe da borda, não no centroide:
   área que abraça o castelo tem forma de L, e o centroide cairia na vizinha. Corte de
   tamanho medido: a menor área tem 20 mil m², o maior recanto 14 mil.
4. **O parque inteiro, miúdo.** O mapa agora enquadra o visitante e as três primeiras
   (zoom em quartos de nível: com inteiros, caía um nível inteiro abaixo do que cabia), e
   só refaz isso quando a resposta muda.
5. **Oito nomes disputando o olhar.** Só as três primeiras têm nome; da quarta em diante,
   número menor. O visitante virou o ponto azul com halo que todo mapa de celular usa.

**No computador**, mapa fixo à direita na altura inteira e uma coluna de 460 px à
esquerda com o cartão, os alvos e **a lista aberta** — o painel existia para poupar
altura, e no computador altura sobra. É o mesmo `<dialog>`, mostrado sem o modo modal.
Passar o ponteiro num item acende o número dele no mapa.

**Segunda rodada, no celular do Gabriel:** o escuro ficou "ideal", mas no claro as vias
ainda sumiam — caminho branco sobre praça e chão claros. O escuro funciona porque ali o
caminho é o que tem mais luz; o claro precisa de borda. As trilhas passaram a ser pintadas
duas vezes, a primeira mais larga e mais escura (a **casca**), como as ruas de qualquer
mapa claro. No escuro a casca não existe. E o botão "Todas as filas" saiu de cima do mapa,
onde se perdia, para uma **barra fixa no pé da tela**, de cor própria — com a cor de ação,
índigo no claro, ela sumia sobre o cartão, que é índigo também.

**Terceira rodada — o tema claro inteiro.** O claro seguia "muito abaixo" do escuro. Três
paletas só de mapa (tinta rosa, rosa e céu) e a 3b clara foram testadas em capturas, e a
causa apareceu: o claro da 3c misturava temperaturas — página lilás-fria, cartão índigo
escuro, mapa lilás —, e o cartão escuro, um "buraco negro" na tela clara, puxava o olho
para longe de todo o resto. O Gabriel trouxe uma especificação completa, "Algodão Doce":
página baunilha, cartão pastel luminoso (degradê rosa → azul), Já fui amarelo, pinos
brancos com aro azul-noite, mapa de chão branco-quente, gramado menta e prédios
rosa-lavanda. Implementada por tokens: tudo que pressupunha cartão escuro virou token,
com o valor antigo no escuro — que continua igual. Quatro tons da especificação não
passavam na WCAG e foram escurecidos o mínimo; a tabela da seção 10 tem os números.

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
| Coleta parar sem ninguém notar (hibernação do Render) | **Alto** | Pinger externo a cada 5 min com alerta de falha; `keep-alive.yml` como reserva. Aconteceu: ~10% de cobertura entre 22/09 e 27/10, com todos os jobs verdes |

### Aspectos legais e éticos
- Dados públicos, consumidos por API pública, sem burlar autenticação ou bloqueio.
- Projeto sem vínculo com a The Walt Disney Company. Aviso explícito no README.
- Crédito à ThemeParks.wiki como fonte, no README e na interface.
- Se o projeto for monetizado no futuro, revisar os termos de uso da fonte antes. Em
  29/10/2026 os termos de uso comercial da API **não foram encontrados** — ver "Se um
  dia for cobrar", na seção 1.
- **A curadoria (Fase 9) não raspa o site da Disney.** Em 27/10/2026, com autorização do
  Gabriel, houve **uma** tentativa de ler o endpoint JSON interno que a listagem oficial
  usa. O site não respondeu a cliente automatizado — proteção contra robôs, colocada de
  propósito —, e a tentativa parou aí: disfarçar a requisição de navegador seria burlar
  um bloqueio, o que este projeto não faz. O dado veio de **capturas de tela feitas pelo
  Gabriel** na listagem pública, transcritas e revisadas. As capturas não vão para o
  repositório: são imagens do site da Disney.
- A curadoria guarda **fatos** (altura mínima, etiquetas de experiência), não texto,
  imagem ou descrição da Disney.

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
| **Baseline** | O modelo bobo contra o qual qualquer modelo esperto precisa se justificar |
| **Persistência** | Prever que o futuro é igual ao presente. Em horizonte curto, dificílimo de bater |
| **Backtest** | Rodar o modelo sobre o passado, usando só o que se sabia na época, e medir o erro |
| **Erro médio absoluto (MAE)** | Média de quanto o modelo erra, na unidade do dado — aqui, minutos de fila |
| **Extrapolação** | Projetar a tendência recente para a frente. Prolongada, sempre sai da realidade |
| **Horizonte** | Quão longe no futuro a previsão olha. Quanto maior, mais difícil |
| **Antecedência (lead time)** | Com quanto tempo a previsão foi feita. Acertar cinco minutos antes não impressiona |
| **Resultado negativo** | Descobrir que algo *não* funciona. Vale tanto quanto o positivo, e quase nunca é registrado |
| **`localStorage`** | Armazenamento do navegador que sobrevive a fechar a aba. Preso a um aparelho, e pode lançar erro |
| **Folha de estilo do navegador** | O CSS padrão que o navegador aplica sozinho. Perde para qualquer regra que você escreva |
| **`!important`** | Força uma regra CSS a vencer. Quase sempre um cheiro; aqui, a forma correta de honrar o `hidden` |
| **`aria-pressed`** | Diz ao leitor de tela se um botão de liga/desliga está ligado |
| **`Intl.DateTimeFormat`** | API do navegador para formatar data em outro fuso — é como se sabe o "hoje" do parque |
| **Pinger / keep-alive** | Serviço que acessa uma URL em intervalo fixo só para mantê-la acordada |
| **Cron** | Agendamento por horário. O do GitHub Actions é "quando der", não um relógio — medido, 4 h de atraso |
| **Perfil horário** | A média histórica de uma atração em cada hora do dia: "às 14h ela costuma ter 40 min" |
| **Matriz de distâncias** | Tabela com o custo entre todos os pares de pontos, calculada uma vez e consultada muitas |
| **Grafo** | Pontos (nós) ligados por arestas com custo. As trilhas de um parque viram um |
| **Dijkstra** | Algoritmo que acha o caminho mais curto num grafo, expandindo sempre o nó mais próximo ainda não visitado |
| **Desigualdade triangular** | Ir de A a C passando por B nunca é mais curto que ir direto. Toda distância honesta obedece |
| **OpenStreetMap (OSM)** | Mapa colaborativo e aberto do mundo, com trilhas de pedestre até dentro de parques |
| **Orienteering Problem** | Parente do Caixeiro Viajante: com tempo limitado, escolher *quais* pontos visitar, e em que ordem, para somar o maior prêmio |
| **Algoritmo guloso** | Escolhe o melhor *agora* e nunca olha adiante. Simples e rápido, mas atravessa o parque e depois volta |
| **Fatorial / explosão combinatória** | 5 alvos têm 120 ordens; 10 têm 3,6 milhões. Testar tudo deixa de caber rápido |
| **Branch and bound** | Busca que monta soluções aos poucos e abandona um ramo quando o começo dele já perde do melhor conhecido |
| **Oráculo** | Num backtest, a estratégia que conhece o futuro. Não existe na prática; serve para medir o teto possível |
| **Injeção de dependência** | Passar a peça trocável (aqui, a previsão) como parâmetro, em vez de fixá-la dentro da função |
| **Curadoria** | Dado conferido por gente numa fonte confiável, com registro de quem conferiu e quando |
| **Rider Switch** | Regra da Disney: um adulto vai na atração enquanto o outro espera com a criança, e depois trocam sem refazer a fila |
| **Alias (Pydantic)** | Nome alternativo de um campo. Aqui, o JSON em português (`altura_minima_cm`) vira o campo em inglês do código (`min_height_cm`) |
| **Wheel** | O pacote Python pronto para instalar. Conferir o que vai dentro dele é o que garante que um arquivo de dados chega à produção |
| **Proteção contra robôs** | Bloqueio que o site põe de propósito para clientes automatizados. Disfarçar-se de navegador para passar por ela é burlá-la |
| **Event loop** | O "maestro" do código assíncrono: alterna entre as tarefas enquanto cada uma espera rede ou banco. Objetos como travas pertencem ao loop que os usou primeiro |
| **ASGITransport** | Transporte do `httpx` que entrega a requisição direto ao app FastAPI, sem rede e no mesmo event loop de quem chama. Nos testes, substitui o `TestClient`, que roda o app num loop próprio |
| **Arquivo de lock** | Lista com a versão exata de cada dependência. Sem ele, cada instalação pega a versão mais nova permitida — foi assim que o SQLAlchemy 2.1 chegou sem aviso |
| **Tiles** | As imagens quadradas que um mapa web monta em mosaico. Já vêm pintadas pelo servidor, então o CSS não muda a cor delas |
| **GeoJSON** | Formato padrão de dados geográficos em JSON: pontos, linhas e polígonos em (longitude, latitude) — a ordem inversa do Leaflet |
| **Overpass API** | Serviço público de consulta aos dados do OpenStreetMap. Gratuito e mantido por voluntários: consulta uma vez, guarda em cache |
| **Douglas-Peucker** | Simplificação de linha: mantém só os pontos que desviam da reta mais que uma tolerância. Aqui, 1 m |
| **Contraste (WCAG)** | Razão de luminância entre texto e fundo, de 1:1 a 21:1. A norma de acessibilidade pede 4,5:1 para texto e 3:1 para gráficos |
| **ODbL** | A licença dos dados do OpenStreetMap: pode usar e redistribuir, desde que dê o crédito ("© OpenStreetMap contributors") |

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
| 20/09/2026 | **Previsão por extrapolação descartada, por medição** | Erra mais que usar a fila atual em todo horizonte — 2,5 vs 3,97 min em 10 min, e pior quanto mais longe |
| 20/09/2026 | O ranking **continua** usando a fila de agora | É o modelo vencedor no backtest; implementar a previsão teria piorado o produto |
| 20/09/2026 | Modelos perdedores ficam no código, documentados | Baseline ruim registrado evita que a próxima pessoa tente a mesma ideia do zero |
| 20/09/2026 | Passar a gravar o `forecast` da fonte | Único candidato não testado, e não dava para avaliá-lo sem histórico dele |
| 20/09/2026 | `queue_forecasts` guarda a **primeira** aparição de cada previsão | A fonte republica o mesmo perfil a cada consulta; sobrescrever destruiria a medida de antecedência |
| 20/09/2026 | Personalização no **`localStorage`**, sem conta de usuário | O app é usado no celular dentro do parque por algumas horas; exigir cadastro antes de responder mataria o produto |
| 20/09/2026 | "Já fui hoje" carimba a **data do parque** | Sem data, o visitante voltaria na semana seguinte com metade das atrações escondidas; e o dia é o do parque, não o do celular |
| 20/09/2026 | Visitadas saem do ranking, mas com aviso e "Mostrar" | Esconder sem avisar faz o app parecer quebrado |
| 20/09/2026 | A etiqueta "melhor escolha" pula as visitadas | Uma atração já feita não é a melhor escolha agora, por melhor que seja o número |
| 20/09/2026 | `[hidden] { display: none !important }` no CSS | A regra do navegador perde para qualquer classe com `display`; sete elementos do projeto dependiam do atributo |
| 20/09/2026 | A tela pede o ranking **inteiro** (`limit=0`) | Pedir 8 e filtrar depois esvaziava a lista ao marcar 8 visitadas; custo medido: 3,5 KB → 12,5 KB |
| 20/09/2026 | Filtrar as visitadas **no navegador**, não na API | Mandar os IDs para o servidor acoplaria a API ao estado do aparelho e contradiria a decisão desta fase |
| 20/09/2026 | No modo "Mostrar", as visitadas **somam-se** às sugestões | Se tomassem a vaga, revelar o que já foi feito custaria uma sugestão a cada marcação |
| 20/09/2026 | Alvos em **seção própria**, não no topo do ranking | São perguntas diferentes: "o que compensa agora" e "quando ir no que eu vim fazer" |
| 20/09/2026 | Alvos **não** ganham bônus no custo | Distorcer o número seria pior que assumir a mudança de critério |
| 20/09/2026 | Alvos **sem** carimbo de data, ao contrário das visitadas | Alvo é desejo, não acontecimento; lista de desejos que some à meia-noite é app que esquece |
| 20/09/2026 | O alvo sai do ranking | Repeti-lo gastaria uma das oito vagas com algo que o visitante acabou de ver |
| 20/09/2026 | A etiqueta "melhor escolha" não aparece entre os alvos | Ela compara o parque inteiro; sobre três atrações diria outra coisa |
| 20/09/2026 | `--sobre-profundo` criado, como o `--sobre-quente` | O roxo inverte no tema escuro; texto branco sobre lilás claro sumiria |
| 20/09/2026 | Seletor de alvos com o **catálogo completo** do parque | Marcar só pelo ranking deixava 27 de 35 atrações inalcançáveis |
| 20/09/2026 | A seção de alvos é **sempre visível**, com convite quando vazia | Escondida, a funcionalidade não existe para quem nunca tropeçou nela |
| 20/09/2026 | `<details>` nativo em vez de painel feito à mão | Abrir, fechar, foco por teclado e anúncio ao leitor de tela vêm de graça |
| 20/09/2026 | O catálogo **não** se reordena enquanto está aberto | Reordenar sob o dedo faz quem escolhe várias perder o lugar; espera reabrir |
| 20/09/2026 | O seletor funciona **antes** do GPS | `/attractions` não exige posição; a lista de desejos se monta a caminho do parque |
| 21/09/2026 | Filtros de **fila** e **caminhada**, não de custo total | Filtrar por custo é redundante com o ranking; as parcelas é que não são intercambiáveis |
| 21/09/2026 | O filtro **corta**, nunca reordena | Mudar o critério de ordenação não é filtrar — é outro produto |
| 21/09/2026 | Os alvos **escapam** do filtro | Esconder o que o visitante marcou como imperdível é discutir com uma escolha explícita |
| 21/09/2026 | Filtros são **globais**, não por parque | "Não quero andar muito" é sobre a pessoa; visitadas e alvos são sobre o parque |
| 21/09/2026 | Selo "ativos" no cabeçalho dos filtros | Filtro esquecido é indistinguível de parque vazio, e o app pareceria quebrado |
| 21/09/2026 | A lista vazia distingue **filtro** de **tudo visitado** | Dizer a frase errada esconde a causa em vez de explicá-la |
| 21/09/2026 | Popularidade = **fila média histórica**, no lugar da radicalidade | A fonte não traz intensidade; a média é dado nosso e já coletado. Verdade externa confere: as primeiras são TRON, Seven Dwarfs, Peter Pan e Space Mountain |
| 21/09/2026 | A faixa é **relativa ao parque**, nunca um limiar em minutos | 59% das medições caem entre 10h e 13h, o que infla a média absoluta — mas infla todas juntas, então a ordem sobrevive e o número não |
| 21/09/2026 | **Razão contra a mediana**, e não tercil por posição | Medido: 83% de estabilidade contra 74%. E o tercil *força* um terço em cada faixa, promovendo dez medianas a "principal" num parque que tem duas |
| 21/09/2026 | Mínimo de **12 medições** para classificar | Uma hora de coleta a 5 min. Abaixo disso a média é uma foto; o corte excluiu exatamente os shows e trens, e nenhuma atração de fila real |
| 21/09/2026 | `UNKNOWN` é faixa própria, **não** `QUIET` | Ausência de dado não é dado. Chamar de tranquila o que nunca medimos manda o visitante para uma fila de uma hora com a nossa bênção |
| 21/09/2026 | A popularidade **não reordena** o ranking | Mesma regra da tendência e dos alvos, e uma a mais: ela descreve a atração, o ranking responde sobre o momento |
| 21/09/2026 | **Oportunidade**: principal com fila abaixo da média dela | É a única combinação que muda a decisão de agora — e em 8 de 23 atrações o histórico discorda do "agora", então há o que dizer |
| 21/09/2026 | A oportunidade só vale para as **principais** | Uma tranquila abaixo da média é 4 min em vez de 7; anunciar isso gastaria a atenção com o que o visitante já sabia |
| 21/09/2026 | `MODERATE` não ganha selo | Um rótulo "mediana" em metade da lista vira ruído, e ruído gasta a atenção do selo que importa |
| 21/09/2026 | A média é **agregada no banco** (`AVG`/`GROUP BY`) | Exceção consciente à lição nº 3: agregar não descarta linha nenhuma, e 7 dias × 35 atrações são ~70 mil linhas para arrastar do Neon a cada recomendação |
| 21/09/2026 | Cache de **1 hora por parque**, global ao processo | Popularidade se move na escala de dias e é propriedade do parque; recalcular por visitante paga latência transcontinental por um número que não mudou |
| 21/09/2026 | Parque **sem histórico não entra no cache** | Guardar o vazio prenderia o resultado por uma hora justamente enquanto o coletor começa a preencher |
| 21/09/2026 | Ausência de `popularity` **libera** a atração no filtro | Sem banco a API devolve `null` em todas; reprovar esvaziaria a tela num ambiente que funciona, sem o visitante ter como adivinhar |
| 21/09/2026 | Desmarcar **todas** as faixas equivale a remarcar todas | Quem desmarca a última quer dizer "volte ao normal", não "não me mostre nada" |
| 21/09/2026 | Ícone de **pessoas** na linha de popularidade | O alvo já significa "vim por esta" no botão ao lado; o mesmo símbolo dizendo duas coisas na mesma linha |
| 21/09/2026 | **Perfil horário medido antes de projetar a Fase 8** | 13,58 min de erro entre a mesma atração na mesma hora em dias consecutivos, contra 2,50 do baseline. Corrigir o nível do dia reduz só 19% — a forma também muda |
| 21/09/2026 | O roteiro será de **3–4 paradas replanejadas**, não um plano do dia | Prever 8h à frente com ~11 min de erro por atração, acumulado em dez paradas, produz ficção — e ficção confiante é pior que nenhum plano |
| 21/09/2026 | Comparar **médias do parque entre dias é inválido** | Se a coleta não cobriu as mesmas atrações, a média se move sem a fila mudar. Só o par (atração, janela) é honesto — quase gerou a conclusão errada |
| 21/09/2026 | O 8.2 é **Orienteering com custo dependente do tempo**, não TSP | Escolhe subconjunto, tem janela de tempo, o custo do nó muda com a hora da chegada e os nós têm prêmios diferentes. A seção 4 supunha Caixeiro Viajante |
| 22/09/2026 | Skills do projeto em `.claude/skills/`, **versionadas** | Fluxos que se repetem viram instrução executável em vez de prosa no CLAUDE.md; e mostram a quem lê o repositório que o próprio processo é automatizado |
| 27/10/2026 | Ping principal no **cron-job.org**, a cada 5 min; `keep-alive.yml` vira reserva | Medido: o cron do GitHub rodou 244 vezes em 37 dias, com mediana de 4 h entre execuções, e o coletor gravou 7–23 ciclos por dia contra ~156 no horário do parque. Todos os jobs verdes |
| 27/10/2026 | Intervalo de **5 min**, e não 10 ou 15 | A hibernação é aos 15 min sem acesso; 5 tolera duas falhas seguidas, e 15 é o próprio limite |
| 27/10/2026 | Saúde da coleta se confere **no banco**, nunca no painel do job | O painel mostrou 100% de sucesso enquanto a coleta rodava a ~10%. Só o efeito (ciclos gravados) prova a causa |
| 27/10/2026 | O forecast da fonte **não** entra no ranking | Medido: no horizonte de uma caminhada (até 30 min) erra 9,52 min, contra 2,03 da fila atual. Confere com o 2,50 do backtest de 20/09 |
| 27/10/2026 | Para horizontes de **horas**, fonte e perfil horário empatam e batem a persistência | ~9–10 min contra ~14 acima de 2 h. Partindo os dias ao meio, cada um ganha numa metade — sem vencedor estável. A escolha fica para depois de uma semana de coleta contínua |
| 27/10/2026 | O perfil de avaliação **deixa de fora o dia avaliado** | Senão a média já contém a resposta e o modelo parece melhor do que é |
| 27/10/2026 | Fator de sinuosidade **1,3 mantido, agora medido** | Contra a rota pelas trilhas do OpenStreetMap em 595 pares do MK: erro de 0,58 min por trecho; o melhor fator único possível é 1,33, com 0,59 |
| 27/10/2026 | A matriz usa **linha reta × fator**, não roteamento sobre o OSM | O erro de caminhada (0,58 min) é pequeno diante do da fila (~9 min); roteador traria dependência, dado por parque e cobertura desigual fora da Disney |
| 27/10/2026 | Matriz **simétrica, calculada uma vez**, `KeyError` para id desconhecido | As atrações não se movem e o otimizador consulta os pares centenas de milhares de vezes; um tempo inventado seria usado sem desconfiar |
| 27/10/2026 | `travel_time_matrix` recebe **pontos, não `ParkCatalog`** | Mantém `geo.py` como "entra número, sai número"; quem conhece o catálogo é o módulo do roteiro |
| 27/10/2026 | **Backtest guloso × plano antes de escrever o otimizador** | Com ~9 min de erro na previsão de horas, o ganho de planejar podia ser engolido. Medido: -4,1% com persistência, teto de -7,6% com o oráculo |
| 27/10/2026 | O roteiro usa **persistência**, não o perfil horário | No backtest, planejar com o perfil rendeu -2,7% contra -4,1% supondo filas paradas. O ganho é de geografia |
| 27/10/2026 | Oráculo como **teto** no backtest | Mostra o máximo que qualquer previsão poderia somar (~7 min em 5 alvos). Sem ele, não se sabe se vale investir em previsão |
| 27/10/2026 | Busca **exata por *branch and bound***, não heurística | Com profundidade 5, até as 35 atrações do MK saem em ~70 ms; heurística trocaria a garantia de ótimo por velocidade de que não se precisa |
| 27/10/2026 | Profundidade máxima de **5 paradas** | Medido: 7 custaria 25 vezes mais; e o roteiro se refaz a cada parada concluída |
| 27/10/2026 | Previsão **injetada** (`WaitPredictor`) | Trocar de previsor não pode exigir tocar no otimizador — e só deve acontecer depois de um backtest |
| 27/10/2026 | Tempo em **minutos a partir de agora** no `core/itinerary.py` | O `core/` continua sem saber de fuso; quem chama converte |
| 27/10/2026 | Duração de atração **fixa em 8 min** (`RIDE_DURATION_MINUTES`) | A fonte não informa duração. Estimativa, com sensibilidade testada: 5, 8 e 15 min dão a mesma conclusão |
| 27/10/2026 | Medições que serão **repetidas** ficam versionadas em `scripts/medicoes/` | O backtest e a avaliação do forecast têm rodadas marcadas; reescrever de memória mediria algo ligeiramente diferente, e a comparação entre rodadas perderia o valor. Exploração de uma vez só continua no scratchpad |
| 27/10/2026 | Scripts de medição só acessam o banco por `_comum.consultar`, que **recusa escrita** | Eles leem o banco de produção; a trava do `conftest.py` protege a suíte, não um script solto |
| 27/10/2026 | O simulador chama o **`plan_itinerary` de produção** | O backtest precisa medir o código que vai para o ar. Reproduziu o ensaio exatamente (178 cenários, mesmos números) |
| 27/10/2026 | `tzdata` como dependência de desenvolvimento | O Windows não traz a base de fusos, e a rodada de 03/11 atravessa o fim do horário de verão de Orlando |
| 27/10/2026 | **Fase 9 — Perfil do visitante** | Com filas niveladas, o ranking vira "o mais perto", que qualquer um vê no mapa. O app sabe o que a atração custa, não o que ela vale para quem pergunta |
| 27/10/2026 | O perfil é **perguntado, não inferido** | Inferência erra, e filtro silencioso repete a lição da 7.3. A inferência pode vir como sugestão visível |
| 27/10/2026 | **Duas perguntas**, ambas puláveis | Altura da criança mais baixa e tipo de atração. Cada pergunta a mais é um visitante a menos que chega à resposta |
| 27/10/2026 | Altura **marca** ("só os adultos"), não esconde | O grupo pode se dividir (*Rider Switch*). Mas a atração não ganha o destaque de "melhor escolha", que é para o grupo todo |
| 27/10/2026 | Curadoria **conferida na listagem oficial**, nada de memória | A memória e os sites de terceiros diziam 102 cm para a Big Thunder; a busca, 102 para a Magic Carpets. A fonte oficial diz 97 e "Any Height" |
| 27/10/2026 | **Sem raspagem** do site da Disney | O endpoint interno não responde a cliente automatizado; disfarçar a requisição seria burlar um bloqueio. O dado veio de capturas de tela da listagem pública |
| 27/10/2026 | Intensidade **por regra escrita** sobre as etiquetas oficiais | Classificação verificável, não opinião. "Dark" e "Spinning" fora: escuro é sensorial, e a Disney marca Buzz e Mad Tea Party igualmente como "Spinning" |
| 27/10/2026 | Guardar as **etiquetas**, não a classificação | A regra fica num lugar só; mudá-la não exige refazer a curadoria |
| 27/10/2026 | Só a linha **conferida** conta | Exige data e autor. Uma altura errada manda uma criança para uma fila em que ela não entra |
| 27/10/2026 | Atração sem curadoria **não tem intensidade** | A regra do `UNKNOWN` da 7.4: chamá-la de tranquila mandaria quem pediu "só tranquilas" para uma montanha-russa |
| 27/10/2026 | Peter Pan **moderada**, Haunted Mansion **tranquila**, Seven Dwarfs **radical** | Revisto com o Gabriel. Deixar o Peter Pan tranquilo arrastaria junto a Pirates, que tem uma queda de verdade no escuro |
| 27/10/2026 | Curadoria em **`data/`**, empacotada com o código | Dado conferido muda por revisão, com commit e autor, e passa pelos testes. Nem fonte externa (`clients/`) nem acumulado (`storage/`) |
| 27/10/2026 | A API **descreve, não decide** | `min_height_cm` e `intensity` saem em toda atração; nada some nem é reordenado. Quem decide é o perfil, na tela, como os filtros da 7.3 |
| 27/10/2026 | Primeira versão **focada no Magic Kingdom** | Decisão do Gabriel: só o MK tem curadoria e histórico. Nos outros parques o app seria a "lista de filas" que a Fase 9 critica. Tirar o seletor, ou limitá-lo a parques igualmente famosos, está em consideração |
| 27/10/2026 | Redesenho: **uma tela, dois estados**, não duas páginas | O app abre mostrando o parque (Fase 5). Cadastro em página separada poria um formulário entre o visitante e a primeira resposta |
| 27/10/2026 | **Desenhar antes de codificar** (Claude Design), com o prompt versionado | O prompt carrega as regras que o código já garante, para o design não propor o que a implementação teria de desfazer. Versionado porque o trabalho continua em outra máquina |
| 27/10/2026 | Nada que imite a **marca Disney** no design | Projeto independente; portfólio público não pode parecer produto oficial |
| 28/10/2026 | Testes de API chamam o app pelo **`ASGITransport`**, não pelo `TestClient` | O SQLAlchemy 2.1 recusa uma conexão usada por dois event loops, e o `TestClient` roda o app num loop à parte enquanto o teste grava no banco pelo outro. Exceção: `test_collector`, que precisa do `lifespan` |
| 28/10/2026 | Corrigir os testes em vez de travar `sqlalchemy<2.1` | A trava esconderia o defeito, que era do desenho dos testes, e teria de sair um dia. Em produção há um loop só (o do uvicorn), então o app não muda |
| 28/10/2026 | Python 3.13 instalado pelo **`py install 3.13`**, ao lado do 3.14 | O gerenciador oficial do Windows instala versões lado a lado sem `winget` nem administrador; o `.venv` segue na versão mais alta do CI |
| 28/10/2026 | Paleta **algodão-doce**: 3c no modo claro, 3b no escuro | Ideia do Gabriel (azul, rosa e amarelo pastel). A cor ganha significado: azul é caminhada, rosa é fila, amarelo é destaque — o mesmo que o pontilhado e a cápsula já diziam pela forma |
| 28/10/2026 | Pastel **só em fundo**; texto usa o tom escuro da mesma cor | Rosa pastel sobre branco dá 1,44:1, e texto pede 4,5:1. Os 24 pares de cada tema foram medidos pela fórmula da WCAG |
| 28/10/2026 | `--glow` dividido em `--glow-ink` (texto) e `--on-glow` (texto sobre ele) | A mesma cor era o número do cartão e o fundo do botão; num cartão claro, um papel contradiz o outro |
| 28/10/2026 | Mapa **real, sem tiles**, em vez do mapa ilustrado do Claude Design | O desenho tem geografia inventada: quebraria o "tocar no mapa define a posição" e o ponto do GPS. Os tiles do OSM já vêm pintados e brigam com a paleta. O Leaflet fica, desenhando um GeoJSON do OSM com as variáveis CSS do tema |
| 28/10/2026 | O GeoJSON é extraído **uma vez** e versionado em `web/mapas/` | A Overpass é pública e gratuita; o app nunca a consulta em tempo real. ~70 KB comprimidos |
| 28/10/2026 | A simplificação **preserva os cruzamentos** das trilhas | 1054 cruzamentos ficavam no meio de uma trilha; apagá-los partiria a rede da rota. Medido: 624 de 624 preservados |
| 28/10/2026 | Praça (`area=yes`) é desenhada como **área**; via larga e calçada têm traços diferentes | 63% do traçado é `footway` e 78 trilhas eram contornos de praça: com a mesma espessura, a Fantasyland virava uma malha |
| 28/10/2026 | A rota no mapa segue as trilhas (Dijkstra), mas **só desenha** | O tempo de caminhada continua vindo da API (linha reta × 1,3). Trocá-lo pela distância das trilhas mudaria o ranking — pede medição antes. A mediana medida foi 1,31× a linha reta |
| 28/10/2026 | Rótulos: número sempre, **nome só onde couber** | Com geografia real, vizinhas de verdade se sobrepõem. Cada nome tenta quatro lados na ordem do roteiro e some se não couber; o roteiro abaixo do mapa dá o nome de cada número |
| 28/10/2026 | "Quero emoção" esconde as tranquilas; "Tranquilas" esconde só as radicais | Decisões do Gabriel. As moderadas (Peter Pan, Pirates, Barnstormer) têm quedas pequenas e ficam. Esconder 27 de 35 só é aceitável porque o aviso diz quantas e deixa mostrar |
| 28/10/2026 | Perfil **global**, como os filtros, e não por parque | "A criança tem 95 cm" é sobre o grupo. Visitadas e alvos são por parque porque descrevem o parque |
| 28/10/2026 | Sem curadoria + criança no grupo = "altura mínima não conferida" | Calar seria ler "não sabemos" como "pode ir". Mas a atração continua elegível ao destaque: fora do Magic Kingdom nada tem curadoria, e o destaque sumiria |
| 28/10/2026 | Painel do perfil em `<dialog>`, escolhas em rádios | Esc, foco preso e anúncio ao leitor de tela vêm do navegador; rádio já é escolha exclusiva com setas do teclado |
| 28/10/2026 | Pular o perfil conta como resposta | Perguntar de novo a cada visita seria insistir com quem disse "agora não". O botão "Seu grupo" continua à vista |
| 28/10/2026 | `--ambar` vira o amarelo de destaque nos dois temas, com tinta própria (`--sobre-ambar`) | A regra da paleta (amarelo destaca). Dividir o `--sobre-quente` com a cor de ação faria um dos dois ilegível: a ação é escura no claro, o amarelo pede tinta escura |
| 28/10/2026 | Degradês de duas cores viram sólidos | Índigo → amarelo com texto branco seria ilegível na metade amarela |
| 28/10/2026 | `rota.js` e `rotulos.js` como objetos globais, sem módulos ES | O app não tem etapa de build, e os outros scripts (`preferencias.js`) já seguem esse padrão |
| 28/10/2026 | Nomes do mapa cortados com reticências | Inteiro, "Prince Charming Regal Carrousel" não cabia em lado nenhum, e a regra escondia justo o da primeira colocada |
| 28/10/2026 | Testes esperam `data-rotulos="prontos"`, não um tempo fixo | No meio da animação de zoom os nomes estão em trânsito; tempo fixo é a receita do teste intermitente |
| 28/10/2026 | Tiles interceptados nos testes | Eles iam à internet desde a Fase 5, furando a regra de que nenhum teste toca a internet |
| 28/10/2026 | Só o Magic Kingdom: seletor fora da tela, código atrás de uma chave | Decisão do Gabriel. A chave (`MOSTRAR_SELETOR_DE_PARQUES`) mantém o código dos outros parques vivo e testado (`abrir(..., seletor=True)`), sem caminho na interface |
| 28/10/2026 | A lista inteira num painel (`<dialog>`), aberto por "Todas as filas · N" | Decisão do Gabriel, como no design: a tela principal fica só com a resposta. O número no botão diz que a lista existe |
| 28/10/2026 | O cartão do próximo passo some quando não há melhor escolha | O aviso distingue as quatro causas de lista vazia; o cartão repetiria só uma |
| 28/10/2026 | "Já fui" do cartão com 5 s para desfazer | O cartão troca de atração na hora, e o toque errado de quem usa uma mão só ficaria sem volta |
| 28/10/2026 | "entra às HH:MM", e não "lá às" (como no design) | Diz sem ambiguidade o que a hora é: agora + caminhada + fila. No fuso do parque |
| 28/10/2026 | Desenho do mapa numa camada (*pane*) própria, sem `bringToBack()` | O `bringToBack()` num grupo invertia a pilha: gramado sobre as trilhas, véu embaixo de tudo. Bug real, achado numa captura depois de o Gabriel estranhar o mapa |
| 28/10/2026 | Contorno do parque e áreas temáticas do OSM, numa segunda consulta em cache | Sem referência, o visitante não sabe em que canto está. Os nomes das áreas são fato geográfico, escritos na fonte do app — nada imita a marca |
| 28/10/2026 | Áreas com 17 mil m² ou mais | Medido: a menor das seis áreas tem 20 mil m², o maior recanto (Storybook Circus, dentro da Fantasyland) 14 mil. O corte é o meio |
| 28/10/2026 | Mapa enquadra o visitante e as três primeiras, com zoom em quartos | No parque inteiro os números cabiam em centímetros. Com zoom inteiro, o enquadramento caía um nível abaixo do que cabia |
| 28/10/2026 | Nome só nas três primeiras; da quarta em diante, número menor | Oito nomes no celular eram uma sopa de letras. As três são as que o visitante compara; a lista dá o nome de todas |
| 28/10/2026 | Tema claro refeito pela especificação "Algodão Doce": página baunilha, cartão pastel (rosa → azul), pinos brancos com aro azul-noite | O claro da 3c seguia "muito abaixo" do escuro, mesmo depois da casca e de três paletas de mapa testadas. O cartão índigo era um "buraco negro" na tela clara e puxava o olho para longe do mapa. O escuro (3b) não muda: os tokens novos herdam nele os valores de antes |
| 28/10/2026 | Quatro tons da especificação escurecidos o mínimo para passar na WCAG | Rosa do número (2,7 → 3,7:1, texto grande), azul de link (3,1 → 4,6:1), pontilhado do cartão (2,8 → 3,5:1) e rota (2,9 → 3,0:1). O "+" ficou azul: branco sobre o rosa forte dá 2,9:1 |
| 28/10/2026 | Posição no cartão em frase ("Ponto de partida definido pelo GPS"), coordenadas no `title` | Coordenada não diz nada a quem está no parque; quem precisar conferir ainda acha o número |
| 28/10/2026 | Casca nas trilhas, só no tema claro | Branco sobre claro some sem borda; no escuro o caminho já é o que tem mais luz, e o Gabriel o achou ideal como estava |
| 28/10/2026 | "Todas as filas" como barra fixa no pé da tela do celular, com cor própria | Sobre o mapa e pequeno, se perdia no desenho. No pé, fica à vista em qualquer ponto da rolagem e sob o polegar. Com a cor de ação, sumia sobre o cartão índigo |
| 28/10/2026 | Computador: mapa fixo à direita, coluna de 460 px com a lista aberta | O layout de celular esticado deixava dois terços da tela vazios. O painel poupava altura, que no computador sobra. Mesmo `<dialog>`, sem o modo modal: um só HTML |

---

*Mantido por Gabriel de Angelis, com Claude Code. Última atualização: 28/10/2026.*

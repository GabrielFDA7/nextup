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

**Fases 0 a 5 concluídas.** A Fase 6 está em andamento: **6.1 (storage), 6.2 (coletor) e
6.3 (tendência)** estão prontos — o histórico é gravado no Neon e a justificativa já diz
"caiu de 45 para 20". O próximo é o **6.4 (rota de histórico) ou o 6.5 (gráfico)**. O
fatiamento da fase está na seção 7 de `docs/PROJETO.md`.

**339 testes passando**: 309 na suíte rápida (~5s) e 30 de interface em navegador (~35s).
CI verde em Python 3.11, 3.12 e 3.13, com job separado para o E2E.

Já existe e funciona:
- Estrutura completa em `src/nextup/` com as 4 camadas
- `config.py` com toda a configuração centralizada
- `core/geo.py` — Haversine, sinuosidade e tempo de caminhada
- `models/` — `Destination`, `ParkCatalog` (com coordenadas GPS) e `LiveData`
- `clients/cache.py` — cache com TTL, relógio injetável
- `clients/themeparks.py` — cliente assíncrono, backoff exponencial, erros próprios
- `core/recommender.py` — **o coração**: ranqueia por `custo_total = caminhada + fila`
- `core/trends.py` — tendência da fila (subindo/caindo/estável), função pura
- `cli.py` — comando `nextup`. Sem coordenadas lista filas; com `--lat/--lon` recomenda.
  `nextup --parks` lista os IDs de parque
- `api/` — FastAPI com 4 rotas sob `/api`: `health`, `destinations`,
  `parks/{id}/attractions` (o parque **sem** exigir posição, com `bounds` para o mapa) e
  `parks/{id}/recommendations?lat&lon&limit`. Docs automáticas em `/docs`
- `web/` — interface em HTML/CSS/JS puro, servida pelo próprio FastAPI. Geolocation,
  mapa Leaflet, e **tocar no mapa define a posição** (saída para quem nega o GPS).
  Abre mostrando o parque antes de qualquer permissão; busca no seletor; o mapa
  reenquadra ao trocar de parque
- `storage/` — persistência do histórico de filas (Fase 6). `tables.py` (desenho),
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
- `tests/test_web_e2e.py` — 30 testes em Chromium real (`pytest -m e2e`)
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

**Limitação do plano gratuito:** hiberna após ~15 min sem acesso. Mitigado pelo workflow
`keep-alive.yml`, que chama `/api/health` a cada 10 min. Dois cuidados: o ping usa
`/api/health` porque essa rota não consulta a ThemeParks.wiki, e o GitHub desativa
agendamentos em repositórios públicos parados há 60 dias.

**Refino visual feito (13/09/2026).** Direção escolhida pelo Gabriel: "personalidade de
parque" — paleta de pôr do sol (coral, âmbar, roxo profundo), fonte Outfit, cantos
arredondados, ícones SVG e marcadores numerados no mapa. Tema escuro revisado: os fundos
quentes clareiam nele, então a tinta por cima inverte via `--sobre-quente` — sem isso, o
botão principal ficaria branco sobre coral claro.

**Pendência:** **Fase 6**, passos 6.4 a 6.6 — rota de histórico, gráfico e previsão na
chegada.

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
> coleta, então o `keep-alive.yml` deixou de ser só cosmético: é ele que mantém o
> histórico contínuo. Se o GitHub desativar o agendamento por inatividade do repositório,
> aparecem buracos silenciosos no histórico.

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
3. O mesmo bug de contagem (`available` refletindo o `limit` em vez do total) apareceu
   **três vezes**, no CLI, na API e quase no frontend. O padrão é sempre o mesmo: pedir a
   lista já cortada e depois medir o tamanho dela. Peça tudo, corte na exibição.
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
pytest -m "not e2e"    # esperado: 309 testes, ~5s
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
pytest -m e2e          # esperado: 30 testes, ~35s
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

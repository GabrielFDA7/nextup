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

**Fases 0 a 4 concluídas** (12/09/2026). Fases 5 e 6 descritas em `docs/PROJETO.md`,
seção 7. **194 testes passando**: 173 na suíte rápida (~7s) e 21 de interface em
navegador (~50s). CI verde em Python 3.11, 3.12 e 3.13, com job separado para o E2E.

Já existe e funciona:
- Estrutura completa em `src/nextup/` com as 4 camadas
- `config.py` com toda a configuração centralizada
- `core/geo.py` — Haversine, sinuosidade e tempo de caminhada
- `models/` — `Destination`, `ParkCatalog` (com coordenadas GPS) e `LiveData`
- `clients/cache.py` — cache com TTL, relógio injetável
- `clients/themeparks.py` — cliente assíncrono, backoff exponencial, erros próprios
- `core/recommender.py` — **o coração**: ranqueia por `custo_total = caminhada + fila`
- `cli.py` — comando `nextup`. Sem coordenadas lista filas; com `--lat/--lon` recomenda.
  `nextup --parks` lista os IDs de parque
- `api/` — FastAPI com 3 rotas sob `/api`: `health`, `destinations` e
  `parks/{id}/recommendations?lat&lon&limit`. Docs automáticas em `/docs`
- `web/` — interface em HTML/CSS/JS puro, servida pelo próprio FastAPI. Geolocation,
  mapa Leaflet, e **tocar no mapa define a posição** (saída para quem nega o GPS)
- `tests/test_arquitetura.py` — a regra de dependência é verificada automaticamente
- `tests/test_web_e2e.py` — 21 testes em Chromium real (`pytest -m e2e`)
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

**Duas pendências combinadas com ele:**
1. **Refino visual da interface** (12/09/2026) — ela funciona e foi aprovada, mas ele
   pediu para "deixar bonito" depois. Fazer antes de divulgar o link publicamente.
2. **Fase 6** — histórico de filas, tendências e previsão.

**Três lições dos dados reais, que valem para as próximas fases:**
1. `OPERATING` **não** garante tempo de fila — 9 das 35 atrações do Magic Kingdom
   estavam abertas sem fila medida. Use sempre `is_rankable`.
2. Validar **antes** de guardar no cache. O contrário já causou bug aqui.
3. O mesmo bug de contagem (`available` refletindo o `limit` em vez do total) apareceu
   **três vezes**, no CLI, na API e quase no frontend. O padrão é sempre o mesmo: pedir a
   lista já cortada e depois medir o tamanho dela. Peça tudo, corte na exibição.

---

## Arquitetura — a regra que não se quebra

```
api  →  core  →  models  ←  clients
```

A dependência é **unidirecional**:

- **`core/`** é o cérebro (distância, score, ranking) e **não importa nada de rede**.
  Recebe objetos, devolve ordenação. Por isso seus testes rodam offline, em milissegundos.
  *Se você sentir vontade de importar `httpx` dentro de `core/`, o desenho está errado.*
- **`clients/`** é o único lugar que sabe que a ThemeParks.wiki existe. Trocar de fonte de
  dados deve afetar só essa pasta.
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
pytest -m "not e2e"    # esperado: 173 testes, ~7s
ruff check .
ruff format --check .
```

Subir a aplicação inteira (API + interface):

```bash
uvicorn nextup.api.main:app --reload     # http://127.0.0.1:8000
```

Testes de interface (exigem `pip install -e ".[dev,e2e]"` e `playwright install chromium`):

```bash
pytest -m e2e          # esperado: 21 testes, ~50s
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

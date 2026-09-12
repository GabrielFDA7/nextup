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

**Fase 0 concluída** (12/09/2026), incluindo o ambiente local (12/09/2026). Fases 1 a 6
descritas em `docs/PROJETO.md`, seção 7.

Já existe e funciona:
- Estrutura completa em `src/nextup/` com as 4 camadas
- `config.py` com toda a configuração centralizada
- `core/geo.py` — Haversine, sinuosidade e tempo de caminhada, **17 testes passando**
- CI no GitHub Actions (ruff + pytest em Python 3.11, 3.12, 3.13)
- README, licença MIT, `.gitignore`, `.gitattributes`, `.env.example`
- `.venv` local com **Python 3.13** (mesma versão mais alta testada no CI), criada em
  12/09/2026 — `pytest`, `ruff check` e `ruff format --check` rodados e aprovados
  localmente pela primeira vez

**Próximo passo: Fase 1 — cliente da API.** Implementar `clients/themeparks.py` e
`clients/cache.py`, com os modelos `pydantic` em `models/`. Conceitos novos a ensinar
nesta fase: cache com TTL, backoff exponencial e **como testar código de rede sem
depender da internet** (`respx`).

**Sobre o lint:** não há mais pendência de nenhum tipo — `ruff` e `pytest` já rodaram
tanto no CI (commit `b33c3b6`, Python 3.11/3.12/3.13) quanto localmente (12/09/2026,
Python 3.13), com o mesmo resultado.

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
pytest                 # esperado: 17 testes passando
ruff check .
ruff format --check .
```

A partir da Fase 3, subir a API com:

```bash
uvicorn nextup.api.main:app --reload
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

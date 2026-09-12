# NextUp 🎢

**Para qual atração eu devo ir agora?**

NextUp responde essa pergunta em tempo real, cruzando o tempo de fila de cada atração com
a distância que você precisa percorrer até ela — e devolve a que custa menos tempo do seu
dia.

[![CI](https://github.com/GabrielFDA7/nextup/actions/workflows/ci.yml/badge.svg)](https://github.com/GabrielFDA7/nextup/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## O problema

Visitantes de parques como Walt Disney World gastam boa parte do dia em filas. Os tempos
de espera são voláteis: uma atração com 90 minutos às 11h pode cair para 15 às 11h40,
porque um show terminou do outro lado do parque e a multidão migrou.

Hoje existe um serviço informal para contornar isso: um consultor monitora um site de
filas e avisa o cliente por WhatsApp — *"corre pro Space Mountain, caiu pra 20 minutos"*.

É um humano executando, em tempo real, um algoritmo. **NextUp é esse algoritmo.**

## O diferencial

A pergunta óbvia seria "qual atração tem a menor fila?" — e ela leva à decisão errada.

> A menor fila do parque está com 5 minutos, mas fica a 900 metros de onde você está.
> Você caminha 15 minutos para economizar 10. Perdeu tempo.

NextUp responde a pergunta certa: **qual atração me custa menos tempo até eu estar sentado
no brinquedo?**

```
custo_total = tempo_de_caminhada + tempo_de_fila
```

É isso que o consultor humano faz de cabeça sem perceber — e é o que separa o NextUp de
um site de tempos de espera comum.

## Como funciona

```
Você (GPS do navegador)
        │
        ▼
   API FastAPI  ──▶  Cache  ──(expirado)──▶  ThemeParks.wiki
        │              │
        │         (válido)
        ▼              │
   Normalização ◀──────┘
        │
        ▼
   Motor de Ranking   ◀── Haversine + filtros + custo total
        │
        ▼
   Top 5 atrações, com a justificativa de cada uma
```

Atrações fechadas, em manutenção ou fora do horário são descartadas antes de qualquer
cálculo. O resultado vem com explicação legível — *"4 min de caminhada + 20 min de fila =
24 min"* — porque uma recomendação sem motivo não gera confiança.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.11+, FastAPI, httpx, Pydantic v2 |
| Frontend | HTML, CSS e JavaScript puro + Leaflet |
| Testes | pytest, respx |
| Qualidade | ruff |
| Infra | Docker, GitHub Actions |

Fonte de dados: [ThemeParks.wiki](https://themeparks.wiki) — API pública e gratuita.

## Rodando localmente

```bash
git clone https://github.com/GabrielFDA7/nextup.git
cd nextup

python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

Rodar os testes:

```bash
pytest
```

Verificar qualidade do código:

```bash
ruff check .
ruff format --check .
```

Subir a API (a partir da Fase 3):

```bash
uvicorn nextup.api.main:app --reload
```

Documentação interativa da API em <http://localhost:8000/docs>.

## Estrutura do projeto

```
src/nextup/
├── clients/    # Conversa com a ThemeParks.wiki (HTTP + cache)
├── models/     # Os dados já validados e tipados
├── core/       # Regra de negócio: distância, score, ranking — sem rede
└── api/        # Exposição HTTP
web/            # Interface do usuário
tests/          # Testes automatizados
```

As camadas dependem em **sentido único**: `api → core → models ← clients`.

O `core/` é o cérebro e não importa nada de rede, então seus testes rodam offline em
milissegundos. O `clients/` é o único lugar que sabe que a ThemeParks.wiki existe — trocar
a fonte de dados afeta só essa pasta.

## Roadmap

- [x] **Fase 0** — Fundação: repositório, estrutura, qualidade, CI
- [ ] **Fase 1** — Cliente da API com cache e tratamento de falhas
- [ ] **Fase 2** — Motor de recomendação
- [ ] **Fase 3** — API HTTP
- [ ] **Fase 4** — Interface web com mapa
- [ ] **Fase 5** — Docker e deploy público
- [ ] **Fase 6** — Histórico de filas, tendências e previsão

Contexto completo, decisões técnicas e detalhes de arquitetura em
[docs/PROJETO.md](docs/PROJETO.md).

## Licença

[MIT](LICENSE).

---

> **Aviso:** projeto pessoal e educacional, sem qualquer vínculo, patrocínio ou aprovação
> da The Walt Disney Company ou de qualquer operador de parque. Consome exclusivamente
> dados públicos da ThemeParks.wiki.

# Medições

Os scripts que produziram os números por trás das decisões do NextUp. Cada limiar, fator
ou escolha de algoritmo documentado em `docs/PROJETO.md` saiu de uma medição; aqui está
**como** ela foi feita, para quem quiser conferir — ou repetir quando houver mais dado.

Não são código de produção: não rodam no servidor e não entram na suíte de testes. Ficam
versionados porque **algumas medições precisam ser repetidas** (a avaliação do forecast e
o backtest do roteiro serão refeitos sobre a coleta contínua), e uma segunda versão
reescrita de memória mediria algo ligeiramente diferente da primeira.

## Antes de rodar

```bash
pip install -e ".[dev]"     # inclui o tzdata, que o Windows não traz
```

Os scripts que leem o banco usam a `NEXTUP_DATABASE_URL` do `.env` — **o banco de
produção** — e consultas próprias do Postgres. Todo acesso passa por
`_comum.consultar`, que **recusa qualquer comando que não seja leitura** antes de abrir
a conexão. A trava do `tests/conftest.py` protege a suíte, não um script solto.

## Os scripts

| Script | Pergunta | Lê o banco | Resultado em |
|---|---|---|---|
| `auditoria_coleta.py` | A coleta está contínua? (`--horas 3` para a checagem rápida) | sim | PROJETO.md, Fase 8, item 8.0 |
| `avaliar_forecast.py` | O forecast da fonte bate a persistência? E o perfil horário? | sim | PROJETO.md, Fase 6 (avaliação do forecast); `core/forecast.py` |
| `simular_roteiro.py` | Planejar as próximas paradas bate o guloso? | sim | PROJETO.md, Fase 8, item 8.2; `core/itinerary.py` |
| `medir_sinuosidade.py` | O fator 1,3 confere com as trilhas reais (OpenStreetMap)? | não | PROJETO.md, Fase 8, item 8.1; `config.py` |
| `medir_desempenho_roteiro.py` | Quanto custa o otimizador, e quanto a poda economiza? | não | PROJETO.md, Fase 8, item 8.2; `config.py` |

Rode da raiz do repositório, por exemplo:

```bash
python scripts/medicoes/auditoria_coleta.py --horas 3
```

## Agenda

- **30/10/2026** — `simular_roteiro.py --desde 2026-10-28 --gap 20`: preliminar sobre a
  coleta contínua (só dias úteis).
- **03/11/2026** — o mesmo, mais `avaliar_forecast.py --desde 2026-10-28`: a rodada
  decisiva, com o fim de semana. Antes de concluir, `auditoria_coleta.py` para conferir
  que a coleta não teve buracos.

## Regras da casa para medir

As mesmas da skill `medir-antes-de-implementar`: compare contra uma verdade externa,
nunca contra a conta do próprio código; compare pelo menos dois critérios, com um
baseline honesto; parta os dados ao meio e confira se a conclusão se repete; e registre
o resultado — inclusive o negativo — onde ele vai ser lido daqui a seis meses.

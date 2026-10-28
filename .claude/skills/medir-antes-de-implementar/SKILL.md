---
name: medir-antes-de-implementar
description: Use antes de escolher um algoritmo, um limiar, um critério de classificação ou qualquer número que vá parar no código do NextUp — e sempre que se pegar prestes a dizer "acho que", "normalmente" ou "faz sentido usar X". Também ao avaliar se uma feature nova tem dado que a sustente. Cobre como escrever o script de medição, contra o que comparar, e onde registrar o resultado (inclusive quando ele for negativo).
---

# Medir antes de implementar

O NextUp tem um banco de produção com histórico real. **Toda vez que um número foi
escolhido por intuição neste projeto, a medição depois mostrou outra coisa.** Toda vez que
foi medido antes, o resultado sustentou a decisão por meses.

Exemplos que valem como prova:

| O que parecia óbvio | O que a medição mostrou |
|---|---|
| Comparar a fila com a medição anterior | 118 de 189 variações eram **zero** — diria "estável" quase sempre. Daí a janela de 30 min |
| Extrapolar a tendência melhora a previsão | **Erra mais** que usar a fila atual, em todo horizonte (6.6) |
| Tercil por posição reparte bem as faixas | 74% de estabilidade contra 83% da razão sobre a mediana, e ainda **força** um terço em cada faixa (7.4) |
| Perfil horário permite montar o roteiro do dia | ~11 min de erro entre dias, contra 2,50 do baseline — inviável por ora |
| O cron do GitHub mantém o Render acordado | Rodava a cada **~4 h**, sempre verde; o coletor ficou ~90% parado por um mês |
| O fator de sinuosidade 1,3 é chute | Medido contra o OpenStreetMap: **estava certo** (o melhor possível é 1,33) |
| O roteiro ganha do guloso por prever a fila | Ganha pela **geografia**; planejar com o perfil horário rende *menos* que supor filas paradas |

---

## Como medir

**1. Primeiro, olhe `scripts/medicoes/`.** Se já existe um script para a pergunta, rode-o
em vez de escrever outro — uma segunda versão mede algo ligeiramente diferente da
primeira, e a comparação entre rodadas perde o valor.

**2. Onde o script novo mora depende de se ele vai ser repetido:**

- **Exploração de uma vez só** → no scratchpad da sessão. Vai embora; o que fica é a
  conclusão, registrada no `PROJETO.md`.
- **Medição que será repetida** (há uma data marcada, ou a conclusão depende de mais
  dado) → em `scripts/medicoes/`, versionada, com o cabeçalho dizendo a origem, onde está
  o resultado e quando repetir. Adicione a linha na tabela do `README.md` da pasta.

Na dúvida, comece no scratchpad e promova quando a repetição aparecer.

**3. Ler o banco de produção é seguro; escrever não.** A medição é sempre `SELECT`. Nos
scripts versionados, use `_comum.consultar`, que recusa qualquer comando que não seja
leitura antes de abrir a conexão. Num script de scratchpad, o `config.py` já carrega o
`.env`, então basta:

```python
from nextup.storage import connection, create_engine
motor = create_engine()
async with connection(motor) as conexao:
    ...
```

> ⚠️ A suíte tem uma trava no `conftest.py` que força SQLite em memória. Ela protege os
> testes, **não** protege um script solto. Confira que o script só lê.

> ⚠️ **Antes de medir sobre o histórico, confira a coleta:**
> `python scripts/medicoes/auditoria_coleta.py --horas 3`, ou sem a opção para o
> período inteiro. ~12 ciclos por hora com o parque aberto é coleta contínua.

> ⚠️ **Fuso do parque, nunca deslocamento fixo.** `_comum.fuso_mk()` lê o fuso do
> catálogo. O horário de verão de Orlando acaba no primeiro domingo de novembro.

**3. Imprima a tabela inteira, não só o agregado.** A média esconde o caso que muda a
decisão. Foi olhando linha a linha que apareceu o `n=3` que invalidava uma faixa, e o
`UNKNOWN` com média preenchida.

**4. Compare pelo menos dois critérios.** Um número sozinho não é evidência de nada —
evidência é um critério ganhando de outro. E prefira um **baseline honesto**: a
persistência simples (repetir o valor atual) é a régua que a 6.6 estabeleceu.

**5. Meça a estabilidade, não só o ajuste.** Partir os dados ao meio e conferir se a
conclusão se repete nas duas metades é o teste mais barato contra se enganar sozinho. Foi
ele que escolheu a mediana no lugar do tercil.

---

## A regra que não se quebra

> **Compare contra uma verdade externa, nunca contra a conta do próprio código.** Se a
> medição repete a lógica que ela deveria julgar, as duas erram juntas e nada é detectado.

Na 7.4 a verdade externa foi que TRON, Seven Dwarfs, Peter Pan e Space Mountain são
reconhecidamente as principais do Magic Kingdom — fato do mundo, não do código. Em
`tests/test_geo.py` são as distâncias Paris–Londres e um grau de latitude.

---

## Depois de medir

**Registre o número onde ele vai ser lido daqui a seis meses:**

1. **No cabeçalho do módulo**, com a tabela que sustenta a escolha. Veja
   `core/trends.py`, `core/forecast.py` e `core/popularity.py` — os três abrem com as
   medições que os originaram.
2. **Na seção 10 do `PROJETO.md`**, uma linha por decisão, com o número na coluna do
   motivo.
3. **Num teste**, quando a conclusão puder ser desfeita sem ninguém notar.
   `tests/test_forecast.py` existe só para fixar um resultado negativo.

**Resultado negativo é resultado.** A 6.6 terminou sem mudar o ranking, e é uma das partes
mais fortes do projeto: mostra que houve hipótese, medição e uma decisão sustentada por
número. Documente com o mesmo cuidado de um resultado positivo, e deixe o aviso que
impede alguém de refazer o caminho sem repetir o backtest.

---

## Dois vieses conhecidos destes dados

**A coleta é enviesada para o meio-dia.** 59% das medições caem entre 10h e 13h locais,
porque é quando o Render está acordado. Isso infla qualquer média absoluta — mas infla
todas as atrações juntas, então **comparações relativas sobrevivem e valores absolutos
não**. Prefira concluir sobre ordem e razão, não sobre minutos.

**As fixtures são todas do Magic Kingdom**, onde 86 de 86 entidades têm coordenada. Um bug
que deixou o Disneyland Paris inacessível desde a Fase 1 sobreviveu a 261 testes por causa
disso. Ao mexer em parsing de catálogo, meça contra um parque que **não** seja o MK.

**Cuidado com composição de amostra.** Comparar a média do parque entre dois dias compara
conjuntos diferentes de atrações se a coleta não cobriu as mesmas — a diferença aparece
sem a fila ter mudado. Compare sempre o mesmo par (atração, janela).

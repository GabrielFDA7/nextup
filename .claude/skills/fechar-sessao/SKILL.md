---
name: fechar-sessao
description: Use ao encerrar uma sessão de trabalho no NextUp — quando o Gabriel disser "vamos fechar", "por hoje é isso", "pode registrar", ou quando uma entrega for concluída e commitada. Também use antes de um `/compact` que encerre o assunto. Cobre o registro obrigatório dos prompts em docs/PROMPTS.md, as decisões na seção 10 de docs/PROJETO.md, a atualização do CLAUDE.md e os commits.
---

# Fechamento de sessão — NextUp

O registro **faz parte da entrega**, não é burocracia: este é o projeto principal de
portfólio do Gabriel, e o histórico é lido por recrutador. Uma sessão sem registro é
trabalho feito que ninguém consegue avaliar.

> ⚠️ **O item 1 é exigência explícita do Gabriel.** Se a sessão acabar sem ele, o combinado
> foi quebrado. Na dúvida sobre o resto, faça ao menos esse.

---

## 1. Os prompts, na íntegra — `docs/PROMPTS.md`

**Sem corrigir digitação, sem reescrever, sem resumir.** O valor do arquivo está em mostrar
como o pedido real virou a entrega real; um prompt "arrumado" apaga justamente isso.

Cada entrada leva:

```markdown
### Prompt #0XX
**Data:** DD/MM/AAAA
**Contexto:** (o que estava acontecendo no projeto neste momento)

```
(prompt exatamente como foi escrito)
```

**O que resultou:** (arquivos, decisões, o que ficou pendente)
```

Há um modelo comentado no fim do arquivo. A numeração é contínua entre sessões — confira
o último número antes de escrever.

**Inclua os erros.** As entradas mais valiosas do arquivo são as que registram o que deu
errado: o teste que fingia testar (7.3), a asserção de guarda que pegou o cenário inerte
(7.4), o Disneyland Paris quebrado desde a Fase 1. Elas mostram método, e método é o que
diferencia um portfólio.

**Credenciais nunca entram.** Senha ou connection string no registro vira `***`.

---

## 2. As decisões — seção 10 de `docs/PROJETO.md`

Toda decisão técnica tomada na sessão vira uma linha da tabela:

```
| DD/MM/AAAA | A decisão, em negrito o que importa | Por que, com o número quando houver |
```

A coluna do motivo é a que vale. `"Razão contra a mediana, e não tercil"` não diz nada
sozinho; `"medido: 83% de estabilidade contra 74%, e o tercil força um terço em cada
faixa"` é o que alguém consegue julgar — ou contestar — daqui a seis meses.

---

## 3. Se uma fase foi concluída

- Marcar a linha na tabela da fase (seção 7) com ✅ e a data
- Atualizar o **cabeçalho de status** no topo do `PROJETO.md`
- Atualizar o bloco "Estado atual" do `CLAUDE.md`
- Rodar a suíte e **atualizar a contagem de testes nos dois arquivos**
  (`pytest -m "not e2e"` e `pytest -m e2e` dão os dois números)
- Atualizar o rodapé `Última atualização:` do `PROJETO.md`

Contagem de testes desatualizada é o erro mais fácil de cometer aqui, porque nada quebra
quando ela erra.

---

## 4. Os commits

Conventional Commits com descrição em português: `feat:`, `fix:`, `docs:`, `chore:`,
`ci:`, `test:`, `refactor:`. **Pequenos e temáticos** — a divisão que tem funcionado é
backend / frontend / docs.

O corpo da mensagem explica o **porquê**, não o quê. O diff já diz o quê.

Terminar com:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

---

## 5. Armadilhas desta máquina

O Gabriel desenvolve em **Windows com PowerShell 5.1**; a ferramenta Bash falha no `fork`.

**Mensagem de commit vai por arquivo**, nunca inline — aspas e acentos quebram no
PowerShell:

```powershell
git commit -F caminho\para\mensagem.txt
```

Escreva esse arquivo no **scratchpad da sessão**, não no repositório.

> ⚠️ **Nunca edite arquivo com `Get-Content -Raw` + regravação.** Sem `-Encoding utf8` o
> PowerShell 5.1 lê UTF-8 como cp1252, e regravar transforma `—` em `â€”` no arquivo
> inteiro. Já quebrou três testes. Use a ferramenta Edit, ou um script Python com
> `read_text(encoding="utf-8")`.

Para anexar blocos longos de markdown, escreva um `.txt` no scratchpad e junte com Python
— `Add-Content` insere BOM ao criar arquivo.

---

## 6. Antes de dar por encerrado

```powershell
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q
git status --short          # a árvore precisa ficar limpa
```

**Push só com o combinado do Gabriel.** Todo push na `main` republica no Render, e desde a
Fase 6.2 o contêiner roda `alembic upgrade head` ao subir — confirme antes de empurrar
algo que mexa em migração.

Se sobrou algo pendente, diga qual é e por quê. Pendência declarada é informação;
pendência silenciosa é dívida.

# Registro de Prompts — NextUp

Histórico de todos os prompts enviados por Gabriel de Angelis nas conversas com o Claude
Code dentro deste projeto.

**Regras deste arquivo:**
- Todo prompt é registrado **na íntegra**, sem correção de digitação ou reescrita.
- Ordem cronológica, mais antigo no topo.
- Cada entrada traz data, contexto e o que resultou dela.
- Este arquivo é atualizado ao final de cada interação, antes de encerrar o assunto.

**Por que manter isso:** o histórico mostra como o projeto foi pensado, não só como ficou.
É rastreabilidade de decisão — e, num portfólio, evidência de processo estruturado de
trabalho com ferramentas de IA, que hoje é uma competência avaliada em entrevista.

---

## Sessão 001 — 11/09/2026

### Prompt #001
**Data:** 11/09/2026
**Contexto:** Primeiro contato. Projeto ainda não existia — pasta vazia, sem Git.

```
Boa noite, Claude.
Tudo bem?

Claude, tenho um projeto que precisamos estruturar juntos de forma bem organizada e profissional, e para ele, quero que você tenha em mente que será meu primeiro projeto do tipo, então quero que você vá me ensinando conforme vamos fazendo ele, ok?

O projeto é o seguinte:
Atualmente, em parques conhecidos pelo mundo, as pessoas enfrentam grandes filas de espera, por exemplo, nos parques da disney, isso acontece de forma bem acentuada nos principais brinquedos e atrações, o que pode fazer com que os clientes e frequentadores percam grande parte daquela experiência mágica em filas e esperas desnecessárias.

Para contornar isso o que as pessoas fazem? É simples, uma pessoa fica de olho em um site que demonstra o tempo de espera atual para cada brinquedo e por whatsapp ou de alguma outra forma, avisa seus contratantes o brinquedo que tem menor fila de espera no momento e está mais próximo da pessoa .

Eu acredito que esse serviço possa ser substituido facilmente por um algorítmo e uma api que mostra pro usuário exatamente a mesma coisa que a pessoa que avisa o cliente faz.

Já tenho uma api para isso, é a ThemesPark.wiki, ela já nos permite selecionar o parque e mostra o tempo de espera para cada brinquedo.

Esse é o nosso projeto. Primeiro de tudo, quero que você me diga se isso é realmente viável e se é fazivel para uma pessoa que tem conhecimento em programação/desenvolvimento (intermediário), mas nunca trabalhou com api e dados dessa maneira. Segundo, isso será usado para estruturar o meu linkedin, será o meu projeto principal para conseguir empregos nessa área, então preciso que seja feito da forma mais profissional e atual possível. Terceiro, quero que você crie um .md que explicará tudo o que foi digitado nessa mensagem e futuramente a estrutura do nosso projeto quando decidida.

Além disso, quero que crie outro .md, que salvará todos os prompts usados por mim em qualquer conversa com o projeto aberto.

Entendido? Manda bala, então!
```

**O que resultou:**

1. **Validação técnica da API com chamadas reais** (não teórica):
   - `GET /destinations` → HTTP 200, sem autenticação, gratuita.
   - Magic Kingdom `/live` → 71 entidades, 35 atrações com `queue.STANDBY.waitTime`.
   - Magic Kingdom `/children` → **35 de 35 atrações com coordenadas GPS**, o que
     viabiliza a parte de "atração mais próxima".
   - Nome correto da API confirmado: **ThemeParks.wiki** (`api.themeparks.wiki/v1`).

2. **Veredito de viabilidade: VIÁVEL, risco baixo.** A parte cara — coletar e normalizar
   dados de fila — já vem pronta da API. O que sobra está dentro do nível intermediário.

3. **Criado `docs/PROJETO.md`** — documento mestre com problema, tese, objetivos,
   evidências de viabilidade, algoritmo, arquitetura, roadmap em 5 fases, riscos,
   glossário e registro de decisões.

4. **Criado `docs/PROMPTS.md`** — este arquivo.

5. **Decisão de produto registrada:** ranquear por **custo total** (caminhada + fila), e
   não pela menor fila isolada. É o que o consultor humano de fato faz, e é o diferencial
   do projeto frente aos sites de fila que já existem.

---

### Decisões #001-A — 11/09/2026
**Contexto:** respostas de Gabriel às perguntas de escopo feitas ao final da análise de
viabilidade. Não foram prompts digitados, e sim escolhas em menu — registradas aqui por
definirem a arquitetura.

**Pergunta:** formato de entrega do MVP.
**Resposta:** **API + web app simples.**

**Pergunta:** tipo de vaga alvo.
**Resposta:** **Desenvolvimento Full-Stack.**

**O que resultou:**
- Estrutura de pastas definida e escrita na seção 6 do `PROJETO.md`, com arquitetura em
  **4 camadas de dependência unidirecional** (`api → core → models ← clients`).
- Frontend decidido **sem framework**: HTML/CSS/JS puro + Leaflet para o mapa. Motivo:
  a tela é lista ordenada + mapa; React adicionaria build e dependências sem ganho.
- Roadmap reorganizado para o perfil full-stack — a interface web subiu para a Fase 4, e
  o MVP passou a fechar na Fase 5 (produção). Inteligência histórica virou Fase 6.
- Nome de pacote provisório: `parkpilot` — **a confirmar antes do primeiro commit**.

**Pendente ao fim da sessão:** confirmar o nome do projeto e executar a Fase 0 (repositório
Git, ambiente virtual, dependências, esqueleto de pastas, primeiro commit).

---

## Sessão 002 — 12/09/2026

### Prompt #002
**Data:** 12/09/2026
**Contexto:** Documentação pronta e arquitetura definida. Faltava nomear o projeto e
executar a Fase 0 do roadmap.

```
Vamos começar essa fase, o nome do app vai ser NextUp. Porém, estou em uma máquina corporativa, acredito que por aqui não consiga criar o ambiente virtual, então pode pular essa etapa. Quando o projeto estiver no github eu vou clonar ele na minha máquina pessoal e lá criaremos o ambiente virtual. Pode ser?
```

**O que resultou — Fase 0 concluída:**

- **Nome definido: NextUp**, pacote Python `nextup`. Documentação toda atualizada.
- **Repositório Git** inicializado na branch `main`.
- **Estrutura em 4 camadas** criada em `src/nextup/` (`clients`, `models`, `core`, `api`).
- **`pyproject.toml`** com dependências, `ruff` e `pytest` configurados; `src layout`.
- **`config.py`** centralizando todo número mágico do projeto, com sobrescrita por
  variável de ambiente.
- **`core/geo.py`** — primeiro módulo funcional: Haversine, correção de sinuosidade e
  conversão em minutos. Escrito sem dependências externas, de propósito, para ser
  executável mesmo sem ambiente virtual.
- **`tests/test_geo.py`** — 17 testes, **todos passando**, validados contra referências
  externas (Paris–Londres, um grau de latitude, pontos antipodais) e coordenadas reais do
  Magic Kingdom.
- **`README.md`**, `LICENSE` (MIT), `.gitignore`, `.gitattributes`, `.env.example`.
- **CI no GitHub Actions** — `ruff` + `pytest` em Python 3.11, 3.12 e 3.13.
- **5 commits temáticos**, seguindo Conventional Commits.

**Decisão de ambiente registrada:** venv pulado por restrição da máquina corporativa. Por
isso `ruff` não foi validado localmente — a primeira verificação de lint virá do CI no
primeiro push. Os testes, esses sim, rodaram e passaram nesta máquina.

**Pendente ao fim da sessão:** criar o repositório no GitHub e dar o primeiro push; clonar
na máquina pessoal e criar o venv; iniciar a Fase 1 (cliente da API com cache).

---

<!--
MODELO PARA NOVAS ENTRADAS — copiar abaixo desta linha

### Prompt #00X
**Data:** DD/MM/AAAA
**Contexto:** (o que estava acontecendo no projeto neste momento)

```
(prompt na íntegra, sem edição)
```

**O que resultou:**
- (arquivos criados ou alterados, decisões tomadas, o que ficou pendente)

---
-->

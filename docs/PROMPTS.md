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

### Prompt #003
**Data:** 12/09/2026
**Contexto:** Fase 0 concluída e enviada ao GitHub. Gabriel vai trocar da máquina
corporativa para a máquina pessoal e continuar de lá.

```
O push foi feito, agora irei continuar a partir do outro computador. Você deixou instruções para continuarmos de onde paramos aqui por lá?
```

**O que resultou:**

- **Push confirmado:** `main` e `origin/main` no mesmo commit, em
  `github.com/GabrielFDA7/nextup`.
- **Lacuna identificada e corrigida.** A memória do assistente é local da máquina
  (`C:\Users\500557\.claude\`) e **não viaja com o repositório**. Sem intervenção, a sessão
  na máquina nova começaria sem saber das convenções combinadas nem de onde paramos.
- **Criado `CLAUDE.md` na raiz** — lido automaticamente pelo Claude Code ao abrir o
  projeto. Reúne: resumo do projeto e a decisão de produto central, como trabalhar com o
  Gabriel (ensinar durante a construção, português, nível intermediário), estado atual e
  próximo passo, a regra de dependência unidirecional das camadas, convenções de código,
  testes, commits e documentação, setup do ambiente e referência rápida da API.

**Decisão registrada:** a continuidade entre máquinas e sessões passa a depender de
arquivos versionados (`CLAUDE.md`, `PROJETO.md`, `PROMPTS.md`), nunca da memória local do
assistente.

**Pendente ao fim da sessão:** na máquina pessoal — clonar o repositório, criar o venv,
instalar as dependências, rodar `pytest` e `ruff`, e então iniciar a Fase 1.

---

## Sessão 003 — 12/09/2026

> Sessão na **máquina pessoal**, a primeira fora da máquina corporativa. Começou com o
> ambiente local inexistente e terminou com as **Fases 1 a 4 concluídas**: modelos,
> cache, cliente HTTP, CLI, motor de recomendação, API FastAPI e interface web.
> 194 testes, CI verde em 4 jobs.

### Prompt #004
**Data:** 12/09/2026
**Contexto:** Abertura da sessão. Repositório clonado na máquina pessoal, sem `.venv`.

```
Muito bem, espero que você tenha o contexto do projeto.
Baseado nisso, qual seria o próximo passo para continuarmos o nosso progresso? Acredito que a fase 0 ainda não esteja totalmente concluída, possívelmente será necessário instalar dependências desse lado de cá para seguirmos.
A .venv ainda não foi iniciada.

Analise e me retorne
```

**O que resultou:**
- Diagnóstico: só havia **Python 3.14** instalado, versão que o CI não testa. Decisão do
  Gabriel: instalar o **3.13**, versão mais alta validada pelo CI, para evitar
  "passa aqui, falha lá".
- `winget install Python.Python.3.13`, `.venv` criada, `pip install -e ".[dev]"`.
- **Primeira execução local da qualidade na história do projeto:** 17 testes passando,
  `ruff check` e `ruff format --check` limpos.

---

### Prompt #005
**Data:** 12/09/2026
**Contexto:** Ambiente pronto; `CLAUDE.md` ainda dizia que o `ruff` nunca rodara local.

```
Atualize o claude.md primeiro e ainda crie para mim um resumo pelo chat do que foi feito até agora, explicando cada termo para que eu possa aprender ainda mais. Após isso, começaremos a parte 1 pelo pydantic.
```

**O que resultou:**
- `CLAUDE.md` e `docs/PROJETO.md` atualizados; decisão do Python 3.13 na seção 10.
- Aula sobre venv, editable install, extras `[dev]`, lint e `winget`.
- Início da Fase 1 pelos modelos `pydantic`.

---

### Prompt #006
**Data:** 12/09/2026
**Contexto:** Após a primeira aula, sobre as ferramentas de qualidade do projeto.

```
como funcionam o pytest e o ruff?
```

**O que resultou:** aula sobre descoberta automática de testes, reescrita de `assert`,
`pytest.approx`, fixtures, e a diferença entre `ruff check` (lint via AST) e
`ruff format` (formatação). Tabela das famílias de regras `E/W/F/I/N/UP/B/SIM/RUF` e as
ferramentas que cada uma substitui.

---

### Prompt #007
**Data:** 12/09/2026
**Contexto:** Antes de iniciar os modelos, dúvida sobre estratégia de teste.

```
Bora para a próxima fase, mas antes quero tirar uma dúvida.
Iremos fazer um test_*.py para cada script que escrevermos?
```

**O que resultou:** esclarecido que **não é 1:1**. Um arquivo de teste nasce quando o
módulo tem uma decisão ou cálculo que pode dar errado de forma não óbvia. `__init__.py`
e constantes puras não ganham teste próprio; teste que só repete o código não prova nada.

---

### Prompt #008
**Data:** 12/09/2026
**Contexto:** Escolha entre começar pelo `Destination` ou pelo `Attraction`.

```
Podemos seguir assim, mas lembre que estou aprendendo, preciso de aulas e explicações para que eu entenda os termos e como eles funcionam dentro do nosso código, e outra, quero que você explique como se estivesse explicando para um completo leigo, de forma que todos consigam entender as explicações.
```

**O que resultou:**
- Preferência registrada na memória do assistente: explicar com analogia do mundo real,
  em linguagem de leigo, antes do código.
- `models/destination.py` + fixture real da API + 11 testes.

---

### Prompt #009
**Data:** 12/09/2026
**Contexto:** Três alterações pendentes sem commit.

```
Entendi, mas quando iremos fazer commits? A cada fase ou de outra forma?
```

**O que resultou:** estabelecida a régua — **um commit por ideia completa**, não por fase
(a Fase 0 sozinha gerou 8 commits). Teste vai junto do código que ele testa, para todo
commit deixar o repositório verde e o `git bisect` funcionar.

---

### Prompt #010
**Data:** 12/09/2026
**Contexto:** Proposta de três commits temáticos, dois deles no mesmo arquivo.

```
Faça
```

**O que resultou:**
- Três commits criados.
- **Erro cometido e corrigido:** a tentativa de dividir `docs/PROJETO.md` com um patch de
  contexto zero inseriu uma linha no lugar errado. Pego na revisão do `git diff --cached`
  antes do commit. Lição registrada: sempre revisar o que está preparado, não só os nomes
  dos arquivos.

---

### Prompt #011
**Data:** 12/09/2026
**Contexto:** Commits locais, ainda não enviados.

```
vamos fazer o push e depois seguir para o Attraction
```

**O que resultou:** push feito, CI verde. `models/attraction.py` com `EntityType`
(enum com `_missing_` → `UNKNOWN`), `Location` com faixa validada e
`ParkCatalog.attractions()`. 16 testes.

---

### Prompt #012
**Data:** 12/09/2026
**Contexto:** `gh` recém-instalado, sem autenticação.

```
Consegue analisar meu terminal?
```

**O que resultou:** esclarecido o limite — o assistente não enxerga a janela do terminal
do Gabriel, só executa comandos e lê a saída. O que fica em disco (arquivos, credenciais,
programas instalados) é compartilhado; o histórico de comandos dele, não.

---

### Prompt #013
**Data:** 12/09/2026
**Contexto:** Gabriel colou dois erros do PowerShell: `Activate.ps1` bloqueado por
política de execução, e `gh` não reconhecido.

```
(saída do terminal com PSSecurityException e CommandNotFoundException)

Quando tentei rodar o gh auth login por mim mesmo, tive esse erro:

Como concertamos
```

**O que resultou:**
- Diagnóstico: política de execução em `Restricted` (padrão de fábrica) e PATH do terminal
  desatualizado.
- Decisão do Gabriel: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

---

### Prompt #014
**Data:** 12/09/2026
**Contexto:** venv passou a ativar, mas `gh` seguia não reconhecido.

```
(saída do terminal)

Comecei a rodar os comandos que você havia indicado, a venv ativou, porém gh ainda não é reconhecido pelo cmdlet
```

**O que resultou:** causa identificada — **o terminal integrado do VS Code herda o PATH do
VS Code**, que foi carregado antes da instalação. Abrir terminal novo não bastava; era
preciso reiniciar o editor. Também corrigida uma orientação anterior do assistente, cujo
comando teria desativado o venv ao reconstruir o PATH.

---

### Prompt #015
**Data:** 12/09/2026
**Contexto:** Problemas de ambiente resolvidos.

```
Prontinho, consegui fazer todos os processos e entendi que o VS code só atualizaria o path se fosse reiniciado. Agora estou logado no GitHub CLI
```

**O que resultou:** `gh` autenticado, passando a permitir consulta do CI pelo terminal.
Implementados `models/live.py` (`LiveStatus`, `is_rankable`) e `clients/cache.py`
(TTL com relógio injetável).

---

### Prompt #016
**Data:** 12/09/2026
**Contexto:** Cache pronto; faltava o cliente HTTP para fechar a Fase 1.

```
Vam bora!
```

**O que resultou:**
- `clients/themeparks.py` — assíncrono, cache, backoff exponencial, erros próprios.
- **Bug encontrado por teste:** o cache guardava o JSON cru **antes** de validar, então uma
  resposta malformada ficava memorizada por 24h. Corrigido guardando o modelo validado.
- **Falha de desenho encontrada ao otimizar os testes:** o `User-Agent` só era enviado
  quando o cliente criava a própria conexão — a Fase 3 teria perdido a identificação com
  a API sem ninguém notar. Cabeçalho e timeout passaram a ir por requisição.

---

### Prompt #017
**Data:** 12/09/2026
**Contexto:** Cliente pronto; faltava a entrega da Fase 1.

```
Seguimos
```

**O que resultou:**
- `cli.py` — comando `nextup`, que o `pyproject.toml` declarava desde a Fase 0 sem o
  módulo existir.
- **Fase 1 concluída.** Bug de contagem encontrado só ao rodar contra a API real:
  `--limit 6` exibia "6 de 35" em vez de "26 de 35".

---

### Prompt #018
**Data:** 12/09/2026
**Contexto:** Fase 1 fechada; Fase 2 é o coração do projeto.

```
Vamos continuar, estou animado com o projeto.
```

**O que resultou:**
- `core/recommender.py` — ranking por `custo_total = caminhada + fila`.
- `tests/test_arquitetura.py` — a regra do `CLAUDE.md` virou teste executável, validado
  com uma violação proposital.
- `cli.py --lat/--lon`. **Fase 2 concluída.**

---

### Prompt #019
**Data:** 12/09/2026
**Contexto:** Motor pronto; faltava expor por HTTP.

```
Seguimos
```

**O que resultou:**
- `api/` com FastAPI: `health`, `destinations`, `parks/{id}/recommendations`.
- Schemas separados dos modelos internos; cliente único no `lifespan`; erros do projeto
  mapeados para 404/502/503.
- **O mesmo bug de contagem reapareceu** — e o primeiro teste escrito para ele
  **afirmava o comportamento errado**, por ter sido escrito olhando o código em vez da
  expectativa. **Fase 3 concluída.**

---

### Prompt #020
**Data:** 12/09/2026
**Contexto:** API pronta; faltava a interface.

```
Seguimos!
```

**O que resultou:**
- `web/` — HTML, CSS e JS puro, servido pelo próprio FastAPI. Geolocation, mapa Leaflet,
  seletor com 198 parques, e **toque no mapa define a posição** (saída para quem nega
  o GPS).
- Decisão do Gabriel: **instalar Playwright** para testar a interface de verdade.
  21 testes E2E em Chromium, incluindo proteção contra XSS e ausência de rolagem lateral.
- CI ganhou segundo job; actions atualizadas para `@v7`. **Fase 4 concluída.**

---

### Prompt #021
**Data:** 12/09/2026
**Contexto:** Interface pronta e testada, mas o Gabriel ainda não a tinha visto.

```
Quero ver o site, como faço?
```

**O que resultou:** servidor no ar em `http://127.0.0.1:8000`, com roteiro do que testar —
incluindo o aviso de que, estando no Brasil, o GPS real daria distâncias absurdas e o
caminho realista é tocar no mapa.

---

### Prompt #022
**Data:** 12/09/2026
**Contexto:** Encerramento da sessão.

```
Ficou maneiro e parece funcional.

Só precisamos deixar bonito agora, mas isso é um trabalho para depois.
Fim da sessão.
```

**O que resultou:**
- Aprovação da interface quanto à **funcionalidade**; refinamento **visual** fica como
  tarefa futura, registrada na seção 7 do `docs/PROJETO.md`.
- Servidor encerrado, prompts registrados, sessão fechada com a árvore limpa.

**Pendente para a próxima sessão:** Fase 5 — Docker, deploy público e README com
demonstração. Refino visual da interface em algum momento antes de divulgar o link.

---

## Sessão 004 — 13/09/2026

> A sessão que colocou o projeto no ar. Fase 5 concluída (Docker, deploy no Render,
> README como vitrine), mais o refino visual que estava pendente desde a sessão anterior.
> **O MVP está fechado: fases 0 a 5 concluídas.**

### Prompt #023
**Data:** 13/09/2026
**Contexto:** Abertura da sessão. Fases 0 a 4 concluídas; Fase 5 era o próximo passo.

```
Vamos!
```

**O que resultou:** verificação do estado (tudo sincronizado, 173 testes verdes) e
descoberta de que **Docker não está instalado na máquina**, o que exigia uma decisão sobre
como validar a imagem.

---

### Prompt #024
**Data:** 13/09/2026
**Contexto:** Perguntado como validar o Docker e onde publicar. Ele escolheu validar pelo
CI e, em vez de escolher uma plataforma, devolveu uma pergunta.

```
Validar só pelo CI (Recomendado)
```
```
O Netlify é uma possibilidade boa?
```

**O que resultou:**
- Consulta à documentação do Netlify em vez de resposta de memória: **Functions suporta
  TypeScript, JavaScript e Go — Python não**, e não há servidor de longa duração.
- **Netlify descartado**, com o motivo que importa: sem processo persistente, o cache de
  24h nasceria vazio a cada requisição, que é exatamente o abuso que a Fase 1 evitou.
- `Dockerfile` em duas etapas, `.dockerignore`, `docker-compose.yml` e o job
  `imagem-docker` no CI. Dois bugs próprios pegos antes do commit: a etapa de construção
  geraria um pacote vazio, e a imagem final copiava o código à toa.

---

### Prompt #025
**Data:** 13/09/2026
**Contexto:** Com o Netlify fora, a pergunta da plataforma voltou.

```
Render (Recomendado)
```

**O que resultou:**
- `render.yaml` versionado junto do código.
- **Armadilha evitada pela documentação:** o `CMD` fixava a porta 8000, mas o Render
  escolhe a porta e a informa por `PORT` (padrão 10000). O serviço subiria saudável e
  nunca receberia requisição. Virou passo de CI.
- README renovado: captura da interface, instruções de Docker, tabela de rotas. Corrigida
  uma afirmação falsa — o README dizia que atrações fora do horário eram filtradas, e esse
  filtro não existe.

---

### Prompt #026
**Data:** 13/09/2026
**Contexto:** Ele criou a conta no Render e conectou o repositório.

```
Feito, o site está no ar.
```

**O que resultou:** tentativa de adivinhar a URL (404 nas duas hipóteses) e pedido do
endereço, em vez de continuar chutando.

---

### Prompt #027
**Data:** 13/09/2026

```
https://nextup-rcux.onrender.com/
```

**O que resultou:** verificação completa em produção — API, interface, arquivos estáticos,
`/docs`, e o fluxo inteiro num navegador real: 198 parques, mapa com tiles, ranking com
dados ao vivo, **zero erro de console**. O link foi para o topo do README.

---

### Prompt #028
**Data:** 13/09/2026
**Contexto:** Apresentadas duas formas de tratar a hibernação do plano gratuito: avisar na
tela ou manter o serviço acordado. Foi dito explicitamente que a segunda contorna o limite
do plano.

```
Vamos usar o ping do github actions
```

**O que resultou:**
- `keep-alive.yml` chamando `/api/health` a cada 10 minutos — intervalo de 10 e não 14
  porque o GitHub atrasa agendamentos.
- O ping usa `/api/health` de propósito: acordar o nosso serviço não pode virar tráfego na
  API pública de terceiros a cada 10 minutos.
- Três tentativas antes de falhar, para não gerar alarme à toa.
- A decisão foi registrada na tabela com o motivo — inclusive o fato de contornar o limite
  do plano gratuito.

---

### Prompt #029
**Data:** 13/09/2026
**Contexto:** MVP no ar; faltava o refino visual pedido na sessão anterior.

```
Vamos para o refino
```
```
Personalidade de parque
```

**O que resultou:**
- Paleta de pôr do sol (coral, âmbar, roxo profundo), fonte **Outfit**, cantos
  arredondados, ícones SVG.
- **Três problemas reais encontrados olhando a tela, não o código:** texto branco sobre
  fundos quentes perdia contraste no tema escuro; os marcadores do mapa eram oito
  alfinetes idênticos; e o marcador nº 1 ficava escondido atrás de outro.
- Publicado e verificado em produção.

---

### Prompt #030
**Data:** 13/09/2026
**Contexto:** Encerramento.

```
Vamos parar por hoje!
```

**O que resultou:** prompts registrados, nenhum servidor deixado rodando, árvore limpa.

**Pendente para a próxima sessão:** **Fase 6** — histórico de filas, tendências e
previsão. É a única frente que resta, e a que tira o projeto de "consome uma API" para
"produz conhecimento próprio a partir de dados".

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

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

## Sessão 005 — 15/09/2026

Retomada do projeto em **outra máquina**, sem ambiente montado. Sessão dividida em duas
partes: preparar a máquina e iniciar a Fase 6.

### Prompt #031
**Data:** 15/09/2026
**Contexto:** Primeira mensagem da sessão. Fases 0 a 5 concluídas, projeto no ar, Fase 6
descrita no roadmap mas ainda sem fatiamento.

```
Claudão, bora retomar o projeto?
Quais seriam os próximos passos?
```

**O que resultou:**
- Leitura do estado atual e proposta da **Fase 6 fatiada em 6 passos** (6.1 a 6.6),
  registrada na seção 7 do `docs/PROJETO.md`.
- Levantamento do problema central da fase: o NextUp era *stateless* e passa a precisar de
  estado persistente e de um processo que roda sozinho.
- Alerta sobre a armadilha do **disco efêmero do Render** — um SQLite no contêiner
  perderia o histórico a cada push, e todo push republica.
- Duas perguntas ao Gabriel: onde persistir e por onde começar.

---

### Prompt #032
**Data:** 15/09/2026
**Contexto:** Resposta às duas perguntas, feita pelo seletor de opções. A escolha de banco
foi a recomendada; a de ponto de partida ele escreveu por conta própria.

**Banco escolhido:** Postgres externo (Neon/Supabase) — recomendado.

**Ponto de partida, na íntegra:**

```
Primeiro de tudo, estamos em um novo computador, onde não temos todas as dependências do projeto instaladas. O primeiro passo vai ser analisar o que temos e baixar todo o restante que falta, depois disso iremos começar o 6.1 - fundação do storage
```

**O que resultou — parte 1, ambiente:**
- Diagnóstico: sem `.venv`; a máquina tinha **Python 3.14 e 3.10**, nenhuma das duas
  adequada — a 3.10 está abaixo do `requires-python`, e a 3.14 não é testada pelo CI.
- **Python 3.13.15 instalado via `winget`**, mantendo a paridade com o CI (a mesma decisão
  registrada em 12/09/2026, agora repetida em máquina nova).
- `.venv` criada, `pip install -e ".[dev,e2e]"`, `playwright install chromium`.
- Suíte completa verde apesar do salto de versões das dependências (`pytest` 8 → 9,
  `fastapi` → 0.141, `starlette` → 1.6): **173 + 21 testes passando**, lint limpo.
- Observação registrada: o **Bash falha nesta máquina** (erro de `fork` do MSYS); a sessão
  inteira correu em PowerShell.

**O que resultou — parte 2, passo 6.1:**
- `models/snapshot.py` — `QueueSnapshot`, Pydantic puro, com `from_live()`.
- `storage/` — `tables.py`, `engine.py`, `snapshots.py`. SQLAlchemy Core assíncrono.
- `migrations/` — Alembic com template assíncrono; `alembic.ini` com a URL **vazia**, para
  não versionar senha num repositório público.
- `config.py` — `NEXTUP_DATABASE_URL`, retenção e `normalize_database_url`.
- 28 testes novos; a suíte rápida foi de **173 para 201**.
- `test_arquitetura.py` estendido: `core/` e `models/` agora também não podem importar
  `sqlalchemy`.
- Três armadilhas encontradas no caminho (autoincremento de `BIGINT` no SQLite, fuso
  perdido na ida e volta, medição duplicada silenciosa) — detalhadas na seção 7 do
  `docs/PROJETO.md`.

---

### Prompt #033
**Data:** 15/09/2026
**Contexto:** O push tinha falhado por falta de credenciais na máquina nova, e eu havia
pedido a connection string do Neon para seguir com o 6.2. O Gabriel colou o roteiro de
onboarding que o próprio painel do Neon gera — junto com a URL do banco, **com a senha**.

```
Por que essa sessão não permite prompts interativos?

Set up this Neon project in the current working directory.

1. `npm i -g neon@latest && neon login`
2. `neon skills -y`
3. `neon mcp -y`
4. `neon link --project-id mute-forest-48970873 --branch production -y`
5. `neon config init`
6. Update `neon.ts`:


postgresql://neondb_owner:***@ep-bitter-scene-acvmxetx-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```ts
import { defineConfig } from "@neon/config/v1";

export default defineConfig({});
```

7. `neon deploy`
```

> **Nota:** a senha foi substituída por `***` neste registro. O prompt está íntegro no
> resto. Registrar credencial em arquivo versionado seria repetir, num lugar pior, o
> problema que o `alembic.ini` vazio existe para evitar.

**O que resultou:**
- **Resposta à pergunta:** as ferramentas de shell da sessão rodam sem terminal
  interativo (stdin no dispositivo nulo), então comandos que *perguntam* algo recebem EOF.
  Por isso o `git push` e o `neon login` não passam; comandos que só executam funcionam.
- **Passos 1 a 7 descartados, com justificativa:** são o fluxo Node/TypeScript do Neon.
  O NextUp é Python e faz deploy pelo Render — um `neon.ts` na raiz seria peso morto. Do
  Neon o projeto precisa só da connection string. (O `npm i -g` foi, de todo modo,
  bloqueado pelo classificador de permissões da sessão.)
- **Aviso de segurança:** a senha circulou em texto plano e deve ser rotacionada.
- **A quinta armadilha da fase, encontrada ao conectar:** a URL do Neon traz
  `?sslmode=require&channel_binding=require`, parâmetros da libpq que o `asyncpg` recusa
  com `TypeError: connect() got an unexpected keyword argument 'sslmode'`.
- `normalize_database_url` passou a removê-los, e `ssl_is_required` a preservar a
  intenção — porque o pior desfecho não seria o erro, seria conectar em **texto plano**
  com a senha viajando aberta.
- TLS resolvido com `ssl.create_default_context()` no `connect_args`, com verificação de
  cadeia e hostname. Validado contra o Neon real, com caso de controle.
- `config.py` passou a carregar o `.env`; **isso criou uma armadilha nova**, fechada na
  mesma sessão: a URL padrão passou a apontar para produção, então o `conftest.py` força
  SQLite em memória e `test_trava_de_seguranca.py` vigia a trava.
- Migração aplicada no Neon e camada de storage validada contra Postgres real: 8
  verificações, incluindo fuso, recusa de duplicata e retenção. Dados de teste removidos.
- Suíte de **201 para 225 testes**.

---

## Sessão 006 — 20/09/2026

### Prompt #034
**Data:** 20/09/2026
**Contexto:** Cinco dias após a sessão anterior. O push pendente já tinha sido feito pelo
Gabriel, e o banco no Neon estava provisionado e vazio.

```
Voltamos!
Temos um próximo passo definido?
```

**O que resultou:** o passo **6.2 — o coletor** foi implementado por inteiro.

- `src/nextup/collector.py`, no nível do `cli.py` porque orquestra `clients/` + `storage/`.
- Sobe como tarefa de fundo no `lifespan` do FastAPI, compartilhando o cliente com as
  rotas para os dois dividirem o mesmo cache.
- `ParkCatalog.attraction_ids()` — mais permissivo que `attractions()`, porque coordenada
  é requisito para ranquear, não para ter histórico.
- Quatro variáveis novas no `config.py`, com `_env_bool` (sem ele, `"false"` seria
  verdadeiro em Python).
- **Validado contra a API ao vivo e o Neon real:** 35 atrações lidas, 35 gravadas, e a
  segunda coleta imediata gravou zero. Sete estavam abertas sem fila medida.
- `render.yaml` ganhou `NEXTUP_DATABASE_URL` com `sync: false` e as variáveis do coletor.
- **Decisão do Gabriel:** automatizar as migrações no contêiner. O `CMD` virou
  `alembic upgrade head && exec uvicorn ...`, o que exigiu copiar `migrations/` e
  `alembic.ini` para a imagem e dar ao usuário sem privilégios a posse de `/app`.
- CI: coletor desligado nos contêineres de teste (não gerar tráfego numa API pública a
  cada build) e dois passos novos confirmando que a migração rodou.
- Suíte de **225 para 242 testes** na parte rápida.

**A armadilha que pegou quem escreveu o teste:** a primeira versão do teste do laço
procurou os snapshots numa janela ao redor do relógio de teste e não achou nada, porque
`observed_at` vem do `lastUpdated` da fonte — e as fixtures são de 12/09. A distinção
entre as duas datas se provou real na primeira vez que importou, e virou o teste
`test_o_instante_gravado_e_o_da_fonte`.

---

### Prompt #035
**Data:** 20/09/2026
**Contexto:** Eu havia pedido que ele cadastrasse `NEXTUP_DATABASE_URL` no painel do
Render, explicando que sem ela o coletor gravaria num SQLite efêmero. Ele voltou com a
string para conferir antes de criar.

```
Crie a Variable com o nome que você me sugeriu e essa connection string:
postgresql://neondb_owner:***@ep-bitter-scene-acvmxetx-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require

Correto?
```

> **Nota:** senha substituída por `***` neste registro, como no Prompt #033.

**O que resultou:**
- **Confirmado:** nome e valor corretos. A string crua, sem editar, é justamente o caso
  que o `normalize_database_url` cobre.
- **Um risco investigado antes de dar o aval:** o host termina em `-pooler`, e existe uma
  incompatibilidade conhecida entre `asyncpg` e PgBouncer por colisão de nomes de
  *prepared statement*. É uma falha que não aparece numa chamada isolada, só sob reuso de
  conexão — o pior tipo. Teste forçando 60 queries concorrentes com reciclagem de pool:
  **nenhuma colisão**. Registrado na seção 7, junto com o sintoma e a cura, caso apareça.
- Confirmado que produção responde `HTTP 200` após o deploy anterior — o que prova de
  quebra que o `alembic upgrade head` do `CMD` funcionou, já que o `&&` impediria o
  servidor de subir se a migração falhasse.
- Lembrete repetido, uma vez, sobre rotacionar a senha.

---

### Prompt #036
**Data:** 20/09/2026
**Contexto:** Variável criada no Render, coletor confirmado rodando em produção. Eu havia
apontado o 6.3 como próximo passo, e ele sinalizou que tinha ideias próprias.

```
Beleza, qual o próximo passo? 
Tenho algumas ideias que precisamos cobrir...
```

**O que resultou:** verificação de que o coletor está vivo em produção — três gravações
do serviço no Render, de 19, 5 e 16 linhas. Não serem 35 a cada vez é a deduplicação
funcionando com dados reais. E 21 atrações já tinham duas ou mais medições.

---

### Prompt #037
**Data:** 20/09/2026
**Contexto:** As ideias, em dois grupos.

```
São algumas coisas:

Presonalização
-> Adicionar Filtros 
-> Escolha de radicalidade
-> Brinquedos Alvo
-> Repetir brinquedos (Sim ou não, escolha do usuário).

Features
-> Ao selecionar um parque, mapa muda automaticamente para as coordenadas do mapa
-> Melhorar a aparência do seletor e como ele funciona (hoje está em ordem alfabética. Será que é a melhor forma de ordenar?)
->Tela inicial apenas para selecionar o Parque
-> Pensar em mais coisas que entregam mais do que uma simples API (o que faz o site ser diferenciado?).

Essas são as ideias atuais.
```

**O que resultou — triagem, antes de implementar:**
- **Investigação dos campos reais da API**, em vez de supor. Dois achados:
  - O `/live` traz um campo **`forecast`** não usado: previsão de fila de hora em hora,
    em 25 das 40 entidades. Reposiciona a Fase 6.6 — o caminho interessante passa a ser
    usar a previsão deles como **baseline** e medir a nossa contra ela.
  - O catálogo traz só `entityType, externalId, id, location, name, parentId, slug`.
    **Radicalidade é impossível** com os dados atuais.
- **Decisões do Gabriel:** atacar a UX barata primeiro; trocar radicalidade por
  **popularidade** (fila média histórica).
- Correção de um diagnóstico meu: o seletor **já** era agrupado por destino.

**O que resultou — implementação:**
- Rota `GET /api/parks/{id}/attractions`, que responde sem exigir posição, com `bounds`.
- `core/geo.py` ganhou `bounding_box`; o mapa passou a usar `fitBounds`.
- Busca no seletor, casando parque **e** destino; destinos ordenados por porte.
- O app abre mostrando o parque, em vez de tela vazia.
- Suíte de 263 para **294 testes**.

**O bug que só apareceu ao rodar o app:** trocar para Disneyland Paris devolvia **502**.
A ThemeParks.wiki manda `location: {latitude: null, longitude: null}` para atrações sem
GPS, e como o `pydantic` valida a lista inteira de uma vez, **uma** atração sem coordenada
derrubava as outras oitenta. O parque estava inacessível **desde a Fase 1**, e sobreviveu
a 261 testes porque todas as fixtures são do Magic Kingdom, onde 86 de 86 entidades têm
coordenada.

**A armadilha percebida só ao olhar a captura de tela:** a lista sem posição ordenava
pela menor fila — a pergunta que o projeto existe para contestar — e no Disneyland Paris
os primeiros colocados eram playgrounds com fila zero. O texto passou a dizer isso
explicitamente.

---

### Prompt #038
**Data:** 20/09/2026
**Contexto:** Testando a busca de parques recém-implementada, o Gabriel encontrou um bug
e liberou o passo seguinte na mesma mensagem.

```
Uma correção a ser feita:

Quando digitamos o nome do parque a lista suspensa se ajusta a opção com o nome mais próximo e isso é ótimo. Porém, quando damos enter, o mapa não se ajusta ao parque. 

Podemos seguir com a tendência.
```

**O que resultou — a correção:**
- Causa: filtrar reconstrói o `<select>` e o navegador passa a **exibir** a primeira
  opção, mas exibir não é selecionar. Nenhum `change` disparava, e a tela mentia — dizia
  "EPCOT" enquanto o app continuava no Magic Kingdom.
- A troca de parque virou função própria, usada pelos dois caminhos.
- Dois problemas achados ao escrever os testes desta correção: os E2E **não interceptavam
  `/attractions`**, então tocavam a ThemeParks.wiki de verdade; e vários esperavam por
  `.item` sem qualificar o modo, o que criou um teste que passava sozinho e falhava na
  suíte. Ambos corrigidos.

**O que resultou — a Fase 6.3, tendência:**
- `core/trends.py`, função pura. **Os dois números do algoritmo saíram de medição sobre
  os 228 snapshots já coletados**, não de intuição:
  - 218 de 218 medições são múltiplos de 5 → limiar de 5 min.
  - 118 de 189 variações consecutivas eram zero → janela de 30 min, comparando com o
    início e não com a medição anterior.
- Integrada ao ranking, à API (`TrendOut`) e à tela (seta + cor + texto).
- **A tendência não reordena** o ranking: seria trocar a tese do projeto por heurística.
- Degradação graciosa verificada em três cenários: sem banco, banco fora do ar, e banco
  sem a tabela.
- `park_history()` novo, para não fazer 35 idas ao banco por resposta.
- Verificado na tela com dados reais do Neon: *"Subiu de 10 para 15 nos últimos 22 min."*
- Suíte de 294 para **339 testes**.

**A frase prometida desde 11/09/2026 agora existe de verdade:**
*"Swiss Family Treehouse — 3 min de caminhada + 5 min de fila = 8 min. Caiu de 45 para 20
nos últimos 30 min."*

---

### Prompt #039
**Data:** 20/09/2026
**Contexto:** Tendência entregue e no ar. Restavam os passos 6.4 (rota de histórico),
6.5 (gráfico) e 6.6 (previsão).

```
Vamos nessa!
```

**O que resultou:** os passos **6.4 e 6.5** de uma vez — a rota sozinha seria invisível, a
mesma lição do 6.3.

- `core/history.py` — resumo de uma série (mín, média, máx, atual, amplitude).
- `GET /parks/{id}/attractions/{id}/history?hours=6` — **o primeiro endpoint do NextUp que
  serve dado nosso.** Todos os outros são a ThemeParks.wiki reempacotada.
- Gráfico em **SVG escrito à mão**, sem biblioteca: 50–200 KB para desenhar uma linha não
  se justificam num projeto sem etapa de build.
- Suíte de 339 para **364 testes**.

**Uma regra se inverteu entre as rotas.** Na recomendação, banco fora do ar é engolido e a
resposta sai sem tendência. Na rota de histórico dá **503** — ali o histórico *é* a
resposta, e servir série vazia mentiria dizendo que a fila ficou parada.

**O erro de visualização percebido só ao olhar a captura:** a primeira versão escalava o
eixo vertical do menor ao maior valor da série, que é o padrão de muitas bibliotecas. A
linha de uma atração cujo histórico foi de 10 a 5 minutos ficava colada no fundo, e uma
oscilação de cinco minutos desenhava a mesma queda dramática que um desabamento de 90 para
5. Escala truncada exagera variação pequena e apaga magnitude; para fila, o eixo tem de
começar em zero, e aí a altura da linha *é* a fila.

---

### Prompt #040
**Data:** 20/09/2026
**Contexto:** Último passo do roadmap original — 6.6, previsão da fila na chegada.

```
Siga!
```

**O que resultou: a Fase 6 fechada, com um resultado negativo medido.**

Antes de implementar qualquer modelo, um backtest sobre 315 medições reais comparou a
previsão contra o baseline óbvio — **persistência**, que é "a fila daqui a N minutos é a
fila de agora", exatamente o que o app já fazia desde a Fase 2:

| Horizonte | Persistência | Tendência extrapolada |
|---|---|---|
| 5 min | **1,86** | 2,66 |
| 10 min | **2,50** | 3,97 |
| 30 min | **4,65** | 9,02 |

Extrapolar **piora** em todo horizonte. A suspeita de viés — a fila fica parada na maior
parte do tempo, o que daria vantagem de graça à persistência — foi testada isolando só os
casos em que a fila mudou, e a persistência continuou ganhando. A razão é que **a direção
não persiste**: uma fila que subiu nos últimos trinta minutos tem chance parecida de cair
nos próximos.

**A decisão foi não implementar.** Trocar o modelo do ranking teria piorado o produto e
ficado bonito no roadmap, que é o pior par possível.

**O que foi construído no lugar:**
- `core/forecast.py` e `tests/test_forecast.py` — os modelos, a régua e a conclusão fixada
  em teste. Baseline ruim documentado evita que a próxima pessoa tente a mesma ideia.
- Tabela `queue_forecasts` e o coletor gravando nela. Sobrou **um candidato não testado**:
  a previsão horária da própria fonte, que o backtest não pôde avaliar porque ninguém a
  guardava. Verificado em produção: 158 previsões, 26 atrações, sete horas à frente.
- Suíte de 364 para **393 testes**.

**Todas as seis fases do roadmap original estão entregues.**

---

## Sessão 007 — 20/09/2026 *(continuação)*

### Prompt #041
**Data:** 20/09/2026
**Contexto:** Roadmap original fechado. O `forecast` da fonte passara a ser gravado, mas
sem dados suficientes para avaliá-lo.

```
Beleza, marque um dia para testarmos o forecast nos nossos arquivos de organização (.md) e vamos seguir para as fazes de personalização.
```

**O que resultou — o agendamento:**
- **27/09/2026** marcado no `docs/PROJETO.md` (fim do bloco da Fase 6.6) e no `CLAUDE.md`.
- Uma semana, e não um número redondo: **filas de sábado não se parecem com as de terça**,
  e o forecast é exatamente um perfil de padrão do dia. Avaliar só com dias úteis mediria
  metade do fenômeno.
- O roteiro do dia inclui conferir buracos na coleta **antes** de concluir qualquer coisa —
  o Render hiberna, e uma madrugada perdida enviesaria a medição em silêncio.

**O que resultou — a Fase 7 aberta e o 7.1 entregue:**
- Fase 7 desenhada no roadmap, com as quatro ideias dele e a ordem justificada: **7.1 e
  7.2 são a fundação do roteiro do dia**, e por isso vêm primeiro.
- Decisão registrada: personalização no **`localStorage`**, sem conta de usuário.
- `web/visitadas.js` — o "já fui hoje", com carimbo da **data do parque**.
- Suíte de 393 para **403 testes**.

**Um bug de CSS que o teste encontrou, e que valia para a página inteira:** o aviso
aparecia mesmo com o atributo `hidden`. O navegador aplica `display: none` a `[hidden]`
pela folha de estilo padrão, que perde para qualquer regra de autor — e
`.visitadas-aviso { display: flex }` a sobrescrevia. O projeto tinha **sete** elementos
usando `hidden` e nenhuma regra `[hidden]` no CSS.

---

### Prompt #042
**Data:** 20/09/2026
**Contexto:** O "já fui hoje" recém-entregue. O Gabriel foi usar o app de verdade e achou
um bug que a suíte não pegava.

```
Está funcional, porém pode melhorar.

Quando o usuário marca todas as 8 primeiras recomendações como Já fui e clica no botão atualizar (para atualizar a lista de atrações), o site não mostra mais nenhuma atração nova, acredito que ele ainda esteja acreditando que as 8 melhores são as visitadas, mas elas ficam ocultas e não são mostradas. Devemos resolver isso, tirando elas da lista de atrações momentaneamente (melhor forma de solução? se não, pode fazer de outro jeito)
```

**O diagnóstico dele estava certo.** A tela pedia `limit=8` ao servidor e só depois
escondia as visitadas — as outras vinte nunca chegaram a existir para o navegador. E a
mensagem "você já passou por todas as atrações disponíveis" **mentia**, com vinte atrações
livres a poucos metros.

É a **quarta vez** que o projeto tropeça no mesmo padrão, e a regra já estava escrita no
`CLAUDE.md` desde a Fase 3: *peça tudo, corte na exibição*. As três primeiras foram
contagens erradas; esta foi uma tela vazia.

**Sobre a solução que ele sugeriu** — mandar os IDs visitados para a API filtrar —, foi
considerada e recusada: acoplaria o servidor ao estado do navegador e contradiria a decisão
da própria Fase 7, de a personalização não sair do aparelho.

**O que resultou:**
- A tela passou a pedir `limit=0` e a cortar depois de filtrar. **Custo medido: 3,5 KB →
  12,5 KB** por atualização.
- Marcar deixou de encolher a lista: a nona colocada sobe.
- No modo "Mostrar", as visitadas **somam-se** às sugestões em vez de tomar a vaga delas.
- O mock dos testes devolvia oito fixos — um mock que entrega menos que a API real testa um
  app que não existe. Corrigido, e três testes novos cobrem o cenário relatado.
- Suíte de 403 para **406 testes**.

---

### Prompt #043
**Data:** 20/09/2026
**Contexto:** Bug do "já fui" corrigido. Faltavam 7.2 (brinquedos alvo), 7.3 (filtros) e
7.4 (popularidade).

```
Seguimos!
```

**O que resultou: a Fase 7.2 — "Você veio por estas".**

A decisão de produto veio antes do código: **o que um alvo faz com o ranking?** Três
alternativas foram descartadas — subir ao topo (quebra a tese do projeto), ganhar bônus no
custo (distorce o número) e só destacar na lista (não resolve nada, o alvo continua
enterrado).

O que se escolheu foi reconhecer que são **perguntas diferentes**: o ranking responde "o
que compensa mais agora"; a lista de alvos responde "quando devo ir naquilo que eu vim
fazer". Cada uma ganhou seu espaço, e nenhuma precisa mentir.

**O caso que justifica a seção**, verificado com dados reais: marcando como alvo a **pior
colocada de trinta** — Peter Pan's Flight, 58 minutos —, ela aparece no topo da tela.
Enterrada no ranking, seria invisível justamente para quem veio por ela.

- `web/preferencias.js` substitui o `visitadas.js`, com base comum e dois namespaces.
- **Alvos não têm prazo**, ao contrário das visitadas: alvo é desejo, não acontecimento.
- Suíte de 406 para **417 testes**.

**Uma armadilha de tema escuro, evitada por verificação:** o botão de alvo usa o roxo
`--profundo`, que no tema claro é escuro e no escuro vira lilás claro — texto branco
sumiria. Foi preciso criar `--sobre-profundo`, exatamente como o projeto já fizera com
`--sobre-quente`. É a segunda vez que a mesma armadilha aparece.

---

### Prompt #044
**Data:** 20/09/2026
**Contexto:** A Fase 7.2 recém-entregue. O Gabriel aprovou a exibição e apontou a falha no
mecanismo de seleção.

```
Legal, gostei da forma que são exibidas depois que o usuário seleciona. Mas o mecânismo de seleção é falho, visto que o usuário não vê a lista toda e atrações do parque.

Crie abaixo do mapa uma parte onde o usuário irá entende que deve selecionar os alvos e dê a lista completa para ele.

Botão de mais, onde quando clicado aparece a lista suspensa ou algo do tipo.

O usuário deve conseguir remover alvos também.
```

**A crítica estava certa, e o problema era maior que o descrito.** Marcar alvos só pelo
ranking deixava **27 de 35 atrações inalcançáveis** — quem veio pelo Space Mountain não
conseguia dizer isso ao app até ele aparecer entre as oito melhores. E a seção ficava
escondida enquanto vazia, então a funcionalidade **não existia** para quem nunca
tropeçasse nela.

**O que resultou:**
- A seção passou a ser **sempre visível**, com convite quando vazia.
- `<details>` nativo com o catálogo completo: busca, fila atual de cada atração e caixa de
  seleção por linha. Marcar e remover pelo mesmo lugar.
- **Funciona antes do GPS** — a rota `/attractions` não exige posição, então a lista de
  desejos se monta a caminho do parque.
- Suíte de 417 para **427 testes**.

**Um problema de UX que só apareceu escrevendo o teste:** a primeira versão redesenhava o
catálogo a cada marcação, e como as marcadas sobem ao topo, a lista **se reordenava sob o
dedo do visitante**. Agora a linha só muda de aparência, e a reordenação espera o painel
reabrir — as marcadas no topo servem a quem veio *remover* algo, que é outro momento.

---

## Sessão 008 — 21/09/2026

### Prompt #045
**Data:** 21/09/2026
**Contexto:** Fase 7 com 7.1 e 7.2 entregues. A coleta atravessou a noite sem buracos —
1221 medições e 502 previsões, contra 353 e 158 no dia anterior.

```
Vamos para os filtros;
```

**O que resultou: a Fase 7.3.** A pergunta que definiu o escopo veio antes do código: *o
ranking já ordena por custo total — o que sobra para um filtro fazer?*

Filtrar por custo seria redundante. O que o ranking não resolve é que ele **soma as
parcelas**: 5 min de caminhada + 35 de fila dá o mesmo total que 20 + 20, e são
experiências opostas para quem empurra um carrinho. Os filtros úteis são os que separam de
volta o que o custo juntou — daí **fila máxima** e **caminhada máxima**, e só.

- O filtro **corta, nunca reordena**: mudar o critério de ordenação não é filtrar.
- **Os alvos escapam do filtro** — esconder o que o visitante marcou como imperdível seria
  o app discutindo com uma escolha explícita.
- **Globais, não por parque:** "não quero andar muito" é sobre a pessoa.
- Selo "ativos" no cabeçalho, e a lista vazia passou a distinguir três causas.
- Suíte de 427 para **437 testes**.

**Um teste que fingia testar.** A primeira versão do teste "filtro esconde tudo" tinha um
`if` que **nunca entrava**: medindo a fixture, com fila ≤ 5 e caminhada ≤ 5 ainda sobrava
uma atração. Um teste que sempre passa e nunca verifica dá confiança falsa. O cenário virou
um realista — apertar o filtro ao mínimo **e** marcar como visitada a única que passa.

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

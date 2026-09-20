# Imagem do NextUp — a API e a interface num contêiner só.
#
# O build tem duas etapas, e a razão é o tamanho da imagem final. A primeira
# etapa instala as dependências (o que exige compilador, cabeçalhos e cache de
# pacotes); a segunda copia só o resultado. Assim o compilador não viaja junto
# para o servidor: menos coisa para baixar, menos superfície para atacar.
#
# Construir e rodar:
#
#     docker build -t nextup .
#     docker run --rm -p 8000:8000 nextup
#
# Depois, abrir http://localhost:8000

# ---------------------------------------------------------------------------
# Etapa 1 — construir o ambiente com as dependências
# ---------------------------------------------------------------------------
# A versão é fixada de propósito. `python:3.13-slim` sem a versão exata mudaria
# sozinha com o tempo, e um build que funciona hoje falharia daqui a meses sem
# ninguém ter tocado no código.
FROM python:3.13.15-slim AS construcao

# Onde o venv vai morar. Fora de /app para não ser sobrescrito por um volume
# montado durante o desenvolvimento.
ENV VENV=/opt/venv
RUN python -m venv $VENV
ENV PATH="$VENV/bin:$PATH"

WORKDIR /app

# O código inteiro vem antes do `pip install` porque o `hatchling` empacota o
# que está em `src/nextup`: instalar com a pasta pela metade produziria um
# pacote incompleto, que só falharia em produção.
#
# O preço é que editar um arquivo Python invalida o cache desta camada e
# reinstala as dependências. Para um projeto com quatro dependências isso custa
# segundos — barato demais para justificar um truque frágil em troca.
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# ---------------------------------------------------------------------------
# Etapa 2 — a imagem que realmente vai para o servidor
# ---------------------------------------------------------------------------
FROM python:3.13.15-slim AS producao

ENV VENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    # Não gerar os .pyc: dentro de um contêiner eles só ocupam espaço, já que o
    # sistema de arquivos é descartado quando o contêiner morre.
    PYTHONDONTWRITEBYTECODE=1 \
    # Sem buffer na saída: o log aparece na hora em vez de ficar preso esperando
    # o buffer encher — o que faria depurar um contêiner virar adivinhação.
    PYTHONUNBUFFERED=1 \
    NEXTUP_WEB_DIR=/app/web

# Rodar como root dentro do contêiner é o padrão do Docker e é uma má ideia: se
# alguém escapar da aplicação, já entra com o usuário mais poderoso da máquina.
# Um usuário sem privilégios limita o estrago.
RUN useradd --create-home --uid 1000 nextup

# O dono é o usuário sem privilégios porque, sem `NEXTUP_DATABASE_URL`, o padrão
# do projeto é um SQLite criado aqui dentro. Sem permissão de escrita, a migração
# do start falharia e o contêiner não subiria — inclusive no CI, que constrói a
# imagem sem banco configurado.
WORKDIR /app
RUN chown nextup:nextup /app

# O código não é copiado de novo: ele já veio instalado dentro do venv. Só o
# frontend precisa existir como arquivo, porque é servido do disco.
COPY --from=construcao $VENV $VENV
COPY --chown=nextup:nextup web/ ./web/

# As migrações, por outro lado, precisam viajar como arquivo: o Alembic lê os
# scripts do disco, não do pacote instalado. Sem isto, `alembic upgrade head`
# dentro do contêiner não encontraria revisão nenhuma e diria que está tudo em dia.
COPY --chown=nextup:nextup alembic.ini ./
COPY --chown=nextup:nextup migrations/ ./migrations/

USER nextup

EXPOSE 8000

# O orquestrador usa isto para saber se o contêiner está saudável e reiniciá-lo
# quando não estiver. Aponta para `/api/health`, que de propósito NÃO consulta a
# ThemeParks.wiki: uma instabilidade da fonte externa não deve derrubar um
# contêiner que está perfeitamente de pé.
# `start-period` maior que antes: o contêiner agora aplica as migrações antes de
# abrir a porta, e durante essa janela o healthcheck falharia sem que houvesse
# problema nenhum.
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD python -c "import os,urllib.request,sys; porta=os.getenv('PORT','8000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{porta}/api/health', timeout=4).status == 200 else 1)"

# Três escolhas deliberadas nesta linha:
#
# `alembic upgrade head` antes de tudo — o banco é levado à forma que este código
# espera, no próprio deploy. A alternativa seria rodar a migração à mão antes de
# cada publicação, e o dia em que alguém esquecer é o dia em que a aplicação sobe
# consultando uma coluna que ainda não existe. Com o `&&`, uma migração que falha
# impede o servidor de subir: é falhar alto, e melhor que servir dados errados.
#
# `0.0.0.0` e não `127.0.0.1` — dentro do contêiner, ouvir só no endereço local
# significaria recusar todo mundo que vem de fora dele, inclusive você.
#
# `${PORT:-8000}` — plataformas de hospedagem escolhem a porta e a informam por
# variável de ambiente (o Render usa 10000 por padrão). Fixar 8000 faria o
# serviço subir e, mesmo saudável, nunca receber uma requisição.
#
# O `exec` importa: sem ele, o `sh` continuaria como processo principal e
# engoliria o sinal de desligamento, fazendo o contêiner demorar a encerrar.
CMD alembic upgrade head && exec uvicorn nextup.api.main:app --host 0.0.0.0 --port ${PORT:-8000}

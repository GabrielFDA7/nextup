"""Configuração central do NextUp.

Todo número mágico do projeto mora aqui. A regra é simples: se um valor pode
precisar de ajuste depois — um tempo de cache, uma velocidade, uma URL — ele não
fica espalhado pelo código, fica nesta página.

Cada constante pode ser sobrescrita por variável de ambiente, o que permite
mudar o comportamento em produção sem tocar no código. Veja `.env.example`.
"""

import os
from urllib.parse import parse_qs, urlencode, urlsplit

from dotenv import load_dotenv

# Carrega o `.env` da raiz, se existir, para quem desenvolve não precisar exportar
# variável na mão a cada comando — em especial a URL do banco, que o `alembic`
# também precisa enxergar.
#
# `override=False` é essencial e é o padrão: variável já definida no ambiente vence
# o arquivo. Em produção quem manda são as variáveis do Render, e um `.env`
# esquecido dentro da imagem não pode sobrescrevê-las.
load_dotenv(override=False)

# ---------------------------------------------------------------------------
# API externa — ThemeParks.wiki
# ---------------------------------------------------------------------------

THEMEPARKS_BASE_URL = os.getenv("NEXTUP_API_BASE_URL", "https://api.themeparks.wiki/v1")

#: Enviado em toda requisição. Identificar o cliente é boa educação com uma API
#: pública e gratuita: se causarmos algum problema, eles sabem com quem falar.
USER_AGENT = os.getenv("NEXTUP_USER_AGENT", "NextUp/0.1 (+https://github.com/GabrielFDA7/nextup)")

#: Segundos até desistir de uma requisição. Sem timeout, uma API lenta trava o
#: nosso app inteiro esperando uma resposta que talvez nunca chegue.
REQUEST_TIMEOUT_S = float(os.getenv("NEXTUP_REQUEST_TIMEOUT", "10.0"))

#: Quantas vezes tentar de novo em caso de falha de rede, com espera crescente
#: entre as tentativas (backoff exponencial).
MAX_RETRIES = int(os.getenv("NEXTUP_MAX_RETRIES", "3"))

#: Espera da primeira retentativa, em segundos. As seguintes dobram: 0,5s, 1s, 2s.
#: Dobrar dá tempo à API de se recuperar — insistir no mesmo ritmo só piora um
#: servidor que já está sobrecarregado.
BACKOFF_BASE_S = float(os.getenv("NEXTUP_BACKOFF_BASE", "0.5"))

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
# Os dois TTLs são muito diferentes de propósito, e o motivo é a natureza do dado:
#
#   /live     → fila e status, mudam a cada poucos minutos  → TTL curto
#   /children → nome e coordenada da atração, quase nunca mudam → TTL longo
#
# Guardar o catálogo por 24h evita milhares de requisições inúteis pedindo uma
# informação que não muda desde 1971.

LIVE_DATA_TTL_S = int(os.getenv("NEXTUP_LIVE_TTL", "60"))
CATALOG_TTL_S = int(os.getenv("NEXTUP_CATALOG_TTL", str(24 * 60 * 60)))

# ---------------------------------------------------------------------------
# Parâmetros de caminhada
# ---------------------------------------------------------------------------

#: Velocidade média a pé dentro de um parque, em metros por segundo.
#: Uma pessoa caminha a ~1,4 m/s na rua. Num parque lotado, empurrando carrinho,
#: com criança e parando para olhar vitrine, o valor real é bem menor.
WALKING_SPEED_MPS = float(os.getenv("NEXTUP_WALKING_SPEED", "1.1"))

#: Correção de sinuosidade do trajeto.
#: A fórmula de Haversine devolve distância em linha reta, mas ninguém atravessa
#: um lago, um castelo ou um prédio — anda pelas trilhas, que fazem curva. Esse
#: multiplicador aproxima a distância real percorrida.
PATH_WINDING_FACTOR = float(os.getenv("NEXTUP_WINDING_FACTOR", "1.3"))

# ---------------------------------------------------------------------------
# Recomendação
# ---------------------------------------------------------------------------

#: Quantas atrações devolver no ranking, por padrão.
DEFAULT_RESULT_LIMIT = int(os.getenv("NEXTUP_RESULT_LIMIT", "5"))

#: Parque usado como padrão no MVP (Magic Kingdom, Walt Disney World).
DEFAULT_PARK_ID = os.getenv("NEXTUP_DEFAULT_PARK", "75ea578a-adc8-4116-a54d-dccb60765ef9")

# ---------------------------------------------------------------------------
# Banco de dados — histórico de filas (Fase 6)
# ---------------------------------------------------------------------------
# O padrão é um SQLite em arquivo, na raiz do projeto: quem clonar o repositório
# roda o projeto inteiro sem instalar banco nenhum. Em produção, a variável
# aponta para um Postgres gerenciado.
#
# O prefixo `+aiosqlite` / `+asyncpg` escolhe o driver assíncrono. Sem ele, o
# SQLAlchemy usaria o driver síncrono e travaria o event loop do FastAPI a cada
# gravação — o servidor pararia de responder enquanto escreve no banco.
#
#: Atenção ao publicar: plataformas costumam entregar a URL no formato
#: `postgres://` ou `postgresql://`, sem driver. `normalize_database_url` conserta.
DATABASE_URL = os.getenv("NEXTUP_DATABASE_URL", "sqlite+aiosqlite:///./nextup.db")

#: Quanto tempo de histórico manter. Um parque com ~35 atrações medidas a cada 5
#: minutos gera ~6 mil linhas por dia; 90 dias são ~540 mil, que qualquer Postgres
#: aguenta sem suar — mas guardar para sempre um dado que ninguém consulta é só
#: conta crescendo.
HISTORY_RETENTION_DAYS = int(os.getenv("NEXTUP_HISTORY_RETENTION_DAYS", "90"))


#: Parâmetros que só a `libpq` entende — a biblioteca C que o `psycopg` usa por
#: baixo. O `asyncpg` não é libpq: tem implementação própria do protocolo e API
#: própria para TLS, então recebê-los faz a conexão morrer com
#: `TypeError: connect() got an unexpected keyword argument 'sslmode'`.
#:
#: Eles não são removidos por serem inúteis, e sim porque o **mesmo requisito é
#: atendido de outro jeito**: o `storage/engine.py` monta um contexto TLS com
#: verificação completa. Ver `ssl_is_required`.
LIBPQ_ONLY_PARAMS = frozenset({"sslmode", "channel_binding"})


def _partes_da_url(url: str) -> tuple[str, dict[str, list[str]]]:
    """Separa a URL da sua query string, já decodificada."""
    partes = urlsplit(url)
    return url.split("?", 1)[0], parse_qs(partes.query, keep_blank_values=True)


def normalize_database_url(url: str) -> str:
    """Deixa a URL do banco no formato que o nosso driver assíncrono aceita.

    Faz duas correções, ambas por causa de URLs que funcionam em toda parte menos
    aqui — o mesmo tipo de armadilha da porta fixa que pegamos na Fase 5.

    **1. O prefixo.** Render, Heroku e afins entregam `postgres://...`, herança de
    uma convenção antiga. O SQLAlchemy 2 não reconhece mais esse prefixo, e mesmo
    `postgresql://` sozinho carregaria o driver síncrono.

    **2. Os parâmetros da libpq.** O Neon entrega a URL com
    `?sslmode=require&channel_binding=require`, que é o padrão do cliente oficial
    do Postgres. O `asyncpg` recusa os dois. Removê-los aqui é o que permite colar
    no `.env` exatamente a string que o painel do Neon mostra, sem editar nada — e
    editar à mão é justamente o passo que alguém esquece no dia do deploy.

    Args:
        url: URL como veio do ambiente.

    Returns:
        A URL com driver assíncrono explícito e sem parâmetros que ele não entenda.
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://"):
        url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)

    if "?" not in url:
        return url

    base, parametros = _partes_da_url(url)
    mantidos = {k: v for k, v in parametros.items() if k.lower() not in LIBPQ_ONLY_PARAMS}

    if not mantidos:
        return base
    return f"{base}?{urlencode(mantidos, doseq=True)}"


def ssl_is_required(url: str) -> bool:
    """Se a URL pede conexão cifrada.

    Lida antes de `normalize_database_url` descartar o `sslmode`, para que a
    *intenção* expressa na URL não se perca junto com o parâmetro. Quem publica
    escreve `sslmode=require` e espera conexão cifrada; entregar uma conexão em
    texto plano porque o driver não reconheceu a palavra seria o pior resultado
    possível — funciona, ninguém percebe, e a senha do banco viaja aberta.

    Args:
        url: URL como veio do ambiente, ainda com os parâmetros originais.

    Returns:
        `True` quando há `sslmode` diferente de `disable`.
    """
    if "?" not in url:
        return False

    _, parametros = _partes_da_url(url)
    modos = parametros.get("sslmode") or parametros.get("sslMode") or []
    return bool(modos) and modos[0].lower() != "disable"

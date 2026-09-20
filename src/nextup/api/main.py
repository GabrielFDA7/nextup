"""Aplicação FastAPI do NextUp.

Monta o app, liga as rotas e faz três coisas que só podem acontecer aqui:

1. **Cria o cliente uma vez**, no `lifespan`, para o cache sobreviver entre
   requisições e a conexão HTTP ser reaproveitada.
2. **Traduz os erros do projeto em códigos HTTP.** As rotas não precisam saber
   disso, e nenhuma delas escreve `try/except`.
3. **Libera o CORS**, sem o qual o navegador recusa a resposta na Fase 4.

Para subir em desenvolvimento:

    uvicorn nextup.api.main:app --reload

A documentação interativa fica em `/docs`, gerada sozinha a partir dos schemas.
"""

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from nextup import __version__
from nextup.api.routes import router
from nextup.api.schemas import ErrorOut
from nextup.clients.errors import (
    EntityNotFoundError,
    InvalidResponseError,
    ThemeParksUnavailableError,
)
from nextup.clients.themeparks import ThemeParksClient
from nextup.collector import run_collector
from nextup.config import COLLECTOR_ENABLED
from nextup.storage import create_engine

logger = logging.getLogger(__name__)

#: Origens liberadas para chamar a API pelo navegador. Em produção deve apontar
#: para o domínio do frontend; `*` só faz sentido enquanto a API é pública e
#: somente leitura, como agora.
CORS_ORIGINS = os.getenv("NEXTUP_CORS_ORIGINS", "*").split(",")

#: Pasta do frontend. Servi-lo pelo próprio FastAPI evita precisar de um segundo
#: servidor e faz o app inteiro caber num contêiner só. A variável de ambiente
#: existe porque no Docker o caminho não é o mesmo do repositório.
WEB_DIR = Path(os.getenv("NEXTUP_WEB_DIR", str(Path(__file__).resolve().parents[3] / "web")))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Cria o cliente e o coletor ao subir, e desmonta os dois ao desligar.

    O `yield` separa as duas metades: o que vem antes roda na inicialização, o
    que vem depois roda no encerramento — inclusive quando o servidor é derrubado
    por um erro. É o mesmo mecanismo do `with`, aplicado ao ciclo de vida do app.

    **O coletor compartilha o cliente com as rotas**, e isso é intencional: os dois
    passam a dividir o mesmo cache. Uma coleta que caia dentro dos 60 segundos de
    cache do `/live` reaproveita o que uma visita ao site acabou de buscar, em vez
    de pedir de novo à ThemeParks.wiki.
    """
    async with httpx.AsyncClient() as conexao:
        app.state.themeparks_client = ThemeParksClient(http_client=conexao)
        app.state.collector_task = None

        # O engine nasce sempre, e não só quando o coletor está ligado: desde a
        # Fase 6.3 as rotas também leem o histórico, para contar a tendência.
        # Criá-lo é barato — o SQLAlchemy só abre conexão de verdade no primeiro
        # uso, então um serviço que nunca consulta o banco não paga nada por isto.
        app.state.db_engine = create_engine()

        if COLLECTOR_ENABLED:
            app.state.collector_task = asyncio.create_task(
                run_collector(
                    client=app.state.themeparks_client,
                    engine=app.state.db_engine,
                )
            )
        else:
            logger.info("coletor desligado por NEXTUP_COLLECTOR_ENABLED")

        try:
            yield
        finally:
            await _encerrar_coletor(app)


async def _encerrar_coletor(app: FastAPI) -> None:
    """Cancela a tarefa de coleta e fecha o banco, sem travar o desligamento.

    Cancelar é pedir, não mandar: a tarefa só para no próximo ponto em que espera
    por algo. Por isso o `await` logo em seguida — sem ele o processo poderia
    morrer com uma transação pela metade.

    O `CancelledError` que volta aqui é a confirmação de que o cancelamento
    funcionou, não um erro a propagar. Deixá-lo subir faria o encerramento de um
    servidor saudável parecer uma falha nos logs.
    """
    tarefa = getattr(app.state, "collector_task", None)
    if tarefa is not None:
        tarefa.cancel()
        with suppress(asyncio.CancelledError):
            await tarefa

    motor = getattr(app.state, "db_engine", None)
    if motor is not None:
        await motor.dispose()


def criar_app() -> FastAPI:
    """Monta a aplicação.

    É uma função, e não um `app = FastAPI()` solto, para que os testes possam
    criar instâncias independentes — cada uma com seu próprio cache.
    """
    app = FastAPI(
        title="NextUp",
        version=__version__,
        summary="Para qual atração ir agora, considerando fila e distância.",
        description=(
            "Ranqueia atrações de parques temáticos por `caminhada + fila`, e não "
            "pela menor fila: a fila mais curta pode estar do outro lado do parque.\n\n"
            "Dados da [ThemeParks.wiki](https://themeparks.wiki). "
            "Projeto sem vínculo com a The Walt Disney Company."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    _registrar_erros(app)
    app.include_router(router, prefix="/api")

    # Depois das rotas, nunca antes: montado na raiz, o arquivo estático engoliria
    # `/api/...`. O `if` deixa a API funcionar mesmo sem o frontend presente —
    # instalada como biblioteca, por exemplo.
    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

    return app


def _registrar_erros(app: FastAPI) -> None:
    """Mapeia os erros do projeto para códigos HTTP.

    A escolha de cada código diz ao cliente **de quem é o problema** e se vale a
    pena tentar de novo — que é a informação mais útil que uma API pode dar:

        404  o ID não existe; tentar de novo não resolve
        502  a fonte respondeu algo que não entendemos (contrato mudou)
        503  a fonte está fora do ar; tentar de novo mais tarde pode funcionar
    """

    @app.exception_handler(EntityNotFoundError)
    async def _nao_encontrado(_: Request, erro: EntityNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content=ErrorOut(detail=str(erro)).model_dump())

    @app.exception_handler(ThemeParksUnavailableError)
    async def _indisponivel(_: Request, erro: ThemeParksUnavailableError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=ErrorOut(
                detail="A fonte de dados está indisponível. Tente novamente em instantes."
            ).model_dump(),
            # Sugere ao cliente quanto esperar antes de insistir, em vez de
            # deixá-lo martelar a nossa API — que martelaria a fonte.
            headers={"Retry-After": "30"},
        )

    @app.exception_handler(InvalidResponseError)
    async def _resposta_invalida(_: Request, erro: InvalidResponseError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content=ErrorOut(
                detail="A fonte de dados respondeu em formato inesperado."
            ).model_dump(),
        )


app = criar_app()

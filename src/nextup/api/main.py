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

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from nextup import __version__
from nextup.api.routes import router
from nextup.api.schemas import ErrorOut
from nextup.clients.errors import (
    EntityNotFoundError,
    InvalidResponseError,
    ThemeParksUnavailableError,
)
from nextup.clients.themeparks import ThemeParksClient

#: Origens liberadas para chamar a API pelo navegador. Em produção deve apontar
#: para o domínio do frontend; `*` só faz sentido enquanto a API é pública e
#: somente leitura, como agora.
CORS_ORIGINS = os.getenv("NEXTUP_CORS_ORIGINS", "*").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Cria o cliente ao subir e o fecha ao desligar.

    O `yield` separa as duas metades: o que vem antes roda na inicialização, o
    que vem depois roda no encerramento — inclusive quando o servidor é derrubado
    por um erro. É o mesmo mecanismo do `with`, aplicado ao ciclo de vida do app.
    """
    async with httpx.AsyncClient() as conexao:
        app.state.themeparks_client = ThemeParksClient(http_client=conexao)
        yield


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

"""Dependências injetadas nas rotas.

O cliente da ThemeParks.wiki é **um só para o processo inteiro**, e isso não é
detalhe de performance — é o que faz o cache existir.

Um cliente novo por requisição nasceria com o cache vazio, e cada visitante que
abrisse o app dispararia requisições à API pública para buscar o mesmo catálogo
que acabou de ser buscado. O TTL de 24h só tem efeito se o cache sobreviver entre
as requisições.

De quebra, a conexão HTTP é reaproveitada: sem isso, cada requisição refaria o
aperto de mão TCP e TLS com o servidor.
"""

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine

from nextup.clients.themeparks import ThemeParksClient


def obter_cliente(request: Request) -> ThemeParksClient:
    """Entrega o cliente criado na inicialização da aplicação.

    Ele fica guardado no estado do app, montado pelo `lifespan` em `main.py`.
    """
    return request.app.state.themeparks_client


def obter_engine(request: Request) -> AsyncEngine | None:
    """Entrega o engine do banco, ou `None` se não houver banco configurado.

    **Opcional de propósito.** O histórico enriquece a recomendação com a
    tendência, mas não a sustenta: o ranking funciona desde a Fase 2 sem banco
    nenhum. Devolver `None` em vez de estourar deixa a rota degradar com
    elegância — perde-se a frase "caiu de 45 para 20", não a resposta.

    O mesmo vale para a aplicação instalada como biblioteca, ou rodando num
    ambiente onde ninguém configurou `NEXTUP_DATABASE_URL`.
    """
    return getattr(request.app.state, "db_engine", None)

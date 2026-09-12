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

from nextup.clients.themeparks import ThemeParksClient


def obter_cliente(request: Request) -> ThemeParksClient:
    """Entrega o cliente criado na inicialização da aplicação.

    Ele fica guardado no estado do app, montado pelo `lifespan` em `main.py`.
    """
    return request.app.state.themeparks_client

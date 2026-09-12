"""Erros do cliente da ThemeParks.wiki.

Existem para que o resto do projeto não precise importar `httpx` só para saber
o que deu errado. Se um dia trocarmos de biblioteca HTTP — ou de fonte de dados —
quem trata esses erros continua igual.

É a mesma ideia dos modelos: `clients/` é o único lugar que conhece os detalhes
de fora; o que atravessa a fronteira já vem no idioma do NextUp.
"""


class ThemeParksError(Exception):
    """Base de todos os erros do cliente.

    Quem quiser tratar "qualquer problema ao falar com a API" captura esta.
    """


class EntityNotFoundError(ThemeParksError):
    """A entidade pedida não existe na API (HTTP 404).

    Separada das demais porque é a única que **não** adianta tentar de novo:
    um ID errado continuará errado na segunda tentativa.
    """

    def __init__(self, entity_id: str) -> None:
        self.entity_id = entity_id
        super().__init__(f"Entidade não encontrada na ThemeParks.wiki: {entity_id}")


class ThemeParksUnavailableError(ThemeParksError):
    """A API não respondeu, mesmo depois de todas as tentativas.

    Pode ser queda da API, timeout ou internet fora. Do ponto de vista do NextUp
    dá no mesmo: não há dado novo agora.
    """

    def __init__(self, url: str, attempts: int, cause: Exception | None = None) -> None:
        self.url = url
        self.attempts = attempts
        self.cause = cause
        super().__init__(f"ThemeParks.wiki indisponível após {attempts} tentativa(s): {url}")


class InvalidResponseError(ThemeParksError):
    """A API respondeu, mas com algo que não conseguimos interpretar.

    Normalmente significa que o contrato da API mudou — risco já previsto na
    seção 8 do `docs/PROJETO.md`. Falhar aqui, alto e claro, é melhor que seguir
    com dado pela metade.
    """

    def __init__(self, url: str, detail: str) -> None:
        self.url = url
        self.detail = detail
        super().__init__(f"Resposta inesperada de {url}: {detail}")

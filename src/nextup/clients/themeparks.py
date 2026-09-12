"""Cliente da ThemeParks.wiki — o único lugar do projeto que fala com a rede.

Junta as três peças da Fase 1: `httpx` faz a requisição, o `TTLCache` evita
repetir pedidos, e os modelos `pydantic` validam o que chega. Para fora, nada
disso aparece: quem chama pede `get_live_data(park_id)` e recebe objetos prontos.

Duas responsabilidades merecem destaque, porque são boa cidadania com uma API
pública e gratuita mantida por voluntários:

1. **Cache antes de pedir.** Catálogo por 24h, fila por 60s.
2. **Backoff exponencial.** Se a API falhar, esperamos cada vez mais entre as
   tentativas, em vez de martelar um servidor que já está em dificuldade.

O cliente é assíncrono porque o tempo aqui é quase todo espera de rede: enquanto
uma resposta não chega, o programa pode cuidar de outra coisa.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from nextup.clients.cache import TTLCache
from nextup.clients.errors import (
    EntityNotFoundError,
    InvalidResponseError,
    ThemeParksUnavailableError,
)
from nextup.config import (
    BACKOFF_BASE_S,
    CATALOG_TTL_S,
    LIVE_DATA_TTL_S,
    MAX_RETRIES,
    REQUEST_TIMEOUT_S,
    THEMEPARKS_BASE_URL,
    USER_AGENT,
)
from nextup.models import DestinationList, LiveDataResponse, ParkCatalog

#: Qualquer modelo `pydantic` — usado para o `_parse` devolver o tipo certo.
ModelT = TypeVar("ModelT", bound=BaseModel)


class ThemeParksClient:
    """Acesso aos dados da ThemeParks.wiki, com cache e retentativas."""

    def __init__(
        self,
        *,
        base_url: str = THEMEPARKS_BASE_URL,
        timeout_s: float = REQUEST_TIMEOUT_S,
        max_retries: int = MAX_RETRIES,
        backoff_base_s: float = BACKOFF_BASE_S,
        http_client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Monta o cliente.

        Args:
            base_url: Raiz da API.
            timeout_s: Segundos até desistir de uma requisição.
            max_retries: Número total de tentativas por requisição.
            backoff_base_s: Espera da primeira retentativa; as seguintes dobram.
            http_client: Conexão HTTP já pronta. Serve para os testes injetarem
                uma conexão falsa, e para a API da Fase 3 reaproveitar a mesma
                conexão entre requisições.
            sleep: Função de espera. Injetável pelo mesmo motivo do relógio do
                cache: sem isso, testar o backoff custaria segundos de suíte.

        Raises:
            ValueError: Se `max_retries` for menor que 1.
        """
        if max_retries < 1:
            raise ValueError(f"max_retries deve ser ao menos 1, recebido: {max_retries}")

        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._backoff_base_s = backoff_base_s
        self._timeout_s = timeout_s
        self._sleep = sleep

        self._http = http_client or httpx.AsyncClient()
        self._owns_http = http_client is None

        self._catalog_cache: TTLCache[Any] = TTLCache(ttl_seconds=CATALOG_TTL_S)
        self._live_cache: TTLCache[Any] = TTLCache(ttl_seconds=LIVE_DATA_TTL_S)

    async def get_destinations(self) -> DestinationList:
        """Todos os destinos e seus parques. Muda raramente — cache de 24h."""
        return await self._get_model("/destinations", self._catalog_cache, DestinationList)

    async def get_park_catalog(self, park_id: str) -> ParkCatalog:
        """Catálogo de um parque: nomes, tipos e **coordenadas GPS**.

        É o dado mais estável da API — a coordenada do Space Mountain não muda
        desde 1975 — por isso o cache longo.
        """
        path = f"/entity/{park_id}/children"
        return await self._get_model(path, self._catalog_cache, ParkCatalog)

    async def get_live_data(self, park_id: str) -> LiveDataResponse:
        """Fila e status agora. Cache de 60s — o dado mais perecível do projeto."""
        path = f"/entity/{park_id}/live"
        return await self._get_model(path, self._live_cache, LiveDataResponse)

    async def aclose(self) -> None:
        """Fecha a conexão, se formos donos dela.

        Uma conexão recebida de fora pertence a quem a criou: fechá-la aqui
        derrubaria outros usuários dela.
        """
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> "ThemeParksClient":
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.aclose()

    async def _get_model(
        self,
        path: str,
        cache: TTLCache[Any],
        model: type[ModelT],
    ) -> ModelT:
        """Devolve o modelo do caminho, buscando na rede só se o cache não servir.

        O que entra no cache é o modelo **já validado**, nunca o JSON cru. A
        ordem importa: guardando antes de validar, uma resposta malformada
        ficaria memorizada por 24 horas e toda chamada seguinte falharia sem nem
        tentar a rede de novo. De quebra, o acerto de cache sai mais barato — não
        revalida o que já foi validado uma vez.
        """
        cached = cache.get(path)
        if cached is not None:
            return cached

        payload = await self._get_json(path)
        parsed = self._parse(model, payload, path)
        cache.set(path, parsed)
        return parsed

    async def _get_json(self, path: str) -> Any:
        """Faz a requisição, com retentativas e espera crescente.

        Raises:
            EntityNotFoundError: Em 404 — não adianta tentar de novo.
            ThemeParksUnavailableError: Se todas as tentativas falharem.
            InvalidResponseError: Se a resposta não for JSON.
        """
        url = f"{self._base_url}{path}"
        ultima_falha: Exception | None = None

        for tentativa in range(self._max_retries):
            try:
                # Cabeçalho e timeout vão por requisição, e não presos à conexão,
                # para valerem também quando a conexão vem de fora. Identificar-se
                # é boa educação com uma API pública: se causarmos algum problema,
                # eles sabem com quem falar.
                resposta = await self._http.get(
                    url,
                    headers={"User-Agent": USER_AGENT},
                    timeout=self._timeout_s,
                )
            except httpx.HTTPError as erro:
                # Timeout, DNS, conexão recusada: pode ser passageiro, vale tentar.
                ultima_falha = erro
            else:
                if resposta.status_code == httpx.codes.NOT_FOUND:
                    raise EntityNotFoundError(path.split("/")[2] if "/entity/" in path else path)

                # 4xx é erro nosso (ID inválido, caminho errado) e não se conserta
                # sozinho; 5xx é problema do servidor e costuma passar.
                if resposta.is_client_error:
                    raise InvalidResponseError(url, f"HTTP {resposta.status_code}")

                if resposta.is_success:
                    try:
                        return resposta.json()
                    except ValueError as erro:
                        raise InvalidResponseError(url, "corpo não é JSON válido") from erro

                ultima_falha = httpx.HTTPStatusError(
                    f"HTTP {resposta.status_code}", request=resposta.request, response=resposta
                )

            # Não espera depois da última tentativa: ninguém vai usar essa pausa.
            if tentativa < self._max_retries - 1:
                await self._sleep(self._backoff_base_s * (2**tentativa))

        raise ThemeParksUnavailableError(url, self._max_retries, ultima_falha)

    @staticmethod
    def _parse(model: type[ModelT], payload: Any, path: str) -> ModelT:
        """Transforma o JSON no modelo, traduzindo erro de validação.

        Quem chama não deveria precisar conhecer `pydantic` para entender que a
        API mudou de formato.
        """
        try:
            return model.model_validate(payload)
        except ValidationError as erro:
            raise InvalidResponseError(path, str(erro)) from erro

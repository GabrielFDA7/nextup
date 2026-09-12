"""Testes do cache com TTL.

O problema central destes testes é o tempo: para ver um dado vencer com TTL de 60
segundos, um teste ingênuo esperaria 60 segundos. Sessenta segundos por teste, e a
suíte inteira do projeto hoje roda em menos de meio segundo.

A saída é o relógio falso abaixo. Ele devolve a hora que mandarmos, e avança
quando mandarmos — então "passaram-se duas horas" custa uma linha e zero espera.
Essa técnica se chama *fake* (dublê), prima do *mock*.
"""

import time

import pytest

from nextup.clients.cache import TTLCache
from nextup.config import CATALOG_TTL_S, LIVE_DATA_TTL_S


class RelogioFalso:
    """Relógio controlado pelo teste, em segundos."""

    def __init__(self, inicio: float = 1_000.0) -> None:
        self.agora = inicio

    def __call__(self) -> float:
        """Faz a instância ser chamável como uma função: `relogio()`."""
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


@pytest.fixture
def relogio() -> RelogioFalso:
    return RelogioFalso()


class TestGuardarERecuperar:
    def test_valor_guardado_e_devolvido(self, relogio):
        cache = TTLCache[str](ttl_seconds=60, clock=relogio)

        cache.set("magic-kingdom", "catálogo")

        assert cache.get("magic-kingdom") == "catálogo"

    def test_chave_nunca_guardada_devolve_none(self, relogio):
        cache = TTLCache[str](ttl_seconds=60, clock=relogio)

        assert cache.get("epcot") is None

    def test_guardar_de_novo_substitui_o_valor(self, relogio):
        cache = TTLCache[str](ttl_seconds=60, clock=relogio)

        cache.set("fila", "45 minutos")
        cache.set("fila", "50 minutos")

        assert cache.get("fila") == "50 minutos"
        assert len(cache) == 1

    def test_chaves_diferentes_nao_se_misturam(self, relogio):
        cache = TTLCache[str](ttl_seconds=60, clock=relogio)

        cache.set("magic-kingdom", "A")
        cache.set("epcot", "B")

        assert cache.get("magic-kingdom") == "A"
        assert cache.get("epcot") == "B"


class TestVencimento:
    def test_valor_continua_valido_antes_do_prazo(self, relogio):
        cache = TTLCache[str](ttl_seconds=60, clock=relogio)
        cache.set("fila", "45 minutos")

        relogio.avancar(59)

        assert cache.get("fila") == "45 minutos"

    def test_valor_vence_exatamente_no_prazo(self, relogio):
        """No segundo 60 o dado já venceu — o TTL é o tempo de vida, não o último
        instante válido."""
        cache = TTLCache[str](ttl_seconds=60, clock=relogio)
        cache.set("fila", "45 minutos")

        relogio.avancar(60)

        assert cache.get("fila") is None

    def test_valor_vence_depois_do_prazo(self, relogio):
        cache = TTLCache[str](ttl_seconds=60, clock=relogio)
        cache.set("fila", "45 minutos")

        relogio.avancar(3_600)

        assert cache.get("fila") is None

    def test_guardar_de_novo_reinicia_o_prazo(self, relogio):
        cache = TTLCache[str](ttl_seconds=60, clock=relogio)
        cache.set("fila", "45 minutos")

        relogio.avancar(59)
        cache.set("fila", "50 minutos")
        relogio.avancar(59)

        assert cache.get("fila") == "50 minutos"

    def test_valor_vencido_e_apagado_da_memoria(self, relogio):
        """Não basta devolver `None`: o vencido tem que sair da memória, senão um
        servidor rodando por semanas acumula lixo."""
        cache = TTLCache[str](ttl_seconds=60, clock=relogio)
        cache.set("fila", "45 minutos")
        relogio.avancar(61)

        assert len(cache) == 1  # ainda ocupa espaço: ninguém consultou
        cache.get("fila")
        assert len(cache) == 0  # a consulta descobriu o vencimento e limpou


class TestDescarte:
    def test_invalidate_remove_so_a_chave_pedida(self, relogio):
        cache = TTLCache[str](ttl_seconds=60, clock=relogio)
        cache.set("magic-kingdom", "A")
        cache.set("epcot", "B")

        cache.invalidate("magic-kingdom")

        assert cache.get("magic-kingdom") is None
        assert cache.get("epcot") == "B"

    def test_invalidate_de_chave_inexistente_nao_quebra(self, relogio):
        cache = TTLCache[str](ttl_seconds=60, clock=relogio)

        cache.invalidate("nunca-existiu")

    def test_clear_esvazia_tudo(self, relogio):
        cache = TTLCache[str](ttl_seconds=60, clock=relogio)
        cache.set("a", "1")
        cache.set("b", "2")

        cache.clear()

        assert len(cache) == 0


class TestOperadorIn:
    def test_in_respeita_o_vencimento(self, relogio):
        cache = TTLCache[str](ttl_seconds=60, clock=relogio)
        cache.set("fila", "45 minutos")

        assert "fila" in cache
        relogio.avancar(61)
        assert "fila" not in cache


class TestConstrucao:
    @pytest.mark.parametrize("ttl_invalido", [0, -1, -60.5])
    def test_ttl_nao_positivo_e_recusado(self, ttl_invalido):
        """TTL zero significaria "vence na hora", o que é um cache que não cacheia."""
        with pytest.raises(ValueError, match="TTL deve ser positivo"):
            TTLCache[str](ttl_seconds=ttl_invalido)

    def test_relogio_padrao_e_monotonico(self):
        """Sem relógio injetado, usa `time.monotonic` — que nunca anda para trás."""
        cache = TTLCache[str](ttl_seconds=60)
        cache.set("fila", "45 minutos")

        assert cache.get("fila") == "45 minutos"

    def test_ttls_do_projeto_sao_aceitos(self):
        """Os valores reais do `config.py` precisam construir um cache válido."""
        assert TTLCache[str](ttl_seconds=LIVE_DATA_TTL_S).ttl_seconds == LIVE_DATA_TTL_S
        assert TTLCache[str](ttl_seconds=CATALOG_TTL_S).ttl_seconds == CATALOG_TTL_S

    def test_live_expira_muito_antes_do_catalogo(self):
        """A diferença entre os dois TTLs é intencional e é o ponto do módulo."""
        assert LIVE_DATA_TTL_S < CATALOG_TTL_S / 100


class TestGuardaQualquerTipo:
    def test_guarda_objetos_ricos_e_nao_so_texto(self, relogio):
        """Na prática o cache vai guardar modelos pydantic inteiros."""
        cache = TTLCache[dict](ttl_seconds=60, clock=relogio)
        payload = {"liveData": [{"id": "x", "waitTime": 45}]}

        cache.set("mk-live", payload)

        assert cache.get("mk-live") is payload


class TestRelogioReal:
    def test_com_relogio_de_verdade_o_dado_vence(self):
        """Uma prova de que o mecanismo funciona fora do relógio falso.

        Usa TTL de 10 milissegundos para não custar tempo de suíte — é o único
        teste do arquivo que realmente espera.
        """
        cache = TTLCache[str](ttl_seconds=0.01)
        cache.set("fila", "45 minutos")

        time.sleep(0.02)

        assert cache.get("fila") is None

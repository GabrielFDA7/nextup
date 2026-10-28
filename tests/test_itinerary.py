"""Testes do roteiro (Fase 8.2).

Os cenários põem as atrações **numa reta**, onde a caminhada é a distância entre as
posições — dá para conferir a resposta de cabeça, sem confiar na conta do código. E a
poda do *branch and bound* é verificada contra a força bruta, que é outro algoritmo:
se os dois concordam em centenas de casos aleatórios, a poda não está cortando o ramo
errado.
"""

import itertools
import random

import pytest

from nextup.core.itinerary import Itinerary, persistence, plan_itinerary


def reta(visitante: float, posicoes: dict[str, float]):
    """Caminhada de partida e matriz para atrações dispostas numa reta (1 min = 1 unidade)."""
    partida = {a: abs(x - visitante) for a, x in posicoes.items()}
    matriz = {a: {b: abs(xa - xb) for b, xb in posicoes.items()} for a, xa in posicoes.items()}
    return partida, matriz


def fila_zero(_atracao, _minutos):
    return 0.0


def guloso(partida, matriz, alvos, prever, duracao):
    """O que o app faz hoje: a cada parada, a menor `caminhada + fila`."""
    agora, onde, restantes, ordem = 0.0, None, set(alvos), []
    while restantes:

        def custo(a, agora=agora, onde=onde):
            andar = partida[a] if onde is None else matriz[onde][a]
            return andar + prever(a, agora + andar)

        prox = min(sorted(restantes), key=custo)
        andar = partida[prox] if onde is None else matriz[onde][prox]
        agora += andar + prever(prox, agora + andar) + duracao
        onde = prox
        restantes.remove(prox)
        ordem.append(prox)
    return ordem, agora


def ordem(roteiro: Itinerary) -> list[str]:
    return [s.attraction_id for s in roteiro.stops]


class TestGeografia:
    def test_o_zigue_zague_que_o_guloso_nao_enxerga(self):
        """O caso que justifica o módulo, resolvido à mão.

        Visitante no 0. Alvos em -2, +1 e +3, todos sem fila.

        - Guloso: vai ao +1 (o mais perto), depois ao +3, e volta ao -2:
          1 + 2 + 5 = **8 min** andando.
        - Roteiro: vai primeiro ao -2 e segue para a direita:
          2 + 3 + 2 = **7 min**.
        """
        partida, matriz = reta(0, {"esq": -2, "dir1": 1, "dir2": 3})

        roteiro = plan_itinerary(
            partida, matriz, ["esq", "dir1", "dir2"], fila_zero, ride_minutes=0
        )
        _, tempo_guloso = guloso(partida, matriz, ["esq", "dir1", "dir2"], fila_zero, 0)

        assert ordem(roteiro) == ["esq", "dir1", "dir2"]
        assert roteiro.total_minutes == 7
        assert tempo_guloso == 8

    def test_em_linha_reta_vai_em_ordem(self):
        partida, matriz = reta(0, {"c": 3, "a": 1, "b": 2})

        roteiro = plan_itinerary(partida, matriz, ["c", "a", "b"], fila_zero, ride_minutes=0)

        assert ordem(roteiro) == ["a", "b", "c"]


class TestHorario:
    def test_deixa_para_depois_a_fila_que_vai_cair(self):
        """*"Vá na Jungle Cruise agora e deixe a TRON para depois."*

        Sem caminhada, para isolar o efeito do horário. A TRON tem 25 min agora e
        5 min a partir dos 30; a Jungle tem 30 sempre.

        - TRON primeiro: 25 + 30 = 55 min.
        - Jungle primeiro: 30, e a TRON já está em 5: **35 min**.

        Com a persistência as duas ordens empatariam em 55 — é a previsão que
        enxerga a diferença. Por isso ela é injetada.
        """
        partida, matriz = reta(0, {"tron": 0, "jungle": 0})

        def prever(atracao, minutos):
            if atracao == "tron":
                return 5.0 if minutos >= 30 else 25.0
            return 30.0

        roteiro = plan_itinerary(partida, matriz, ["tron", "jungle"], prever, ride_minutes=0)

        assert ordem(roteiro) == ["jungle", "tron"]
        assert roteiro.total_minutes == 35


class TestConta:
    def test_cada_parada_traz_a_conta_aberta(self):
        """Visitante no 0; alvos em 2 (fila 10) e 5 (fila 4); 8 min dentro de cada."""
        partida, matriz = reta(0, {"a": 2, "b": 5})
        prever = persistence({"a": 10, "b": 4})

        roteiro = plan_itinerary(partida, matriz, ["a", "b"], prever, ride_minutes=8)
        primeira, segunda = roteiro.stops

        assert (primeira.attraction_id, primeira.arrival_minute, primeira.departure_minute) == (
            "a",
            2,
            20,
        )
        assert (segunda.walking_minutes, segunda.arrival_minute, segunda.departure_minute) == (
            3,
            23,
            35,
        )
        assert roteiro.next_stop == primeira
        assert roteiro.total_minutes == 35


class TestLimites:
    def test_sem_alvos_devolve_roteiro_vazio(self):
        roteiro = plan_itinerary({}, {}, [], fila_zero)

        assert roteiro.stops == ()
        assert roteiro.next_stop is None
        assert roteiro.total_minutes == 0

    def test_planeja_no_maximo_max_stops(self):
        partida, matriz = reta(0, {str(i): i for i in range(1, 7)})

        roteiro = plan_itinerary(partida, matriz, list(partida), fila_zero, max_stops=3)

        assert ordem(roteiro) == ["1", "2", "3"]

    def test_alvo_repetido_nao_vira_duas_paradas(self):
        partida, matriz = reta(0, {"a": 1, "b": 2})

        roteiro = plan_itinerary(partida, matriz, ["a", "b", "a"], fila_zero)

        assert ordem(roteiro) == ["a", "b"]

    def test_empate_se_resolve_pelo_identificador(self):
        """O mesmo pedido precisa dar a mesma resposta, ou a tela pisca entre duas."""
        partida, matriz = reta(0, {"b": 1, "a": -1})

        roteiro = plan_itinerary(partida, matriz, ["b", "a"], fila_zero)

        assert roteiro.next_stop.attraction_id == "a"


class TestPersistencia:
    def test_a_fila_nao_muda_com_o_tempo(self):
        prever = persistence({"tron": 45})

        assert prever("tron", 0) == prever("tron", 120) == 45

    def test_atracao_sem_fila_medida_falha_alto(self):
        """Quem chama filtra com `is_rankable`; inventar uma fila zero seria pior."""
        with pytest.raises(KeyError):
            persistence({"tron": 45})("jungle", 0)


def _instancia(semente: int, n: int):
    rnd = random.Random(semente)
    posicoes = {f"a{i}": (rnd.uniform(0, 10), rnd.uniform(0, 10)) for i in range(n)}
    visitante = (rnd.uniform(0, 10), rnd.uniform(0, 10))
    filas = {a: rnd.choice([0, 5, 10, 20, 45, 60]) for a in posicoes}

    def dist(p, q):
        return ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5

    partida = {a: dist(visitante, p) for a, p in posicoes.items()}
    matriz = {a: {b: dist(p, q) for b, q in posicoes.items()} for a, p in posicoes.items()}

    def prever(a, minutos):  # muda com o tempo, para a poda enfrentar o caso difícil
        return max(0.0, filas[a] - minutos / 4)

    return partida, matriz, prever


def _fim_da_sequencia(partida, matriz, prever, seq):
    """Força bruta: o tempo de uma ordem, calculado sem poda nenhuma."""
    agora, onde = 0.0, None
    for a in seq:
        agora += partida[a] if onde is None else matriz[onde][a]
        agora += prever(a, agora) + 8
        onde = a
    return agora


class TestContraForcaBruta:
    @pytest.mark.parametrize("semente", range(150))
    def test_poda_nao_perde_o_otimo(self, semente):
        n = 3 + semente % 4
        partida, matriz, prever = _instancia(semente, n)

        otimo = min(
            _fim_da_sequencia(partida, matriz, prever, p) for p in itertools.permutations(partida)
        )
        roteiro = plan_itinerary(
            partida, matriz, list(partida), prever, ride_minutes=8, max_stops=n
        )

        assert roteiro.total_minutes == pytest.approx(otimo)

    @pytest.mark.parametrize("semente", range(60))
    def test_profundidade_parcial_tambem_e_otima(self, semente):
        """Com mais alvos que `max_stops`, o ótimo é entre os arranjos de `k` deles."""
        partida, matriz, prever = _instancia(semente, 7)
        k = 2 + semente % 3

        otimo = min(
            _fim_da_sequencia(partida, matriz, prever, p)
            for p in itertools.permutations(partida, k)
        )
        roteiro = plan_itinerary(
            partida, matriz, list(partida), prever, ride_minutes=8, max_stops=k
        )

        assert len(roteiro.stops) == k
        assert roteiro.total_minutes == pytest.approx(otimo)

    @pytest.mark.parametrize("semente", range(50))
    def test_nunca_perde_do_guloso_quando_a_previsao_acerta(self, semente):
        """Com a previsão certa, o melhor de todas as ordens não perde para uma delas."""
        partida, matriz, prever = _instancia(semente, 5)

        roteiro = plan_itinerary(partida, matriz, list(partida), prever, ride_minutes=8)
        _, tempo_guloso = guloso(partida, matriz, list(partida), prever, 8)

        assert roteiro.total_minutes <= tempo_guloso + 1e-9

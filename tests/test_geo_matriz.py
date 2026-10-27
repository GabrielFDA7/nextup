"""Testes da matriz de caminhada entre atrações (Fase 8.1).

A verdade externa aqui é o **OpenStreetMap**: em 27/10/2026, a rota mais curta pelas
trilhas de pedestre foi calculada entre os 595 pares de atrações do Magic Kingdom, e os
números abaixo saíram dessa medição — não da conta que este código faz. Se alguém mudar
a velocidade ou a sinuosidade sem medir de novo, estes testes reclamam.
"""

import itertools
import json
from pathlib import Path

import pytest

from nextup.core.geo import travel_time_matrix

FIXTURES = Path(__file__).parent / "fixtures"

#: Caminhada média real entre duas atrações do Magic Kingdom, pelo OSM.
OSM_MEDIA_MIN = 6.43

#: Space Mountain ↔ TRON, vizinhas em Tomorrowland: 123 m pelas trilhas.
OSM_SPACE_TRON_MIN = 1.87

#: Big Thunder ↔ Haunted Mansion: 174 m em linha reta, 417 m a pé — o rio fica no meio.
OSM_THUNDER_MANSION_MIN = 6.32


@pytest.fixture(scope="module")
def pontos_mk() -> dict[str, tuple[float, float]]:
    """As atrações reais do Magic Kingdom, com o nome como identificador."""
    catalogo = json.loads((FIXTURES / "children_magic_kingdom.json").read_text(encoding="utf-8"))
    return {
        e["name"]: (e["location"]["latitude"], e["location"]["longitude"])
        for e in catalogo["children"]
        if e["entityType"] == "ATTRACTION" and e.get("location")
    }


@pytest.fixture(scope="module")
def matriz_mk(pontos_mk):
    return travel_time_matrix(pontos_mk)


class TestFormato:
    def test_cobre_todos_os_pares(self, pontos_mk, matriz_mk):
        assert set(matriz_mk) == set(pontos_mk)
        assert all(set(linha) == set(pontos_mk) for linha in matriz_mk.values())

    def test_diagonal_e_zero(self, matriz_mk):
        assert all(matriz_mk[a][a] == 0.0 for a in matriz_mk)

    def test_simetrica(self, matriz_mk):
        assert all(
            matriz_mk[a][b] == matriz_mk[b][a] for a, b in itertools.combinations(matriz_mk, 2)
        )

    def test_sem_pontos_devolve_matriz_vazia(self):
        assert travel_time_matrix({}) == {}

    def test_um_ponto_so(self):
        assert travel_time_matrix({"a": (28.42, -81.58)}) == {"a": {"a": 0.0}}

    def test_identificador_desconhecido_falha_alto(self, matriz_mk):
        """Um tempo inventado seria usado pelo otimizador sem desconfiar."""
        with pytest.raises(KeyError):
            matriz_mk["Space Mountain"]["atração que não existe"]


class TestGeometria:
    def test_desigualdade_triangular(self, matriz_mk):
        """Ir de A a C passando por B nunca é mais curto que ir direto.

        É propriedade matemática de qualquer distância, não detalhe do código. Se a
        matriz a violasse, o otimizador acharia "atalhos" que só existem na conta —
        e recomendaria uma parada a mais por ela ser, absurdamente, de graça.
        """
        violacoes = [
            (a, b, c)
            for a, b, c in itertools.permutations(matriz_mk, 3)
            if matriz_mk[a][c] > matriz_mk[a][b] + matriz_mk[b][c] + 1e-9
        ]
        assert violacoes == []


class TestContraOpenStreetMap:
    def test_media_confere_com_as_trilhas_reais(self, matriz_mk):
        """Em média, a estimativa fica a menos de meio minuto da rota real.

        Medido: 6,15 contra 6,43 min — a estimativa é 4% curta, o que é aceitável
        para um número que soma com uma previsão de fila que erra ~9 min.
        """
        pares = list(itertools.combinations(matriz_mk, 2))
        media = sum(matriz_mk[a][b] for a, b in pares) / len(pares)

        assert media == pytest.approx(OSM_MEDIA_MIN, abs=0.5)

    def test_vizinhas_em_tomorrowland(self, matriz_mk):
        assert matriz_mk["Space Mountain"]["TRON Lightcycle / Run"] == pytest.approx(
            OSM_SPACE_TRON_MIN, abs=0.3
        )

    def test_limitacao_conhecida_o_rio(self, matriz_mk):
        """Onde há água no caminho, o fator único subestima — e este teste o documenta.

        3,4 min estimados contra 6,3 reais. Fica registrado como limitação aceita,
        não como acerto: se um dia a matriz passar a usar as trilhas de verdade, este
        teste deve ser invertido para exigir a proximidade com o OSM.
        """
        estimado = matriz_mk["Big Thunder Mountain Railroad"]["Haunted Mansion"]

        assert estimado < OSM_THUNDER_MANSION_MIN * 0.6

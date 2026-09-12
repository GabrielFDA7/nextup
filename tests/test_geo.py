"""Testes dos cálculos geográficos.

Um bom teste não repete a conta do código — se ele fizesse isso, os dois erram
juntos e o teste não serve para nada. O teste precisa comparar o resultado com
uma verdade vinda de fora.

Aqui a verdade externa vem de três lugares: distâncias reais conhecidas entre
cidades, propriedades matemáticas que a fórmula tem que respeitar (distância de
um ponto até ele mesmo é zero, ida e volta dão o mesmo valor) e coordenadas
reais de atrações do Magic Kingdom.
"""

import math

import pytest

from nextup.core.geo import (
    EARTH_RADIUS_M,
    haversine_distance_m,
    travel_time_minutes,
    walking_distance_m,
    walking_time_minutes,
)

# Coordenadas reais, obtidas da ThemeParks.wiki em 11/09/2026.
SEVEN_DWARFS = (28.42037, -81.58031)
BIG_THUNDER = (28.4199638504, -81.5846422864)
DUMBO = (28.4207661576, -81.5783907473)


class TestHaversine:
    """Distância em linha reta entre dois pontos GPS."""

    def test_distancia_de_um_ponto_ate_ele_mesmo_e_zero(self):
        assert haversine_distance_m(*SEVEN_DWARFS, *SEVEN_DWARFS) == pytest.approx(0.0, abs=1e-6)

    def test_distancia_e_simetrica(self):
        """Ir de A até B tem que dar o mesmo que ir de B até A."""
        ida = haversine_distance_m(*SEVEN_DWARFS, *BIG_THUNDER)
        volta = haversine_distance_m(*BIG_THUNDER, *SEVEN_DWARFS)
        assert ida == pytest.approx(volta, rel=1e-9)

    def test_paris_a_londres(self):
        """Referência externa: a distância real é ~343,5 km.

        Tolerância de 1% cobre a diferença entre esfera e elipsoide.
        """
        paris = (48.8566, 2.3522)
        londres = (51.5074, -0.1278)
        assert haversine_distance_m(*paris, *londres) == pytest.approx(343_500, rel=0.01)

    def test_um_grau_de_latitude(self):
        """Um grau de latitude vale ~111,19 km em qualquer lugar do planeta."""
        assert haversine_distance_m(0.0, 0.0, 1.0, 0.0) == pytest.approx(111_195, rel=0.001)

    def test_pontos_antipodais(self):
        """Dois pontos opostos no globo ficam a meia circunferência de distância."""
        esperado = math.pi * EARTH_RADIUS_M
        assert haversine_distance_m(0.0, 0.0, 0.0, 180.0) == pytest.approx(esperado, rel=1e-9)

    def test_atracoes_vizinhas_do_magic_kingdom(self):
        """Duas atrações do mesmo parque ficam a poucas centenas de metros."""
        distancia = haversine_distance_m(*SEVEN_DWARFS, *BIG_THUNDER)
        assert 100 < distancia < 1000, f"Distância fora do esperado: {distancia:.0f} m"


class TestWalkingDistance:
    """Correção de sinuosidade do trajeto."""

    def test_trajeto_real_e_maior_que_a_linha_reta(self):
        assert walking_distance_m(100.0, winding_factor=1.3) == pytest.approx(130.0)

    def test_fator_um_nao_altera_a_distancia(self):
        assert walking_distance_m(250.0, winding_factor=1.0) == pytest.approx(250.0)


class TestWalkingTime:
    """Conversão de distância em tempo."""

    def test_conversao_conhecida(self):
        """A 1 m/s, 600 metros levam exatamente 10 minutos."""
        assert walking_time_minutes(600.0, speed_mps=1.0) == pytest.approx(10.0)

    def test_distancia_zero_leva_tempo_zero(self):
        assert walking_time_minutes(0.0) == pytest.approx(0.0)

    def test_mais_rapido_leva_menos_tempo(self):
        assert walking_time_minutes(500.0, speed_mps=2.0) < walking_time_minutes(
            500.0, speed_mps=1.0
        )

    @pytest.mark.parametrize("velocidade_invalida", [0.0, -1.0, -0.5])
    def test_velocidade_nao_positiva_e_rejeitada(self, velocidade_invalida):
        """Falhar alto e cedo é melhor que devolver um tempo negativo silencioso."""
        with pytest.raises(ValueError, match="deve ser positiva"):
            walking_time_minutes(100.0, speed_mps=velocidade_invalida)


class TestTravelTime:
    """A função que o resto do projeto usa de fato."""

    def test_atracao_vizinha_leva_poucos_minutos(self):
        minutos = travel_time_minutes(*SEVEN_DWARFS, *BIG_THUNDER)
        assert 1 < minutos < 15, f"Tempo fora do esperado: {minutos:.1f} min"

    def test_mesma_atracao_leva_tempo_zero(self):
        assert travel_time_minutes(*DUMBO, *DUMBO) == pytest.approx(0.0, abs=1e-6)

    def test_mais_longe_leva_mais_tempo(self):
        perto = travel_time_minutes(*DUMBO, *SEVEN_DWARFS)
        longe = travel_time_minutes(*DUMBO, *BIG_THUNDER)
        assert longe > perto

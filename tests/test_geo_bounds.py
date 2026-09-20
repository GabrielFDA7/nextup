"""Testes do retângulo que enquadra um parque.

Como todo teste de `core/geo.py`, comparam contra uma **verdade externa** em vez de
repetir a conta do código — se repetissem, os dois errariam juntos e o teste não
detectaria nada. Aqui a verdade externa são as coordenadas reais do Magic Kingdom,
já usadas em `test_geo.py`.
"""

from nextup.core.geo import BoundingBox, bounding_box

#: Cantos reais do Magic Kingdom, medidos sobre as 86 entidades do catálogo.
MK_SUL, MK_NORTE = 28.41654, 28.42130
MK_OESTE, MK_LESTE = -81.58498, -81.57798


class TestRetangulo:
    def test_enquadra_o_magic_kingdom(self):
        """Três pontos reais do parque têm de caber no retângulo que sai daqui."""
        caixa = bounding_box(
            [
                (28.4207661576, -81.5783907473),  # The Barnstormer
                (MK_SUL, MK_OESTE),
                (MK_NORTE, MK_LESTE),
            ]
        )

        assert caixa == BoundingBox(south=MK_SUL, west=MK_OESTE, north=MK_NORTE, east=MK_LESTE)

    def test_um_ponto_vira_retangulo_degenerado(self):
        """Um parque com uma atração só ainda precisa de enquadramento válido."""
        caixa = bounding_box([(28.42, -81.58)])

        assert caixa == BoundingBox(south=28.42, west=-81.58, north=28.42, east=-81.58)

    def test_sem_pontos_devolve_nulo(self):
        """Nulo obriga quem chama a decidir.

        A alternativa seria devolver um retângulo com zeros, que é um lugar de
        verdade no Golfo da Guiné — o mapa enquadraria o oceano e ninguém saberia
        por quê.
        """
        assert bounding_box([]) is None

    def test_aceita_gerador(self):
        """A rota passa uma expressão geradora; consumir duas vezes a esvaziaria."""
        caixa = bounding_box((lat, lon) for lat, lon in [(1.0, 2.0), (3.0, 4.0)])

        assert caixa == BoundingBox(south=1.0, west=2.0, north=3.0, east=4.0)

    def test_ordem_dos_pontos_nao_importa(self):
        pontos = [(10.0, 20.0), (-5.0, 40.0), (3.0, -1.0)]

        assert bounding_box(pontos) == bounding_box(list(reversed(pontos)))


class TestCentro:
    def test_centro_do_retangulo(self):
        caixa = BoundingBox(south=0.0, west=0.0, north=10.0, east=20.0)

        assert caixa.center == (5.0, 10.0)

    def test_centro_com_coordenadas_negativas(self):
        """Orlando fica em longitude negativa; o centro não pode virar positivo."""
        caixa = BoundingBox(south=MK_SUL, west=MK_OESTE, north=MK_NORTE, east=MK_LESTE)
        latitude, longitude = caixa.center

        assert MK_SUL < latitude < MK_NORTE
        assert MK_OESTE < longitude < MK_LESTE

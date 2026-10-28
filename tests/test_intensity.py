"""Testes da regra de intensidade.

A verdade externa são as **etiquetas oficiais da Disney**, conferidas na listagem do
Magic Kingdom em 27/10/2026, e o consenso sobre as atrações: a Big Thunder é uma
montanha-russa, o Buzz Lightyear é um passeio de carrinho que gira.
"""

import pytest

from nextup.core.intensity import Intensity, classify_intensity
from nextup.data import load_curation


class TestEtiquetasReais:
    """As cinco atrações cujas etiquetas a listagem oficial entregou."""

    @pytest.mark.parametrize(
        ("atracao", "etiquetas", "esperado"),
        [
            ("Big Thunder Mountain Railroad", ["Small Drops", "Thrill Rides"], Intensity.THRILL),
            ("The Barnstormer", ["Small Drops"], Intensity.MODERATE),
            ("Astro Orbiter", ["Slow Rides", "Spinning"], Intensity.CALM),
            ("Buzz Lightyear's Space Ranger Spin", ["Slow Rides", "Spinning"], Intensity.CALM),
            ("Casey Jr. Splash 'N' Soak Station", ["Water"], Intensity.CALM),
        ],
    )
    def test_classificacao(self, atracao, etiquetas, esperado):
        assert classify_intensity(etiquetas) is esperado, atracao


@pytest.fixture
def nivel() -> dict[str, Intensity]:
    """A intensidade de cada atração conferida do Magic Kingdom, pela regra."""
    curadoria = load_curation("75ea578a-adc8-4116-a54d-dccb60765ef9").verified()
    return {a.name: classify_intensity(a.disney_tags) for a in curadoria.values()}


class TestSensoComum:
    """O que qualquer pessoa que conhece o Magic Kingdom diria — conferido contra a
    curadoria real. Se a regra mudar e uma destas inverter, a regra é que está errada."""

    @pytest.mark.parametrize(
        "atracao", ["TRON Lightcycle / Run", "Space Mountain", "Tiana's Bayou Adventure"]
    )
    def test_montanhas_russas_sao_radicais(self, nivel, atracao):
        assert nivel[atracao] is Intensity.THRILL

    @pytest.mark.parametrize(
        "atracao",
        ['"it\'s a small world"', "Dumbo the Flying Elephant", "Haunted Mansion", "Jungle Cruise"],
    )
    def test_classicas_infantis_sao_tranquilas(self, nivel, atracao):
        assert nivel[atracao] is Intensity.CALM


class TestRegra:
    def test_queda_grande_basta_para_ser_radical(self):
        assert classify_intensity(["Big Drops"]) is Intensity.THRILL

    def test_radical_vence_moderada(self):
        """A etiqueta mais forte decide; queda pequena não rebaixa uma montanha-russa."""
        assert classify_intensity(["Small Drops", "Big Drops"]) is Intensity.THRILL

    def test_assustadora_e_moderada(self):
        assert classify_intensity(["Scary", "Dark"]) is Intensity.MODERATE

    def test_escuro_sozinho_nao_e_intensidade(self):
        """A Haunted Mansion é "Dark, Slow Rides" na listagem oficial, e é tranquila."""
        assert classify_intensity(["Dark", "Slow Rides"]) is Intensity.CALM

    def test_girar_sozinho_nao_e_intensidade(self):
        """A Disney marca Buzz e Mad Tea Party como "Spinning"; não dá para separá-los por aí."""
        assert classify_intensity(["Spinning"]) is Intensity.CALM

    def test_conferida_sem_etiquetas_e_tranquila(self):
        """Só vale para atração **conferida** — a sem curadoria nem chega aqui."""
        assert classify_intensity([]) is Intensity.CALM

    def test_tolera_caixa_e_espacos_da_digitacao_manual(self):
        """A curadoria é digitada por gente; "thrill rides " não pode virar tranquila."""
        assert classify_intensity([" thrill rides "]) is Intensity.THRILL

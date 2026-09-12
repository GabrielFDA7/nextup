"""Testes do catálogo de parque.

A verdade externa é `tests/fixtures/children_magic_kingdom.json`, a resposta real
de `/entity/{id}/children` capturada em 12/09/2026. Os números conferidos aqui
(86 itens, 35 atrações) vêm da API, não do nosso código.

O teste mais importante do arquivo é o que fecha o ciclo com `core/geo.py`: pega
duas atrações reais do catálogo e confirma que a distância entre elas bate com o
tamanho conhecido do Magic Kingdom.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from nextup.core.geo import haversine_distance_m
from nextup.models import EntityType, Location, ParkCatalog, ParkEntity

FIXTURE = Path(__file__).parent / "fixtures" / "children_magic_kingdom.json"


@pytest.fixture
def catalogo() -> ParkCatalog:
    """O catálogo real do Magic Kingdom, já validado pelo modelo."""
    return ParkCatalog.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


class TestParsingDaRespostaReal:
    def test_catalogo_real_e_aceito(self, catalogo):
        assert catalogo.name == "Magic Kingdom Park"
        assert catalogo.timezone == "America/New_York"
        assert len(catalogo.children) == 86

    def test_camelcase_da_api_vira_snake_case_no_modelo(self, catalogo):
        """A API manda `entityType`; aqui dentro o campo se chama `entity_type`."""
        assert all(isinstance(e.entity_type, EntityType) for e in catalogo.children)

    def test_os_tres_tipos_da_api_sao_reconhecidos(self, catalogo):
        tipos = {e.entity_type for e in catalogo.children}

        assert tipos == {EntityType.ATTRACTION, EntityType.SHOW, EntityType.RESTAURANT}
        assert EntityType.UNKNOWN not in tipos

    def test_toda_entidade_do_magic_kingdom_tem_coordenada(self, catalogo):
        """Verdade externa confirmada na API: 86 de 86 com GPS."""
        assert all(e.location is not None for e in catalogo.children)


class TestAttractions:
    def test_magic_kingdom_tem_35_atracoes(self, catalogo):
        assert len(catalogo.attractions()) == 35

    def test_shows_e_restaurantes_ficam_de_fora(self, catalogo):
        atracoes = catalogo.attractions()

        assert len(atracoes) < len(catalogo.children)
        assert all(a.entity_type is EntityType.ATTRACTION for a in atracoes)

    def test_atracao_sem_coordenada_e_descartada(self):
        """Sem GPS não há distância — e sem distância a atração não entra no ranking."""
        catalogo = ParkCatalog.model_validate(
            {
                "id": "parque",
                "name": "Parque de Teste",
                "timezone": "America/New_York",
                "children": [
                    {
                        "id": "com-gps",
                        "name": "Com GPS",
                        "entityType": "ATTRACTION",
                        "location": {"latitude": 28.42, "longitude": -81.58},
                    },
                    {
                        "id": "sem-gps",
                        "name": "Sem GPS",
                        "entityType": "ATTRACTION",
                        "location": None,
                    },
                ],
            }
        )

        sobreviventes = [a.id for a in catalogo.attractions()]

        assert sobreviventes == ["com-gps"]


class TestCoordenadasReais:
    def test_distancia_entre_duas_atracoes_cabe_dentro_do_parque(self, catalogo):
        """Fecha o ciclo com `core/geo.py` usando dados que vieram da API.

        O Magic Kingdom tem cerca de 430 mil m² — nenhuma atração pode estar a
        quilômetros de outra. Se este teste falhar, ou a coordenada veio errada,
        ou o modelo trocou latitude por longitude.
        """
        atracoes = catalogo.attractions()
        primeira, ultima = atracoes[0], atracoes[-1]

        distancia = haversine_distance_m(
            primeira.location.latitude,
            primeira.location.longitude,
            ultima.location.latitude,
            ultima.location.longitude,
        )

        assert 0 < distancia < 2_000

    def test_atracoes_ficam_na_florida(self, catalogo):
        """Magic Kingdom fica perto de 28.42 N, -81.58 W. Confere a ordem lat/lon."""
        for atracao in catalogo.attractions():
            assert 28.3 < atracao.location.latitude < 28.5
            assert -81.7 < atracao.location.longitude < -81.5


class TestValidacao:
    def test_tipo_desconhecido_vira_unknown_em_vez_de_erro(self):
        """Se a API criar "PARADE" amanhã, o catálogo não pode parar de funcionar."""
        entidade = ParkEntity.model_validate(
            {"id": "x", "name": "Parada da Tarde", "entityType": "PARADE"}
        )

        assert entidade.entity_type is EntityType.UNKNOWN

    @pytest.mark.parametrize(
        "latitude,longitude",
        [
            (91.0, 0.0),  # acima do polo norte
            (-91.0, 0.0),
            (0.0, 181.0),
            (0.0, -181.0),
        ],
    )
    def test_coordenada_fora_do_planeta_e_recusada(self, latitude, longitude):
        with pytest.raises(ValidationError):
            Location(latitude=latitude, longitude=longitude)

    def test_coordenada_valida_e_aceita(self):
        local = Location(latitude=28.42037, longitude=-81.58031)

        assert local.latitude == pytest.approx(28.42037)

    def test_entidade_da_api_nao_pode_ser_alterada(self, catalogo):
        with pytest.raises(ValidationError):
            catalogo.children[0].name = "Outro nome"

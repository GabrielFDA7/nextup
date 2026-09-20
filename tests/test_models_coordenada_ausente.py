"""Testes da coordenada que a API manda preenchida com nulos.

Cobrem um bug que viveu no projeto **da Fase 1 até a Fase 6.2**, sem nunca
aparecer: o Magic Kingdom, usado em todos os testes e fixtures, tem coordenada em
100% das entidades. Parques como o Disneyland Paris não têm — e lá o NextUp
respondia 502, dizendo "formato inesperado", como se a fonte estivesse errada.

A fonte não estava errada. Ela tem duas formas de dizer "não sei onde isto fica":
omitir `location`, ou mandá-lo com nulos dentro. O projeto só entendia a primeira.

O estrago era desproporcional à causa: o `pydantic` valida a lista inteira de uma
vez, então **uma** atração sem GPS invalidava as outras oitenta e o parque
desaparecia. É a mesma lição do `EntityType._missing_`, registrada na seção 10 em
12/09/2026: perder um item é aceitável, perder o parque não.
"""

import pytest

from nextup.models import EntityType, ParkCatalog, ParkEntity

PARQUE_COM_BURACO = {
    "id": "dae968d5-630d-4719-8b06-3d107e944401",
    "name": "Disneyland Park",
    "entityType": "PARK",
    "timezone": "Europe/Paris",
    "children": [
        {
            "id": "com-gps",
            "name": "Big Thunder Mountain",
            "entityType": "ATTRACTION",
            "location": {"latitude": 48.8722, "longitude": 2.7758},
        },
        {
            "id": "location-com-nulos",
            "name": "Atração sem GPS",
            "entityType": "ATTRACTION",
            "location": {"latitude": None, "longitude": None},
        },
        {
            "id": "sem-location",
            "name": "Outra sem GPS",
            "entityType": "ATTRACTION",
        },
    ],
}


class TestCoordenadaIncompleta:
    def test_o_catalogo_inteiro_sobrevive(self):
        """O comportamento que faltava: uma atração sem GPS não derruba o parque."""
        catalogo = ParkCatalog.model_validate(PARQUE_COM_BURACO)

        assert catalogo.name == "Disneyland Park"
        assert len(catalogo.children) == 3

    def test_nulos_viram_ausencia(self):
        entidade = ParkEntity.model_validate(
            {
                "id": "x",
                "name": "Atração",
                "entityType": "ATTRACTION",
                "location": {"latitude": None, "longitude": None},
            }
        )

        assert entidade.location is None

    @pytest.mark.parametrize(
        "location",
        [
            {"latitude": None, "longitude": 2.77},
            {"latitude": 48.87, "longitude": None},
            {},
        ],
        ids=["sem-latitude", "sem-longitude", "objeto-vazio"],
    )
    def test_meia_coordenada_tambem_vira_ausencia(self, location):
        """Meia coordenada não é meio caminho: sem as duas não há ponto no mapa.

        Aceitar uma delas deixaria a atração entrar no ranking com a outra valendo
        zero — e zero é um lugar de verdade, no Golfo da Guiné.
        """
        entidade = ParkEntity.model_validate(
            {"id": "x", "name": "Atração", "entityType": "ATTRACTION", "location": location}
        )

        assert entidade.location is None

    def test_a_entidade_continua_no_catalogo(self):
        """Ela some do *ranking*, não do catálogo: nome e tipo continuam válidos."""
        catalogo = ParkCatalog.model_validate(PARQUE_COM_BURACO)
        sem_gps = next(c for c in catalogo.children if c.id == "location-com-nulos")

        assert sem_gps.name == "Atração sem GPS"
        assert sem_gps.entity_type is EntityType.ATTRACTION

    def test_coordenada_valida_continua_intacta(self):
        """A correção não pode engolir dado bom junto com o ruim."""
        catalogo = ParkCatalog.model_validate(PARQUE_COM_BURACO)
        com_gps = next(c for c in catalogo.children if c.id == "com-gps")

        assert com_gps.location is not None
        assert com_gps.location.latitude == pytest.approx(48.8722)
        assert com_gps.location.longitude == pytest.approx(2.7758)


class TestEfeitoNoRanking:
    def test_so_as_ranqueaveis_entram_em_attractions(self):
        """`attractions()` exige coordenada — sem ela não há distância a calcular."""
        catalogo = ParkCatalog.model_validate(PARQUE_COM_BURACO)

        assert [a.id for a in catalogo.attractions()] == ["com-gps"]

    def test_o_coletor_guarda_o_historico_das_tres(self):
        """`attraction_ids()` é mais permissivo, e aqui está o porquê.

        Coordenada é requisito para ranquear, não para ter histórico. Se o
        Disneyland Paris preencher o GPS dessas atrações amanhã, elas entram no
        ranking já com semanas de passado — em vez de começarem do zero.
        """
        catalogo = ParkCatalog.model_validate(PARQUE_COM_BURACO)

        assert catalogo.attraction_ids() == {"com-gps", "location-com-nulos", "sem-location"}


class TestCoordenadaInvalidaContinuaSendoErro:
    """Nulo é "não sei"; 91 graus de latitude é dado corrompido. São coisas diferentes."""

    def test_latitude_fora_da_faixa_ainda_falha(self):
        with pytest.raises(ValueError):
            ParkEntity.model_validate(
                {
                    "id": "x",
                    "name": "Atração",
                    "entityType": "ATTRACTION",
                    "location": {"latitude": 91.0, "longitude": 0.0},
                }
            )

    def test_texto_no_lugar_do_numero_ainda_falha(self):
        with pytest.raises(ValueError):
            ParkEntity.model_validate(
                {
                    "id": "x",
                    "name": "Atração",
                    "entityType": "ATTRACTION",
                    "location": {"latitude": "sei lá", "longitude": 0.0},
                }
            )

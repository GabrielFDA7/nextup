"""Testes dos modelos de destino e parque.

A verdade externa aqui é `tests/fixtures/destinations.json`: um recorte da resposta
real da ThemeParks.wiki, capturada em 12/09/2026. Testar contra ela responde à
pergunta que importa — "nossos modelos aguentam o JSON que a API realmente manda?"
— sem depender da internet para isso.

A outra verdade externa é o `config.py`: se o ID de parque padrão do projeto não
existir mais na resposta da API, é melhor um teste falhar agora do que o app
quebrar na frente de um usuário.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from nextup.config import DEFAULT_PARK_ID
from nextup.models import Destination, DestinationList, Park

FIXTURE = Path(__file__).parent / "fixtures" / "destinations.json"

MAGIC_KINGDOM_NAME = "Magic Kingdom Park"


@pytest.fixture
def payload() -> dict:
    """O JSON real da API, lido do disco uma vez por teste que pedir por ele."""
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class TestParsingDaRespostaReal:
    """O modelo tem que aguentar o JSON de verdade, não uma versão idealizada dele."""

    def test_resposta_real_e_aceita(self, payload):
        resultado = DestinationList.model_validate(payload)
        assert len(resultado.destinations) == 3

    def test_walt_disney_world_tem_seis_parques(self, payload):
        """Verdade externa: WDW tem 4 parques temáticos + 2 parques aquáticos."""
        resultado = DestinationList.model_validate(payload)
        wdw = next(d for d in resultado.destinations if d.slug == "waltdisneyworldresort")

        assert len(wdw.parks) == 6
        assert MAGIC_KINGDOM_NAME in [park.name for park in wdw.parks]

    def test_parque_padrao_do_config_existe_na_api(self, payload):
        """Se este teste falhar, o `DEFAULT_PARK_ID` do projeto virou um ID morto."""
        resultado = DestinationList.model_validate(payload)
        todos_os_parques = [park for dest in resultado.destinations for park in dest.parks]

        encontrado = next((p for p in todos_os_parques if p.id == DEFAULT_PARK_ID), None)

        assert encontrado is not None
        assert encontrado.name == MAGIC_KINGDOM_NAME

    def test_campo_desconhecido_da_api_nao_quebra_o_modelo(self, payload):
        """A fixture tem `externalId`, que não modelamos.

        Se a API acrescentar campos amanhã, o NextUp continua funcionando — só
        ignora o que não conhece.
        """
        resultado = DestinationList.model_validate(payload)

        assert not hasattr(resultado.destinations[0], "externalId")


class TestValidacao:
    """O modelo precisa recusar dado inválido na entrada, não deixar passar."""

    def test_campo_obrigatorio_faltando_e_recusado(self):
        with pytest.raises(ValidationError):
            Park.model_validate({"id": "abc"})  # sem `name`

    def test_id_vazio_e_recusado(self):
        """String vazia é tecnicamente uma string, mas não é um ID utilizável."""
        with pytest.raises(ValidationError):
            Park.model_validate({"id": "", "name": "Magic Kingdom Park"})

    def test_tipo_errado_e_recusado(self):
        with pytest.raises(ValidationError):
            Destination.model_validate(
                {"id": "x", "name": "y", "slug": "z", "parks": "não é uma lista"}
            )

    def test_objeto_da_api_nao_pode_ser_alterado(self):
        park = Park(id="abc", name="Magic Kingdom Park")

        with pytest.raises(ValidationError):
            park.name = "Outro nome"


class TestFindPark:
    def test_encontra_parque_pelo_id(self, payload):
        resultado = DestinationList.model_validate(payload)
        wdw = next(d for d in resultado.destinations if d.slug == "waltdisneyworldresort")

        park = wdw.find_park(DEFAULT_PARK_ID)

        assert park is not None
        assert park.name == MAGIC_KINGDOM_NAME

    def test_id_inexistente_devolve_none(self, payload):
        resultado = DestinationList.model_validate(payload)
        wdw = next(d for d in resultado.destinations if d.slug == "waltdisneyworldresort")

        assert wdw.find_park("id-que-nao-existe") is None

    def test_nao_encontra_parque_de_outro_destino(self, payload):
        """Magic Kingdom é da WDW; procurar por ele na Disneyland tem que dar `None`."""
        resultado = DestinationList.model_validate(payload)
        disneyland = next(d for d in resultado.destinations if d.slug == "disneylandresort")

        assert disneyland.find_park(DEFAULT_PARK_ID) is None

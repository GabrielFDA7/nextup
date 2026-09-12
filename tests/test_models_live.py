"""Testes dos dados ao vivo.

A verdade externa é `tests/fixtures/live_magic_kingdom.json`, capturada da API em
12/09/2026 às 15h54 UTC. Ela traz as 35 atrações do parque, mais uma amostra de
show, restaurante e do próprio parque, cobrindo os quatro status que a API usa.
As listas de `forecast` e `showtimes` foram truncadas: o NextUp não as modela, e
elas sozinhas dobravam o tamanho do arquivo.

Os números conferidos aqui (35 atrações, 26 ranqueáveis) vieram da API naquele
momento, não de uma conta feita pelo nosso código.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from nextup.models import LiveData, LiveDataResponse, LiveStatus

FIXTURE = Path(__file__).parent / "fixtures" / "live_magic_kingdom.json"

TRON_ID = "5a43d1a7-ad53-4d25-abfe-25625f0da304"


@pytest.fixture
def ao_vivo() -> LiveDataResponse:
    return LiveDataResponse.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


class TestParsingDaRespostaReal:
    def test_resposta_real_e_aceita(self, ao_vivo):
        assert ao_vivo.name == "Magic Kingdom Park"
        assert len(ao_vivo.live_data) == 40

    def test_os_quatro_status_da_api_aparecem(self, ao_vivo):
        status = {item.status for item in ao_vivo.live_data}

        assert status == {
            LiveStatus.OPERATING,
            LiveStatus.CLOSED,
            LiveStatus.DOWN,
            LiveStatus.REFURBISHMENT,
        }

    def test_data_vira_datetime_com_fuso(self, ao_vivo):
        """A API manda texto ISO-8601; o modelo entrega um `datetime` de verdade."""
        momento = ao_vivo.live_data[0].last_updated

        assert isinstance(momento, datetime)
        assert momento.tzinfo is not None
        assert momento.astimezone(UTC).date() == datetime(2026, 9, 12, tzinfo=UTC).date()

    def test_fila_do_tron_e_lida_corretamente(self, ao_vivo):
        """Verdade externa: TRON marcava 45 minutos no momento da captura."""
        tron = ao_vivo.by_id()[TRON_ID]

        assert tron.name == "TRON Lightcycle / Run"
        assert tron.wait_time_minutes == 45
        assert tron.status is LiveStatus.OPERATING


class TestIsRankable:
    def test_vinte_e_seis_atracoes_estavam_ranqueaveis(self, ao_vivo):
        ranqueaveis = [item for item in ao_vivo.live_data if item.is_rankable]

        assert len(ranqueaveis) == 26

    def test_aberta_sem_fila_nao_e_ranqueavel(self, ao_vivo):
        """O Castelo da Cinderela está OPERATING, mas não tem fila para medir."""
        castelo = next(i for i in ao_vivo.live_data if i.name == "Cinderella Castle")

        assert castelo.status is LiveStatus.OPERATING
        assert castelo.wait_time_minutes is None
        assert castelo.is_rankable is False

    def test_atracao_quebrada_nao_e_ranqueavel(self, ao_vivo):
        quebrada = next(i for i in ao_vivo.live_data if i.status is LiveStatus.DOWN)

        assert quebrada.is_rankable is False

    def test_todo_ranqueavel_tem_fila_e_esta_operando(self, ao_vivo):
        """A regra vale nos dois sentidos, para toda a fixture."""
        for item in ao_vivo.live_data:
            if item.is_rankable:
                assert item.status is LiveStatus.OPERATING
                assert item.wait_time_minutes is not None


class TestBusca:
    def test_indice_cobre_todos_os_itens(self, ao_vivo):
        indice = ao_vivo.by_id()

        assert len(indice) == len(ao_vivo.live_data)
        assert indice[TRON_ID].id == TRON_ID


class TestValidacao:
    def test_status_desconhecido_vira_unknown(self):
        item = LiveData.model_validate(
            {
                "id": "x",
                "name": "Atração Nova",
                "status": "EVACUATED",
                "lastUpdated": "2026-09-12T15:54:19.095Z",
            }
        )

        assert item.status is LiveStatus.UNKNOWN
        assert item.is_rankable is False

    def test_fila_negativa_e_recusada(self):
        """Fila de -10 minutos é dado corrompido, não uma fila curta."""
        with pytest.raises(ValidationError):
            LiveData.model_validate(
                {
                    "id": "x",
                    "name": "y",
                    "status": "OPERATING",
                    "lastUpdated": "2026-09-12T15:54:19.095Z",
                    "queue": {"STANDBY": {"waitTime": -10}},
                }
            )

    def test_fila_zerada_e_valida(self):
        """Zero não é ausência de dado: é atração sem fila, entrada direta."""
        item = LiveData.model_validate(
            {
                "id": "x",
                "name": "y",
                "status": "OPERATING",
                "lastUpdated": "2026-09-12T15:54:19.095Z",
                "queue": {"STANDBY": {"waitTime": 0}},
            }
        )

        assert item.wait_time_minutes == 0
        assert item.is_rankable is True

    def test_data_obrigatoria(self):
        with pytest.raises(ValidationError):
            LiveData.model_validate({"id": "x", "name": "y", "status": "OPERATING"})

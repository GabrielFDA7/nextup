"""Testes do motor de recomendação.

O teste mais importante deste arquivo — e provavelmente do projeto — é
`test_fila_menor_perde_para_atracao_mais_perto`. Ele prova a tese do NextUp: que
ranquear pela menor fila é a resposta errada. Se algum dia alguém "simplificar" o
algoritmo para ordenar só por `waitTime`, é esse teste que vai acusar.

Os cenários usam catálogos montados à mão, com distâncias escolhidas de propósito,
porque a fixture real não tem o caso extremo que interessa: uma fila curta do
outro lado do parque. Depois, a última classe roda o algoritmo sobre os dados
reais do Magic Kingdom, para garantir que ele aguenta a bagunça do mundo.
"""

import json
from pathlib import Path

import pytest

from nextup.core.recommender import Recommendation, recommend
from nextup.models import LiveDataResponse, Location, ParkCatalog

FIXTURES = Path(__file__).parent / "fixtures"

#: Um grau de latitude vale ~111.320 m. Usar isso deixa as distâncias dos
#: cenários explícitas: somar 0,00898 grau é ficar a ~1 km ao norte.
METROS_POR_GRAU_LAT = 111_320.0

VISITANTE = Location(latitude=28.4200, longitude=-81.5800)


def ao_norte(metros: float) -> tuple[float, float]:
    """Coordenada a N metros ao norte do visitante, na mesma longitude."""
    return (VISITANTE.latitude + metros / METROS_POR_GRAU_LAT, VISITANTE.longitude)


def montar_catalogo(*atracoes: tuple[str, str, float, float]) -> ParkCatalog:
    """Catálogo de teste a partir de tuplas `(id, nome, latitude, longitude)`."""
    return ParkCatalog.model_validate(
        {
            "id": "parque-teste",
            "name": "Parque de Teste",
            "timezone": "America/New_York",
            "children": [
                {
                    "id": id_,
                    "name": nome,
                    "entityType": "ATTRACTION",
                    "location": {"latitude": lat, "longitude": lon},
                }
                for id_, nome, lat, lon in atracoes
            ],
        }
    )


def montar_live(*estados: tuple[str, str, str, int | None]) -> LiveDataResponse:
    """Dados ao vivo a partir de tuplas `(id, nome, status, minutos_de_fila)`."""
    return LiveDataResponse.model_validate(
        {
            "id": "parque-teste",
            "name": "Parque de Teste",
            "liveData": [
                {
                    "id": id_,
                    "name": nome,
                    "status": status,
                    "lastUpdated": "2026-09-12T15:54:19.095Z",
                    "queue": {"STANDBY": {"waitTime": fila}},
                }
                for id_, nome, status, fila in estados
            ],
        }
    )


class TestATeseDoProjeto:
    """A razão de o NextUp existir."""

    def test_fila_menor_perde_para_atracao_mais_perto(self):
        """O caso que o README promete resolver.

        Longe: fila de 10 min, a 900 m — ~18 min de caminhada, 28 no total.
        Perto: fila de 20 min, a 50 m — ~1 min de caminhada, 21 no total.

        Ordenar por fila colocaria a de 10 min em primeiro. Ordenar por custo
        total mostra a verdade: ir até lá custa 7 minutos a mais.
        """
        lat_longe, lon_longe = ao_norte(900)
        lat_perto, lon_perto = ao_norte(50)

        resultado = recommend(
            catalog=montar_catalogo(
                ("longe", "Fila Curta Longe", lat_longe, lon_longe),
                ("perto", "Fila Longa Perto", lat_perto, lon_perto),
            ),
            live=montar_live(
                ("longe", "Fila Curta Longe", "OPERATING", 10),
                ("perto", "Fila Longa Perto", "OPERATING", 20),
            ),
            visitor=VISITANTE,
        )

        assert [r.attraction.id for r in resultado] == ["perto", "longe"]
        assert resultado[0].total_minutes < resultado[1].total_minutes

    def test_entre_filas_iguais_vence_a_mais_perto(self):
        lat_longe, lon_longe = ao_norte(800)
        lat_perto, lon_perto = ao_norte(30)

        resultado = recommend(
            catalog=montar_catalogo(
                ("longe", "Longe", lat_longe, lon_longe),
                ("perto", "Perto", lat_perto, lon_perto),
            ),
            live=montar_live(
                ("longe", "Longe", "OPERATING", 15),
                ("perto", "Perto", "OPERATING", 15),
            ),
            visitor=VISITANTE,
        )

        assert resultado[0].attraction.id == "perto"

    def test_a_distancias_iguais_vence_a_fila_menor(self):
        """O outro lado da moeda: sem diferença de caminhada, a fila decide."""
        lat, lon = ao_norte(100)

        resultado = recommend(
            catalog=montar_catalogo(
                ("cheia", "Cheia", lat, lon),
                ("vazia", "Vazia", lat, lon),
            ),
            live=montar_live(
                ("cheia", "Cheia", "OPERATING", 60),
                ("vazia", "Vazia", "OPERATING", 5),
            ),
            visitor=VISITANTE,
        )

        assert resultado[0].attraction.id == "vazia"

    def test_caminhada_muito_longa_derruba_fila_zerada(self):
        """Fila zero a 2 km perde para fila de 10 min ao lado."""
        lat_longe, lon_longe = ao_norte(2_000)
        lat_perto, lon_perto = ao_norte(20)

        resultado = recommend(
            catalog=montar_catalogo(
                ("longe", "Sem Fila Longe", lat_longe, lon_longe),
                ("perto", "Com Fila Perto", lat_perto, lon_perto),
            ),
            live=montar_live(
                ("longe", "Sem Fila Longe", "OPERATING", 0),
                ("perto", "Com Fila Perto", "OPERATING", 10),
            ),
            visitor=VISITANTE,
        )

        assert resultado[0].attraction.id == "perto"


class TestOrdenacao:
    def test_resultado_sai_em_ordem_crescente_de_custo(self):
        resultado = recommend(
            catalog=montar_catalogo(
                ("a", "A", *ao_norte(100)),
                ("b", "B", *ao_norte(200)),
                ("c", "C", *ao_norte(300)),
            ),
            live=montar_live(
                ("a", "A", "OPERATING", 40),
                ("b", "B", "OPERATING", 5),
                ("c", "C", "OPERATING", 20),
            ),
            visitor=VISITANTE,
            limit=0,
        )

        custos = [r.total_minutes for r in resultado]
        assert custos == sorted(custos)

    def test_limit_corta_o_topo_da_lista(self):
        resultado = recommend(
            catalog=montar_catalogo(
                ("a", "A", *ao_norte(100)),
                ("b", "B", *ao_norte(200)),
                ("c", "C", *ao_norte(300)),
            ),
            live=montar_live(
                ("a", "A", "OPERATING", 10),
                ("b", "B", "OPERATING", 20),
                ("c", "C", "OPERATING", 30),
            ),
            visitor=VISITANTE,
            limit=2,
        )

        assert len(resultado) == 2
        assert [r.attraction.id for r in resultado] == ["a", "b"]

    def test_limit_zero_devolve_todas(self):
        resultado = recommend(
            catalog=montar_catalogo(
                ("a", "A", *ao_norte(100)),
                ("b", "B", *ao_norte(200)),
            ),
            live=montar_live(
                ("a", "A", "OPERATING", 10),
                ("b", "B", "OPERATING", 20),
            ),
            visitor=VISITANTE,
            limit=0,
        )

        assert len(resultado) == 2


class TestFiltrosEliminatorios:
    @pytest.mark.parametrize("status", ["CLOSED", "DOWN", "REFURBISHMENT"])
    def test_atracao_que_nao_esta_operando_fica_de_fora(self, status):
        resultado = recommend(
            catalog=montar_catalogo(
                ("fora", "Fora do Ar", *ao_norte(50)),
                ("ok", "Funcionando", *ao_norte(500)),
            ),
            live=montar_live(
                ("fora", "Fora do Ar", status, 5),
                ("ok", "Funcionando", "OPERATING", 30),
            ),
            visitor=VISITANTE,
        )

        assert [r.attraction.id for r in resultado] == ["ok"]

    def test_atracao_sem_fila_medida_fica_de_fora(self):
        """O Castelo da Cinderela está aberto e não é brinquedo."""
        resultado = recommend(
            catalog=montar_catalogo(
                ("castelo", "Castelo", *ao_norte(10)),
                ("ok", "Brinquedo", *ao_norte(500)),
            ),
            live=montar_live(
                ("castelo", "Castelo", "OPERATING", None),
                ("ok", "Brinquedo", "OPERATING", 30),
            ),
            visitor=VISITANTE,
        )

        assert [r.attraction.id for r in resultado] == ["ok"]

    def test_atracao_sem_dado_ao_vivo_fica_de_fora(self):
        """Está no catálogo mas a API não reportou estado: não dá para avaliar."""
        resultado = recommend(
            catalog=montar_catalogo(
                ("fantasma", "Sem Dado", *ao_norte(10)),
                ("ok", "Com Dado", *ao_norte(500)),
            ),
            live=montar_live(("ok", "Com Dado", "OPERATING", 30)),
            visitor=VISITANTE,
        )

        assert [r.attraction.id for r in resultado] == ["ok"]

    def test_parque_todo_fechado_devolve_lista_vazia(self):
        """Madrugada não é erro: é uma resposta legítima."""
        resultado = recommend(
            catalog=montar_catalogo(("a", "A", *ao_norte(100))),
            live=montar_live(("a", "A", "CLOSED", None)),
            visitor=VISITANTE,
        )

        assert resultado == []


class TestConta:
    def test_custo_total_e_a_soma_das_duas_parcelas(self):
        recomendacao = Recommendation(
            attraction=montar_catalogo(("a", "A", *ao_norte(100))).children[0],
            walking_minutes=4.0,
            queue_minutes=20,
        )

        assert recomendacao.total_minutes == 24.0

    def test_estar_em_cima_da_atracao_zera_a_caminhada(self):
        resultado = recommend(
            catalog=montar_catalogo(("a", "A", VISITANTE.latitude, VISITANTE.longitude)),
            live=montar_live(("a", "A", "OPERATING", 20)),
            visitor=VISITANTE,
        )

        assert resultado[0].walking_minutes == pytest.approx(0.0, abs=0.01)
        assert resultado[0].total_minutes == pytest.approx(20.0, abs=0.01)

    def test_caminhada_bate_com_o_esperado_para_a_distancia(self):
        """Verdade externa: 900 m em linha reta, com sinuosidade 1,3 e 1,1 m/s.

        900 x 1,3 = 1.170 m; 1.170 / 1,1 = 1.063 s = ~17,7 min.
        """
        resultado = recommend(
            catalog=montar_catalogo(("a", "A", *ao_norte(900))),
            live=montar_live(("a", "A", "OPERATING", 0)),
            visitor=VISITANTE,
        )

        assert resultado[0].walking_minutes == pytest.approx(17.7, abs=0.3)

    def test_andar_mais_devagar_aumenta_o_custo(self):
        argumentos = {
            "catalog": montar_catalogo(("a", "A", *ao_norte(500))),
            "live": montar_live(("a", "A", "OPERATING", 10)),
            "visitor": VISITANTE,
        }

        rapido = recommend(**argumentos, speed_mps=1.4)
        devagar = recommend(**argumentos, speed_mps=0.8)

        assert devagar[0].total_minutes > rapido[0].total_minutes

    def test_trajeto_mais_sinuoso_aumenta_o_custo(self):
        argumentos = {
            "catalog": montar_catalogo(("a", "A", *ao_norte(500))),
            "live": montar_live(("a", "A", "OPERATING", 10)),
            "visitor": VISITANTE,
        }

        reto = recommend(**argumentos, winding_factor=1.0)
        sinuoso = recommend(**argumentos, winding_factor=1.6)

        assert sinuoso[0].total_minutes > reto[0].total_minutes


class TestJustificativa:
    def test_explica_a_conta_em_texto(self):
        recomendacao = Recommendation(
            attraction=montar_catalogo(("a", "Big Thunder Mountain", *ao_norte(100))).children[0],
            walking_minutes=4.2,
            queue_minutes=20,
        )

        assert recomendacao.explain() == (
            "Big Thunder Mountain — 4 min de caminhada + 20 min de fila = 24 min"
        )


class TestComDadosReais:
    """O algoritmo sobre o Magic Kingdom de verdade, capturado em 12/09/2026."""

    @pytest.fixture
    def catalogo(self) -> ParkCatalog:
        caminho = FIXTURES / "children_magic_kingdom.json"
        return ParkCatalog.model_validate(json.loads(caminho.read_text(encoding="utf-8")))

    @pytest.fixture
    def ao_vivo(self) -> LiveDataResponse:
        caminho = FIXTURES / "live_magic_kingdom.json"
        return LiveDataResponse.model_validate(json.loads(caminho.read_text(encoding="utf-8")))

    def test_ranqueia_as_26_atracoes_disponiveis(self, catalogo, ao_vivo):
        """Mesmo número que o CLI mostra: as ranqueáveis da fixture."""
        resultado = recommend(
            catalog=catalogo,
            live=ao_vivo,
            visitor=Location(latitude=28.42037, longitude=-81.58031),
            limit=0,
        )

        assert len(resultado) == 26

    def test_nenhum_custo_e_menor_que_a_propria_fila(self, catalogo, ao_vivo):
        """Caminhada nunca é negativa, então o total sempre cobre a fila."""
        resultado = recommend(
            catalog=catalogo,
            live=ao_vivo,
            visitor=Location(latitude=28.42037, longitude=-81.58031),
            limit=0,
        )

        for r in resultado:
            assert r.total_minutes >= r.queue_minutes

    def test_caminhada_dentro_do_parque_nunca_passa_de_meia_hora(self, catalogo, ao_vivo):
        """O Magic Kingdom tem ~430 mil m². Nada lá dentro fica a 30 min a pé."""
        resultado = recommend(
            catalog=catalogo,
            live=ao_vivo,
            visitor=Location(latitude=28.42037, longitude=-81.58031),
            limit=0,
        )

        assert all(r.walking_minutes < 30 for r in resultado)

    def test_o_ponto_de_partida_muda_a_recomendacao(self, catalogo, ao_vivo):
        """Prova que a distância pesa de verdade: dois visitantes em pontas
        opostas do parque não recebem a mesma resposta."""
        norte = recommend(
            catalog=catalogo,
            live=ao_vivo,
            visitor=Location(latitude=28.4210, longitude=-81.5810),
        )
        sul = recommend(
            catalog=catalogo,
            live=ao_vivo,
            visitor=Location(latitude=28.4180, longitude=-81.5820),
        )

        assert [r.attraction.id for r in norte] != [r.attraction.id for r in sul]

"""Testes da persistência do histórico de filas.

Rodam contra um **SQLite em memória**, criado e destruído a cada teste. São rápidos
como os testes do `core/` e, como eles, não dependem de nada externo estar de pé —
ninguém precisa ter um Postgres instalado para rodar a suíte.

O que este arquivo protege, acima de tudo, é a **defesa contra medição duplicada**.
É uma falha que não dá erro: as linhas repetidas entram, ninguém percebe, e a média
histórica que alimenta a previsão passa a contar o mesmo dado duas vezes. Um teste
é o único jeito de esse comportamento continuar existindo daqui a seis meses.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from nextup.models import LiveData, LiveStatus, QueueForecast, QueueSnapshot
from nextup.storage import (
    average_waits,
    connection,
    create_schema,
    forecasts_for,
    history,
    purge_older_than,
    save_forecasts,
    save_many,
)
from nextup.storage.engine import create_engine

PARQUE = "75ea578a-adc8-4116-a54d-dccb60765ef9"
SPACE_MOUNTAIN = "8ea94a92-1a80-4d0e-bb39-6be2b2b4f2a9"
BIG_THUNDER = "f3d64a2d-0b0f-4b3f-a2b5-d4b2b2b2b2b2"

#: Um instante fixo. Teste que usa `now()` real passa hoje e falha quando o relógio
#: cruza uma virada de dia ou de horário de verão.
AGORA = datetime(2026, 9, 15, 14, 30, tzinfo=UTC)


@pytest.fixture
async def engine() -> AsyncEngine:
    """Um banco SQLite em memória, só para este teste.

    `:memory:` some quando a conexão fecha, o que é exatamente o isolamento que se
    quer: nenhum teste enxerga o que outro gravou, e não fica arquivo sobrando na
    máquina de quem roda a suíte.
    """
    motor = create_engine("sqlite+aiosqlite:///:memory:")
    await create_schema(motor)
    yield motor
    await motor.dispose()


def snapshot(
    *,
    attraction_id: str = SPACE_MOUNTAIN,
    wait: int | None = 45,
    status: LiveStatus = LiveStatus.OPERATING,
    observed_at: datetime = AGORA,
    recorded_at: datetime | None = None,
) -> QueueSnapshot:
    """Constrói um snapshot com padrões razoáveis, para o teste dizer só o que importa."""
    return QueueSnapshot(
        park_id=PARQUE,
        attraction_id=attraction_id,
        status=status,
        wait_time_minutes=wait,
        observed_at=observed_at,
        recorded_at=recorded_at or observed_at,
    )


class TestGravar:
    async def test_grava_e_devolve_a_quantidade(self, engine):
        async with connection(engine) as conexao:
            gravados = await save_many(conexao, [snapshot(), snapshot(attraction_id=BIG_THUNDER)])

        assert gravados == 2

    async def test_lista_vazia_nao_quebra(self, engine):
        """Parque fechado de madrugada devolve zero atrações. Não é erro."""
        async with connection(engine) as conexao:
            assert await save_many(conexao, []) == 0

    async def test_a_mesma_medicao_nao_entra_duas_vezes(self, engine):
        """O coração desta fase: coletar de novo antes de a fonte atualizar não duplica.

        Os dois snapshots têm o mesmo `observed_at` — é a *mesma* medição, lida em
        dois momentos nossos diferentes. Só a primeira deve virar linha.
        """
        async with connection(engine) as conexao:
            primeira = await save_many(conexao, [snapshot(recorded_at=AGORA)])
            segunda = await save_many(conexao, [snapshot(recorded_at=AGORA + timedelta(minutes=5))])

            guardados = await history(
                conexao, attraction_id=SPACE_MOUNTAIN, since=AGORA - timedelta(days=1)
            )

        assert (primeira, segunda) == (1, 0)
        assert len(guardados) == 1

    async def test_duplicata_no_meio_do_lote_nao_impede_as_outras(self, engine):
        """Uma repetida não pode fazer o lote inteiro ser descartado.

        Sem `ON CONFLICT DO NOTHING` a transação abortaria na linha repetida e as
        boas se perderiam junto — o coletor passaria a perder ciclos inteiros por
        causa de uma única atração que a fonte não atualizou.
        """
        async with connection(engine) as conexao:
            await save_many(conexao, [snapshot()])

            gravados = await save_many(
                conexao,
                [
                    snapshot(attraction_id=BIG_THUNDER),
                    snapshot(),  # repetida
                    snapshot(
                        attraction_id=SPACE_MOUNTAIN, observed_at=AGORA + timedelta(minutes=10)
                    ),
                ],
            )

        assert gravados == 2

    async def test_atracoes_diferentes_no_mesmo_instante_convivem(self, engine):
        """A unicidade é por atração *e* instante — o parque inteiro é medido junto."""
        async with connection(engine) as conexao:
            gravados = await save_many(
                conexao,
                [snapshot(), snapshot(attraction_id=BIG_THUNDER)],
            )

        assert gravados == 2

    async def test_guarda_atracao_fechada_sem_fila(self, engine):
        """Fila nula é história legítima: descartá-la criaria buraco no gráfico."""
        async with connection(engine) as conexao:
            await save_many(conexao, [snapshot(status=LiveStatus.CLOSED, wait=None)])

            guardados = await history(
                conexao, attraction_id=SPACE_MOUNTAIN, since=AGORA - timedelta(days=1)
            )

        assert guardados[0].wait_time_minutes is None
        assert guardados[0].status is LiveStatus.CLOSED


class TestConsultarHistorico:
    async def test_devolve_em_ordem_cronologica(self, engine):
        """Gravados fora de ordem de propósito — quem ordena é a consulta, não a inserção."""
        async with connection(engine) as conexao:
            await save_many(
                conexao,
                [
                    snapshot(wait=30, observed_at=AGORA + timedelta(minutes=20)),
                    snapshot(wait=50, observed_at=AGORA),
                    snapshot(wait=40, observed_at=AGORA + timedelta(minutes=10)),
                ],
            )

            linha_do_tempo = await history(
                conexao, attraction_id=SPACE_MOUNTAIN, since=AGORA - timedelta(hours=1)
            )

        assert [s.wait_time_minutes for s in linha_do_tempo] == [50, 40, 30]

    async def test_ignora_outras_atracoes(self, engine):
        async with connection(engine) as conexao:
            await save_many(conexao, [snapshot(), snapshot(attraction_id=BIG_THUNDER)])

            apenas_uma = await history(
                conexao, attraction_id=SPACE_MOUNTAIN, since=AGORA - timedelta(hours=1)
            )

        assert [s.attraction_id for s in apenas_uma] == [SPACE_MOUNTAIN]

    async def test_respeita_a_janela_pedida(self, engine):
        async with connection(engine) as conexao:
            await save_many(
                conexao,
                [
                    snapshot(wait=10, observed_at=AGORA - timedelta(hours=5)),
                    snapshot(wait=20, observed_at=AGORA - timedelta(hours=1)),
                    snapshot(wait=30, observed_at=AGORA + timedelta(hours=1)),
                ],
            )

            janela = await history(
                conexao,
                attraction_id=SPACE_MOUNTAIN,
                since=AGORA - timedelta(hours=2),
                until=AGORA,
            )

        assert [s.wait_time_minutes for s in janela] == [20]

    async def test_sem_dados_devolve_lista_vazia(self, engine):
        """Atração nova, ou janela anterior ao início da coleta. Não é erro."""
        async with connection(engine) as conexao:
            assert await history(conexao, attraction_id=SPACE_MOUNTAIN, since=AGORA) == []

    async def test_o_fuso_sobrevive_a_ida_e_volta(self, engine):
        """A armadilha do SQLite: ele não guarda fuso, e devolveria data ingênua.

        Comparar contra o instante original — uma verdade externa ao código de
        leitura — é o que detecta um deslocamento de horas no histórico.
        """
        async with connection(engine) as conexao:
            await save_many(conexao, [snapshot(observed_at=AGORA)])

            lido = await history(
                conexao, attraction_id=SPACE_MOUNTAIN, since=AGORA - timedelta(hours=1)
            )

        assert lido[0].observed_at == AGORA
        assert lido[0].observed_at.tzinfo is not None


class TestRetencao:
    async def test_apaga_so_o_que_passou_do_prazo(self, engine):
        corte = AGORA - timedelta(days=90)

        async with connection(engine) as conexao:
            await save_many(
                conexao,
                [
                    snapshot(observed_at=corte - timedelta(days=1)),
                    snapshot(observed_at=corte + timedelta(days=1)),
                    snapshot(observed_at=AGORA),
                ],
            )

            apagados = await purge_older_than(conexao, corte)
            restantes = await history(
                conexao, attraction_id=SPACE_MOUNTAIN, since=corte - timedelta(days=365)
            )

        assert apagados == 1
        assert len(restantes) == 2

    async def test_banco_vazio_nao_quebra(self, engine):
        async with connection(engine) as conexao:
            assert await purge_older_than(conexao, AGORA) == 0


class TestPrevisoesDaFonte:
    """A tabela que torna a previsão da fonte auditável.

    A deduplicação aqui tem propósito diferente da dos snapshots. Lá, impede contar
    a mesma medição duas vezes na média. Aqui, **preserva a antecedência**: a fonte
    republica o mesmo perfil horário a cada consulta, e guardar só a estreia é o que
    faz `recorded_at` significar "quando a fonte se comprometeu com esse número".
    """

    def previsao(self, *, para_daqui_a: float, minutos: int = 40, vista_em=None):
        return QueueForecast(
            park_id=PARQUE,
            attraction_id=SPACE_MOUNTAIN,
            forecast_for=AGORA + timedelta(hours=para_daqui_a),
            predicted_minutes=minutos,
            recorded_at=vista_em or AGORA,
        )

    async def test_grava_as_previsoes(self, engine):
        async with connection(engine) as conexao:
            gravadas = await save_forecasts(
                conexao,
                [self.previsao(para_daqui_a=1), self.previsao(para_daqui_a=2)],
            )

        assert gravadas == 2

    async def test_a_republicacao_nao_vira_linha_nova(self, engine):
        """A fonte republica o mesmo perfil a cada consulta — 288 vezes por dia."""
        async with connection(engine) as conexao:
            primeira = await save_forecasts(conexao, [self.previsao(para_daqui_a=3)])
            repetida = await save_forecasts(
                conexao,
                [self.previsao(para_daqui_a=3, vista_em=AGORA + timedelta(minutes=5))],
            )

        assert (primeira, repetida) == (1, 0)

    async def test_preserva_a_antecedencia_da_primeira_vez(self, engine):
        """O ponto da deduplicação.

        Se a repetição sobrescrevesse, `recorded_at` passaria a dizer "a última vez
        que vimos" — e a antecedência, que é o que dá valor à previsão, viraria
        sempre alguns minutos.
        """
        async with connection(engine) as conexao:
            await save_forecasts(conexao, [self.previsao(para_daqui_a=3)])
            await save_forecasts(
                conexao,
                [self.previsao(para_daqui_a=3, vista_em=AGORA + timedelta(hours=2))],
            )

            guardadas = await forecasts_for(conexao, attraction_id=SPACE_MOUNTAIN, since=AGORA)

        assert len(guardadas) == 1
        assert guardadas[0].recorded_at == AGORA
        assert guardadas[0].lead_time_minutes == pytest.approx(180)

    async def test_consulta_respeita_a_janela(self, engine):
        async with connection(engine) as conexao:
            await save_forecasts(
                conexao,
                [self.previsao(para_daqui_a=1), self.previsao(para_daqui_a=8)],
            )

            proximas = await forecasts_for(
                conexao,
                attraction_id=SPACE_MOUNTAIN,
                since=AGORA,
                until=AGORA + timedelta(hours=4),
            )

        assert len(proximas) == 1

    async def test_so_o_futuro_e_convertido(self):
        """A fonte devolve o dia inteiro; o passado já virou fato medido."""
        live = LiveData.model_validate(
            {
                "id": SPACE_MOUNTAIN,
                "name": "Space Mountain",
                "status": "OPERATING",
                "queue": {"STANDBY": {"waitTime": 45}},
                "lastUpdated": "2026-09-15T14:30:00Z",
                "forecast": [
                    {"time": "2026-09-15T13:00:00Z", "waitTime": 20, "percentage": 30},
                    {"time": "2026-09-15T16:00:00Z", "waitTime": 60, "percentage": 80},
                ],
            }
        )

        previsoes = QueueForecast.from_live(park_id=PARQUE, live=live, recorded_at=AGORA)

        assert [p.predicted_minutes for p in previsoes] == [60]

    async def test_atracao_sem_forecast_nao_gera_nada(self):
        """Cerca de dois terços das entidades não têm previsão. Não é erro."""
        live = LiveData.model_validate(
            {
                "id": SPACE_MOUNTAIN,
                "name": "Space Mountain",
                "status": "OPERATING",
                "lastUpdated": "2026-09-15T14:30:00Z",
            }
        )

        assert QueueForecast.from_live(park_id=PARQUE, live=live, recorded_at=AGORA) == []


class TestConversaoDoLiveData:
    """`QueueSnapshot.from_live` é a ponte entre o que a API devolve e o que guardamos."""

    def test_converte_uma_leitura_ao_vivo(self):
        live = LiveData.model_validate(
            {
                "id": SPACE_MOUNTAIN,
                "name": "Space Mountain",
                "status": "OPERATING",
                "queue": {"STANDBY": {"waitTime": 45}},
                "lastUpdated": "2026-09-15T14:30:00Z",
            }
        )

        convertido = QueueSnapshot.from_live(park_id=PARQUE, live=live, recorded_at=AGORA)

        assert convertido.attraction_id == SPACE_MOUNTAIN
        assert convertido.wait_time_minutes == 45
        assert convertido.observed_at == AGORA

    def test_atracao_sem_fila_vira_snapshot_com_nulo(self):
        """O Castelo da Cinderela: aberto, sem fila medida. Ver `LiveData.is_rankable`."""
        live = LiveData.model_validate(
            {
                "id": SPACE_MOUNTAIN,
                "name": "Cinderella Castle",
                "status": "OPERATING",
                "lastUpdated": "2026-09-15T14:30:00Z",
            }
        )

        convertido = QueueSnapshot.from_live(park_id=PARQUE, live=live, recorded_at=AGORA)

        assert convertido.wait_time_minutes is None

    def test_converte_o_fuso_para_utc(self):
        """A API pode responder em qualquer offset; o banco guarda tudo em UTC."""
        live = LiveData.model_validate(
            {
                "id": SPACE_MOUNTAIN,
                "name": "Space Mountain",
                "status": "OPERATING",
                "queue": {"STANDBY": {"waitTime": 45}},
                # 10:30 em Orlando (UTC-4) é 14:30 UTC — o mesmo instante de `AGORA`.
                "lastUpdated": "2026-09-15T10:30:00-04:00",
            }
        )

        convertido = QueueSnapshot.from_live(park_id=PARQUE, live=live, recorded_at=AGORA)

        assert convertido.observed_at == AGORA

    def test_data_sem_fuso_e_recusada(self):
        """Falhar alto e cedo. Uma data ingênua aceita aqui vira gráfico torto depois."""
        with pytest.raises(ValueError, match="fuso"):
            QueueSnapshot(
                park_id=PARQUE,
                attraction_id=SPACE_MOUNTAIN,
                status=LiveStatus.OPERATING,
                wait_time_minutes=45,
                observed_at=datetime(2026, 9, 15, 14, 30),  # sem tzinfo
                recorded_at=AGORA,
            )


class TestMediaDeEspera:
    """A agregação que alimenta a popularidade.

    A conta roda **no banco**, e não na memória: a janela é de sete dias e um
    parque gera cerca de 70 mil linhas nesse período. Trazê-las do Neon para somar
    aqui seria arrastar megabytes pela rede a cada recomendação.
    """

    async def test_calcula_a_media_por_atracao(self, engine):
        async with connection(engine) as conexao:
            await save_many(
                conexao,
                [
                    snapshot(wait=10, observed_at=AGORA),
                    snapshot(wait=20, observed_at=AGORA + timedelta(minutes=5)),
                    snapshot(attraction_id=BIG_THUNDER, wait=60, observed_at=AGORA),
                ],
            )
            medias = await average_waits(conexao, park_id=PARQUE, since=AGORA - timedelta(days=7))

        assert medias[SPACE_MOUNTAIN] == (15.0, 2)
        assert medias[BIG_THUNDER] == (60.0, 1)

    async def test_ignora_medicao_sem_fila(self, engine):
        """Mesmo critério de `core.history.summarize`, pelo mesmo motivo: contar
        atração fechada como zero faria a madrugada parecer o melhor horário."""
        async with connection(engine) as conexao:
            await save_many(
                conexao,
                [
                    snapshot(wait=30, observed_at=AGORA),
                    snapshot(
                        wait=None,
                        status=LiveStatus.CLOSED,
                        observed_at=AGORA + timedelta(minutes=5),
                    ),
                ],
            )
            medias = await average_waits(conexao, park_id=PARQUE, since=AGORA - timedelta(days=7))

        # 30, e não 15: a fechada não entrou nem no numerador nem no denominador.
        assert medias[SPACE_MOUNTAIN] == (30.0, 1)

    async def test_atracao_so_com_medicao_vazia_nao_aparece(self, engine):
        """Ausente é diferente de zero. Quem classifica precisa da distinção."""
        async with connection(engine) as conexao:
            await save_many(conexao, [snapshot(wait=None, status=LiveStatus.CLOSED)])
            medias = await average_waits(conexao, park_id=PARQUE, since=AGORA - timedelta(days=7))

        assert SPACE_MOUNTAIN not in medias

    async def test_respeita_a_janela(self, engine):
        async with connection(engine) as conexao:
            await save_many(
                conexao,
                [
                    snapshot(wait=90, observed_at=AGORA - timedelta(days=30)),
                    snapshot(wait=10, observed_at=AGORA),
                ],
            )
            medias = await average_waits(conexao, park_id=PARQUE, since=AGORA - timedelta(days=7))

        # A medição de 30 dias atrás ficaria com média 50 se tivesse entrado.
        assert medias[SPACE_MOUNTAIN] == (10.0, 1)

    async def test_ignora_outro_parque(self, engine):
        async with connection(engine) as conexao:
            await save_many(conexao, [snapshot(wait=10)])
            medias = await average_waits(
                conexao, park_id="outro-parque", since=AGORA - timedelta(days=7)
            )

        assert medias == {}

    async def test_banco_vazio_devolve_mapa_vazio(self, engine):
        """Primeiro dia de coleta. Resposta legítima, não erro."""
        async with connection(engine) as conexao:
            assert await average_waits(conexao, park_id=PARQUE, since=AGORA) == {}

    async def test_a_media_sai_como_float(self, engine):
        """O Postgres devolve `AVG` de inteiro como `Decimal` e o SQLite como
        `float`. Sem a conversão explícita, só o ambiente de produção quebraria."""
        async with connection(engine) as conexao:
            await save_many(conexao, [snapshot(wait=45)])
            medias = await average_waits(conexao, park_id=PARQUE, since=AGORA - timedelta(days=7))

        assert isinstance(medias[SPACE_MOUNTAIN][0], float)

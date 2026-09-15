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

from nextup.models import LiveData, LiveStatus, QueueSnapshot
from nextup.storage import connection, create_schema, history, purge_older_than, save_many
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

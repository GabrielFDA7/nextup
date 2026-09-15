"""Snapshot de fila — uma medição isolada, guardada para virar história.

Este é o primeiro modelo do NextUp que **não** vem da ThemeParks.wiki: nasce de um
`LiveData`, mas quem o produz somos nós, gravando o estado de uma atração num
instante. É a matéria-prima da Fase 6 — tendência, melhor horário e previsão só
existem porque alguém guardou o passado.

**Duas datas, de propósito.** `observed_at` é quando a *fonte* mediu a fila;
`recorded_at` é quando *nós* gravamos. Parecem redundantes e não são:

- A API atualiza a cada poucos minutos, num ritmo que não controlamos. Se o
  coletor rodar mais rápido que isso, a mesma medição chegaria duas vezes — e uma
  média histórica contando o mesmo dado em dobro fica enviesada **sem nunca dar
  erro**. É `observed_at` que identifica a medição e permite recusar a repetida.
- A diferença entre as duas responde "o dado já estava velho quando recomendamos?".

Como em todo modelo desta pasta, aqui não existe banco: `models/` é o idioma
comum. O mapeamento para tabela mora em `storage/`.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from nextup.models.live import LiveData, LiveStatus


class QueueSnapshot(BaseModel):
    """O estado de uma atração num instante, pronto para ser persistido."""

    model_config = ConfigDict(frozen=True)

    #: Guardado junto para permitir consultar o histórico de um parque inteiro sem
    #: precisar do catálogo para descobrir quais atrações pertencem a ele.
    park_id: str = Field(min_length=1)

    attraction_id: str = Field(min_length=1)

    status: LiveStatus

    #: Nulo é dado legítimo, não falha: atração fechada, ou aberta sem fila medida.
    #: Guardamos a linha mesmo assim — "esteve fechada às 14h" também é história,
    #: e descartá-la criaria buracos que pareceriam falha do coletor.
    wait_time_minutes: int | None = Field(default=None, ge=0)

    #: Quando a *fonte* mediu. Identifica a medição — ver o cabeçalho do módulo.
    observed_at: datetime

    #: Quando *nós* gravamos.
    recorded_at: datetime

    @field_validator("observed_at", "recorded_at")
    @classmethod
    def exigir_utc(cls, valor: datetime) -> datetime:
        """Converte para UTC e recusa data sem fuso.

        Sem isso o projeto acumularia uma bomba-relógio: o Postgres guarda o fuso,
        o SQLite não. Um `datetime` ingênuo gravado em produção e lido em
        desenvolvimento viraria outro horário, e o histórico ficaria deslocado em
        algumas horas — erro que não aparece em teste nenhum, só no gráfico torto.
        Normalizando na entrada, todo instante do banco está em UTC por construção.
        """
        if valor.tzinfo is None:
            raise ValueError(
                "instante sem fuso horário; use datetime com timezone "
                "(ex.: datetime.now(UTC)) para o histórico não ficar deslocado"
            )
        return valor.astimezone(UTC)

    @classmethod
    def from_live(cls, *, park_id: str, live: LiveData, recorded_at: datetime) -> "QueueSnapshot":
        """Converte uma leitura ao vivo em snapshot.

        O `recorded_at` é recebido em vez de calculado aqui dentro pelo mesmo motivo
        do relógio injetável do cache: um valor vindo de fora é um valor que o teste
        consegue fixar.

        Args:
            park_id: Parque a que a atração pertence.
            live: A leitura ao vivo, já validada.
            recorded_at: Instante da nossa gravação.
        """
        return cls(
            park_id=park_id,
            attraction_id=live.id,
            status=live.status,
            wait_time_minutes=live.wait_time_minutes,
            observed_at=live.last_updated,
            recorded_at=recorded_at,
        )

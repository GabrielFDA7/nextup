"""guarda as previsoes publicadas pela fonte

Nasce de um resultado negativo, e isso é o ponto. Em 20/09/2026 um backtest sobre
o histórico real mostrou que extrapolar a tendência **piora** a previsão da fila em
todos os horizontes testados — inclusive isolando os casos em que a fila mudou.
Sobrou um único candidato não testado: a previsão horária que a própria
ThemeParks.wiki publica.

Ela não podia ser avaliada porque ninguém a estava guardando. Esta tabela conserta
isso. Cada linha é uma previsão da fonte, e `recorded_at` registra com quanta
antecedência ela foi feita — cruzando com `queue_snapshots` depois, dá para medir
o erro de verdade em vez de confiar por intuição.

Revision ID: 36d60703d445
Revises: cf3e3ac607b6
Create Date: 2026-09-20 12:53:11.402676
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "36d60703d445"
down_revision: str | Sequence[str] | None = "cf3e3ac607b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `queue_forecasts`, para tornar a previsão da fonte auditável."""
    op.create_table(
        "queue_forecasts",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("park_id", sa.String(length=64), nullable=False),
        sa.Column("attraction_id", sa.String(length=64), nullable=False),
        # O horário que a previsão descreve.
        sa.Column("forecast_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("predicted_minutes", sa.Integer(), nullable=False),
        sa.Column("percentage", sa.Float(), nullable=True),
        # Quando vimos esta previsão pela primeira vez. A distância até
        # `forecast_for` é a antecedência — e previsão de três horas antes vale
        # muito mais que previsão de cinco minutos antes.
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_queue_forecasts")),
        # A fonte republica o mesmo perfil horário a cada consulta. Sem esta
        # restrição, prever "18h -> 40 min" viraria 288 linhas idênticas por dia; e,
        # pior, `recorded_at` passaria a dizer "a última vez que vimos" em vez de
        # "quando a fonte se comprometeu", destruindo a medida de antecedência.
        sa.UniqueConstraint("attraction_id", "forecast_for", name="uq_queue_forecasts_previsao"),
    )
    with op.batch_alter_table("queue_forecasts", schema=None) as batch_op:
        batch_op.create_index(
            "ix_queue_forecasts_avaliacao", ["attraction_id", "forecast_for"], unique=False
        )


def downgrade() -> None:
    """Remove a tabela, e com ela todo o registro de previsões da fonte.

    O histórico de filas em `queue_snapshots` não é afetado — o ranking e o gráfico
    continuam funcionando. O que se perde é a capacidade de avaliar a fonte.
    """
    with op.batch_alter_table("queue_forecasts", schema=None) as batch_op:
        batch_op.drop_index("ix_queue_forecasts_avaliacao")

    op.drop_table("queue_forecasts")

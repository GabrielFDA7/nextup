"""cria a tabela de snapshots de fila

A primeira migração do NextUp, e o marco em que o projeto deixa de ser sem estado:
até aqui ele consultava a ThemeParks.wiki e esquecia; a partir daqui ele acumula
história própria, que é o que a Fase 6 transforma em tendência e previsão.

Revision ID: cf3e3ac607b6
Revises:
Create Date: 2026-09-15 19:05:57.014441
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cf3e3ac607b6"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `queue_snapshots`, com a restrição que impede medição duplicada."""
    op.create_table(
        "queue_snapshots",
        # A variante para SQLite não é enfeite: só `INTEGER PRIMARY KEY` recebe ID
        # automático nele, e com `BIGINT` a inserção falharia com chave nula.
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("park_id", sa.String(length=64), nullable=False),
        sa.Column("attraction_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        # Nulo é dado legítimo: atração fechada, ou aberta sem fila medida.
        sa.Column("wait_time_minutes", sa.Integer(), nullable=True),
        # `observed_at` é quando a fonte mediu; `recorded_at`, quando gravamos.
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_queue_snapshots")),
        # A defesa contra contar a mesma medição duas vezes na média histórica.
        sa.UniqueConstraint("attraction_id", "observed_at", name="uq_queue_snapshots_medicao"),
    )
    with op.batch_alter_table("queue_snapshots", schema=None) as batch_op:
        batch_op.create_index(
            "ix_queue_snapshots_historico", ["attraction_id", "observed_at"], unique=False
        )
        batch_op.create_index("ix_queue_snapshots_parque", ["park_id", "observed_at"], unique=False)


def downgrade() -> None:
    """Desfaz a criação da tabela.

    Apaga o histórico junto — é o que "desfazer" significa aqui. Existe para o
    caminho de volta ser testável, não para ser rodado em produção sem pensar.
    """
    with op.batch_alter_table("queue_snapshots", schema=None) as batch_op:
        batch_op.drop_index("ix_queue_snapshots_parque")
        batch_op.drop_index("ix_queue_snapshots_historico")

    op.drop_table("queue_snapshots")

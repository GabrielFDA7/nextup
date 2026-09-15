"""O desenho das tabelas — e só isso.

Separado do repositório de propósito: aqui mora a *forma* dos dados, lá mora o
*acesso* a eles. É também o arquivo que o Alembic lê para descobrir o que mudou e
gerar a migração.

Usamos o SQLAlchemy Core (`Table`) em vez do ORM declarativo. O motivo é a
arquitetura do projeto: o idioma comum já são os modelos Pydantic de `models/`.
Um segundo conjunto de classes de domínio, agora com comportamento de ORM, criaria
duas verdades sobre o que é um snapshot — e um caminho tentador para o `core/`
receber objetos que sabem falar com o banco.
"""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

#: Convenção de nomes para índices e restrições.
#: Sem ela, cada banco inventa o nome que quiser e o Alembic não consegue gerar um
#: `downgrade` que funcione — ele não sabe o nome do que precisa remover. Definir a
#: convenção antes da primeira migração evita reescrever o histórico depois.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


queue_snapshots = Table(
    "queue_snapshots",
    metadata,
    # `BIGINT` porque a tabela cresce para sempre e um `INT` de 32 bits tem fim.
    # A variante para SQLite não é capricho: ele só gera ID automático quando a
    # coluna é declarada exatamente `INTEGER PRIMARY KEY` — com `BIGINT` a chave
    # sai nula e a inserção falha. No SQLite todo inteiro já é de 64 bits, então a
    # troca não perde nada.
    Column(
        "id",
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    ),
    Column("park_id", String(64), nullable=False),
    Column("attraction_id", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    # Nulo é dado legítimo: fechada, ou aberta sem fila medida. Ver `QueueSnapshot`.
    Column("wait_time_minutes", Integer, nullable=True),
    # `timezone=True` vira TIMESTAMPTZ no Postgres. O SQLite ignora o fuso, e é por
    # isso que `QueueSnapshot` normaliza tudo para UTC antes de chegar aqui: a
    # garantia não pode depender do banco.
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    # A defesa contra medição duplicada. O coletor roda num ritmo que escolhemos; a
    # fonte atualiza num ritmo que não controlamos. Quando o primeiro é mais rápido
    # que o segundo, a mesma medição chega de novo — e o banco a recusa aqui, em vez
    # de deixá-la enviesar silenciosamente toda média histórica.
    UniqueConstraint("attraction_id", "observed_at", name="uq_queue_snapshots_medicao"),
    # A consulta que a Fase 6 faz o tempo todo: "a fila desta atração nas últimas N
    # horas". Sem índice, o banco varreria a tabela inteira — que só cresce.
    Index("ix_queue_snapshots_historico", "attraction_id", "observed_at"),
    # E a versão do parque inteiro, para gráficos comparativos.
    Index("ix_queue_snapshots_parque", "park_id", "observed_at"),
)

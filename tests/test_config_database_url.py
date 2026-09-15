"""Testes do tratamento da URL do banco.

Esta é a camada que absorve a diferença entre "a string que a plataforma entrega"
e "a string que o nosso driver aceita". Parece detalhe de formatação e não é: uma
URL malformada não falha em teste nenhum, falha **no deploy** — e foi exatamente
assim que a porta fixa quase passou na Fase 5.

Todos os casos abaixo vieram de formatos reais: o `postgres://` do Render e do
Heroku, e o `?sslmode=require&channel_binding=require` que o painel do Neon manda
copiar.
"""

import ssl

import pytest

from nextup.config import normalize_database_url, ssl_is_required
from nextup.storage.engine import connect_args_for

#: A string exatamente como o Neon a apresenta, com a senha trocada.
NEON = (
    "postgresql://usuario:senha@ep-exemplo-pooler.sa-east-1.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)


class TestPrefixoDoDriver:
    def test_postgres_antigo_vira_asyncpg(self):
        """`postgres://` é herança que Render e Heroku ainda entregam."""
        assert normalize_database_url("postgres://u:s@host/db").startswith("postgresql+asyncpg://")

    def test_postgresql_sem_driver_vira_asyncpg(self):
        """Sem o `+asyncpg`, o SQLAlchemy carregaria o driver síncrono e travaria o loop."""
        assert normalize_database_url("postgresql://u:s@host/db").startswith(
            "postgresql+asyncpg://"
        )

    def test_sqlite_vira_aiosqlite(self):
        assert normalize_database_url("sqlite:///./nextup.db") == "sqlite+aiosqlite:///./nextup.db"

    def test_driver_ja_explicito_nao_e_mexido(self):
        """Quem escreveu o driver na mão sabe o que quer; não sobrescrever."""
        url = "postgresql+asyncpg://u:s@host/db"
        assert normalize_database_url(url) == url

    def test_o_resto_da_url_sobrevive(self):
        """Usuário, senha, host, porta e banco têm de atravessar intactos."""
        resultado = normalize_database_url("postgres://u:s3nh@@host:5432/meubanco")
        assert resultado.endswith("@host:5432/meubanco")


class TestParametrosDaLibpq:
    """`sslmode` e `channel_binding` são do cliente C do Postgres, não do asyncpg."""

    def test_remove_sslmode_e_channel_binding(self):
        """Sem isto: `TypeError: connect() got an unexpected keyword argument 'sslmode'`."""
        resultado = normalize_database_url(NEON)

        assert "sslmode" not in resultado
        assert "channel_binding" not in resultado

    def test_a_url_do_neon_fica_utilizavel(self):
        """O objetivo é colar do painel no `.env` sem editar nada."""
        resultado = normalize_database_url(NEON)

        assert resultado == (
            "postgresql+asyncpg://usuario:senha@ep-exemplo-pooler.sa-east-1.aws.neon.tech/neondb"
        )

    def test_preserva_parametros_que_nao_sao_da_libpq(self):
        """Remover a query inteira seria fácil e errado — pode haver opção legítima."""
        resultado = normalize_database_url(
            "postgresql://u:s@host/db?sslmode=require&application_name=nextup"
        )

        assert "application_name=nextup" in resultado
        assert "sslmode" not in resultado

    def test_url_sem_query_string_nao_muda(self):
        assert normalize_database_url("postgresql://u:s@host/db") == (
            "postgresql+asyncpg://u:s@host/db"
        )


class TestIntencaoDeCifrar:
    """A intenção do `sslmode` não pode se perder junto com o parâmetro.

    Este é o teste que impede o pior desfecho possível: a URL pedir conexão
    cifrada, o driver não reconhecer a palavra, e o NextUp conectar em texto plano
    sem ninguém perceber — com a senha do banco viajando aberta.
    """

    def test_sslmode_require_pede_cifra(self):
        assert ssl_is_required(NEON) is True

    @pytest.mark.parametrize("modo", ["require", "verify-full", "verify-ca", "prefer", "allow"])
    def test_qualquer_modo_menos_disable_pede_cifra(self, modo):
        assert ssl_is_required(f"postgresql://u:s@host/db?sslmode={modo}") is True

    def test_disable_nao_pede_cifra(self):
        assert ssl_is_required("postgresql://u:s@host/db?sslmode=disable") is False

    def test_sem_sslmode_nao_pede_cifra(self):
        """Postgres local de desenvolvimento costuma não ter TLS configurado."""
        assert ssl_is_required("postgresql://u:s@localhost/db") is False

    def test_sqlite_nao_pede_cifra(self):
        assert ssl_is_required("sqlite+aiosqlite:///./nextup.db") is False


class TestContextoDeConexao:
    def test_url_do_neon_recebe_contexto_ssl(self):
        argumentos = connect_args_for(NEON)

        assert isinstance(argumentos["ssl"], ssl.SSLContext)

    def test_o_contexto_verifica_certificado_e_hostname(self):
        """O ponto da coisa toda.

        Um contexto sem estas duas ligadas cifraria a conexão e aceitaria qualquer
        um do outro lado — o que protege contra bisbilhotagem passiva, mas não
        contra alguém se passando pelo banco.
        """
        contexto = connect_args_for(NEON)["ssl"]

        assert contexto.verify_mode is ssl.CERT_REQUIRED
        assert contexto.check_hostname is True

    def test_sqlite_nao_recebe_configuracao_de_ssl(self):
        """Passar `ssl` para o aiosqlite seria erro de argumento na conexão."""
        assert connect_args_for("sqlite+aiosqlite:///:memory:") == {}

    def test_sslmode_disable_nao_recebe_contexto(self):
        assert connect_args_for("postgresql://u:s@host/db?sslmode=disable") == {}

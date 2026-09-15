"""Verifica a trava que impede a suíte de falar com o banco de produção.

Desde que o `config.py` passou a ler o `.env`, a URL padrão numa máquina de
desenvolvimento aponta para o Postgres gerenciado. Um teste que criasse um engine
sem URL explícita escreveria — ou apagaria — dados reais, e isso é um estrago que
não avisa antes de acontecer.

O `conftest.py` sobrescreve a URL antes de qualquer `import nextup`. Este arquivo
existe para o dia em que alguém mexer naquele trecho: sem ele, remover a trava não
quebraria teste nenhum, e a proteção sumiria em silêncio.
"""

from nextup.config import DATABASE_URL


def test_a_suite_usa_sqlite_em_memoria():
    """Se isto falhar, a suíte está prestes a conversar com um banco de verdade."""
    assert DATABASE_URL == "sqlite+aiosqlite:///:memory:", (
        f"a URL padrão dos testes é {DATABASE_URL!r}. A trava do conftest.py não "
        "está valendo, e um teste distraído pode escrever no banco de produção."
    )


def test_nao_aponta_para_postgres():
    """Rede de segurança explícita, para o caso de alguém trocar a trava por outra URL."""
    assert "postgres" not in DATABASE_URL.lower()
    assert "neon.tech" not in DATABASE_URL.lower()

"""Fixtures compartilhadas por todos os testes.

O `pytest` carrega este arquivo sozinho: o que estiver aqui fica disponível em
qualquer teste da pasta, sem precisar importar nada.
"""

import os

# ---------------------------------------------------------------------------
# Trava de segurança: nenhum teste fala com o banco de produção.
# ---------------------------------------------------------------------------
# Desde que o `config.py` passou a carregar o `.env`, a URL padrão numa máquina de
# desenvolvimento aponta para o Postgres gerenciado — o mesmo que guarda o
# histórico de verdade. Bastaria um teste criar um engine sem URL explícita para
# escrever, ou apagar, dados reais.
#
# Isto precisa acontecer **antes** de qualquer `import nextup`, porque o
# `config.py` lê o ambiente na importação e congela os valores em constantes. Por
# isso é código solto no topo do arquivo, e não uma fixture: fixture roda tarde
# demais. O `conftest.py` é importado antes dos módulos de teste, o que torna esta
# a primeira coisa a rodar na suíte inteira.
os.environ["NEXTUP_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import httpx
import pytest


@pytest.fixture(scope="session")
def conexao() -> httpx.AsyncClient:
    """Uma conexão HTTP para a suíte inteira.

    Criar um `httpx.AsyncClient` monta um contexto SSL e carrega os certificados
    do sistema, o que custa ~0,7s. Fazer isso uma vez por teste tornaria estes
    arquivos mais lentos que todo o resto do projeto somado.

    Compartilhar é seguro porque o `respx` intercepta antes de qualquer byte sair
    da máquina, e porque o estado que importa — o cache — vive no
    `ThemeParksClient`, que continua sendo criado do zero a cada teste.
    """
    return httpx.AsyncClient()

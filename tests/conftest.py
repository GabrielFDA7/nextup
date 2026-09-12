"""Fixtures compartilhadas por todos os testes.

O `pytest` carrega este arquivo sozinho: o que estiver aqui fica disponível em
qualquer teste da pasta, sem precisar importar nada.
"""

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

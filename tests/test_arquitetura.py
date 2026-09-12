"""Testes da regra de arquitetura.

O `CLAUDE.md` define uma dependência unidirecional:

    api  →  core  →  models  ←  clients

E avisa: *"se você sentir vontade de importar `httpx` dentro de `core/`, o desenho
está errado"*. Uma regra que vive só na documentação é uma regra que se perde na
terceira pressa. Aqui ela vira teste.

O que se protege na prática: enquanto o `core/` não souber o que é rede, os testes
do algoritmo continuam rodando offline, em milissegundos, sem depender de a API
estar no ar nem de o parque estar aberto.
"""

import ast
from pathlib import Path

import pytest

CORE = Path(__file__).parent.parent / "src" / "nextup" / "core"

#: Nem a biblioteca HTTP, nem o cliente que a usa, nem o cache que serve a ela.
PROIBIDOS_NO_CORE = {"httpx", "respx", "asyncio", "nextup.clients"}


def imports_de(arquivo: Path) -> set[str]:
    """Todos os módulos importados por um arquivo, lidos sem executá-lo.

    Usa a árvore sintática (`ast`) em vez de importar de verdade: assim o teste
    não roda o código do projeto para descobrir o que ele importa.
    """
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    encontrados = set()

    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            encontrados.update(alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            encontrados.add(no.module)

    return encontrados


def modulos_do_core() -> list[Path]:
    return sorted(p for p in CORE.glob("*.py") if p.name != "__init__.py")


class TestCoreNaoConheceRede:
    def test_existe_codigo_para_verificar(self):
        """Protege o próprio teste: se a pasta esvaziar, ele não pode passar à toa."""
        assert modulos_do_core()

    @pytest.mark.parametrize("arquivo", modulos_do_core(), ids=lambda p: p.name)
    def test_modulo_do_core_nao_importa_rede(self, arquivo):
        importados = imports_de(arquivo)

        proibidos_usados = {
            proibido
            for proibido in PROIBIDOS_NO_CORE
            for importado in importados
            if importado == proibido or importado.startswith(f"{proibido}.")
        }

        assert not proibidos_usados, (
            f"{arquivo.name} importa {proibidos_usados}. O core é lógica pura: "
            "receba objetos prontos em vez de buscá-los."
        )

    @pytest.mark.parametrize("arquivo", modulos_do_core(), ids=lambda p: p.name)
    def test_core_so_depende_de_models_e_config(self, arquivo):
        """Dentro do projeto, o `core` só pode olhar para `models` e `config`."""
        internos = {i for i in imports_de(arquivo) if i.startswith("nextup")}
        permitidos = {"nextup.config", "nextup.models", "nextup.core"}

        for importado in internos:
            assert any(importado == p or importado.startswith(f"{p}.") for p in permitidos), (
                f"{arquivo.name} importa {importado}, fora do permitido para o core."
            )

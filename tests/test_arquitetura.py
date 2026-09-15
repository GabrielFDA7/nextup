"""Testes da regra de arquitetura.

O `CLAUDE.md` define uma dependência unidirecional:

    api  →  core  →  models  ←  clients

E avisa: *"se você sentir vontade de importar `httpx` dentro de `core/`, o desenho
está errado"*. Uma regra que vive só na documentação é uma regra que se perde na
terceira pressa. Aqui ela vira teste.

O que se protege na prática: enquanto o `core/` não souber o que é rede, os testes
do algoritmo continuam rodando offline, em milissegundos, sem depender de a API
estar no ar nem de o parque estar aberto.

A Fase 6 acrescentou uma segunda tentação, do mesmo formato: o banco. O cálculo de
tendência recebe uma lista de snapshots e não tem por que saber de onde ela veio —
se o `core/` aprender a consultar o Postgres, seus testes passam a precisar de um
banco de pé, e a rapidez que sustenta a suíte inteira acaba. A regra aqui é a mesma,
com outro nome: *se você sentir vontade de importar `sqlalchemy` dentro de `core/`,
o desenho está errado*.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src" / "nextup"
CORE = SRC / "core"
MODELS = SRC / "models"
STORAGE = SRC / "storage"

#: Nem a biblioteca HTTP, nem o cliente que a usa, nem o cache que serve a ela.
#: Nem o banco, nem a camada que fala com ele.
PROIBIDOS_NO_CORE = {
    "httpx",
    "respx",
    "asyncio",
    "nextup.clients",
    "sqlalchemy",
    "alembic",
    "nextup.storage",
}

#: `models/` é o idioma comum — o que atravessa todas as camadas. Se ele souber de
#: SQLAlchemy, o banco vaza para dentro de todo mundo que fala esse idioma, incluindo
#: o `core/`, por tabela.
PROIBIDOS_NOS_MODELS = {"httpx", "sqlalchemy", "alembic", "nextup.clients", "nextup.storage"}


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


def modulos_de(pasta: Path) -> list[Path]:
    """Os módulos de uma camada, ignorando o `__init__.py`, que só reexporta."""
    return sorted(p for p in pasta.glob("*.py") if p.name != "__init__.py")


def modulos_do_core() -> list[Path]:
    return modulos_de(CORE)


def importa_proibido(arquivo: Path, proibidos: set[str]) -> set[str]:
    """Quais itens da lista de proibidos o arquivo importa.

    Compara por prefixo de módulo para que `sqlalchemy` também pegue
    `sqlalchemy.ext.asyncio` — senão a regra seria contornada sem querer, só por
    importar de um submódulo.
    """
    importados = imports_de(arquivo)
    return {
        proibido
        for proibido in proibidos
        for importado in importados
        if importado == proibido or importado.startswith(f"{proibido}.")
    }


class TestCoreNaoConheceRede:
    def test_existe_codigo_para_verificar(self):
        """Protege o próprio teste: se a pasta esvaziar, ele não pode passar à toa."""
        assert modulos_do_core()

    @pytest.mark.parametrize("arquivo", modulos_do_core(), ids=lambda p: p.name)
    def test_modulo_do_core_nao_importa_rede_nem_banco(self, arquivo):
        proibidos_usados = importa_proibido(arquivo, PROIBIDOS_NO_CORE)

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


class TestModelsEOIdiomaComum:
    """`models/` é o que todas as camadas falam, então não pode conhecer nenhuma.

    A consequência prática de quebrar isto é sutil: bastaria `models/` importar
    SQLAlchemy para que o `core/` passasse a depender do banco de forma indireta,
    sem nenhum `import sqlalchemy` visível no arquivo do algoritmo.
    """

    def test_existe_codigo_para_verificar(self):
        assert modulos_de(MODELS)

    @pytest.mark.parametrize("arquivo", modulos_de(MODELS), ids=lambda p: p.name)
    def test_modelo_nao_conhece_rede_nem_banco(self, arquivo):
        proibidos_usados = importa_proibido(arquivo, PROIBIDOS_NOS_MODELS)

        assert not proibidos_usados, (
            f"{arquivo.name} importa {proibidos_usados}. models/ é só o idioma comum: "
            "o mapeamento para tabela mora em storage/."
        )


class TestStorageFicaNaPeriferia:
    """`storage/` pode falar com o banco — mas só olha para `models/` e `config`.

    É a mesma regra que vale para `clients/`. A diferença entre as duas pastas é a
    origem do dado: `clients/` busca o que é de fora, `storage/` guarda o que é
    nosso. Nenhuma das duas pode chamar a camada de cima.
    """

    def test_existe_codigo_para_verificar(self):
        assert modulos_de(STORAGE)

    @pytest.mark.parametrize("arquivo", modulos_de(STORAGE), ids=lambda p: p.name)
    def test_storage_nao_sobe_na_arquitetura(self, arquivo):
        internos = {i for i in imports_de(arquivo) if i.startswith("nextup")}
        permitidos = {"nextup.config", "nextup.models", "nextup.storage"}

        for importado in internos:
            assert any(importado == p or importado.startswith(f"{p}.") for p in permitidos), (
                f"{arquivo.name} importa {importado}, fora do permitido para o storage. "
                "A dependência aponta para models/, nunca para core/ ou api/."
            )

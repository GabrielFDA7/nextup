"""Linha de comando do NextUp — a entrega da Fase 1.

Mostra as filas de um parque, ordenadas da menor para a maior. Ainda **não** é a
recomendação do projeto: aqui falta a distância, que é justamente o diferencial
do NextUp e chega na Fase 2. Por enquanto isto responde "onde estão as menores
filas", não "para onde eu devo ir".

Serve como prova de que a Fase 1 funciona de ponta a ponta: requisição real,
cache, validação e dado na tela.
"""

import argparse
import asyncio
import sys

from nextup.clients.errors import ThemeParksError
from nextup.clients.themeparks import ThemeParksClient
from nextup.config import DEFAULT_PARK_ID, DEFAULT_RESULT_LIMIT
from nextup.models import LiveData, ParkCatalog, ParkEntity


def _montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nextup",
        description="Mostra as filas de um parque temático, da menor para a maior.",
    )
    parser.add_argument(
        "--park",
        default=DEFAULT_PARK_ID,
        metavar="ID",
        help="ID do parque (padrão: Magic Kingdom).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_RESULT_LIMIT,
        metavar="N",
        help=f"Quantas atrações mostrar (padrão: {DEFAULT_RESULT_LIMIT}). Use 0 para todas.",
    )
    parser.add_argument(
        "--parks",
        action="store_true",
        help="Lista os parques disponíveis com seus IDs, em vez das filas.",
    )
    return parser


async def _listar_parques(cliente: ThemeParksClient) -> None:
    destinos = await cliente.get_destinations()

    for destino in sorted(destinos.destinations, key=lambda d: d.name):
        print(f"\n{destino.name}")
        for parque in destino.parks:
            print(f"  {parque.id}  {parque.name}")


def _juntar(
    catalogo: ParkCatalog, ao_vivo: dict[str, LiveData]
) -> list[tuple[ParkEntity, LiveData]]:
    """Cruza catálogo e dados ao vivo, ficando só com o que dá para mostrar.

    O catálogo diz o que é atração; o live diz qual é a fila agora. Nenhum dos
    dois sozinho basta — e é esse mesmo cruzamento que a Fase 2 vai usar, só que
    aproveitando também a coordenada que o catálogo traz.
    """
    pares = []
    for atracao in catalogo.attractions():
        estado = ao_vivo.get(atracao.id)
        if estado is not None and estado.is_rankable:
            pares.append((atracao, estado))

    return sorted(pares, key=lambda par: par[1].wait_time_minutes or 0)


def _imprimir_filas(
    catalogo: ParkCatalog, pares: list[tuple[ParkEntity, LiveData]], limite: int
) -> None:
    total_atracoes = len(catalogo.attractions())

    print(f"\n{catalogo.name} — filas agora")
    print(f"{len(pares)} de {total_atracoes} atrações com fila informada\n")

    if not pares:
        print("Nenhuma atração com fila informada no momento.")
        print("O parque pode estar fechado.")
        return

    mostrados = pares if limite <= 0 else pares[:limite]

    for posicao, (atracao, estado) in enumerate(mostrados, start=1):
        print(f"{posicao:>3}. {estado.wait_time_minutes:>3} min   {atracao.name}")

    if len(mostrados) < len(pares):
        print(f"\n... e mais {len(pares) - len(mostrados)}. Use --limit 0 para ver todas.")

    momento = pares[0][1].last_updated.astimezone()
    print(f"\nDado da API de {momento:%d/%m/%Y %H:%M} (horário local).")


async def _executar(args: argparse.Namespace) -> int:
    async with ThemeParksClient() as cliente:
        if args.parks:
            await _listar_parques(cliente)
            return 0

        # As duas respostas não dependem uma da outra, então são pedidas ao mesmo
        # tempo: o tempo total passa a ser o da mais lenta, em vez da soma das duas.
        catalogo, ao_vivo = await asyncio.gather(
            cliente.get_park_catalog(args.park),
            cliente.get_live_data(args.park),
        )

    _imprimir_filas(catalogo, _juntar(catalogo, ao_vivo.by_id()), args.limit)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada do comando `nextup`.

    Devolve o código de saída: 0 deu certo, 1 deu errado. É como um programa de
    terminal avisa o resultado para quem o chamou — um script ou o próprio CI.
    """
    args = _montar_parser().parse_args(argv)

    try:
        return asyncio.run(_executar(args))
    except ThemeParksError as erro:
        # O usuário do terminal não tem nada a ver com detalhe de HTTP: mensagem
        # clara na saída de erro, e código 1 para quem estiver automatizando.
        print(f"Erro ao consultar a API: {erro}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelado.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

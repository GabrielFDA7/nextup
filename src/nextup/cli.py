"""Linha de comando do NextUp.

Tem dois modos, e a diferença entre eles é o projeto inteiro:

    nextup                              → "onde estão as menores filas"
    nextup --lat 28.42 --lon -81.58     → "para onde eu devo ir agora"

O primeiro ordena por fila e é útil para dar uma olhada geral. O segundo é o que
o NextUp promete: ranqueia por `custo_total = caminhada + fila`, porque a menor
fila pode estar do outro lado do parque.

A regra de negócio não mora aqui. Este módulo lê argumentos, chama o `core` e
formata o resultado — quem decide a ordem é `core/recommender.py`.
"""

import argparse
import asyncio
import sys

from pydantic import ValidationError

from nextup.clients.errors import ThemeParksError
from nextup.clients.themeparks import ThemeParksClient
from nextup.config import DEFAULT_PARK_ID, DEFAULT_RESULT_LIMIT
from nextup.core.recommender import Recommendation, recommend
from nextup.models import LiveData, LiveDataResponse, Location, ParkCatalog, ParkEntity


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
    parser.add_argument(
        "--lat",
        type=float,
        metavar="GRAUS",
        help="Sua latitude. Com --lon, ranqueia por caminhada + fila.",
    )
    parser.add_argument(
        "--lon",
        type=float,
        metavar="GRAUS",
        help="Sua longitude. Precisa vir junto com --lat.",
    )
    return parser


def _posicao_do_visitante(args: argparse.Namespace) -> Location | None:
    """Lê a posição dos argumentos, exigindo as duas coordenadas juntas.

    Uma latitude sem longitude não localiza ninguém: é erro de uso, e avisar
    disso é melhor que ignorar em silêncio o que a pessoa quis fazer.
    """
    if (args.lat is None) != (args.lon is None):
        raise ValueError("--lat e --lon precisam ser usados juntos.")

    if args.lat is None:
        return None

    try:
        return Location(latitude=args.lat, longitude=args.lon)
    except ValidationError as erro:
        raise ValueError(f"Coordenada inválida: {erro}") from erro


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
    print("Dica: passe --lat e --lon para ranquear por caminhada + fila.")


def _imprimir_recomendacoes(
    catalogo: ParkCatalog,
    ao_vivo: LiveDataResponse,
    recomendacoes: list[Recommendation],
    limite: int,
) -> None:
    """Imprime o ranking.

    Recebe a lista **inteira** e corta aqui, para que a contagem exibida seja a
    de atrações realmente disponíveis, e não a do limite pedido.
    """
    total_atracoes = len(catalogo.attractions())

    print(f"\n{catalogo.name} — para onde ir agora")
    print(f"{len(recomendacoes)} de {total_atracoes} atrações disponíveis\n")

    if not recomendacoes:
        print("Nenhuma atração disponível no momento.")
        print("O parque pode estar fechado.")
        return

    mostradas = recomendacoes if limite <= 0 else recomendacoes[:limite]

    for posicao, recomendacao in enumerate(mostradas, start=1):
        print(f"{posicao:>3}. {recomendacao.explain()}")

    if len(mostradas) < len(recomendacoes):
        print(f"\n... e mais {len(recomendacoes) - len(mostradas)}. Use --limit 0 para ver todas.")

    # A comparação com a menor fila é o argumento do projeto, e só vale a pena
    # mostrar quando a resposta certa não é a óbvia.
    melhor = recomendacoes[0]
    menor_fila = min(recomendacoes, key=lambda r: r.queue_minutes)
    if menor_fila is not melhor and menor_fila.total_minutes > melhor.total_minutes:
        print(
            f"\nA menor fila é a de {menor_fila.attraction.name} "
            f"({menor_fila.queue_minutes} min), mas chegar lá custa "
            f"{round(menor_fila.total_minutes)} min no total — "
            f"{round(menor_fila.total_minutes - melhor.total_minutes)} a mais."
        )

    momento = ao_vivo.live_data[0].last_updated.astimezone()
    print(f"\nDado da API de {momento:%d/%m/%Y %H:%M} (horário local).")


async def _executar(args: argparse.Namespace, visitante: Location | None) -> int:
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

    if visitante is None:
        _imprimir_filas(catalogo, _juntar(catalogo, ao_vivo.by_id()), args.limit)
        return 0

    _imprimir_recomendacoes(
        catalogo,
        ao_vivo,
        # Pede todas: quem corta é a impressão, para a contagem ficar honesta.
        recommend(catalog=catalogo, live=ao_vivo, visitor=visitante, limit=0),
        args.limit,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada do comando `nextup`.

    Devolve o código de saída: 0 deu certo, 1 deu errado. É como um programa de
    terminal avisa o resultado para quem o chamou — um script ou o próprio CI.
    """
    args = _montar_parser().parse_args(argv)

    try:
        visitante = _posicao_do_visitante(args)
    except ValueError as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 2

    try:
        return asyncio.run(_executar(args, visitante))
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

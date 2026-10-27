"""Cálculos geográficos: distância entre dois pontos e tempo de caminhada.

Este módulo é o exemplo mais puro do que a camada `core` deve ser: entra número,
sai número. Ele não sabe o que é HTTP, não sabe o que é a ThemeParks.wiki e não
importa nada além da biblioteca padrão do Python.

Isso tem uma consequência prática importante: os testes daqui rodam offline, em
milissegundos, e nunca falham porque a internet caiu ou o parque fechou.
"""

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from nextup.config import PATH_WINDING_FACTOR, WALKING_SPEED_MPS

#: Raio médio da Terra em metros, usado pela fórmula de Haversine.
EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class BoundingBox:
    """O retângulo que contém todos os pontos dados.

    Serve para enquadrar um parque no mapa. Enquadrar é melhor que centralizar:
    centralizar exige adivinhar o zoom, e o zoom certo para o Magic Kingdom é o
    errado para um parque três vezes maior. Com os quatro cantos, quem desenha o
    mapa calcula o zoom sozinho.
    """

    south: float
    west: float
    north: float
    east: float

    @property
    def center(self) -> tuple[float, float]:
        """O meio do retângulo, como (latitude, longitude)."""
        return ((self.south + self.north) / 2, (self.west + self.east) / 2)


def bounding_box(points: Iterable[tuple[float, float]]) -> BoundingBox | None:
    """O retângulo que contém todos os pontos.

    Args:
        points: Pares (latitude, longitude).

    Returns:
        O retângulo, ou `None` se não houver ponto nenhum — caso legítimo para um
        parque cujo catálogo veio sem coordenadas. Devolver `None` obriga quem
        chama a decidir o que fazer, em vez de receber um retângulo no meio do
        oceano, que é onde ficaria um "zero, zero" tratado como dado válido.

    Note:
        Não trata a travessia do antimeridiano (longitude ±180). Um parque
        temático tem menos de dois quilômetros de ponta a ponta, e nenhum deles
        fica sobre essa linha — mas se algum dia o NextUp enquadrar algo maior que
        um parque, isto precisa de atenção.
    """
    latitudes = []
    longitudes = []

    for latitude, longitude in points:
        latitudes.append(latitude)
        longitudes.append(longitude)

    if not latitudes:
        return None

    return BoundingBox(
        south=min(latitudes),
        west=min(longitudes),
        north=max(latitudes),
        east=max(longitudes),
    )


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em linha reta entre dois pontos GPS, em metros.

    A Terra é curva, então não dá para usar Pitágoras direto em latitude e
    longitude: um grau de longitude vale ~111 km na linha do Equador e quase
    nada perto dos polos. A fórmula de Haversine resolve isso medindo a distância
    ao longo da superfície da esfera.

    Numa escala de parque temático (menos de 2 km), o erro de tratar a Terra como
    esfera perfeita em vez de elipsoide fica na casa dos centímetros — irrelevante
    para quem só quer saber se vale a pena andar até lá.

    Args:
        lat1: Latitude do primeiro ponto, em graus.
        lon1: Longitude do primeiro ponto, em graus.
        lat2: Latitude do segundo ponto, em graus.
        lon2: Longitude do segundo ponto, em graus.

    Returns:
        Distância em metros, sempre positiva.
    """
    # Trigonometria em Python trabalha em radianos, não em graus.
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    # atan2 é usado no lugar de asin por ser numericamente estável mesmo quando
    # os dois pontos são quase o mesmo — caso comum aqui, já que atrações vizinhas
    # ficam a poucos metros uma da outra.
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_M * c


def walking_distance_m(
    straight_line_m: float,
    winding_factor: float = PATH_WINDING_FACTOR,
) -> float:
    """Converte distância em linha reta na distância realmente caminhada.

    Haversine mede o voo do pássaro. O visitante não voa: ele contorna o lago,
    dá a volta no castelo e segue a trilha, que faz curva. O fator de sinuosidade
    aproxima essa diferença.

    Args:
        straight_line_m: Distância em linha reta, em metros.
        winding_factor: Multiplicador do trajeto real sobre a linha reta.

    Returns:
        Distância estimada de caminhada, em metros.
    """
    return straight_line_m * winding_factor


def walking_time_minutes(
    distance_m: float,
    speed_mps: float = WALKING_SPEED_MPS,
) -> float:
    """Tempo estimado para caminhar uma distância, em minutos.

    Args:
        distance_m: Distância a percorrer, em metros.
        speed_mps: Velocidade de caminhada, em metros por segundo.

    Returns:
        Tempo em minutos.

    Raises:
        ValueError: Se a velocidade não for positiva (evita divisão por zero e
            resultados negativos sem sentido).
    """
    if speed_mps <= 0:
        raise ValueError(f"Velocidade de caminhada deve ser positiva, recebido: {speed_mps}")

    return (distance_m / speed_mps) / 60


def travel_time_minutes(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    speed_mps: float = WALKING_SPEED_MPS,
    winding_factor: float = PATH_WINDING_FACTOR,
) -> float:
    """Tempo estimado de caminhada entre dois pontos GPS, em minutos.

    É a função que o resto do projeto realmente usa: junta os três passos —
    distância em linha reta, correção do trajeto e conversão em tempo — numa
    chamada só.

    Args:
        lat1: Latitude de origem, em graus.
        lon1: Longitude de origem, em graus.
        lat2: Latitude de destino, em graus.
        lon2: Longitude de destino, em graus.
        speed_mps: Velocidade de caminhada, em metros por segundo.
        winding_factor: Multiplicador do trajeto real sobre a linha reta.

    Returns:
        Tempo estimado de caminhada, em minutos.
    """
    straight = haversine_distance_m(lat1, lon1, lat2, lon2)
    walked = walking_distance_m(straight, winding_factor)
    return walking_time_minutes(walked, speed_mps)


def travel_time_matrix(
    points: Mapping[str, tuple[float, float]],
    speed_mps: float = WALKING_SPEED_MPS,
    winding_factor: float = PATH_WINDING_FACTOR,
) -> dict[str, dict[str, float]]:
    """Tempo de caminhada entre todos os pares de pontos, em minutos.

    O ranking só precisa de *visitante → atração*. O roteiro (Fase 8) precisa de
    *atração → atração*: para escolher a segunda parada, é preciso saber quanto se
    anda saindo da primeira. O otimizador consulta esses tempos centenas de milhares
    de vezes ao comparar sequências, e eles não mudam — as atrações não saem do
    lugar. Por isso a conta é feita uma vez, aqui, e depois só se lê.

    Args:
        points: Identificador → (latitude, longitude). Quem chama decide o que é um
            ponto; atração sem coordenada simplesmente não entra.
        speed_mps: Velocidade de caminhada, em metros por segundo.
        winding_factor: Multiplicador do trajeto real sobre a linha reta.

    Returns:
        `matriz[a][b]` é o tempo de `a` até `b`. Simétrica, com zero na diagonal.
        Um identificador desconhecido levanta `KeyError` — melhor que um tempo
        inventado, que o otimizador usaria sem desconfiar.
    """
    ids = list(points)
    matriz: dict[str, dict[str, float]] = {a: {a: 0.0} for a in ids}

    # Só metade da conta: a caminhada de A até B é a mesma de B até A. Num parque
    # há subidas e filas de travessia que quebrariam isso, mas a estimativa por
    # linha reta não as enxerga de qualquer forma.
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            minutos = travel_time_minutes(
                *points[a], *points[b], speed_mps=speed_mps, winding_factor=winding_factor
            )
            matriz[a][b] = minutos
            matriz[b][a] = minutos

    return matriz

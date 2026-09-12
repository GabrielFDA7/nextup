"""Cálculos geográficos: distância entre dois pontos e tempo de caminhada.

Este módulo é o exemplo mais puro do que a camada `core` deve ser: entra número,
sai número. Ele não sabe o que é HTTP, não sabe o que é a ThemeParks.wiki e não
importa nada além da biblioteca padrão do Python.

Isso tem uma consequência prática importante: os testes daqui rodam offline, em
milissegundos, e nunca falham porque a internet caiu ou o parque fechou.
"""

import math

from nextup.config import PATH_WINDING_FACTOR, WALKING_SPEED_MPS

#: Raio médio da Terra em metros, usado pela fórmula de Haversine.
EARTH_RADIUS_M = 6_371_000.0


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

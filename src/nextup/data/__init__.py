"""Dados curados à mão — o terceiro tipo de dado do NextUp.

`clients/` busca dado **de fora**, que muda sem aviso (a ThemeParks.wiki). `storage/`
guarda dado **acumulado** por nós (o histórico). Esta pasta guarda dado **conferido**
por gente, que muda raramente e só quando alguém decide: a curadoria de altura e
intensidade de cada atração.

Os arquivos vão empacotados com o código, e não num banco, porque mudam por revisão,
não por coleta: cada alteração é um commit, com autor e data, e passa pelos testes.
"""

import json
from functools import cache
from importlib import resources

from nextup.models.curation import ParkCuration

#: Parque -> arquivo de curadoria. Parque sem entrada aqui não tem curadoria, e a API
#: devolve altura e intensidade nulas: o recurso fica desligado, não quebrado.
_ARQUIVOS = {
    "75ea578a-adc8-4116-a54d-dccb60765ef9": "curadoria_magic_kingdom.json",
}


@cache
def load_curation(park_id: str) -> ParkCuration | None:
    """A curadoria de um parque, ou `None` se ele ainda não tem uma.

    Lida uma vez por processo: o arquivo só muda com um novo deploy.
    """
    nome = _ARQUIVOS.get(park_id)
    if nome is None:
        return None

    texto = resources.files(__name__).joinpath(nome).read_text(encoding="utf-8")
    return ParkCuration.model_validate(json.loads(texto))

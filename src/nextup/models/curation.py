"""Curadoria — o que a fonte não informa e nós conferimos à mão.

A ThemeParks.wiki diz onde cada atração fica e qual é a fila, mas não diz **quem pode
entrar** nem **quão intensa ela é**. As duas coisas definem se uma atração serve para
um grupo — a criança de 90 cm não entra na TRON, por mais curta que esteja a fila.

O arquivo é preenchido por gente, conferindo o site oficial da Disney, e por isso as
chaves do JSON estão em português: quem o edita é o curador, não o código. Os aliases
traduzem para o idioma do projeto.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class CuratedAttraction(BaseModel):
    """Uma atração conferida (ou ainda não) na fonte oficial."""

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    id: str
    name: str = Field(alias="nome")

    #: `None` é "sem exigência" **numa linha conferida**, e "não sei" numa que não
    #: foi. É por isso que a linha não conferida nunca é usada — ver `is_verified`.
    min_height_cm: int | None = Field(default=None, alias="altura_minima_cm")

    #: As etiquetas da Disney como aparecem no site ("Thrill Rides", "Big Drops"...).
    #: Guardar as originais, e não a classificação, mantém a regra de intensidade
    #: num lugar só: mudar a regra não exige recurar o parque.
    disney_tags: tuple[str, ...] = Field(default=(), alias="etiquetas_disney")

    checked_on: date | None = Field(default=None, alias="conferido_em")
    checked_by: str | None = Field(default=None, alias="conferido_por")

    @property
    def is_verified(self) -> bool:
        """Só o que alguém viu na fonte oficial pode chegar ao visitante.

        Uma altura errada manda uma criança para uma fila em que ela não pode
        entrar — pior que não dizer nada. Rascunho não conta.
        """
        return self.checked_on is not None and bool(self.checked_by)


class ParkCuration(BaseModel):
    """A curadoria de um parque."""

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    park_name: str = Field(alias="parque")
    park_id: str = Field(alias="parque_id")
    source: str = Field(alias="fonte")
    attractions: tuple[CuratedAttraction, ...] = Field(alias="atracoes")

    def verified(self) -> dict[str, CuratedAttraction]:
        """Por id, **só as conferidas**. As demais ficam de fora, como desconhecidas."""
        return {a.id: a for a in self.attractions if a.is_verified}

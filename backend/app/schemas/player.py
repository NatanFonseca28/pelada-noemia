from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, Field, model_validator

from app.domain.phone import normalize_phone

from app.models.enums import PlayerType, Position
from app.schemas.common import ORMModel


# Telefone em E.164; aceita formatos comuns de digitação e vazio (= sem telefone)
Phone = Annotated[str | None, Field(default=None, max_length=30), AfterValidator(normalize_phone)]


def _validate_positions(primary: Position | None, secondary: Position | None) -> None:
    if secondary is None:
        return
    if secondary == Position.GOLEIRO_FIXO:
        raise ValueError("Goleiro fixo não pode ser posição secundária")
    if primary == Position.GOLEIRO_FIXO:
        raise ValueError("Goleiro fixo joga apenas no gol e não tem posição secundária")
    if primary == secondary:
        raise ValueError("A posição secundária deve ser diferente da principal")


class PlayerBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    nickname: str | None = Field(default=None, max_length=60)
    type: PlayerType
    primary_position: Position
    secondary_position: Position | None = None
    skill_level: int | None = Field(default=None, ge=1, le=5)
    active: bool = True
    # Contato — só ADMIN vê e edita (ver routers/players.py:_visible)
    phone: Phone = None
    whatsapp_opt_in: bool = False


class PlayerCreate(PlayerBase):
    @model_validator(mode="after")
    def check_positions(self) -> Self:
        _validate_positions(self.primary_position, self.secondary_position)
        return self


class PlayerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    nickname: str | None = Field(default=None, max_length=60)
    type: PlayerType | None = None
    primary_position: Position | None = None
    secondary_position: Position | None = None
    skill_level: int | None = Field(default=None, ge=1, le=5)
    active: bool | None = None
    phone: Phone = None
    whatsapp_opt_in: bool | None = None


class PlayerOut(ORMModel, PlayerBase):
    id: int
    primary_position: Position | None  # None = "a definir" (jogador importado)
    photo_url: str | None = None
    display_name: str

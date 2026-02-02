"""Modelos de datos para el visor de Alembic."""

from dataclasses import dataclass


@dataclass
class Migration:
    """Representa una migración de Alembic."""

    revision: str
    down_revision: str | tuple[str, ...] | None
    message: str
    filename: str
    create_date: str = ""
    is_merge: bool = False


@dataclass
class NodePosition:
    """Posición de un nodo en el canvas."""

    x: float = 0
    y: float = 0
    level: int = 0
    column: int = 0

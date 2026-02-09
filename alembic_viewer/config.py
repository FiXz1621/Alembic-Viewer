"""Configuración y gestión de colores para el visor de Alembic."""

import json
from pathlib import Path

# Archivo de configuración
CONFIG_FILE = Path.home() / ".alembic_viewer_config.json"

# Colores por defecto
DEFAULT_COLORS = {
    "node_normal": "#4a90d9",  # Azul - nodos normales
    "node_head": "#9b59b6",  # Púrpura - HEAD (sin hijos)
    "node_root": "#f1c40f",  # Amarillo - ROOT (sin padres)
    "node_merge": "#e67e22",  # Naranja - merge (múltiples padres)
    "node_selected": "#2ecc71",  # Verde - nodo seleccionado
    "edge_normal": "#7f8c8d",  # Gris - aristas normales
    "edge_merge": "#e67e22",  # Naranja - aristas hacia merge
    "edge_parent": "#27ae60",  # Verde oscuro - aristas hacia padres
    "edge_child": "#58d68d",  # Verde claro - aristas hacia hijos
    "node_parent_border": "#27ae60",  # Verde oscuro - borde de nodos padre
    "node_child_border": "#58d68d",  # Verde claro - borde de nodos hijo
    "text": "#2c3e50",
    "background": "#ecf0f1",
}

# Nombres descriptivos para la UI
COLOR_LABELS = {
    "node_normal": "Nodo Normal",
    "node_head": "Nodo HEAD (sin hijos)",
    "node_root": "Nodo ROOT (sin padres)",
    "node_merge": "Nodo MERGE",
    "node_selected": "Nodo Seleccionado",
    "edge_normal": "Arista Normal",
    "edge_merge": "Arista Merge",
    "edge_parent": "Arista a Padre",
    "edge_child": "Arista a Hijo",
    "node_parent_border": "Borde Nodo Padre",
    "node_child_border": "Borde Nodo Hijo",
    "text": "Texto",
    "background": "Fondo",
}


def load_config() -> dict:
    """Carga la configuración desde el archivo."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def is_first_run() -> bool:
    """Detecta si es la primera ejecución (no existe archivo de configuración)."""
    return not CONFIG_FILE.exists()


def save_config(config: dict):
    """Guarda la configuración en el archivo."""
    try:
        CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
    except OSError as e:
        print(f"Error guardando configuración: {e}")


def get_colors(config: dict) -> dict:
    """Obtiene los colores de la configuración o usa los valores por defecto."""
    saved_colors = config.get("colors", {})
    colors = DEFAULT_COLORS.copy()
    colors.update(saved_colors)
    return colors


def get_alembic_paths(config: dict) -> list[dict]:
    """Obtiene la lista de rutas de alembic configuradas.
    
    Retorna una lista de diccionarios con 'path' y 'alias'.
    Soporta formatos antiguos para compatibilidad hacia atrás.
    """
    # Formato nuevo: lista de dicts con path y alias
    if "alembic_paths" in config:
        paths = config["alembic_paths"]
        # Normalizar: si es lista de strings, convertir a dicts
        result = []
        for item in paths:
            if isinstance(item, str):
                result.append({"path": item, "alias": ""})
            elif isinstance(item, dict):
                result.append({"path": item.get("path", ""), "alias": item.get("alias", "")})
        return result
    
    # Formato antiguo: un solo path (migrar automáticamente)
    if "alembic_path" in config:
        return [{"path": config["alembic_path"], "alias": ""}]
    
    return []


def set_alembic_paths(config: dict, paths: list[dict]):
    """Establece la lista de rutas de alembic con sus alias.
    
    Cada elemento debe ser un dict con 'path' y opcionalmente 'alias'.
    También elimina el formato antiguo si existe.
    """
    config["alembic_paths"] = paths
    # Eliminar formato antiguo si existe
    config.pop("alembic_path", None)

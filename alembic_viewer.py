#!/usr/bin/env python3
"""
Alembic Migration Graph Viewer
Aplicación de escritorio para visualizar el grafo de migraciones de Alembic.

Uso:
    python alembic_viewer.py [--path /ruta/al/proyecto]

Si no se especifica --path, usa la ubicación del script o la configuración guardada.
"""

from alembic_viewer.__main__ import main

if __name__ == "__main__":
    main()

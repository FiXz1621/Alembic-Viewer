#!/usr/bin/env python3
"""
Alembic Migration Graph Viewer
Aplicación de escritorio para visualizar el grafo de migraciones de Alembic.

Uso:
    python -m alembic_viewer [--path /ruta/al/proyecto]

Si no se especifica --path, usa la ubicación del script o la configuración guardada.
"""

import argparse
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from alembic_viewer.app import AlembicViewerApp


def main():
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Visualizador de grafo de migraciones de Alembic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    python -m alembic_viewer
    python -m alembic_viewer --path /ruta/al/proyecto/alembic
    python -m alembic_viewer -p ./mi_proyecto/alembic
        """,
    )
    parser.add_argument("-p", "--path", type=str, help="Ruta a la carpeta 'alembic' del proyecto")
    args = parser.parse_args()

    alembic_path = Path(args.path) if args.path else None

    root = tk.Tk()

    # Configurar icono de la aplicación
    icon_path = Path(__file__).parent.parent / "alembic_viewer.ico"
    if icon_path.exists():
        try:
            root.iconbitmap(str(icon_path))
        except tk.TclError:
            pass

    # Configurar estilo
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Error.TEntry", fieldbackground="#ffcccc")

    AlembicViewerApp(root, alembic_path)

    # Forzar focus en la ventana (especialmente importante en macOS)
    root.lift()
    root.attributes("-topmost", True)
    root.after(100, lambda: root.attributes("-topmost", False))
    root.focus_force()

    root.mainloop()


if __name__ == "__main__":
    main()

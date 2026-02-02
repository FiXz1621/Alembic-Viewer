#!/usr/bin/env python3
"""
Alembic Migration Graph Viewer
Aplicación de escritorio para visualizar el grafo de migraciones de Alembic.

Uso:
    python alembic_viewer.py [--path /ruta/al/proyecto]
    
Si no se especifica --path, usa la ubicación del script o la configuración guardada.
"""

import argparse
import json
import os
import re
import subprocess
import platform
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import math
from datetime import date

# Intentar importar tkcalendar para selector de fechas
try:
    from tkcalendar import Calendar
    HAS_TKCALENDAR = True
except ImportError:
    HAS_TKCALENDAR = False


# Archivo de configuración
CONFIG_FILE = Path.home() / ".alembic_viewer_config.json"


def load_config() -> dict:
    """Carga la configuración desde el archivo."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_config(config: dict):
    """Guarda la configuración en el archivo."""
    try:
        CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
    except IOError as e:
        print(f"Error guardando configuración: {e}")


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


def parse_migration_file(filepath: Path) -> Migration | None:
    """Parsea un archivo de migración y extrae la información relevante."""
    try:
        content = filepath.read_text(encoding="utf-8")
        
        # Extraer revision
        rev_match = re.search(r"^revision:\s*str\s*=\s*['\"]([^'\"]+)['\"]", content, re.MULTILINE)
        if not rev_match:
            rev_match = re.search(r"^revision\s*=\s*['\"]([^'\"]+)['\"]", content, re.MULTILINE)
        
        # Extraer down_revision
        down_match = re.search(
            r"^down_revision:\s*(?:Union\[str,\s*None\]\s*=|str\s*=|=)\s*(.+?)$", 
            content, 
            re.MULTILINE
        )
        if not down_match:
            down_match = re.search(r"^down_revision\s*=\s*(.+?)$", content, re.MULTILINE)
        
        # Extraer mensaje (docstring)
        msg_match = re.search(r'^"""(.+?)"""', content, re.DOTALL)
        
        # Extraer fecha de creación
        date_match = re.search(r"Create Date:\s*(.+?)$", content, re.MULTILINE)
        
        if not rev_match:
            return None
        
        revision = rev_match.group(1)
        
        # Parsear down_revision
        down_revision: str | tuple[str, ...] | None = None
        if down_match:
            down_str = down_match.group(1).strip()
            if down_str == "None":
                down_revision = None
            elif down_str.startswith("("):
                # Es una tupla (merge)
                revs = re.findall(r"['\"]([^'\"]+)['\"]", down_str)
                down_revision = tuple(revs) if revs else None
            else:
                rev = re.search(r"['\"]([^'\"]+)['\"]", down_str)
                down_revision = rev.group(1) if rev else None
        
        message = msg_match.group(1).strip().split("\n")[0] if msg_match else filepath.stem
        create_date = date_match.group(1).strip() if date_match else ""
        is_merge = isinstance(down_revision, tuple) and len(down_revision) > 1
        
        return Migration(
            revision=revision,
            down_revision=down_revision,
            message=message,
            filename=filepath.name,
            create_date=create_date,
            is_merge=is_merge
        )
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None


def load_migrations(versions_path: Path) -> dict[str, Migration]:
    """Carga todas las migraciones de una carpeta."""
    migrations: dict[str, Migration] = {}
    
    if not versions_path.exists():
        return migrations
    
    for filepath in versions_path.glob("*.py"):
        if filepath.name.startswith("__"):
            continue
        migration = parse_migration_file(filepath)
        if migration:
            migrations[migration.revision] = migration
    
    return migrations


def build_graph_structure(migrations: dict[str, Migration]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Construye diccionarios de padres e hijos para cada revisión."""
    children: dict[str, list[str]] = defaultdict(list)
    parents: dict[str, list[str]] = defaultdict(list)
    
    for rev, migration in migrations.items():
        if migration.down_revision is None:
            parents[rev] = []
        elif isinstance(migration.down_revision, tuple):
            for parent in migration.down_revision:
                if parent in migrations:
                    children[parent].append(rev)
                    parents[rev].append(parent)
        else:
            if migration.down_revision in migrations:
                children[migration.down_revision].append(rev)
                parents[rev].append(migration.down_revision)
    
    return dict(children), dict(parents)


def find_heads(migrations: dict[str, Migration], children: dict[str, list[str]]) -> list[str]:
    """Encuentra las cabezas (migraciones sin hijos)."""
    return [rev for rev in migrations if not children.get(rev)]


def find_roots(migrations: dict[str, Migration], parents: dict[str, list[str]]) -> list[str]:
    """Encuentra las raíces (migraciones sin padres)."""
    return [rev for rev in migrations if not parents.get(rev)]


class GraphCanvas(tk.Canvas):
    """Canvas personalizado para dibujar el grafo de migraciones."""
    
    # Colores
    COLOR_NODE_NORMAL = "#4a90d9"      # Azul - nodos normales
    COLOR_NODE_HEAD = "#9b59b6"        # Púrpura - HEAD (sin hijos)
    COLOR_NODE_ROOT = "#f1c40f"        # Amarillo - ROOT (sin padres)
    COLOR_NODE_MERGE = "#e67e22"       # Naranja - merge (múltiples padres)
    COLOR_NODE_SELECTED = "#2ecc71"    # Verde - nodo seleccionado
    COLOR_EDGE = "#7f8c8d"             # Gris - aristas normales
    COLOR_EDGE_MERGE = "#e67e22"       # Naranja - aristas hacia merge
    COLOR_EDGE_PARENT = "#27ae60"      # Verde oscuro - aristas hacia padres
    COLOR_EDGE_CHILD = "#58d68d"       # Verde claro - aristas hacia hijos
    COLOR_NODE_PARENT = "#27ae60"      # Verde oscuro - borde de nodos padre
    COLOR_NODE_CHILD = "#58d68d"       # Verde claro - borde de nodos hijo
    COLOR_TEXT = "#2c3e50"
    COLOR_BG = "#ecf0f1"
    
    # Dimensiones
    NODE_RADIUS = 32
    LEVEL_HEIGHT = 100
    COLUMN_WIDTH = 150
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=self.COLOR_BG, **kwargs)
        
        self.migrations: dict[str, Migration] = {}
        self._graph_children: dict[str, list[str]] = {}
        self._graph_parents: dict[str, list[str]] = {}
        self.positions: dict[str, NodePosition] = {}
        self.node_items: dict[str, int] = {}  # revision -> canvas item id
        self.item_to_rev: dict[int, str] = {}  # canvas item id -> revision (mapeo inverso)
        self.selected_node: str | None = None
        self.on_node_select = None
        self.on_node_double_click = None  # Callback para doble-click
        self.on_node_deselect = None  # Callback para deselección
        
        # Para pan y zoom
        self.scale_factor = 1.0
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._is_dragging = False
        
        # Bindings para click y arrastre
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Double-Button-1>", self._on_double_click)  # Doble-click
        
        # Zoom con scroll
        self.bind("<MouseWheel>", self._on_scroll)  # macOS/Windows
        self.bind("<Button-4>", self._on_scroll)  # Linux scroll up
        self.bind("<Button-5>", self._on_scroll)  # Linux scroll down
        
        # Zoom con pinch en trackpad (macOS)
        self.bind("<Control-MouseWheel>", self._on_scroll)
    
    def set_data(self, migrations: dict[str, Migration], 
                 children: dict[str, list[str]], 
                 parents: dict[str, list[str]]):
        """Establece los datos del grafo."""
        self.migrations = migrations
        self._graph_children = children
        self._graph_parents = parents
        self._calculate_positions()
        self._draw_graph()
        self.reset_view()
    
    def _calculate_positions(self):
        """Calcula las posiciones de los nodos usando un layout por niveles."""
        self.positions.clear()
        
        if not self.migrations:
            return
        
        # Calcular nivel: cada nodo debe estar en un nivel mayor que TODOS sus padres
        # Usamos un algoritmo de ordenamiento topológico
        levels: dict[str, int] = {}
        
        # Inicializar: las raíces están en nivel 0
        roots = find_roots(self.migrations, self._graph_parents)
        for root in roots:
            levels[root] = 0
        
        # Función para calcular el nivel de un nodo recursivamente
        def get_level(rev: str, visited_stack: set[str] | None = None) -> int:
            if visited_stack is None:
                visited_stack = set()
            
            # Detectar ciclos
            if rev in visited_stack:
                return levels.get(rev, 0)
            
            # Si ya está calculado, retornar
            if rev in levels:
                return levels[rev]
            
            visited_stack.add(rev)
            
            # El nivel es max(nivel de padres) + 1
            parent_revs = self._graph_parents.get(rev, [])
            if not parent_revs:
                levels[rev] = 0
            else:
                max_parent_level = -1
                for parent in parent_revs:
                    if parent in self.migrations:
                        parent_level = get_level(parent, visited_stack.copy())
                        max_parent_level = max(max_parent_level, parent_level)
                levels[rev] = max_parent_level + 1
            
            visited_stack.discard(rev)
            return levels[rev]
        
        # Calcular nivel para todos los nodos
        for rev in self.migrations:
            get_level(rev)
        
        # Agrupar por nivel
        level_groups: dict[int, list[str]] = defaultdict(list)
        for rev, level in levels.items():
            level_groups[level].append(rev)
        
        # Ordenar nodos en cada nivel por fecha de creación
        for level, revs in level_groups.items():
            level_groups[level] = sorted(
                revs, 
                key=lambda r: self.migrations[r].create_date if self.migrations[r].create_date else ""
            )
        
        # Asignar posiciones
        max_level = max(levels.values()) if levels else 0
        
        for level, revs in level_groups.items():
            num_nodes = len(revs)
            for col, rev in enumerate(revs):
                self.positions[rev] = NodePosition(
                    x=100 + col * self.COLUMN_WIDTH,
                    y=50 + level * self.LEVEL_HEIGHT,
                    level=level,
                    column=col
                )
    
    def _draw_graph(self):
        """Dibuja el grafo completo."""
        self.delete("all")
        self.node_items.clear()
        self.item_to_rev.clear()
        
        if not self.migrations:
            self.create_text(
                self.winfo_width() // 2, 
                self.winfo_height() // 2,
                text="No hay migraciones para mostrar",
                font=("TkDefaultFont", 14),
                fill=self.COLOR_TEXT
            )
            return
        
        # Calcular bounds para ajustar scroll region
        if self.positions:
            max_x = max(p.x for p in self.positions.values()) + 150
            max_y = max(p.y for p in self.positions.values()) + 100
            self.configure(scrollregion=(0, 0, max_x * self.scale_factor, max_y * self.scale_factor))
        
        # Dibujar aristas primero (para que queden detrás)
        self._draw_edges()
        
        # Dibujar nodos
        self._draw_nodes()
    
    def _draw_edges(self):
        """Dibuja las aristas del grafo."""
        # Obtener nodos relacionados con el seleccionado
        selected_parents = set()
        selected_children = set()
        if self.selected_node:
            selected_parents = set(self._graph_parents.get(self.selected_node, []))
            # Buscar hijos del nodo seleccionado
            for rev, parents in self._graph_parents.items():
                if self.selected_node in parents:
                    selected_children.add(rev)
        
        for rev, migration in self.migrations.items():
            if rev not in self.positions:
                continue
            
            pos = self.positions[rev]
            x1 = pos.x * self.scale_factor
            y1 = pos.y * self.scale_factor
            
            # Dibujar arista hacia cada padre
            parent_revs = self._graph_parents.get(rev, [])
            is_merge = len(parent_revs) > 1
            
            for parent_rev in parent_revs:
                if parent_rev not in self.positions:
                    continue
                
                parent_pos = self.positions[parent_rev]
                x2 = parent_pos.x * self.scale_factor
                y2 = parent_pos.y * self.scale_factor
                
                # Determinar color y grosor de la arista
                # Arista desde selected hacia su padre
                is_to_parent = (rev == self.selected_node and parent_rev in selected_parents)
                # Arista desde hijo hacia selected (selected es el padre)
                is_from_child = (rev in selected_children and parent_rev == self.selected_node)
                
                if is_to_parent:
                    edge_color = self.COLOR_EDGE_PARENT
                    edge_width = 4
                elif is_from_child:
                    edge_color = self.COLOR_EDGE_CHILD
                    edge_width = 4
                elif is_merge:
                    edge_color = self.COLOR_EDGE_MERGE
                    edge_width = 2
                else:
                    edge_color = self.COLOR_EDGE
                    edge_width = 2
                
                # Dibujar línea curva si no están alineados
                if abs(x1 - x2) > 10:
                    # Bezier simplificada con línea quebrada
                    mid_y = (y1 + y2) / 2
                    self.create_line(
                        x1, y1 - self.NODE_RADIUS * self.scale_factor,
                        x1, mid_y,
                        x2, mid_y,
                        x2, y2 + self.NODE_RADIUS * self.scale_factor,
                        fill=edge_color,
                        width=edge_width,
                        smooth=True,
                        arrow=tk.FIRST,
                        arrowshape=(8, 10, 4)
                    )
                else:
                    # Línea recta
                    self.create_line(
                        x1, y1 - self.NODE_RADIUS * self.scale_factor,
                        x2, y2 + self.NODE_RADIUS * self.scale_factor,
                        fill=edge_color,
                        width=edge_width,
                        arrow=tk.FIRST,
                        arrowshape=(8, 10, 4)
                    )
    
    def _draw_nodes(self):
        """Dibuja los nodos del grafo."""
        heads = find_heads(self.migrations, self._graph_children)
        roots = find_roots(self.migrations, self._graph_parents)
        
        # Calcular nodos relacionados con el seleccionado (una sola vez)
        parent_nodes: set[str] = set()
        child_nodes: set[str] = set()
        if self.selected_node and self.selected_node in self.migrations:
            # Padres del seleccionado
            parent_nodes.update(self._graph_parents.get(self.selected_node, []))
            # Hijos del seleccionado
            child_nodes.update(self._graph_children.get(self.selected_node, []))
        
        for rev, migration in self.migrations.items():
            if rev not in self.positions:
                continue
            
            pos = self.positions[rev]
            x = pos.x * self.scale_factor
            y = pos.y * self.scale_factor
            r = self.NODE_RADIUS * self.scale_factor
            
            # Determinar color de relleno
            if rev == self.selected_node:
                color = self.COLOR_NODE_SELECTED
            elif rev in heads:
                color = self.COLOR_NODE_HEAD
            elif rev in roots:
                color = self.COLOR_NODE_ROOT
            elif migration.is_merge:
                color = self.COLOR_NODE_MERGE
            else:
                color = self.COLOR_NODE_NORMAL
            
            # Determinar color y grosor del borde
            if rev in parent_nodes:
                outline_color = self.COLOR_NODE_PARENT
                outline_width = 4
            elif rev in child_nodes:
                outline_color = self.COLOR_NODE_CHILD
                outline_width = 4
            else:
                outline_color = "#2c3e50"
                outline_width = 2
            
            # Dibujar círculo del nodo
            node_id = self.create_oval(
                x - r, y - r,
                x + r, y + r,
                fill=color,
                outline=outline_color,
                width=outline_width,
                tags=("node",)
            )
            self.node_items[rev] = node_id
            self.item_to_rev[node_id] = rev
            
            # Etiqueta del nodo (revision corta)
            short_rev = rev[:8]
            text_id = self.create_text(
                x, y,
                text=short_rev,
                font=("Monaco", int(9 * self.scale_factor)),
                fill="white",
                tags=("node_text",)
            )
            self.item_to_rev[text_id] = rev
    
    def _get_node_at_position(self, canvas_x: float, canvas_y: float) -> str | None:
        """Encuentra el nodo en la posición dada del canvas."""
        for rev, pos in self.positions.items():
            # Posición del nodo en el canvas
            node_x = pos.x * self.scale_factor
            node_y = pos.y * self.scale_factor
            
            # Distancia desde el click al centro del nodo
            dx = canvas_x - node_x
            dy = canvas_y - node_y
            distance = (dx * dx + dy * dy) ** 0.5
            
            # Radio escalado
            scaled_radius = self.NODE_RADIUS * self.scale_factor
            
            if distance <= scaled_radius:
                return rev
        
        return None
    
    def _on_press(self, event):
        """Maneja el inicio de click/arrastre."""
        # Convertir a coordenadas del canvas (considerando scroll)
        canvas_x = self.canvasx(event.x)
        canvas_y = self.canvasy(event.y)
        
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        self._is_dragging = False
        
        # Iniciar scan para arrastre
        self.scan_mark(event.x, event.y)
        
        # Guardar el nodo bajo el cursor (si hay)
        self._click_target = self._get_node_at_position(canvas_x, canvas_y)
    
    def _on_drag(self, event):
        """Maneja el arrastre para pan."""
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y
        
        # Si se movió más de 5 pixels, es un arrastre (no un click)
        if abs(dx) > 5 or abs(dy) > 5:
            self._is_dragging = True
        
        if self._is_dragging:
            # Mover el canvas
            self.scan_dragto(event.x, event.y, gain=1)
    
    def _on_release(self, event):
        """Maneja el fin de click/arrastre."""
        if not self._is_dragging:
            # Fue un click, no un arrastre
            canvas_x = self.canvasx(event.x)
            canvas_y = self.canvasy(event.y)
            
            clicked_rev = self._get_node_at_position(canvas_x, canvas_y)
            if clicked_rev:
                self.select_node(clicked_rev)
            else:
                # Click en fondo -> deseleccionar
                self.deselect_node()
        
        self._is_dragging = False
        self._click_target = None
    
    def select_node(self, rev: str):
        """Selecciona un nodo."""
        self.selected_node = rev
        self._draw_graph()  # Redibujar para actualizar selección
        
        if self.on_node_select:
            self.on_node_select(rev)
    
    def deselect_node(self):
        """Deselecciona el nodo actual."""
        if self.selected_node is None:
            return
        
        self.selected_node = None
        self._draw_graph()  # Redibujar para quitar selección
        
        if self.on_node_deselect:
            self.on_node_deselect()
    
    def _on_double_click(self, event):
        """Maneja el doble-click en un nodo."""
        canvas_x = self.canvasx(event.x)
        canvas_y = self.canvasy(event.y)
        
        clicked_rev = self._get_node_at_position(canvas_x, canvas_y)
        if clicked_rev and self.on_node_double_click:
            self.on_node_double_click(clicked_rev)
    
    def _on_scroll(self, event):
        """Maneja el scroll para zoom."""
        # Obtener posición del cursor en el canvas
        canvas_x = self.canvasx(event.x)
        canvas_y = self.canvasy(event.y)
        
        # Determinar dirección del scroll
        if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
            factor = 1.1
        elif event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
            factor = 0.9
        else:
            return
        
        # Limitar zoom
        new_scale = self.scale_factor * factor
        if 0.3 <= new_scale <= 3.0:
            # Calcular el offset para hacer zoom centrado en el cursor
            old_scale = self.scale_factor
            self.scale_factor = new_scale
            
            # Ajustar scroll para mantener el punto bajo el cursor
            scale_ratio = new_scale / old_scale
            new_canvas_x = canvas_x * scale_ratio
            new_canvas_y = canvas_y * scale_ratio
            
            # Redibujar
            self._draw_graph()
            
            # Ajustar la vista
            self.xview_moveto(0)
            self.yview_moveto(0)
            self.scan_mark(0, 0)
            self.scan_dragto(int(event.x - new_canvas_x), int(event.y - new_canvas_y), gain=1)
    
    def reset_view(self):
        """Resetea la vista a valores por defecto, mostrando el final (HEAD)."""
        self.scale_factor = 1.0
        self._draw_graph()
        self.xview_moveto(0)
        self.yview_moveto(1)  # Ir al final para ver HEAD
    
    def center_on_node(self, rev: str):
        """Centra la vista en un nodo específico."""
        if rev not in self.positions:
            return False
        
        pos = self.positions[rev]
        node_x = pos.x * self.scale_factor
        node_y = pos.y * self.scale_factor
        
        # Obtener dimensiones del canvas visible
        self.update_idletasks()  # Asegurar que las dimensiones están actualizadas
        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()
        
        # Obtener scroll region configurado
        scroll_region = self.cget("scrollregion")
        if not scroll_region:
            return False
        
        # Parse scroll region (es un string "x1 y1 x2 y2")
        sr = [float(x) for x in scroll_region.split()]
        total_width = sr[2] - sr[0]
        total_height = sr[3] - sr[1]
        
        # Calcular fracción de scroll para centrar el nodo
        # La fracción representa dónde empieza la vista visible
        target_x = node_x - canvas_width / 2
        target_y = node_y - canvas_height / 2
        
        # Normalizar a fracción [0, 1]
        if total_width > canvas_width:
            x_fraction = max(0, min(1, target_x / total_width))
            self.xview_moveto(x_fraction)
        
        if total_height > canvas_height:
            y_fraction = max(0, min(1, target_y / total_height))
            self.yview_moveto(y_fraction)
        
        # Seleccionar el nodo
        self.select_node(rev)
        return True
    
    def find_nodes(self, search_text: str) -> list[str]:
        """Busca nodos por ID de revisión o mensaje (fuzzy)."""
        search_lower = search_text.lower().strip()
        if not search_lower:
            return []
        
        results: list[str] = []
        
        # Buscar coincidencia exacta en ID primero
        for rev in self.migrations:
            if rev.lower() == search_lower:
                return [rev]  # Coincidencia exacta, devolver solo ese
        
        # Buscar en ID (parcial) y mensaje
        for rev, migration in self.migrations.items():
            # Coincidencia en ID
            if search_lower in rev.lower():
                if rev not in results:
                    results.append(rev)
            # Coincidencia en mensaje
            elif search_lower in migration.message.lower():
                if rev not in results:
                    results.append(rev)
        
        # Ordenar por fecha de creación
        results.sort(key=lambda r: self.migrations[r].create_date if self.migrations[r].create_date else "")
        
        return results
    
    def find_node(self, search_text: str) -> str | None:
        """Busca un nodo por ID de revisión (parcial o completo). Deprecated, usar find_nodes."""
        results = self.find_nodes(search_text)
        return results[0] if results else None


class AlembicViewerApp:
    """Aplicación principal del visor de Alembic."""
    
    def __init__(self, root: tk.Tk, alembic_path: Path | None = None):
        self.root = root
        self.root.title("Alembic Migration Graph Viewer")
        self.root.geometry("1400x900")
        
        # Configuración de rutas
        self.config = load_config()
        
        # Determinar ruta de alembic: argumento > config > auto-detectar
        if alembic_path:
            self.alembic_path = alembic_path
        elif "alembic_path" in self.config:
            self.alembic_path = Path(self.config["alembic_path"])
        else:
            self.alembic_path = Path(__file__).parent / "alembic"
        
        self.migrations: dict[str, dict[str, Migration]] = {}
        self.children: dict[str, dict[str, list[str]]] = {}
        self.parents: dict[str, dict[str, list[str]]] = {}
        
        self._setup_ui()
        self._load_all_migrations()
    
    def _setup_ui(self):
        """Configura la interfaz de usuario."""
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Panel superior - controles
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(control_frame, text="Versiones:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.version_var = tk.StringVar()
        self.version_combo = ttk.Combobox(
            control_frame, 
            textvariable=self.version_var, 
            state="readonly",
            width=30
        )
        self.version_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.version_combo.bind("<<ComboboxSelected>>", self._on_version_change)
        
        ttk.Button(control_frame, text="Refrescar", command=self._load_all_migrations).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Reset Vista", command=self._reset_view).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="⚙️ Configurar", command=self._show_config_dialog).pack(side=tk.LEFT, padx=5)
        
        # Separador
        ttk.Separator(control_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        
        # Campo de búsqueda
        ttk.Label(control_frame, text="Buscar:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(control_frame, textvariable=self.search_var, width=15)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry.bind("<Return>", self._on_search)
        self.search_entry.bind("<KeyRelease>", self._on_search_key)
        ttk.Button(control_frame, text="🔍", width=3, command=self._on_search).pack(side=tk.LEFT)
        
        # Navegación entre resultados de búsqueda
        self.search_results: list[str] = []
        self.search_index: int = 0
        
        self.search_prev_btn = ttk.Button(control_frame, text="◀", width=2, command=self._search_prev, state=tk.DISABLED)
        self.search_prev_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        self.search_counter_label = ttk.Label(control_frame, text="")
        self.search_counter_label.pack(side=tk.LEFT, padx=2)
        
        self.search_next_btn = ttk.Button(control_frame, text="▶", width=2, command=self._search_next, state=tk.DISABLED)
        self.search_next_btn.pack(side=tk.LEFT)
        
        # Keybind Cmd+F / Ctrl+F para focus en búsqueda
        self.root.bind("<Command-f>", self._focus_search)  # macOS
        self.root.bind("<Control-f>", self._focus_search)  # Windows/Linux
        self.root.bind("<Escape>", self._on_deselect)  # Deseleccionar nodo
        
        # Info de estadísticas
        self.stats_label = ttk.Label(control_frame, text="")
        self.stats_label.pack(side=tk.RIGHT, padx=10)
        
        # Segunda fila - filtros por fecha
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(filter_frame, text="Filtrar por fecha:").pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Label(filter_frame, text="Desde:").pack(side=tk.LEFT, padx=(10, 2))
        
        # Campo de fecha "desde" con botón de calendario
        self.date_from_var = tk.StringVar()
        self.date_from_entry = ttk.Entry(filter_frame, textvariable=self.date_from_var, width=12)
        self.date_from_entry.pack(side=tk.LEFT)
        
        if HAS_TKCALENDAR:
            ttk.Button(filter_frame, text="📅", width=3, 
                      command=lambda: self._show_calendar_popup(self.date_from_var)).pack(side=tk.LEFT, padx=(2, 0))
        
        ttk.Label(filter_frame, text="Hasta:").pack(side=tk.LEFT, padx=(10, 2))
        
        # Campo de fecha "hasta" con botón de calendario
        self.date_to_var = tk.StringVar()
        self.date_to_entry = ttk.Entry(filter_frame, textvariable=self.date_to_var, width=12)
        self.date_to_entry.pack(side=tk.LEFT)
        
        if HAS_TKCALENDAR:
            ttk.Button(filter_frame, text="📅", width=3,
                      command=lambda: self._show_calendar_popup(self.date_to_var)).pack(side=tk.LEFT, padx=(2, 0))
        
        ttk.Button(filter_frame, text="Aplicar Filtro", command=self._apply_date_filter).pack(side=tk.LEFT, padx=(10, 5))
        ttk.Button(filter_frame, text="Limpiar", command=self._clear_date_filter).pack(side=tk.LEFT)
        
        self.filter_label = ttk.Label(filter_frame, text="", foreground="blue")
        self.filter_label.pack(side=tk.LEFT, padx=15)
        
        # Panel dividido
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Panel izquierdo - grafo
        graph_frame = ttk.Frame(paned)
        paned.add(graph_frame, weight=3)
        
        ttk.Label(graph_frame, text="Grafo de Migraciones", font=("TkDefaultFont", 12, "bold")).pack(anchor=tk.W)
        
        # Canvas con scrollbars
        canvas_container = ttk.Frame(graph_frame)
        canvas_container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.graph_canvas = GraphCanvas(canvas_container, highlightthickness=0)
        self.graph_canvas.on_node_select = self._on_node_select
        self.graph_canvas.on_node_double_click = self._on_node_double_click
        self.graph_canvas.on_node_deselect = self._on_node_deselect
        
        vsb = ttk.Scrollbar(canvas_container, orient="vertical", command=self.graph_canvas.yview)
        hsb = ttk.Scrollbar(canvas_container, orient="horizontal", command=self.graph_canvas.xview)
        self.graph_canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.graph_canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)
        
        # Panel derecho - detalles con tabs
        detail_frame = ttk.Frame(paned, width=400)
        paned.add(detail_frame, weight=1)
        
        # Cabecera de detalles con botón
        detail_header = ttk.Frame(detail_frame)
        detail_header.pack(fill=tk.X)
        
        ttk.Label(detail_header, text="Detalles", font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT, anchor=tk.W)
        
        self.open_file_btn = ttk.Button(detail_header, text="📂 Abrir archivo", command=self._open_selected_file, state=tk.DISABLED)
        self.open_file_btn.pack(side=tk.RIGHT, padx=5)
        
        self.selected_revision: str | None = None
        
        # Notebook con tabs
        self.detail_notebook = ttk.Notebook(detail_frame)
        self.detail_notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Tab 1: Información
        info_tab = ttk.Frame(self.detail_notebook)
        self.detail_notebook.add(info_tab, text="📋 Info")
        
        self.detail_text = tk.Text(info_tab, wrap=tk.WORD, width=40, height=20, state=tk.DISABLED)
        detail_scroll = ttk.Scrollbar(info_tab, orient="vertical", command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=detail_scroll.set)
        
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Tab 2: Código fuente
        code_tab = ttk.Frame(self.detail_notebook)
        self.detail_notebook.add(code_tab, text="📝 Código")
        
        self.code_text = tk.Text(
            code_tab, 
            wrap=tk.NONE, 
            width=40, 
            height=20,
            font=("Monaco", 11),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            state=tk.DISABLED
        )
        code_scroll_y = ttk.Scrollbar(code_tab, orient="vertical", command=self.code_text.yview)
        code_scroll_x = ttk.Scrollbar(code_tab, orient="horizontal", command=self.code_text.xview)
        self.code_text.configure(yscrollcommand=code_scroll_y.set, xscrollcommand=code_scroll_x.set)
        
        self.code_text.grid(row=0, column=0, sticky="nsew")
        code_scroll_y.grid(row=0, column=1, sticky="ns")
        code_scroll_x.grid(row=1, column=0, sticky="ew")
        
        code_tab.grid_rowconfigure(0, weight=1)
        code_tab.grid_columnconfigure(0, weight=1)
        
        # Leyenda
        legend_frame = ttk.LabelFrame(main_frame, text="Leyenda", padding=5)
        legend_frame.pack(fill=tk.X, pady=(10, 0))
        
        legends = [
            ("HEAD", "Sin hijos", GraphCanvas.COLOR_NODE_HEAD),
            ("ROOT", "Sin padre", GraphCanvas.COLOR_NODE_ROOT),
            ("MERGE", "Múltiples padres", GraphCanvas.COLOR_NODE_MERGE),
            ("Normal", "Migración estándar", GraphCanvas.COLOR_NODE_NORMAL),
        ]
        
        for i, (name, desc, color) in enumerate(legends):
            frame = ttk.Frame(legend_frame)
            frame.grid(row=0, column=i, padx=15, sticky=tk.W)
            
            # Círculo de color
            c = tk.Canvas(frame, width=16, height=16, highlightthickness=0)
            c.create_oval(2, 2, 14, 14, fill=color, outline="#2c3e50")
            c.pack(side=tk.LEFT, padx=(0, 5))
            
            ttk.Label(frame, text=f"{name}: {desc}").pack(side=tk.LEFT)
        
        # Instrucciones
        ttk.Label(
            legend_frame, 
            text="   |   🖱️ Click: seleccionar  •  Arrastrar: mover  •  Scroll/Scrollbars: navegar",
            foreground="gray"
        ).grid(row=0, column=len(legends), padx=20, sticky=tk.E)
    
    def _load_all_migrations(self):
        """Carga todas las migraciones de todas las carpetas de versiones."""
        self.migrations.clear()
        self.children.clear()
        self.parents.clear()
        
        # Buscar carpetas de versiones
        version_dirs = []
        if self.alembic_path.exists():
            for item in self.alembic_path.iterdir():
                if item.is_dir() and "versions" in item.name:
                    version_dirs.append(item)
        
        if not version_dirs:
            messagebox.showwarning("Aviso", f"No se encontraron carpetas de versiones en {self.alembic_path}")
            return
        
        # Cargar migraciones de cada carpeta
        for version_dir in version_dirs:
            name = version_dir.name
            self.migrations[name] = load_migrations(version_dir)
            children, parents = build_graph_structure(self.migrations[name])
            self.children[name] = children
            self.parents[name] = parents
        
        # Actualizar combo
        self.version_combo["values"] = list(self.migrations.keys())
        if self.migrations:
            self.version_combo.current(0)
            self._on_version_change(None)
    
    def _on_version_change(self, event):
        """Maneja el cambio de versión seleccionada."""
        version = self.version_var.get()
        if not version:
            return
        
        migrations = self.migrations.get(version, {})
        children = self.children.get(version, {})
        parents = self.parents.get(version, {})
        
        # Actualizar estadísticas
        heads = find_heads(migrations, children)
        merge_count = sum(1 for m in migrations.values() if m.is_merge)
        self.stats_label.config(
            text=f"Total: {len(migrations)} | Merges: {merge_count} | Heads: {len(heads)}"
        )
        
        # Actualizar grafo (reset_view se llama automáticamente en set_data)
        self.graph_canvas.set_data(migrations, children, parents)
    
    def _show_calendar_popup(self, target_var: tk.StringVar):
        """Muestra un popup con calendario para seleccionar fecha."""
        popup = tk.Toplevel(self.root)
        popup.title("Seleccionar fecha")
        popup.transient(self.root)
        popup.grab_set()
        
        # Posicionar cerca del cursor
        popup.geometry(f"+{self.root.winfo_pointerx()}+{self.root.winfo_pointery()}")
        
        # Crear calendario
        cal = Calendar(
            popup,
            selectmode='day',
            date_pattern='yyyy-mm-dd',
            showweeknumbers=False,
            firstweekday='monday'
        )
        cal.pack(padx=10, pady=10)
        
        def on_select():
            target_var.set(cal.get_date())
            popup.destroy()
        
        def on_cancel():
            popup.destroy()
        
        # Botones
        btn_frame = ttk.Frame(popup)
        btn_frame.pack(pady=(0, 10))
        ttk.Button(btn_frame, text="Seleccionar", command=on_select).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=on_cancel).pack(side=tk.LEFT, padx=5)
        
        # Cerrar con Escape
        popup.bind("<Escape>", lambda e: popup.destroy())
        
        # Centrar y enfocar
        popup.focus_set()
        popup.wait_window()
    
    def _apply_date_filter(self):
        """Aplica el filtro de fechas a las migraciones mostradas."""
        version = self.version_var.get()
        if not version:
            return
        
        # Obtener fechas de los StringVar
        date_from = self.date_from_var.get().strip()
        date_to = self.date_to_var.get().strip()
        
        if not date_from and not date_to:
            messagebox.showinfo("Info", "Introduce al menos una fecha para filtrar.")
            return
        
        # Obtener migraciones originales
        all_migrations = self.migrations.get(version, {})
        
        # Filtrar por fecha
        filtered: dict[str, Migration] = {}
        for rev, migration in all_migrations.items():
            create_date = migration.create_date[:10] if migration.create_date else ""  # YYYY-MM-DD
            
            if date_from and create_date < date_from:
                continue
            if date_to and create_date > date_to:
                continue
            
            filtered[rev] = migration
        
        if not filtered:
            messagebox.showinfo("Info", "No hay migraciones en el rango de fechas especificado.")
            return
        
        # Reconstruir grafo con migraciones filtradas
        children, parents = build_graph_structure(filtered)
        
        # Actualizar estadísticas
        heads = find_heads(filtered, children)
        merge_count = sum(1 for m in filtered.values() if m.is_merge)
        self.stats_label.config(
            text=f"Filtrado: {len(filtered)}/{len(all_migrations)} | Merges: {merge_count} | Heads: {len(heads)}"
        )
        
        # Mostrar indicador de filtro activo
        self.filter_label.config(text=f"⚠️ Filtro activo: {date_from or '*'} → {date_to or '*'}")
        
        # Actualizar grafo
        self.graph_canvas.set_data(filtered, children, parents)
    
    def _clear_date_filter(self):
        """Limpia el filtro de fechas y muestra todas las migraciones."""
        self.date_from_var.set("")
        self.date_to_var.set("")
        self.filter_label.config(text="")
        
        # Recargar versión actual sin filtro
        self._on_version_change(None)
    
    def _on_node_select(self, rev: str):
        """Muestra los detalles de la migración seleccionada."""
        version = self.version_var.get()
        migrations = self.migrations.get(version, {})
        children = self.children.get(version, {})
        parents = self.parents.get(version, {})
        
        if rev not in migrations:
            return
        
        # Guardar revisión seleccionada y habilitar botón
        self.selected_revision = rev
        self.open_file_btn.config(state=tk.NORMAL)
        
        migration = migrations[rev]
        heads = find_heads(migrations, children)
        roots = find_roots(migrations, parents)
        
        # Determinar tipo
        if rev in heads:
            node_type = "🟢 HEAD"
        elif rev in roots:
            node_type = "🟣 ROOT"
        elif migration.is_merge:
            node_type = "🟠 MERGE"
        else:
            node_type = "🔵 Normal"
        
        # Mostrar detalles
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        
        details = f"""📋 DETALLES DE LA MIGRACIÓN
{'='*40}

{node_type}

🔑 Revision ID:
   {migration.revision}

📝 Mensaje:
   {migration.message}

📁 Archivo:
   {migration.filename}

📅 Fecha de creación:
   {migration.create_date or 'N/A'}

"""
        
        # Mostrar padres
        parent_revs = parents.get(rev, [])
        if parent_revs:
            details += f"⬇️ Padres ({len(parent_revs)}):\n"
            for p in parent_revs:
                p_msg = migrations[p].message[:30] if p in migrations else "?"
                details += f"   • {p[:12]} - {p_msg}\n"
        else:
            details += "⬇️ Sin padres (ROOT)\n"
        
        details += "\n"
        
        # Encontrar hijos
        child_revs = children.get(rev, [])
        if child_revs:
            details += f"⬆️ Hijos ({len(child_revs)}):\n"
            for child in child_revs:
                child_msg = migrations[child].message[:30] if child in migrations else "?"
                details += f"   • {child[:12]} - {child_msg}\n"
        else:
            details += "⬆️ Sin hijos (HEAD)\n"
        
        self.detail_text.insert("1.0", details)
        self.detail_text.config(state=tk.DISABLED)
        
        # Cargar código fuente en el tab de código
        self._load_code_preview(migration)
    
    def _load_code_preview(self, migration: Migration):
        """Carga el código fuente de la migración en el panel de vista previa."""
        version = self.version_var.get()
        
        # Determinar la carpeta de versiones
        if "delfos" in version.lower():
            versions_folder = "delfos_versions"
        else:
            versions_folder = "tenant_versions"
        
        filepath = self.alembic_path / versions_folder / migration.filename
        
        self.code_text.config(state=tk.NORMAL)
        self.code_text.delete("1.0", tk.END)
        
        if filepath.exists():
            try:
                content = filepath.read_text(encoding="utf-8")
                self.code_text.insert("1.0", content)
            except Exception as e:
                self.code_text.insert("1.0", f"Error leyendo archivo:\n{e}")
        else:
            self.code_text.insert("1.0", f"Archivo no encontrado:\n{filepath}")
        
        self.code_text.config(state=tk.DISABLED)
    
    def _reset_view(self):
        """Resetea la vista del grafo."""
        self.graph_canvas.reset_view()
    
    def _on_search(self, event=None):
        """Busca nodos por ID de revisión o mensaje y centra la vista."""
        search_text = self.search_var.get().strip()
        if not search_text:
            self._clear_search_results()
            return
        
        self.search_results = self.graph_canvas.find_nodes(search_text)
        
        if self.search_results:
            self.search_index = 0
            self._navigate_to_search_result()
        else:
            self._clear_search_results()
            # Flash visual para indicar que no se encontró
            self.search_entry.configure(style="Error.TEntry")
            self.root.after(500, lambda: self.search_entry.configure(style="TEntry"))
    
    def _clear_search_results(self):
        """Limpia los resultados de búsqueda."""
        self.search_results = []
        self.search_index = 0
        self.search_counter_label.config(text="")
        self.search_prev_btn.config(state=tk.DISABLED)
        self.search_next_btn.config(state=tk.DISABLED)
    
    def _navigate_to_search_result(self):
        """Navega al resultado actual de búsqueda."""
        if not self.search_results:
            return
        
        rev = self.search_results[self.search_index]
        self.graph_canvas.center_on_node(rev)
        
        # Actualizar contador
        total = len(self.search_results)
        self.search_counter_label.config(text=f"{self.search_index + 1}/{total}")
        
        # Habilitar/deshabilitar botones de navegación
        self.search_prev_btn.config(state=tk.NORMAL if self.search_index > 0 else tk.DISABLED)
        self.search_next_btn.config(state=tk.NORMAL if self.search_index < total - 1 else tk.DISABLED)
    
    def _search_prev(self):
        """Navega al resultado anterior."""
        if self.search_results and self.search_index > 0:
            self.search_index -= 1
            self._navigate_to_search_result()
    
    def _search_next(self):
        """Navega al resultado siguiente."""
        if self.search_results and self.search_index < len(self.search_results) - 1:
            self.search_index += 1
            self._navigate_to_search_result()
    
    def _on_search_key(self, event=None):
        """Maneja el evento de tecla en el campo de búsqueda."""
        # Resetear estilo si hubo error previo
        self.search_entry.configure(style="TEntry")
    
    def _focus_search(self, event=None):
        """Hace focus en el campo de búsqueda."""
        self.search_entry.focus_set()
        self.search_entry.select_range(0, tk.END)
        return "break"  # Evitar que el evento se propague
    
    def _show_config_dialog(self):
        """Muestra el diálogo de configuración de rutas."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Configuración")
        dialog.geometry("600x200")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Centrar en la ventana principal
        dialog.geometry(f"+{self.root.winfo_x() + 100}+{self.root.winfo_y() + 100}")
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Ruta actual
        ttk.Label(frame, text="Carpeta de Alembic:", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 5)
        )
        
        path_var = tk.StringVar(value=str(self.alembic_path))
        path_entry = ttk.Entry(frame, textvariable=path_var, width=60)
        path_entry.grid(row=1, column=0, sticky=tk.EW, padx=(0, 5))
        
        def browse_folder():
            folder = filedialog.askdirectory(
                title="Seleccionar carpeta de Alembic",
                initialdir=self.alembic_path if self.alembic_path.exists() else Path.home()
            )
            if folder:
                path_var.set(folder)
        
        ttk.Button(frame, text="📁 Explorar...", command=browse_folder).grid(
            row=1, column=1, padx=(5, 0)
        )
        
        # Información
        info_label = ttk.Label(
            frame, 
            text="La carpeta debe contener subcarpetas como 'delfos_versions' y 'tenant_versions'.",
            foreground="gray"
        )
        info_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))
        
        # Ruta actual mostrada
        current_label = ttk.Label(frame, text=f"Ruta actual: {self.alembic_path}", foreground="blue")
        current_label.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        # Botones
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(20, 0))
        
        def save_and_reload():
            new_path = Path(path_var.get())
            if not new_path.exists():
                messagebox.showerror("Error", f"La carpeta no existe:\n{new_path}")
                return
            
            # Verificar que tiene subcarpetas de versiones
            has_versions = any([
                (new_path / "delfos_versions").exists(),
                (new_path / "tenant_versions").exists(),
                (new_path / "versions").exists()
            ])
            
            if not has_versions:
                if not messagebox.askyesno(
                    "Advertencia",
                    "No se encontraron carpetas de versiones (delfos_versions, tenant_versions).\n"
                    "¿Continuar de todos modos?"
                ):
                    return
            
            # Guardar configuración
            self.config["alembic_path"] = str(new_path)
            save_config(self.config)
            
            # Actualizar y recargar
            self.alembic_path = new_path
            self._load_all_migrations()
            
            dialog.destroy()
            messagebox.showinfo("Éxito", f"Configuración guardada.\nUsando: {new_path}")
        
        def reset_to_default():
            default_path = Path(__file__).parent / "alembic"
            path_var.set(str(default_path))
        
        ttk.Button(btn_frame, text="Restablecer", command=reset_to_default).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Guardar y Recargar", command=save_and_reload).pack(side=tk.LEFT, padx=5)
        
        frame.columnconfigure(0, weight=1)
    
    def _on_deselect(self, event=None):
        """Deselecciona el nodo actual (llamado por Escape)."""
        self.graph_canvas.deselect_node()
    
    def _on_node_deselect(self):
        """Maneja la deselección de un nodo."""
        self.selected_revision = None
        self.open_file_btn.config(state=tk.DISABLED)
        
        # Limpiar panel de detalles
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", "Selecciona un nodo para ver sus detalles.")
        self.detail_text.config(state=tk.DISABLED)
        
        # Limpiar panel de código
        self.code_text.config(state=tk.NORMAL)
        self.code_text.delete("1.0", tk.END)
        self.code_text.insert("1.0", "Selecciona un nodo para ver su código fuente.")
        self.code_text.config(state=tk.DISABLED)
    
    def _open_selected_file(self):
        """Abre el archivo de la revisión seleccionada."""
        if not self.selected_revision:
            return
        
        version = self.version_var.get()
        migrations = self.migrations.get(version, {})
        
        if self.selected_revision not in migrations:
            return
        
        migration = migrations[self.selected_revision]
        
        # Determinar la carpeta de versiones
        if "delfos" in version.lower():
            versions_folder = "delfos_versions"
        else:
            versions_folder = "tenant_versions"
        
        filepath = self.alembic_path / versions_folder / migration.filename
        
        if not filepath.exists():
            messagebox.showerror("Error", f"Archivo no encontrado:\n{filepath}")
            return
        
        self._open_file_in_editor(filepath)
    
    def _open_file_in_editor(self, filepath: Path):
        """Abre un archivo en el editor, intentando VS Code primero."""
        filepath_str = str(filepath)
        
        # Intentar con VS Code primero
        try:
            result = subprocess.run(
                ["code", filepath_str],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Fallback según el sistema operativo
        system = platform.system()
        try:
            if system == "Darwin":  # macOS
                subprocess.run(["open", filepath_str], check=True)
            elif system == "Windows":
                os.startfile(filepath_str)
            else:  # Linux y otros
                subprocess.run(["xdg-open", filepath_str], check=True)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el archivo:\n{e}")
    
    def _on_node_double_click(self, rev: str):
        """Maneja el doble-click en un nodo para abrir el archivo."""
        self.selected_revision = rev
        self._open_selected_file()


def main():
    """Punto de entrada principal."""
    # Parsear argumentos de línea de comandos
    parser = argparse.ArgumentParser(
        description="Visualizador de grafo de migraciones de Alembic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    python alembic_viewer.py
    python alembic_viewer.py --path /ruta/al/proyecto/alembic
    python alembic_viewer.py -p ./mi_proyecto/alembic
        """
    )
    parser.add_argument(
        "-p", "--path",
        type=str,
        help="Ruta a la carpeta 'alembic' del proyecto"
    )
    args = parser.parse_args()
    
    # Convertir path a Path si se proporcionó
    alembic_path = Path(args.path) if args.path else None
    
    root = tk.Tk()
    
    # Configurar estilo
    style = ttk.Style()
    style.theme_use("clam")
    
    # Estilo para campo de búsqueda con error
    style.configure("Error.TEntry", fieldbackground="#ffcccc")
    
    app = AlembicViewerApp(root, alembic_path)
    root.mainloop()


if __name__ == "__main__":
    main()

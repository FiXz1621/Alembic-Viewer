"""Canvas para dibujar el grafo de migraciones."""

import tkinter as tk
from collections import defaultdict
from collections.abc import Callable

from alembic_viewer.config import DEFAULT_COLORS
from alembic_viewer.models import Migration, NodePosition
from alembic_viewer.parser import find_heads, find_roots


class GraphCanvas(tk.Canvas):
    """Canvas personalizado para dibujar el grafo de migraciones."""

    # Dimensiones
    NODE_RADIUS = 32
    LEVEL_HEIGHT = 100
    COLUMN_WIDTH = 150

    def __init__(self, parent, **kwargs):
        # Inicializar colores con valores por defecto
        self._colors = DEFAULT_COLORS.copy()
        super().__init__(parent, bg=self._colors["background"], **kwargs)

        self.migrations: dict[str, Migration] = {}
        self._graph_children: dict[str, list[str]] = {}
        self._graph_parents: dict[str, list[str]] = {}
        self.positions: dict[str, NodePosition] = {}
        self.node_items: dict[str, int] = {}  # revision -> canvas item id
        self.item_to_rev: dict[int, str] = {}  # canvas item id -> revision (mapeo inverso)
        self.selected_node: str | None = None
        self.on_node_select: Callable[[str], None] | None = None
        self.on_node_double_click: Callable[[str], None] | None = None
        self.on_node_deselect: Callable[[], None] | None = None

        # Para pan y zoom
        self.scale_factor = 1.0
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._is_dragging = False
        self._click_target: str | None = None

        # Bindings
        self._setup_bindings()

    def _setup_bindings(self):
        """Configura los bindings de eventos."""
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Double-Button-1>", self._on_double_click)

        # Zoom con scroll
        self.bind("<MouseWheel>", self._on_scroll)  # macOS/Windows
        self.bind("<Button-4>", self._on_scroll)  # Linux scroll up
        self.bind("<Button-5>", self._on_scroll)  # Linux scroll down
        self.bind("<Control-MouseWheel>", self._on_scroll)

    def set_colors(self, colors: dict):
        """Actualiza los colores del canvas."""
        self._colors = DEFAULT_COLORS.copy()
        self._colors.update(colors)
        self.configure(bg=self._colors["background"])
        self._draw_graph()

    def set_data(self, migrations: dict[str, Migration], children: dict[str, list[str]], parents: dict[str, list[str]]):
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

        levels: dict[str, int] = {}
        roots = find_roots(self.migrations, self._graph_parents)
        for root in roots:
            levels[root] = 0

        def get_level(rev: str, visited_stack: set[str] | None = None) -> int:
            if visited_stack is None:
                visited_stack = set()

            if rev in visited_stack:
                return levels.get(rev, 0)

            if rev in levels:
                return levels[rev]

            visited_stack.add(rev)

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

        for rev in self.migrations:
            get_level(rev)

        level_groups: dict[int, list[str]] = defaultdict(list)
        for rev, level in levels.items():
            level_groups[level].append(rev)

        for level, revs in level_groups.items():
            level_groups[level] = sorted(
                revs, key=lambda r: self.migrations[r].create_date if self.migrations[r].create_date else ""
            )

        for level, revs in level_groups.items():
            for col, rev in enumerate(revs):
                self.positions[rev] = NodePosition(
                    x=100 + col * self.COLUMN_WIDTH, y=50 + level * self.LEVEL_HEIGHT, level=level, column=col
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
                fill=self._colors["text"],
            )
            return

        if self.positions:
            max_x = max(p.x for p in self.positions.values()) + 150
            max_y = max(p.y for p in self.positions.values()) + 100
            self.configure(scrollregion=(0, 0, max_x * self.scale_factor, max_y * self.scale_factor))

        self._draw_edges()
        self._draw_nodes()

    def _draw_edges(self):
        """Dibuja las aristas del grafo."""
        selected_parents = set()
        selected_children = set()
        if self.selected_node:
            selected_parents = set(self._graph_parents.get(self.selected_node, []))
            for rev, parents in self._graph_parents.items():
                if self.selected_node in parents:
                    selected_children.add(rev)

        for rev, migration in self.migrations.items():
            if rev not in self.positions:
                continue

            pos = self.positions[rev]
            x1 = pos.x * self.scale_factor
            y1 = pos.y * self.scale_factor

            parent_revs = self._graph_parents.get(rev, [])
            is_merge = len(parent_revs) > 1

            for parent_rev in parent_revs:
                if parent_rev not in self.positions:
                    continue

                parent_pos = self.positions[parent_rev]
                x2 = parent_pos.x * self.scale_factor
                y2 = parent_pos.y * self.scale_factor

                is_to_parent = rev == self.selected_node and parent_rev in selected_parents
                is_from_child = rev in selected_children and parent_rev == self.selected_node

                if is_to_parent:
                    edge_color = self._colors["edge_parent"]
                    edge_width = 4
                elif is_from_child:
                    edge_color = self._colors["edge_child"]
                    edge_width = 4
                elif is_merge:
                    edge_color = self._colors["edge_merge"]
                    edge_width = 2
                else:
                    edge_color = self._colors["edge_normal"]
                    edge_width = 2

                if abs(x1 - x2) > 10:
                    mid_y = (y1 + y2) / 2
                    self.create_line(
                        x1,
                        y1 - self.NODE_RADIUS * self.scale_factor,
                        x1,
                        mid_y,
                        x2,
                        mid_y,
                        x2,
                        y2 + self.NODE_RADIUS * self.scale_factor,
                        fill=edge_color,
                        width=edge_width,
                        smooth=True,
                        arrow=tk.FIRST,
                        arrowshape=(8, 10, 4),
                    )  # pyright: ignore[reportCallIssue]
                else:
                    self.create_line(
                        x1,
                        y1 - self.NODE_RADIUS * self.scale_factor,
                        x2,
                        y2 + self.NODE_RADIUS * self.scale_factor,
                        fill=edge_color,
                        width=edge_width,
                        arrow=tk.FIRST,
                        arrowshape=(8, 10, 4),
                    )

    def _draw_nodes(self):
        """Dibuja los nodos del grafo."""
        heads = find_heads(self.migrations, self._graph_children)
        roots = find_roots(self.migrations, self._graph_parents)

        parent_nodes: set[str] = set()
        child_nodes: set[str] = set()
        if self.selected_node and self.selected_node in self.migrations:
            parent_nodes.update(self._graph_parents.get(self.selected_node, []))
            child_nodes.update(self._graph_children.get(self.selected_node, []))

        for rev, migration in self.migrations.items():
            if rev not in self.positions:
                continue

            pos = self.positions[rev]
            x = pos.x * self.scale_factor
            y = pos.y * self.scale_factor
            r = self.NODE_RADIUS * self.scale_factor

            if rev == self.selected_node:
                color = self._colors["node_selected"]
            elif rev in heads:
                color = self._colors["node_head"]
            elif rev in roots:
                color = self._colors["node_root"]
            elif migration.is_merge:
                color = self._colors["node_merge"]
            else:
                color = self._colors["node_normal"]

            if rev in parent_nodes:
                outline_color = self._colors["node_parent_border"]
                outline_width = 4
            elif rev in child_nodes:
                outline_color = self._colors["node_child_border"]
                outline_width = 4
            else:
                outline_color = "#2c3e50"
                outline_width = 2

            node_id = self.create_oval(
                x - r, y - r, x + r, y + r, fill=color, outline=outline_color, width=outline_width, tags=("node",)
            )
            self.node_items[rev] = node_id
            self.item_to_rev[node_id] = rev

            short_rev = rev[:8]
            text_id = self.create_text(
                x, y, text=short_rev, font=("Monaco", int(9 * self.scale_factor)), fill="white", tags=("node_text",)
            )
            self.item_to_rev[text_id] = rev

    def _get_node_at_position(self, canvas_x: float, canvas_y: float) -> str | None:
        """Encuentra el nodo en la posición dada del canvas."""
        for rev, pos in self.positions.items():
            node_x = pos.x * self.scale_factor
            node_y = pos.y * self.scale_factor
            dx = canvas_x - node_x
            dy = canvas_y - node_y
            distance = (dx * dx + dy * dy) ** 0.5
            scaled_radius = self.NODE_RADIUS * self.scale_factor

            if distance <= scaled_radius:
                return rev
        return None

    def _on_press(self, event):
        """Maneja el inicio de click/arrastre."""
        canvas_x = self.canvasx(event.x)
        canvas_y = self.canvasy(event.y)

        self._drag_start_x = event.x
        self._drag_start_y = event.y
        self._is_dragging = False

        self.scan_mark(event.x, event.y)
        self._click_target = self._get_node_at_position(canvas_x, canvas_y)

    def _on_drag(self, event):
        """Maneja el arrastre para pan."""
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y

        if abs(dx) > 5 or abs(dy) > 5:
            self._is_dragging = True

        if self._is_dragging:
            self.scan_dragto(event.x, event.y, gain=1)

    def _on_release(self, event):
        """Maneja el fin de click/arrastre."""
        if not self._is_dragging:
            canvas_x = self.canvasx(event.x)
            canvas_y = self.canvasy(event.y)

            clicked_rev = self._get_node_at_position(canvas_x, canvas_y)
            if clicked_rev:
                self.select_node(clicked_rev)
            else:
                self.deselect_node()

        self._is_dragging = False
        self._click_target = None

    def select_node(self, rev: str):
        """Selecciona un nodo."""
        self.selected_node = rev
        self._draw_graph()

        if self.on_node_select:
            self.on_node_select(rev)

    def deselect_node(self):
        """Deselecciona el nodo actual."""
        if self.selected_node is None:
            return

        self.selected_node = None
        self._draw_graph()

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
        canvas_x = self.canvasx(event.x)
        canvas_y = self.canvasy(event.y)

        if event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
            factor = 1.1
        elif event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
            factor = 0.9
        else:
            return

        new_scale = self.scale_factor * factor
        if 0.3 <= new_scale <= 3.0:
            old_scale = self.scale_factor
            self.scale_factor = new_scale

            scale_ratio = new_scale / old_scale
            new_canvas_x = canvas_x * scale_ratio
            new_canvas_y = canvas_y * scale_ratio

            self._draw_graph()

            self.xview_moveto(0)
            self.yview_moveto(0)
            self.scan_mark(0, 0)
            self.scan_dragto(int(event.x - new_canvas_x), int(event.y - new_canvas_y), gain=1)

    def reset_view(self):
        """Resetea la vista a valores por defecto, mostrando el final (HEAD)."""
        self.scale_factor = 1.0
        self._draw_graph()
        self.xview_moveto(0)
        self.yview_moveto(1)

    def center_on_node(self, rev: str):
        """Centra la vista en un nodo específico."""
        if rev not in self.positions:
            return False

        pos = self.positions[rev]
        node_x = pos.x * self.scale_factor
        node_y = pos.y * self.scale_factor

        self.update_idletasks()
        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()

        scroll_region = self.cget("scrollregion")
        if not scroll_region:
            return False

        sr = [float(x) for x in scroll_region.split()]
        total_width = sr[2] - sr[0]
        total_height = sr[3] - sr[1]

        target_x = node_x - canvas_width / 2
        target_y = node_y - canvas_height / 2

        if total_width > canvas_width:
            x_fraction = max(0, min(1, target_x / total_width))
            self.xview_moveto(x_fraction)

        if total_height > canvas_height:
            y_fraction = max(0, min(1, target_y / total_height))
            self.yview_moveto(y_fraction)

        self.select_node(rev)
        return True

    def find_nodes(self, search_text: str) -> list[str]:
        """Busca nodos por ID de revisión o mensaje (fuzzy)."""
        search_lower = search_text.lower().strip()
        if not search_lower:
            return []

        results: list[str] = []

        for rev in self.migrations:
            if rev.lower() == search_lower:
                return [rev]

        for rev, migration in self.migrations.items():
            if search_lower in rev.lower() or search_lower in migration.message.lower():
                if rev not in results:
                    results.append(rev)

        results.sort(key=lambda r: self.migrations[r].create_date if self.migrations[r].create_date else "")
        return results

    def find_node(self, search_text: str) -> str | None:
        """Busca un nodo por ID de revisión (parcial o completo). Deprecated, usar find_nodes."""
        results = self.find_nodes(search_text)
        return results[0] if results else None

"""Aplicación principal del visor de Alembic."""

import os
import platform
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from alembic_viewer.canvas import GraphCanvas
from alembic_viewer.config import get_colors, load_config
from alembic_viewer.dialogs import HAS_TKCALENDAR, show_calendar_popup, show_color_config_dialog, show_config_dialog
from alembic_viewer.models import Migration
from alembic_viewer.parser import build_graph_structure, find_heads, find_roots, load_migrations


class AlembicViewerApp:
    """Aplicación principal del visor de Alembic."""

    def __init__(self, root: tk.Tk, alembic_path: Path | None = None):
        self.root = root
        self.root.title("Alembic Migration Graph Viewer")
        self.root.geometry("1400x900")

        self.config = load_config()

        if alembic_path:
            self.alembic_path = alembic_path
        elif "alembic_path" in self.config:
            self.alembic_path = Path(self.config["alembic_path"])
        else:
            self.alembic_path = Path(__file__).parent.parent / "alembic"

        self.migrations: dict[str, dict[str, Migration]] = {}
        self.children: dict[str, dict[str, list[str]]] = {}
        self.parents: dict[str, dict[str, list[str]]] = {}

        self.selected_revision: str | None = None
        self.search_results: list[str] = []
        self.search_index: int = 0

        self._setup_ui()
        self._load_all_migrations()

    def _setup_ui(self):
        """Configura la interfaz de usuario."""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self._setup_control_bar(main_frame)
        self._setup_filter_bar(main_frame)
        self._setup_main_panels(main_frame)
        self._setup_legend(main_frame)
        self._setup_keybindings()

    def _setup_control_bar(self, parent: ttk.Frame):
        """Configura la barra de control superior."""
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(control_frame, text="Versiones:").pack(side=tk.LEFT, padx=(0, 5))

        self.version_var = tk.StringVar()
        self.version_combo = ttk.Combobox(control_frame, textvariable=self.version_var, state="readonly", width=30)
        self.version_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.version_combo.bind("<<ComboboxSelected>>", self._on_version_change)

        ttk.Button(control_frame, text="Refrescar", command=self._load_all_migrations).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Reset Vista", command=self._reset_view).pack(side=tk.LEFT, padx=5)

        config_menubutton = ttk.Menubutton(control_frame, text="Configuracion")
        config_menubutton.pack(side=tk.LEFT, padx=5)

        config_menu = tk.Menu(config_menubutton, tearoff=0)
        config_menubutton["menu"] = config_menu

        config_menu.add_command(label="Ruta de Alembic...", command=self._show_config_dialog)
        config_menu.add_command(label="Colores del grafo...", command=self._show_color_config_dialog)

        ttk.Separator(control_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        ttk.Label(control_frame, text="Buscar:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(control_frame, textvariable=self.search_var, width=15)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry.bind("<Return>", self._on_search)
        self.search_entry.bind("<KeyRelease>", self._on_search_key)
        ttk.Button(control_frame, text="Buscar", width=6, command=self._on_search).pack(side=tk.LEFT)

        self.search_prev_btn = ttk.Button(
            control_frame, text="<", width=3, command=self._search_prev, state=tk.DISABLED
        )
        self.search_prev_btn.pack(side=tk.LEFT, padx=(5, 0))

        self.search_counter_label = ttk.Label(control_frame, text="")
        self.search_counter_label.pack(side=tk.LEFT, padx=2)

        self.search_next_btn = ttk.Button(
            control_frame, text=">", width=3, command=self._search_next, state=tk.DISABLED
        )
        self.search_next_btn.pack(side=tk.LEFT)

        self.stats_label = ttk.Label(control_frame, text="")
        self.stats_label.pack(side=tk.RIGHT, padx=10)

    def _setup_filter_bar(self, parent: ttk.Frame):
        """Configura la barra de filtros por fecha."""
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text="Filtrar por fecha:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(filter_frame, text="Desde:").pack(side=tk.LEFT, padx=(10, 2))

        self.date_from_var = tk.StringVar()
        self.date_from_entry = ttk.Entry(filter_frame, textvariable=self.date_from_var, width=12)
        self.date_from_entry.pack(side=tk.LEFT)

        if HAS_TKCALENDAR:
            ttk.Button(
                filter_frame, text="...", width=3, command=lambda: show_calendar_popup(self.root, self.date_from_var)
            ).pack(side=tk.LEFT, padx=(2, 0))

        ttk.Label(filter_frame, text="Hasta:").pack(side=tk.LEFT, padx=(10, 2))

        self.date_to_var = tk.StringVar()
        self.date_to_entry = ttk.Entry(filter_frame, textvariable=self.date_to_var, width=12)
        self.date_to_entry.pack(side=tk.LEFT)

        if HAS_TKCALENDAR:
            ttk.Button(
                filter_frame, text="...", width=3, command=lambda: show_calendar_popup(self.root, self.date_to_var)
            ).pack(side=tk.LEFT, padx=(2, 0))

        ttk.Button(filter_frame, text="Aplicar Filtro", command=self._apply_date_filter).pack(side=tk.LEFT, padx=(10, 5))
        ttk.Button(filter_frame, text="Limpiar", command=self._clear_date_filter).pack(side=tk.LEFT)

        self.filter_label = ttk.Label(filter_frame, text="", foreground="blue")
        self.filter_label.pack(side=tk.LEFT, padx=15)

    def _setup_main_panels(self, parent: ttk.Frame):
        """Configura los paneles principales (grafo y detalles)."""
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Panel izquierdo - grafo
        graph_frame = ttk.Frame(paned)
        paned.add(graph_frame, weight=3)

        ttk.Label(graph_frame, text="Grafo de Migraciones", font=("TkDefaultFont", 12, "bold")).pack(anchor=tk.W)

        canvas_container = ttk.Frame(graph_frame)
        canvas_container.pack(fill=tk.BOTH, expand=True, pady=5)

        self.graph_canvas = GraphCanvas(canvas_container, highlightthickness=0)
        self.graph_canvas.set_colors(get_colors(self.config))
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

        # Panel derecho - detalles
        detail_frame = ttk.Frame(paned, width=400)
        paned.add(detail_frame, weight=1)

        self._setup_detail_panel(detail_frame)

    def _setup_detail_panel(self, parent: ttk.Frame):
        """Configura el panel de detalles."""
        detail_header = ttk.Frame(parent)
        detail_header.pack(fill=tk.X)

        ttk.Label(detail_header, text="Detalles", font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT, anchor=tk.W)

        self.open_file_btn = ttk.Button(
            detail_header, text="Abrir archivo", command=self._open_selected_file, state=tk.DISABLED
        )
        self.open_file_btn.pack(side=tk.RIGHT, padx=5)

        self.detail_notebook = ttk.Notebook(parent)
        self.detail_notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # Tab Info
        info_tab = ttk.Frame(self.detail_notebook)
        self.detail_notebook.add(info_tab, text="Info")

        self.detail_text = tk.Text(info_tab, wrap=tk.WORD, width=40, height=20, state=tk.DISABLED)
        detail_scroll = ttk.Scrollbar(info_tab, orient="vertical", command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=detail_scroll.set)

        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Tab Código
        code_tab = ttk.Frame(self.detail_notebook)
        self.detail_notebook.add(code_tab, text="Codigo")

        self.code_text = tk.Text(
            code_tab,
            wrap=tk.NONE,
            width=40,
            height=20,
            font=("Monaco", 11),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            state=tk.DISABLED,
        )
        code_scroll_y = ttk.Scrollbar(code_tab, orient="vertical", command=self.code_text.yview)
        code_scroll_x = ttk.Scrollbar(code_tab, orient="horizontal", command=self.code_text.xview)
        self.code_text.configure(yscrollcommand=code_scroll_y.set, xscrollcommand=code_scroll_x.set)

        self.code_text.grid(row=0, column=0, sticky="nsew")
        code_scroll_y.grid(row=0, column=1, sticky="ns")
        code_scroll_x.grid(row=1, column=0, sticky="ew")

        code_tab.grid_rowconfigure(0, weight=1)
        code_tab.grid_columnconfigure(0, weight=1)

    def _setup_legend(self, parent: ttk.Frame):
        """Configura la leyenda."""
        legend_frame = ttk.LabelFrame(parent, text="Leyenda", padding=5)
        legend_frame.pack(fill=tk.X, pady=(10, 0))

        colors = get_colors(self.config)
        legends = [
            ("HEAD", "Sin hijos", colors["node_head"]),
            ("ROOT", "Sin padre", colors["node_root"]),
            ("MERGE", "Múltiples padres", colors["node_merge"]),
            ("Normal", "Migración estándar", colors["node_normal"]),
        ]

        for i, (name, desc, color) in enumerate(legends):
            frame = ttk.Frame(legend_frame)
            frame.grid(row=0, column=i, padx=15, sticky=tk.W)

            c = tk.Canvas(frame, width=16, height=16, highlightthickness=0)
            c.create_oval(2, 2, 14, 14, fill=color, outline="#2c3e50")
            c.pack(side=tk.LEFT, padx=(0, 5))

            ttk.Label(frame, text=f"{name}: {desc}").pack(side=tk.LEFT)

        ttk.Label(
            legend_frame,
            text="   |   Click: seleccionar  -  Arrastrar: mover  -  Scroll: navegar",
            foreground="gray",
        ).grid(row=0, column=len(legends), padx=20, sticky=tk.E)

    def _setup_keybindings(self):
        """Configura los atajos de teclado."""
        self.root.bind("<Command-f>", self._focus_search)
        self.root.bind("<Control-f>", self._focus_search)
        self.root.bind("<Escape>", self._on_deselect)

    def _load_all_migrations(self):
        """Carga todas las migraciones de todas las carpetas de versiones."""
        self.migrations.clear()
        self.children.clear()
        self.parents.clear()

        version_dirs = []
        if self.alembic_path.exists():
            for item in self.alembic_path.iterdir():
                if item.is_dir() and "versions" in item.name:
                    version_dirs.append(item)

        if not version_dirs:
            messagebox.showwarning("Aviso", f"No se encontraron carpetas de versiones en {self.alembic_path}")
            return

        for version_dir in version_dirs:
            name = version_dir.name
            self.migrations[name] = load_migrations(version_dir)
            children, parents = build_graph_structure(self.migrations[name])
            self.children[name] = children
            self.parents[name] = parents

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

        heads = find_heads(migrations, children)
        merge_count = sum(1 for m in migrations.values() if m.is_merge)
        self.stats_label.config(text=f"Total: {len(migrations)} | Merges: {merge_count} | Heads: {len(heads)}")

        self.graph_canvas.set_data(migrations, children, parents)

    def _apply_date_filter(self):
        """Aplica el filtro de fechas a las migraciones mostradas."""
        version = self.version_var.get()
        if not version:
            return

        date_from = self.date_from_var.get().strip()
        date_to = self.date_to_var.get().strip()

        if not date_from and not date_to:
            messagebox.showinfo("Info", "Introduce al menos una fecha para filtrar.")
            return

        all_migrations = self.migrations.get(version, {})

        filtered: dict[str, Migration] = {}
        for rev, migration in all_migrations.items():
            create_date = migration.create_date[:10] if migration.create_date else ""

            if date_from and create_date < date_from:
                continue
            if date_to and create_date > date_to:
                continue

            filtered[rev] = migration

        if not filtered:
            messagebox.showinfo("Info", "No hay migraciones en el rango de fechas especificado.")
            return

        children, parents = build_graph_structure(filtered)

        heads = find_heads(filtered, children)
        merge_count = sum(1 for m in filtered.values() if m.is_merge)
        self.stats_label.config(
            text=f"Filtrado: {len(filtered)}/{len(all_migrations)} | Merges: {merge_count} | Heads: {len(heads)}"
        )

        self.filter_label.config(text=f"⚠️ Filtro activo: {date_from or '*'} → {date_to or '*'}")

        self.graph_canvas.set_data(filtered, children, parents)

    def _clear_date_filter(self):
        """Limpia el filtro de fechas y muestra todas las migraciones."""
        self.date_from_var.set("")
        self.date_to_var.set("")
        self.filter_label.config(text="")
        self._on_version_change(None)

    def _on_node_select(self, rev: str):
        """Muestra los detalles de la migración seleccionada."""
        version = self.version_var.get()
        migrations = self.migrations.get(version, {})
        children = self.children.get(version, {})
        parents = self.parents.get(version, {})

        if rev not in migrations:
            return

        self.selected_revision = rev
        self.open_file_btn.config(state=tk.NORMAL)

        migration = migrations[rev]
        heads = find_heads(migrations, children)
        roots = find_roots(migrations, parents)

        if rev in heads:
            node_type = "[HEAD]"
        elif rev in roots:
            node_type = "[ROOT]"
        elif migration.is_merge:
            node_type = "[MERGE]"
        else:
            node_type = "[Normal]"

        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)

        details = f"""DETALLES DE LA MIGRACION
{"=" * 40}

{node_type}

Revision ID:
   {migration.revision}

Mensaje:
   {migration.message}

Archivo:
   {migration.filename}

Fecha de creacion:
   {migration.create_date or "N/A"}

"""

        parent_revs = parents.get(rev, [])
        if parent_revs:
            details += f"Padres ({len(parent_revs)}):\n"
            for p in parent_revs:
                p_msg = migrations[p].message[:30] if p in migrations else "?"
                details += f"   - {p[:12]} - {p_msg}\n"
        else:
            details += "Sin padres (ROOT)\n"

        details += "\n"

        child_revs = children.get(rev, [])
        if child_revs:
            details += f"Hijos ({len(child_revs)}):\n"
            for child in child_revs:
                child_msg = migrations[child].message[:30] if child in migrations else "?"
                details += f"   - {child[:12]} - {child_msg}\n"
        else:
            details += "Sin hijos (HEAD)\n"

        self.detail_text.insert("1.0", details)
        self.detail_text.config(state=tk.DISABLED)

        self._load_code_preview(migration)

    def _load_code_preview(self, migration: Migration):
        """Carga el código fuente de la migración en el panel de vista previa."""
        version = self.version_var.get()

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

        total = len(self.search_results)
        self.search_counter_label.config(text=f"{self.search_index + 1}/{total}")

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
        self.search_entry.configure(style="TEntry")

    def _focus_search(self, event=None):
        """Hace focus en el campo de búsqueda."""
        self.search_entry.focus_set()
        self.search_entry.select_range(0, tk.END)
        return "break"

    def _show_config_dialog(self):
        """Muestra el diálogo de configuración de rutas."""

        def on_save(new_path: Path):
            self.alembic_path = new_path
            self._load_all_migrations()

        show_config_dialog(self.root, self.alembic_path, self.config, on_save)

    def _show_color_config_dialog(self):
        """Muestra el diálogo de configuración de colores."""

        def on_apply(colors: dict):
            self.graph_canvas.set_colors(colors)

        def on_save(colors: dict):
            self.graph_canvas.set_colors(colors)

        show_color_config_dialog(self.root, self.config, on_apply, on_save)

    def _on_deselect(self, event=None):
        """Deselecciona el nodo actual (llamado por Escape)."""
        self.graph_canvas.deselect_node()

    def _on_node_deselect(self):
        """Maneja la deselección de un nodo."""
        self.selected_revision = None
        self.open_file_btn.config(state=tk.DISABLED)

        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", "Selecciona un nodo para ver sus detalles.")
        self.detail_text.config(state=tk.DISABLED)

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

        try:
            result = subprocess.run(["code", filepath_str], capture_output=True, timeout=5)
            if result.returncode == 0:
                return
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        system = platform.system()
        try:
            if system == "Darwin":
                subprocess.run(["open", filepath_str], check=True)
            elif system == "Windows":
                os.startfile(filepath_str)  # pyright: ignore[reportAttributeAccessIssue]
            else:
                subprocess.run(["xdg-open", filepath_str], check=True)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el archivo:\n{e}")

    def _on_node_double_click(self, rev: str):
        """Maneja el doble-click en un nodo para abrir el archivo."""
        self.selected_revision = rev
        self._open_selected_file()

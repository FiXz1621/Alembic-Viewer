"""Diálogos de configuración para el visor de Alembic."""

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from alembic_viewer.config import (
    COLOR_LABELS,
    DEFAULT_COLORS,
    get_alembic_paths,
    get_colors,
    save_config,
    set_alembic_paths,
)

# Intentar importar tkcalendar para selector de fechas
try:
    from tkcalendar import Calendar

    HAS_TKCALENDAR = True
except ImportError:
    HAS_TKCALENDAR = False


def show_calendar_popup(parent: tk.Tk, target_var: tk.StringVar):
    """Muestra un popup con calendario para seleccionar fecha."""
    if not HAS_TKCALENDAR:
        messagebox.showinfo("Info", "tkcalendar no está instalado.")
        return

    popup = tk.Toplevel(parent)
    popup.title("Seleccionar fecha")
    popup.transient(parent)
    popup.grab_set()

    popup.geometry(f"+{parent.winfo_pointerx()}+{parent.winfo_pointery()}")

    cal = Calendar(popup, selectmode="day", date_pattern="yyyy-mm-dd", showweeknumbers=False, firstweekday="monday")
    cal.pack(padx=10, pady=10)

    def on_select():
        target_var.set(cal.get_date())
        popup.destroy()

    def on_cancel():
        popup.destroy()

    btn_frame = ttk.Frame(popup)
    btn_frame.pack(pady=(0, 10))
    ttk.Button(btn_frame, text="Seleccionar", command=on_select).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancelar", command=on_cancel).pack(side=tk.LEFT, padx=5)

    popup.bind("<Escape>", lambda e: popup.destroy())
    popup.focus_set()
    popup.wait_window()


def show_config_dialog(parent: tk.Tk, config: dict, on_save: Callable):
    """Muestra el diálogo de configuración de carpetas de Alembic."""
    dialog = tk.Toplevel(parent)
    dialog.title("Configuracion de Carpetas")
    dialog.geometry("700x450")
    dialog.resizable(True, True)
    dialog.transient(parent)
    dialog.grab_set()

    # Centrar en la ventana principal
    x = parent.winfo_x() + (parent.winfo_width() - 700) // 2
    y = parent.winfo_y() + (parent.winfo_height() - 450) // 2
    dialog.geometry(f"+{x}+{y}")

    frame = ttk.Frame(dialog, padding=15)
    frame.pack(fill=tk.BOTH, expand=True)

    # Título
    ttk.Label(
        frame, text="Carpetas de Versiones", font=("TkDefaultFont", 12, "bold")
    ).pack(anchor=tk.W, pady=(0, 5))

    ttk.Label(
        frame,
        text="Agrega las carpetas que contienen los archivos de migraciones (.py). Puedes asignar un alias para identificarlas.",
        foreground="gray",
    ).pack(anchor=tk.W, pady=(0, 10))

    # Frame para la lista con Treeview
    list_frame = ttk.Frame(frame)
    list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Botones de acción para la lista (primero para que siempre estén visibles)
    action_frame = ttk.Frame(list_frame)
    action_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

    # Treeview con columnas (en un frame que ocupa el resto del espacio)
    tree_frame = ttk.Frame(list_frame)
    tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    columns = ("alias", "path")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=8)
    tree.heading("alias", text="Alias")
    tree.heading("path", text="Ruta")
    tree.column("alias", width=120, minwidth=80, stretch=False)
    tree.column("path", width=800, minwidth=400, stretch=False)

    # Scrollbars vertical y horizontal
    scrollbar_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
    scrollbar_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

    # Layout con grid para soportar ambos scrollbars
    tree.grid(row=0, column=0, sticky="nsew")
    scrollbar_y.grid(row=0, column=1, sticky="ns")
    scrollbar_x.grid(row=1, column=0, sticky="ew")
    tree_frame.grid_rowconfigure(0, weight=1)
    tree_frame.grid_columnconfigure(0, weight=1)

    # Lista interna de paths: [{path: str, alias: str}, ...]
    current_paths: list[dict] = [item.copy() for item in get_alembic_paths(config)]

    def refresh_tree():
        tree.delete(*tree.get_children())
        for item in current_paths:
            alias = item.get("alias", "") or "(sin alias)"
            tree.insert("", tk.END, values=(alias, item["path"]))

    refresh_tree()

    def add_folder():
        folder = filedialog.askdirectory(
            title="Seleccionar carpeta de versiones",
            initialdir=Path.home(),
        )
        if folder:
            # Verificar que no esté duplicada
            existing_paths = [item["path"] for item in current_paths]
            if folder in existing_paths:
                messagebox.showwarning("Aviso", "Esta carpeta ya esta en la lista.")
                return

            # Verificar que tenga archivos de migraciones
            folder_path = Path(folder)
            if folder_path.exists():
                has_migrations = any(
                    item.is_file() and item.suffix == ".py" and item.name != "__init__.py"
                    for item in folder_path.iterdir()
                )
                if not has_migrations:
                    if not messagebox.askyesno(
                        "Advertencia",
                        f"No se encontraron archivos de migracion (.py) en:\n{folder}\n\n"
                        "Continuar de todos modos?",
                    ):
                        return

            # Preguntar por alias
            alias = _ask_alias(dialog, folder_path.name)
            current_paths.append({"path": folder, "alias": alias or ""})
            refresh_tree()
            update_info()

    def edit_selected():
        selection = tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Selecciona una carpeta para editar.")
            return

        idx = tree.index(selection[0])
        item = current_paths[idx]

        new_alias = _ask_alias(dialog, Path(item["path"]).name, item.get("alias", ""))
        if new_alias is not None:
            current_paths[idx]["alias"] = new_alias
            refresh_tree()

    def remove_selected():
        selection = tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Selecciona una carpeta para eliminar.")
            return

        idx = tree.index(selection[0])
        item = current_paths[idx]

        display = item.get("alias") or item["path"]
        if messagebox.askyesno("Confirmar", f"Eliminar esta carpeta de la lista?\n\n{display}"):
            current_paths.pop(idx)
            refresh_tree()
            update_info()

    def move_up():
        selection = tree.selection()
        if not selection:
            return
        idx = tree.index(selection[0])
        if idx == 0:
            return
        current_paths[idx], current_paths[idx - 1] = current_paths[idx - 1], current_paths[idx]
        refresh_tree()
        # Reseleccionar
        children = tree.get_children()
        if children:
            tree.selection_set(children[idx - 1])

    def move_down():
        selection = tree.selection()
        if not selection:
            return
        idx = tree.index(selection[0])
        if idx >= len(current_paths) - 1:
            return
        current_paths[idx], current_paths[idx + 1] = current_paths[idx + 1], current_paths[idx]
        refresh_tree()
        # Reseleccionar
        children = tree.get_children()
        if children:
            tree.selection_set(children[idx + 1])

    ttk.Button(action_frame, text="Agregar...", command=add_folder, width=12).pack(pady=2)
    ttk.Button(action_frame, text="Editar...", command=edit_selected, width=12).pack(pady=2)
    ttk.Button(action_frame, text="Eliminar", command=remove_selected, width=12).pack(pady=2)
    ttk.Separator(action_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
    ttk.Button(action_frame, text="Subir", command=move_up, width=12).pack(pady=2)
    ttk.Button(action_frame, text="Bajar", command=move_down, width=12).pack(pady=2)

    # Doble click para editar
    tree.bind("<Double-1>", lambda e: edit_selected())

    # Separador
    ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

    # Botones de diálogo
    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill=tk.X)

    def save_and_close():
        if not current_paths:
            messagebox.showwarning("Aviso", "Debes agregar al menos una carpeta.")
            return

        set_alembic_paths(config, current_paths)
        save_config(config)
        dialog.destroy()
        on_save(current_paths)
        messagebox.showinfo("Exito", f"Configuracion guardada.\n{len(current_paths)} carpeta(s) configurada(s).")

    ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    ttk.Button(btn_frame, text="Guardar y Recargar", command=save_and_close).pack(side=tk.RIGHT, padx=5)

    # Info de carpetas
    info_label = ttk.Label(
        btn_frame,
        text=f"{len(current_paths)} carpeta(s) configurada(s)",
        foreground="blue",
    )
    info_label.pack(side=tk.LEFT)

    def update_info():
        info_label.config(text=f"{len(current_paths)} carpeta(s) configurada(s)")

    dialog.bind("<Escape>", lambda e: dialog.destroy())


def _ask_alias(parent: tk.Toplevel, default_name: str, current_alias: str = "") -> str | None:
    """Muestra un diálogo para pedir el alias de una carpeta."""
    result = [current_alias]  # Usamos lista para poder modificar desde el closure

    popup = tk.Toplevel(parent)
    popup.title("Alias de carpeta")
    popup.geometry("400x180")
    popup.transient(parent)
    popup.grab_set()

    # Centrar
    popup.geometry(f"+{parent.winfo_x() + 100}+{parent.winfo_y() + 100}")

    frame = ttk.Frame(popup, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=f"Carpeta: {default_name}", font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W)
    ttk.Label(frame, text="Alias (dejar vacio para usar el nombre de la carpeta):").pack(anchor=tk.W, pady=(10, 5))

    alias_var = tk.StringVar(value=current_alias)
    entry = ttk.Entry(frame, textvariable=alias_var, width=40)
    entry.pack(fill=tk.X)
    entry.focus_set()
    entry.select_range(0, tk.END)

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(pady=(15, 0))

    def on_ok():
        result[0] = alias_var.get().strip()
        popup.destroy()

    def on_cancel():
        result[0] = current_alias  # Mantener el valor original
        popup.destroy()

    entry.bind("<Return>", lambda e: on_ok())
    popup.bind("<Escape>", lambda e: on_cancel())

    ttk.Button(btn_frame, text="Aceptar", command=on_ok).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancelar", command=on_cancel).pack(side=tk.LEFT, padx=5)

    popup.wait_window()
    return result[0]


def show_color_config_dialog(parent: tk.Tk, config: dict, on_apply: Callable, on_save: Callable):
    """Muestra el diálogo de configuración de colores."""
    dialog = tk.Toplevel(parent)
    dialog.title("Configuración de Colores")
    dialog.transient(parent)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Personalizar colores del grafo", font=("TkDefaultFont", 14, "bold")).pack(
        anchor=tk.W, pady=(0, 15)
    )

    colors_frame = ttk.Frame(main_frame)
    colors_frame.pack(fill=tk.BOTH, expand=True)

    current_colors = get_colors(config)
    color_vars: dict[str, tk.StringVar] = {}
    color_previews: dict[str, tk.Canvas] = {}

    def pick_color(key: str):
        current = color_vars[key].get()
        result = colorchooser.askcolor(color=current, title=f"Elegir color: {COLOR_LABELS[key]}")
        if result[1]:
            color_vars[key].set(result[1])
            color_previews[key].configure(bg=result[1])

    for i, (key, label) in enumerate(COLOR_LABELS.items()):
        ttk.Label(colors_frame, text=label, anchor=tk.W).grid(row=i, column=0, sticky=tk.W, padx=(0, 15), pady=4)

        color_vars[key] = tk.StringVar(value=current_colors.get(key, DEFAULT_COLORS[key]))

        preview = tk.Canvas(
            colors_frame,
            width=35,
            height=22,
            highlightthickness=1,
            highlightbackground="#999",
            bg=color_vars[key].get(),
        )
        preview.grid(row=i, column=1, padx=(0, 8), pady=4)
        color_previews[key] = preview

        entry = ttk.Entry(colors_frame, textvariable=color_vars[key], width=10)
        entry.grid(row=i, column=2, padx=(0, 8), pady=4)

        def update_preview(var_key=key):
            try:
                color_previews[var_key].configure(bg=color_vars[var_key].get())
            except tk.TclError:
                pass

        color_vars[key].trace_add("write", lambda *args, k=key: update_preview(k))

        ttk.Button(colors_frame, text="Elegir...", width=8, command=lambda k=key: pick_color(k)).grid(
            row=i, column=3, pady=4
        )

    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill=tk.X, pady=(15, 0))

    def reset_colors():
        for key, default_val in DEFAULT_COLORS.items():
            color_vars[key].set(default_val)
            color_previews[key].configure(bg=default_val)

    def apply_colors():
        colors = {key: var.get() for key, var in color_vars.items()}
        on_apply(colors)

    def save_and_close():
        colors = {key: var.get() for key, var in color_vars.items()}
        config["colors"] = colors
        save_config(config)
        on_save(colors)
        dialog.destroy()
        messagebox.showinfo("Éxito", "Colores guardados correctamente.")

    ttk.Separator(btn_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))

    buttons_container = ttk.Frame(btn_frame)
    buttons_container.pack()

    ttk.Button(buttons_container, text="Restablecer", command=reset_colors).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_container, text="Aplicar", command=apply_colors).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_container, text="Cancelar", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_container, text="Guardar", command=save_and_close).pack(side=tk.LEFT, padx=5)

    dialog.bind("<Escape>", lambda e: dialog.destroy())

    dialog.update_idletasks()
    dialog.minsize(dialog.winfo_width(), dialog.winfo_height())

    x = parent.winfo_x() + (parent.winfo_width() - dialog.winfo_width()) // 2
    y = parent.winfo_y() + (parent.winfo_height() - dialog.winfo_height()) // 2
    dialog.geometry(f"+{x}+{y}")

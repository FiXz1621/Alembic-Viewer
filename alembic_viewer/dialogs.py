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
    dialog.geometry("650x400")
    dialog.resizable(True, True)
    dialog.transient(parent)
    dialog.grab_set()

    # Centrar en la ventana principal
    x = parent.winfo_x() + (parent.winfo_width() - 650) // 2
    y = parent.winfo_y() + (parent.winfo_height() - 400) // 2
    dialog.geometry(f"+{x}+{y}")

    frame = ttk.Frame(dialog, padding=15)
    frame.pack(fill=tk.BOTH, expand=True)

    # Título
    ttk.Label(
        frame, text="Carpetas de Versiones", font=("TkDefaultFont", 12, "bold")
    ).pack(anchor=tk.W, pady=(0, 5))

    ttk.Label(
        frame,
        text="Agrega las carpetas que contienen los archivos de migraciones (.py).",
        foreground="gray",
    ).pack(anchor=tk.W, pady=(0, 10))

    # Frame para la lista
    list_frame = ttk.Frame(frame)
    list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Listbox con scrollbar
    listbox_frame = ttk.Frame(list_frame)
    listbox_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(listbox_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    paths_listbox = tk.Listbox(
        listbox_frame,
        height=10,
        selectmode=tk.SINGLE,
        yscrollcommand=scrollbar.set,
        font=("TkDefaultFont", 10),
    )
    paths_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=paths_listbox.yview)

    # Cargar paths existentes
    current_paths = get_alembic_paths(config).copy()
    for path in current_paths:
        paths_listbox.insert(tk.END, path)

    # Botones de acción para la lista
    action_frame = ttk.Frame(list_frame)
    action_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

    def add_folder():
        folder = filedialog.askdirectory(
            title="Seleccionar carpeta de Alembic",
            initialdir=Path.home(),
        )
        if folder:
            # Verificar que no esté duplicada
            if folder in current_paths:
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

            current_paths.append(folder)
            paths_listbox.insert(tk.END, folder)

    def remove_selected():
        selection = paths_listbox.curselection()
        if not selection:
            messagebox.showinfo("Info", "Selecciona una carpeta para eliminar.")
            return

        idx = selection[0]
        path = paths_listbox.get(idx)

        if messagebox.askyesno("Confirmar", f"Eliminar esta carpeta de la lista?\n\n{path}"):
            paths_listbox.delete(idx)
            current_paths.remove(path)

    def move_up():
        selection = paths_listbox.curselection()
        if not selection or selection[0] == 0:
            return
        idx = selection[0]
        path = current_paths.pop(idx)
        current_paths.insert(idx - 1, path)
        paths_listbox.delete(0, tk.END)
        for p in current_paths:
            paths_listbox.insert(tk.END, p)
        paths_listbox.selection_set(idx - 1)

    def move_down():
        selection = paths_listbox.curselection()
        if not selection or selection[0] >= len(current_paths) - 1:
            return
        idx = selection[0]
        path = current_paths.pop(idx)
        current_paths.insert(idx + 1, path)
        paths_listbox.delete(0, tk.END)
        for p in current_paths:
            paths_listbox.insert(tk.END, p)
        paths_listbox.selection_set(idx + 1)

    ttk.Button(action_frame, text="Agregar...", command=add_folder, width=12).pack(pady=2)
    ttk.Button(action_frame, text="Eliminar", command=remove_selected, width=12).pack(pady=2)
    ttk.Separator(action_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
    ttk.Button(action_frame, text="Subir", command=move_up, width=12).pack(pady=2)
    ttk.Button(action_frame, text="Bajar", command=move_down, width=12).pack(pady=2)

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

    def update_info(*args):
        info_label.config(text=f"{len(current_paths)} carpeta(s) configurada(s)")

    # Actualizar contador cuando cambie la lista
    paths_listbox.bind("<<ListboxSelect>>", update_info)

    dialog.bind("<Escape>", lambda e: dialog.destroy())


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

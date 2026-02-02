"""Diálogos de configuración para el visor de Alembic."""

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from alembic_viewer.config import COLOR_LABELS, DEFAULT_COLORS, get_colors, save_config

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


def show_config_dialog(parent: tk.Tk, alembic_path: Path, config: dict, on_save: Callable):
    """Muestra el diálogo de configuración de rutas."""
    dialog = tk.Toplevel(parent)
    dialog.title("Configuración")
    dialog.geometry("600x200")
    dialog.resizable(False, False)
    dialog.transient(parent)
    dialog.grab_set()

    dialog.geometry(f"+{parent.winfo_x() + 100}+{parent.winfo_y() + 100}")

    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="Carpeta de Alembic:", font=("TkDefaultFont", 10, "bold")).grid(
        row=0, column=0, sticky=tk.W, pady=(0, 5)
    )

    path_var = tk.StringVar(value=str(alembic_path))
    path_entry = ttk.Entry(frame, textvariable=path_var, width=60)
    path_entry.grid(row=1, column=0, sticky=tk.EW, padx=(0, 5))

    def browse_folder():
        folder = filedialog.askdirectory(
            title="Seleccionar carpeta de Alembic",
            initialdir=alembic_path if alembic_path.exists() else Path.home(),
        )
        if folder:
            path_var.set(folder)

    ttk.Button(frame, text="Explorar...", command=browse_folder).grid(row=1, column=1, padx=(5, 0))

    info_label = ttk.Label(
        frame,
        text="La carpeta debe contener subcarpetas como 'delfos_versions' y 'tenant_versions'.",
        foreground="gray",
    )
    info_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))

    current_label = ttk.Label(frame, text=f"Ruta actual: {alembic_path}", foreground="blue")
    current_label.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=4, column=0, columnspan=2, pady=(20, 0))

    def save_and_reload():
        new_path = Path(path_var.get())
        if not new_path.exists():
            messagebox.showerror("Error", f"La carpeta no existe:\n{new_path}")
            return

        has_versions = any(
            [
                (new_path / "delfos_versions").exists(),
                (new_path / "tenant_versions").exists(),
                (new_path / "versions").exists(),
            ]
        )

        if not has_versions:
            if not messagebox.askyesno(
                "Advertencia",
                "No se encontraron carpetas de versiones (delfos_versions, tenant_versions).\n"
                "¿Continuar de todos modos?",
            ):
                return

        config["alembic_path"] = str(new_path)
        save_config(config)

        dialog.destroy()
        on_save(new_path)
        messagebox.showinfo("Éxito", f"Configuración guardada.\nUsando: {new_path}")

    def reset_to_default():
        default_path = Path(__file__).parent.parent / "alembic"
        path_var.set(str(default_path))

    ttk.Button(btn_frame, text="Restablecer", command=reset_to_default).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Guardar y Recargar", command=save_and_reload).pack(side=tk.LEFT, padx=5)

    frame.columnconfigure(0, weight=1)


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

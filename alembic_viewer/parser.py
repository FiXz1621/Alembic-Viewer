"""Parser de archivos de migración de Alembic."""

import re
from collections import defaultdict
from pathlib import Path

from alembic_viewer.models import Migration


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
            r"^down_revision:\s*(?:Union\[str,\s*None\]\s*=|str\s*=|=)\s*(.+?)$", content, re.MULTILINE
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
            is_merge=is_merge,
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

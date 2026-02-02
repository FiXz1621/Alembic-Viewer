# Alembic Viewer

Desktop application to visualize Alembic migration graphs with an interactive GUI.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Features

- 📊 **Graph visualization** of Alembic migrations
- 🔍 **Search** by revision ID or message (fuzzy matching)
- 📅 **Date filtering** with calendar picker
- 🎨 **Color-coded nodes**: HEAD (purple), ROOT (yellow), MERGE (orange)
- 🔗 **Relationship highlighting**: Parents (dark green) and children (light green)
- 📝 **Code preview** with syntax highlighting
- ⚙️ **Configurable paths** (CLI, config file, or UI dialog)
- 🖱️ **Pan & zoom** with mouse/trackpad

## Installation

### From source (development)

```bash
# Clone the repository
git clone <repo-url>
cd alembic_viewer

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Dependencies

- Python 3.10+
- tkinter (usually included with Python)
- tkcalendar

## Usage

### Run directly

```bash
python alembic_viewer.py --path /path/to/your/alembic/project
```

### As installed package

```bash
alembic-viewer --path /path/to/your/alembic/project
```

### Without arguments

The app will:
1. Check for saved path in `~/.alembic_viewer_config.json`
2. Look for `alembic/` folder in current directory
3. Open a folder selection dialog

## Building executables

Create a standalone executable (no Python required):

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Build for current platform
pyinstaller --onefile --windowed --name "AlembicViewer" alembic_viewer.py
```

The executable will be in `dist/AlembicViewer`.

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd/Ctrl + F` | Focus search field |
| `Enter` | Search / Next result |
| `Escape` | Deselect node / Close dialogs |
| `Scroll` | Zoom in/out |
| `Drag` | Pan the graph |

## Configuration

Settings are saved in `~/.alembic_viewer_config.json`:

```json
{
    "alembic_path": "/path/to/your/project"
}
```

## License

MIT License

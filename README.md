# Alembic Viewer

Desktop application to visualize Alembic migration graphs with an interactive GUI.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)

## Features

### 📊 Graph Visualization
- Interactive graph visualization of Alembic migration history
- **Color-coded nodes** by type:
  - 🟣 **HEAD** (purple) - Migrations without children
  - 🟡 **ROOT** (yellow) - Initial migrations without parents
  - 🟠 **MERGE** (orange) - Merge migrations with multiple parents
  - 🔵 **Normal** (blue) - Standard migrations
- Visual highlighting of parent/child relationships when selecting a node

### 🔍 Search & Navigation
- **Fuzzy search** by revision ID or commit message
- Navigate between multiple search results with ◀ ▶ buttons
- Click to select nodes, double-click to open the migration file
- Pan & zoom with mouse/trackpad

### 📅 Date Filtering
- Filter migrations by date range
- Interactive calendar picker (requires tkcalendar)
- Visual indicator when filter is active

### 🎨 Customizable Colors
- Configure all graph colors via UI (Settings → Graph Colors)
- Colors are persisted in configuration file
- Live preview before saving

### 📝 Migration Details
- **Info tab**: Revision ID, message, filename, date, parents & children
- **Code tab**: Full source code preview with dark theme

### ⚙️ Multiple Configuration Options
- Command-line argument: `--path /path/to/alembic`
- Persistent configuration file
- UI dialog for folder selection

## Installation

### Using uv (recommended)

```bash
# Clone the repository
git clone https://github.com/FiXz1621/Alembic-Viewer.git
cd Alembic-Viewer

# Install with uv
uv sync

# Run
uv run alembic_viewer.py
```

### Using pip

```bash
# Clone the repository
git clone https://github.com/FiXz1621/Alembic-Viewer.git
cd Alembic-Viewer

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install
pip install -e .

# Run
alembic-viewer
```

### Pre-built Binaries

Download the latest release for your platform from the [Releases](https://github.com/FiXz1621/Alembic-Viewer/releases) page:
- **macOS**: `AlembicViewer-macOS.dmg`
- **Windows**: `AlembicViewer.exe`

## Usage

### Run from source

```bash
# With uv
uv run alembic_viewer.py --path /path/to/your/alembic

# With pip install
alembic-viewer --path /path/to/your/alembic

# As module
python -m alembic_viewer --path /path/to/your/alembic
```

### Without arguments

The app will:
1. Check for saved path in `~/.alembic_viewer_config.json`
2. Look for `alembic/` folder relative to the script
3. Prompt you to select a folder via UI

## Development

### Setup

```bash
uv sync --dev
```

### Commands

```bash
# Run the app
make run

# Lint & format
make lint
make format

# Type checking
make typecheck

# Run tests
make test

# Build executable
make build-exe
```

### Project Structure

```
alembic_viewer/
├── __init__.py       # Package exports
├── __main__.py       # Entry point (python -m alembic_viewer)
├── models.py         # Migration, NodePosition dataclasses
├── config.py         # Colors, configuration load/save
├── parser.py         # Migration file parsing
├── canvas.py         # GraphCanvas visualization
├── dialogs.py        # Configuration dialogs
└── app.py            # Main AlembicViewerApp class
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd/Ctrl + F` | Focus search field |
| `Enter` | Search / Next result |
| `◀ / ▶` | Navigate search results |
| `Escape` | Deselect node / Close dialogs |
| `Scroll` | Zoom in/out |
| `Drag` | Pan the graph |
| `Double-click` | Open migration file in editor |

## Configuration

Settings are saved in `~/.alembic_viewer_config.json`:

```json
{
  "alembic_path": "/path/to/your/project/alembic",
  "colors": {
    "node_normal": "#4a90d9",
    "node_head": "#9b59b6",
    "node_root": "#f1c40f",
    "node_merge": "#e67e22",
    "node_selected": "#2ecc71",
    "edge_normal": "#7f8c8d",
    "background": "#ecf0f1"
  }
}
```

## Building Executables

### macOS (.app bundle)

```bash
uv run pyinstaller --noconfirm AlembicViewer.spec
# Output: dist/AlembicViewer.app
```

### Windows (.exe)

```bash
uv run pyinstaller --onefile --windowed --name AlembicViewer --icon=alembic_viewer.ico alembic_viewer.py
# Output: dist/AlembicViewer.exe
```

## License

MIT License

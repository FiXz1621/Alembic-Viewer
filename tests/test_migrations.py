"""Tests for migration parsing functionality."""

from pathlib import Path

from alembic_viewer.models import Migration
from alembic_viewer.parser import build_graph_structure, parse_migration_file


class TestParseMigrationFile:
    """Tests for parse_migration_file function."""

    def test_parse_simple_migration(self, tmp_path: Path):
        """Test parsing a simple migration file."""
        content = '''"""Add users table

Revision ID: abc123
Revises:
Create Date: 2024-01-15 10:30:00.000000

"""
revision: str = "abc123"
down_revision: str = None

def upgrade():
    pass

def downgrade():
    pass
'''
        filepath = tmp_path / "abc123_add_users.py"
        filepath.write_text(content)

        migration = parse_migration_file(filepath)

        assert migration is not None
        assert migration.revision == "abc123"
        assert migration.down_revision is None
        assert "Add users table" in migration.message
        assert migration.is_merge is False

    def test_parse_migration_with_parent(self, tmp_path: Path):
        """Test parsing a migration with a parent revision."""
        content = '''"""Add posts table

Revision ID: def456
Revises: abc123
Create Date: 2024-01-16 11:00:00.000000

"""
revision: str = "def456"
down_revision: str = "abc123"

def upgrade():
    pass
'''
        filepath = tmp_path / "def456_add_posts.py"
        filepath.write_text(content)

        migration = parse_migration_file(filepath)

        assert migration is not None
        assert migration.revision == "def456"
        assert migration.down_revision == "abc123"
        assert migration.is_merge is False

    def test_parse_merge_migration(self, tmp_path: Path):
        """Test parsing a merge migration."""
        content = '''"""Merge branches

Revision ID: merge123
Revises:
Create Date: 2024-01-17 12:00:00.000000

"""
revision: str = "merge123"
down_revision = ("branch1", "branch2")

def upgrade():
    pass
'''
        filepath = tmp_path / "merge123_merge.py"
        filepath.write_text(content)

        migration = parse_migration_file(filepath)

        assert migration is not None
        assert migration.revision == "merge123"
        assert migration.down_revision == ("branch1", "branch2")
        assert migration.is_merge is True

    def test_parse_invalid_file(self, tmp_path: Path):
        """Test parsing an invalid migration file."""
        content = "# This is not a valid migration file"
        filepath = tmp_path / "invalid.py"
        filepath.write_text(content)

        migration = parse_migration_file(filepath)

        assert migration is None


class TestBuildGraphStructure:
    """Tests for build_graph_structure function."""

    def test_empty_migrations(self):
        """Test with empty migrations dict."""
        children, parents = build_graph_structure({})
        assert children == {}
        assert parents == {}

    def test_single_root_migration(self):
        """Test with a single root migration."""
        migrations = {
            "abc123": Migration(revision="abc123", down_revision=None, message="Initial", filename="abc123.py")
        }

        children, parents = build_graph_structure(migrations)

        assert parents.get("abc123", []) == []

    def test_linear_chain(self):
        """Test with a linear chain of migrations."""
        migrations = {
            "rev1": Migration(revision="rev1", down_revision=None, message="First", filename="1.py"),
            "rev2": Migration(revision="rev2", down_revision="rev1", message="Second", filename="2.py"),
            "rev3": Migration(revision="rev3", down_revision="rev2", message="Third", filename="3.py"),
        }

        children, parents = build_graph_structure(migrations)

        assert "rev2" in children.get("rev1", [])
        assert "rev3" in children.get("rev2", [])
        assert parents.get("rev2") == ["rev1"]
        assert parents.get("rev3") == ["rev2"]

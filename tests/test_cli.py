"""Tests for CLI module (argument parsing only — no actual dispatch)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vorlix_cli.main import VERSION


class TestCLI:
    def test_version_string(self):
        assert VERSION == "Vorlix 1.0.0-beta.4", f"Unexpected version: {VERSION}"

    def test_import_main(self):
        """Verify the main module can be imported without errors."""
        from vorlix_cli import main
        assert main is not None

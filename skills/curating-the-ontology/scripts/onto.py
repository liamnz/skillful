# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6", "jsonschema>=4"]
# ///
"""Entry point for the curating-the-ontology CLI.

Run with `uv run --script <skill>/scripts/onto.py --help`. This file only makes the
sibling `ontokit` package importable, wherever the skill directory was copied to,
and hands over to it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ontokit.cli import main

if __name__ == "__main__":
    sys.exit(main())

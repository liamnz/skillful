Host project for tests/test_isolation.py: its pyproject.toml, uv.lock and .venv must
survive every onto.py command byte-identical. The test creates a stand-in .venv at run time
(this repository ignores .venv directories).

"""T26: the skill never touches the host project's Python environment.

Every command runs via `uv run --script`, which uses the script's own inline metadata and
ignores the project, so a host's pyproject.toml, uv.lock and .venv stay byte-identical and
no new environment files appear.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ontotest import BASELINE, FIXTURES, SKILL_DIR, commit_all, git, run_onto

HOST = FIXTURES / "host-project"
ENVIRONMENT = ("pyproject.toml", "uv.lock", ".venv")


def environment_snapshot(project: Path) -> dict[str, bytes]:
    files = {}
    for name in ENVIRONMENT:
        path = project / name
        items = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
        files |= {p.relative_to(project).as_posix(): p.read_bytes() for p in items}
    return files


def host_project(tmp_path: Path) -> Path:
    project = tmp_path / "host"
    shutil.copytree(HOST, project, ignore=shutil.ignore_patterns("README.md"))
    shutil.copytree(BASELINE, project, dirs_exist_ok=True, ignore=shutil.ignore_patterns("README.md"))
    venv = project / ".venv"
    (venv / "Lib" / "site-packages").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /nonexistent/python\nversion = 3.10.0\n", encoding="utf-8")
    (venv / "Lib" / "site-packages" / "host_marker.py").write_text("# untouched\n", encoding="utf-8")
    shutil.copytree(
        SKILL_DIR, project / ".agents" / "skills" / SKILL_DIR.name, ignore=shutil.ignore_patterns("__pycache__")
    )
    git(project, "init", "-q")
    commit_all(project, "host project")
    return project


def test_every_command_leaves_the_host_environment_alone(tmp_path: Path) -> None:
    project = host_project(tmp_path)
    script = project / ".agents" / "skills" / SKILL_DIR.name / "scripts" / "onto.py"
    before = environment_snapshot(project)
    assert set(before) == {"pyproject.toml", "uv.lock", ".venv/pyvenv.cfg", ".venv/Lib/site-packages/host_marker.py"}
    top_level = {p.name for p in project.iterdir()}

    commands = [
        ["--version"],
        ["init", "--root", "docs/other", "--no-agents-md", "--no-gitattributes"],
        ["validate", "--json"],
        ["vocab", "list"],
        ["vocab", "new", "kind", "rule", "--rationale", "Policies recur."],
        ["new", "refund", "--name", "Refund", "--kind", "event"],
        ["impact", "--base", "HEAD"],
        ["review", "customer"],
        ["build"],
        ["build", "--check"],
    ]
    for command in commands:
        result = run_onto(command, cwd=project, script=script)
        assert result.returncode == 0, f"{command}: {result.stderr}"

    assert environment_snapshot(project) == before, "pyproject.toml, uv.lock and .venv are byte-identical"
    assert {p.name for p in project.iterdir()} == top_level, "no new environment files at the project root"
    status = git(project, "status", "--porcelain", "--", *ENVIRONMENT)
    assert status == ""

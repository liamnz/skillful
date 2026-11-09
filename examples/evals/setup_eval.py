# /// script
# requires-python = ">=3.11"
# ///
"""Make a throwaway copy of the sample project for one Cursor eval scenario.

    uv run examples/evals/setup_eval.py <scenario> [destination]

<scenario> is a letter from a to f (see examples/evals.md). The destination defaults to
~/ontology-evals/scenario-<letter> and must not exist yet. The copy is its own git
repository (branch `main`, then a working branch `eval-<letter>`), with the skill in
.cursor/skills/ and the AGENTS.md pointer installed, so it behaves like a real project.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SAMPLE = REPO / "examples" / "sample-project"
SKILL = REPO / "skills" / "curating-the-ontology"
SCENARIOS = "abcdef"
SETUP_IDENTITY = ["-c", "user.name=Eval setup", "-c", "user.email=eval-setup@example.invalid"]

# Scenario (c): deliberate mud across several criteria, committed before the eval starts.
MUD = {
    "docs/ontology/concepts/plan-price.yaml": (
        "  What a subscriber is charged for one billing interval of a subscription\n"
        "  plan, before any promotional discount.\n",
        "  What a subscriber pays per interval.\n",
    ),
    "docs/ontology/concepts/order-amount.yaml": (
        "  The total charged for an order after discounts and before any refunds,\n  in the shop's currency.\n",
        "  The amount column of fct_orders, after discounts and before any refunds,\n  in the shop's currency.\n",
    ),
    "docs/ontology/concepts/order-line.yaml": (
        "relations:\n",
        'discouraged_terms:\n  - {term: basket, note: "Warehouse team"}\nrelations:\n',
    ),
}
MUD_DELETE = ["models/legacy/dim_client.sql"]


def run(cmd: list[str], cwd: Path) -> None:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        sys.exit(f"failed: {' '.join(cmd)}\n{result.stdout}{result.stderr}")


def onto(dest: Path, *args: str) -> None:
    script = dest / ".cursor" / "skills" / SKILL.name / "scripts" / "onto.py"
    run(["uv", "run", "--script", str(script), *args], dest)


def commit(dest: Path, message: str) -> None:
    run(["git", "add", "-A"], dest)
    run(["git", *SETUP_IDENTITY, "commit", "-q", "-m", message], dest)


def apply_mud(dest: Path) -> None:
    for rel, (old, new) in MUD.items():
        path = dest / rel
        text = path.read_text(encoding="utf-8")
        if old not in text:
            sys.exit(f"scenario c setup is out of date: {rel} no longer contains the expected text")
        path.write_bytes(text.replace(old, new, 1).encode("utf-8"))
    for rel in MUD_DELETE:
        (dest / rel).unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenario", choices=list(SCENARIOS))
    parser.add_argument("destination", nargs="?", type=Path)
    args = parser.parse_args(argv)
    dest = (args.destination or Path.home() / "ontology-evals" / f"scenario-{args.scenario}").resolve()
    if dest.exists():
        sys.exit(f"{dest} already exists; delete it or pass another destination")
    if REPO in dest.parents:
        sys.exit("put the copy outside this repository, so the agent sees only the sample project")

    shutil.copytree(SAMPLE, dest)
    shutil.copytree(SKILL, dest / ".cursor" / "skills" / SKILL.name, ignore=shutil.ignore_patterns("__pycache__"))
    run(["git", "init", "-q", "-b", "main"], dest)
    onto(dest, "init", "--agents-md", "--no-gitattributes")
    commit(dest, "Acme Analytics warehouse")
    if args.scenario == "c":
        apply_mud(dest)
        onto(dest, "build")
        commit(dest, "Assorted model and ontology edits")
    run(["git", "checkout", "-q", "-b", f"eval-{args.scenario}"], dest)

    print(f"Scenario ({args.scenario}) is ready in {dest}")
    print("Open that folder in Cursor, start a new agent chat, and follow examples/evals.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

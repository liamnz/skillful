"""The only module that runs git.

All paths passed in are relative to the working directory (the project root, where
commands are run), using forward slashes.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class Hunk:
    removed: tuple[int, ...]  # line numbers in the old version
    added: tuple[int, ...]  # line numbers in the new version


@dataclass
class Git:
    """A git repository, queried from the working directory `cwd`."""

    cwd: Path
    _cache: dict[tuple[str, ...], str | None] = field(default_factory=dict, repr=False)

    @classmethod
    def discover(cls, cwd: Path | None = None) -> Git | None:
        """The repository containing cwd, or None outside git or before the first commit."""
        repo = cls(cwd or Path.cwd())
        if repo._run("rev-parse", "--is-inside-work-tree") != "true":
            return None
        if repo.head() is None:
            return None
        return repo

    def _run(self, *args: str) -> str | None:
        """stdout of a git command, or None if it fails. Results are cached per run."""
        if args in self._cache:
            return self._cache[args]
        try:
            result = subprocess.run(
                ["git", "-c", "core.quotepath=false", *args],
                cwd=self.cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
            )
        except FileNotFoundError:  # git not installed
            output = None
        else:
            output = result.stdout.rstrip("\n") if result.returncode == 0 else None
        self._cache[args] = output
        return output

    def head(self) -> str | None:
        return self._run("rev-parse", "--verify", "--quiet", "HEAD")

    def is_reachable(self, commit: str) -> bool:
        """True if `commit` exists and is an ancestor of (or equal to) HEAD."""
        full = self._run("rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")
        if full is None:
            return False
        return self._run("merge-base", "--is-ancestor", full, "HEAD") is not None

    def last_commit(self, path: str) -> str | None:
        """The last commit that touched `path`, or None if it was never committed."""
        return self._run("log", "-1", "--format=%H", "--", path) or None

    def commit_date(self, commit: str) -> str | None:
        """Committer date of `commit` in strict ISO 8601."""
        return self._run("log", "-1", "--format=%cI", commit) or None

    def first_commit_date(self, path: str, line_pattern: str | None = None) -> str | None:
        """Committer date (ISO 8601) of the first commit that added `path`, or None if never committed.

        With `line_pattern` (a regex), the first commit whose diff of `path` adds or removes a
        line matching it: for example when an entry was added to a shared file.
        """
        args = ["log", "--reverse", "--format=%cI"]
        if line_pattern is not None:
            args.append(f"-G{line_pattern}")
        output = self._run(*args, "--", path)
        return output.splitlines()[0] if output else None

    def merge_base(self, ref: str) -> str | None:
        return self._run("merge-base", ref, "HEAD")

    def ref_exists(self, ref: str) -> bool:
        return self._run("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}") is not None

    def default_branch(self) -> str | None:
        """origin's default branch if known, else a local main or master; None if it can't be told."""
        remote = self._run("symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
        if remote:
            return remote
        return next((b for b in ("main", "master") if self.ref_exists(f"refs/heads/{b}")), None)

    def changed_files(self, base: str) -> list[str]:
        """Files changed since `base` (committed since the merge-base, staged, unstaged and untracked).

        Paths are relative to the working directory, and only files under it are listed.
        """
        outputs = [
            self._run("diff", "--name-only", "--relative", "--no-renames", f"{base}...HEAD"),
            self._run("diff", "--name-only", "--relative", "--no-renames", "HEAD"),
            self._run("ls-files", "--others", "--exclude-standard"),
        ]
        return sorted({line for output in outputs if output for line in output.splitlines() if line})

    def short(self, commit: str) -> str:
        return self._run("rev-parse", "--short", commit) or commit[:7]

    def has_uncommitted_changes(self, path: str) -> bool:
        """True if `path` differs from HEAD in the index or working tree, or is untracked."""
        status = self._run("status", "--porcelain", "--untracked-files=all", "--", path)
        return bool(status)

    def show(self, commit: str, path: str) -> str:
        """Content of `path` at `commit`, or '' if it did not exist there."""
        return self._run("show", f"{commit}:./{path}") or ""

    def diff_hunks(self, base: str, path: str) -> list[Hunk]:
        """Changed lines in `path` between `base` and the working tree (committed + uncommitted)."""
        diff = self._run("diff", "--no-color", "--no-ext-diff", "-U0", base, "--", path)
        if not diff:
            return []
        hunks: list[Hunk] = []
        for line in diff.splitlines():
            match = _HUNK.match(line)
            if not match:
                continue
            old_start, old_len, new_start, new_len = match.groups()
            old_count = 1 if old_len is None else int(old_len)
            new_count = 1 if new_len is None else int(new_len)
            hunks.append(
                Hunk(
                    removed=tuple(range(int(old_start), int(old_start) + old_count)),
                    added=tuple(range(int(new_start), int(new_start) + new_count)),
                )
            )
        return hunks

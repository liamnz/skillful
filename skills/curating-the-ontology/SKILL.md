---
name: curating-the-ontology
description: >-
  Curates a human-owned domain ontology kept in docs/ontology/: proposes new or
  changed domain concepts at the end of coding tasks, critiques human-written
  definitions against the code, runs health checks for consistency and drift, and
  builds an interactive HTML graph of the concepts. Use when working in a repo that
  has docs/ontology/, when a task introduces or changes domain terms, data models,
  metrics or business rules, or when the user mentions the ontology, domain
  concepts, glossary, definitions, terminology or what a domain term means.
compatibility: Requires git and uv (uv provides Python 3.11+ and script dependencies).
metadata:
  version: "0.1.0"
---

# Curating the ontology

> Work in progress. The full workflow, hard rules and references are written in a
> later task. Until then, this skill is not ready for use.

Run the CLI from the project root, where `$SKILL` is the directory containing this
`SKILL.md`:

```bash
uv run --script $SKILL/scripts/onto.py --help
```

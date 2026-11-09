<!-- curating-the-ontology:start (maintained by `onto.py init --agents-md`; edits inside these markers are replaced) -->
## Domain ontology

This repository keeps a human-owned domain ontology in `{{root}}/`: one YAML file per
concept, each with a definition written by a person, and a generated view in
`{{root}}/index.html`.

- Use the canonical concept names from the ontology in code, docs and conversation.
  If someone uses a discouraged term, say which concept it maps to, then use the canonical name.
- At the end of any task that changed code, follow the `curating-the-ontology` skill:
  propose at most three new or changed concepts, and create nothing without the user's consent.
- Never write or change a definition, or mark a concept `defined`, on your own. Definitions are the humans' to write.
<!-- curating-the-ontology:end -->

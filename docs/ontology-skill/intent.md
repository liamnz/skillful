# Intent: `curating-the-ontology` skill

*Confirmed 2026-11-08 via an interview-me session.*

## Problem

As the data team adopts agentic coding, humans puzzle through less of the domain themselves and build weaker mental models of it. This skill counters that by turning the mental model into an explicit, documented ontology that lives in the repo. It is inspired by Gruber's definition of an ontology as "an explicit specification of a conceptualization".

## Statement of intent

- **Outcome:** An AI skill that turns the domain understanding that agentic coding erodes into an explicit ontology in the repo. Humans own the ontology and actively shape it.
- **User:** The data team, working across several project codebases (one ontology per repo), plus the agents working alongside them.
- **Why now:** The team is rolling out agentic coding, and the less people puzzle through themselves, the weaker their mental model of the domain becomes.
- **Human role:** "Soft B." People are nudged to define and revise concepts in their own words. The agent never adds a concept on its own authority. The team is trusted to act with integrity. A visible ontology, muddy parts included, is expected to deepen understanding over time as people notice problems and revise them.
- **Agent role:** While it works, the agent notices new or changed domain concepts and briefly proposes them at the end of a task. It keeps the ontology healthy by flagging inconsistencies, drift between ontology and code, and stale entries. Its rubric is Gruber's five design criteria: clarity, coherence, extendibility, minimal encoding bias, and minimal ontological commitment.
- **Shape:**
  - The source of truth is a set of YAML concept records under `docs/`, written to a fixed schema. They are machine-checkable and stay readable by people.
  - Deterministic scripts build and validate the ontology: `uv run` scripts with inline PEP 723 dependencies. They never touch the project's own dependencies and assume only `git` and `uv`.
  - The human-facing view is a generated, self-contained HTML page with good UI/UX.
  - *Amended 2026-11-08:* The page leads with an interactive relationship graph. Well-designed, interactive visuals are how the skill encourages people to use and understand the ontology. Reading lists of terms takes too much effort and would discourage use.
  - Validation is part of the skill as a health check that the agent or a human can run.
- **Success:** Qualitative. The team says they like the ontology and rely on it as a core tool for keeping their understanding of a project codebase. There is no formal assessment and there are no coverage metrics.
- **Out of scope (for now):**
  - Wiring the validator into CI or pre-commit.
  - Formal semantic-web tooling (OWL, RDF, reasoners).
  - Hard gates that block work until concepts are defined.
  - Coverage targets.
  - The agent writing concepts into the ontology without a human taking part.

# Statement of intent: solution architecture skill

Confirmed with the project owner on 2026-11-09. This records what the skill is for. The spec records how it works.

- **Outcome:** A self-contained, drop-in skill that keeps human and agent aligned on how the solution is designed to meet its spec, through a living **target architecture** that changes only by deliberate decision.
- **User:** Python data team members working with agents across requests, analyses, pipelines, warehousing, reporting and dashboards. They need no formal architecture training, so the skill and its agent supply that expertise.
- **Why now:** Letting agents steer produced meandering, path-dependent designs that the human lost their grip on, and a long ARCHITECTURE.md with basic mermaid diagrams is too demanding to learn from.
- **Roles:** The spec is an existing input that defines the need. Human and agent co-design the shape of the solution. The human has the final say on every target change. The agent handles detail inside the components and shows that the design is up to the job.
- **What it holds:** One architecture per repo, at whiteboard level: the main components, their responsibilities, their real connections, the key decisions and reasons behind them, and each component's build status. A standard set of architecture views (such as data, runtime and deployment) attach to the components, and a project uses only those it needs. Its language fits an analysis as well as a pipeline, and depth scales with the work.
- **How it's used:**
  - At **planning**, ask whether the work fits the target or the target must change first.
  - At **merge**, ask whether the branch honoured the target and whether anything learned should change it.
  - Keep "absent" (not built yet) distinct from "off target" (built differently).
- **How it's learned:** A generated, self-contained visual explorer for exploring and learning the design and its decisions, with structured source files behind it.
- **Checking:** A modest tool flags unowned code, components with no code, and disallowed Python imports or dbt references where there is lasting code. Projects may be Python, dbt, or a hybrid of both. The agent judges whether a branch truly honoured the design and shows that judgement to the human.
- **Success:** With the agent switched off, the human can sketch the system from memory, predict where a change lands, and spot when an agent's plan breaks the design. The target has a visible record of why each change was made.
- **Constraint:** It stays light enough on a small analysis that people keep using it, follows the ontology skill's packaging discipline (self-contained, harness-neutral, minimal dependencies), and works independently of the ontology skill.
- **Out of scope:**
  - Writing or replacing the spec.
  - Designing the detail inside components.
  - Deep, multi-language code analysis.
  - Repos holding many unrelated analyses.
  - CI or pre-commit wiring.
  - Quick lookups below the floor: a single obvious query where a wrong approach carries little risk.

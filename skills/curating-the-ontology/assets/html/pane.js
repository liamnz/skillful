// Concept detail pane. Section headings are the concept file's field names (underscores read as
// spaces), in the file's order; Findings and Incoming relations are the two sections that are not
// fields. Fields that are empty are left out, except an empty definition ("Needs a definition").
(function (root) {
  "use strict";

  const G = root.OntologyGraph;
  const SVG_NS = "http://www.w3.org/2000/svg";

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function svgIcon(size, build) {
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("width", size);
    svg.setAttribute("height", size);
    svg.setAttribute("viewBox", `${-size / 2} ${-size / 2} ${size} ${size}`);
    svg.setAttribute("aria-hidden", "true");
    build(svg);
    return svg;
  }

  function path(d, className) {
    const p = document.createElementNS(SVG_NS, "path");
    p.setAttribute("d", d);
    p.setAttribute("class", className);
    return p;
  }

  // A kind glyph as a small inline icon (legend, pane, list, previews).
  function kindIcon(encoding, proposed) {
    const tokens = getComputedStyle(document.documentElement);
    const g = parseFloat(tokens.getPropertyValue("--node-glyph-size"));
    const slot = encoding.slot === "fallback" ? "k-fallback" : `k${encoding.slot}`;
    return svgIcon(g + 4, (svg) => {
      svg.setAttribute("class", "kind-icon");
      svg.append(path(root.OntologyGraphView.glyphPath(encoding.shape, g), `glyph ${slot}${proposed ? " proposed" : ""}`));
    });
  }

  // A finding badge as an inline icon: severity is read from the symbol; colour only reinforces it.
  function badgeIcon(severity) {
    const tokens = getComputedStyle(document.documentElement);
    const size = parseFloat(tokens.getPropertyValue("--badge-size"));
    const icon = svgIcon(size + 2, (svg) => {
      const disc = document.createElementNS(SVG_NS, "circle");
      disc.setAttribute("r", size / 2);
      disc.setAttribute("class", `badge ${severity}`);
      svg.append(disc, path(root.OntologyGraphView.badgeSymbol(severity, size / 2), "badge-glyph"));
    });
    icon.setAttribute("class", "badge-icon");
    icon.setAttribute("data-severity", severity);
    return icon;
  }

  const SEVERITY_WORD = { error: "error", warn: "warning", info: "info" };

  function heading(text) {
    return el("h3", "", text);
  }

  function list(items, render) {
    const ul = el("ul");
    for (const item of items) {
      const li = el("li");
      render(li, item);
      ul.append(li);
    }
    return ul;
  }

  function shortDate(iso) {
    return iso ? iso.slice(0, 10) : null;
  }

  // ctx: {conceptsById, encodingOf(kind), relationTypes (Map), incoming(id), findings(id),
  //       pathToProject, select(id)}
  function render(container, concept, ctx) {
    container.replaceChildren();
    if (!concept) return;
    const link = (id, label) => {
      const target = ctx.conceptsById.get(id);
      const a = el("a", "concept-link", label || (target ? target.name : id));
      a.href = `#${encodeURIComponent(id)}`;
      a.dataset.id = id;
      a.addEventListener("click", (event) => {
        event.preventDefault();
        ctx.select(id);
      });
      if (target && target.status !== "defined") {
        const span = el("span");
        span.append(a, el("span", "faint", ` (${target.status})`));
        return span;
      }
      return a;
    };

    const meta = el("div", "meta");
    meta.append(kindIcon(ctx.encodingOf(concept.kind), concept.status === "proposed"), `${concept.kind} · ${concept.status}`);
    const title = el("h2", "", concept.name);
    title.id = "pane-title";
    container.append(meta, title, el("div", "id", concept.id));

    const findings = ctx.findings(concept.id);
    if (findings.length) {
      container.append(heading("Findings"));
      container.append(
        list(findings, (li, f) => {
          li.className = "finding";
          const text = el("span");
          text.append(el("span", "code", [f.code, f.criterion].filter(Boolean).join(" · ")), el("br"), f.message);
          li.append(badgeIcon(f.severity), text);
          li.setAttribute("aria-label", `${SEVERITY_WORD[f.severity]} ${f.code}`);
        }),
      );
    }

    container.append(heading("Definition"));
    if (concept.definition) {
      container.append(el("p", "definition", concept.definition));
    } else {
      const needs = el("div", "needs");
      needs.append(
        el("strong", "", "Needs a definition."),
        ` Nobody has defined this concept yet. Write it in your own words in `,
        el("code", "", `concepts/${concept.id}.yaml`),
        ", then set ",
        el("code", "", "status: defined"),
        ".",
      );
      container.append(needs);
    }

    if (concept.discouraged_terms.length) {
      container.append(heading("Discouraged terms"));
      container.append(
        list(concept.discouraged_terms, (li, term) => {
          li.append(el("span", "term", term.term));
          if (term.note) li.append(el("span", "muted", ` — ${term.note}`));
        }),
      );
    }
    for (const [field, title, className] of [
      ["examples", "Examples", ""],
      ["non_examples", "Non examples", "muted"],
      ["rules", "Rules", ""],
    ]) {
      if (concept[field].length) {
        container.append(heading(title), list(concept[field], (li, text) => {
          li.textContent = text;
          if (className) li.className = className;
        }));
      }
    }

    const sentence = (li, subject, label, cardinality, incoming, otherId) => {
      const phrase = G.relationPhrase(label, cardinality, incoming);
      const other = ctx.conceptsById.get(otherId);
      const otherName = other ? (phrase.many ? G.plural(other.name) : other.name) : otherId;
      li.append(`${subject} `, el("span", "rel-label", phrase.verb), " ", link(otherId, otherName));
      if (cardinality) li.title = `cardinality ${cardinality}`;
    };

    if (concept.relations.length) {
      container.append(heading("Relations"));
      container.append(
        list(concept.relations, (li, r) => sentence(li, concept.name, r.type, r.cardinality, false, r.target)),
      );
    }

    if (concept.implemented_in.length) {
      container.append(heading("Implemented in"));
      const impl = el("div", "impl");
      for (const entry of concept.implemented_in) {
        const row = el("div");
        const a = el("a", "path-link");
        a.href = `${ctx.pathToProject}${entry.path}`;
        a.append(el("code", "", entry.path));
        row.append(a);
        if (entry.symbol) row.append(el("span", "faint", " · "), el("code", "", entry.symbol));
        let when = "Never reviewed";
        if (entry.reviewed_at) {
          const date = shortDate(entry.reviewed_date);
          when = date
            ? `Reviewed at ${entry.reviewed_at.slice(0, 7)} · ${date}`
            : `Reviewed at ${entry.reviewed_at.slice(0, 7)} (not in this history)`;
        }
        impl.append(row, el("div", "when", when));
      }
      container.append(impl);
    }

    if (concept.open_questions.length) {
      container.append(heading("Open questions"), list(concept.open_questions, (li, q) => (li.textContent = q)));
    }

    if (concept.proposal && (concept.proposal.rationale || concept.proposal.suggested_definition)) {
      container.append(heading("Proposal"));
      const box = el("div", "suggestion");
      if (concept.proposal.suggested_definition) {
        box.append(
          el("div", "who", "Suggested definition · written by the agent, not a definition"),
          el("p", "suggested", concept.proposal.suggested_definition),
        );
      }
      if (concept.proposal.rationale) {
        box.append(el("div", "who", "Rationale"), el("p", "rationale", concept.proposal.rationale));
      }
      container.append(box);
    }

    if (concept.replaced_by) {
      const p = el("p");
      p.append("Use ", link(concept.replaced_by), " instead.");
      container.append(heading("Replaced by"), p);
    }

    const incoming = ctx.incoming(concept.id);
    if (incoming.length) {
      container.append(heading("Incoming relations"));
      container.append(
        list(incoming, (li, edge) => {
          const type = ctx.relationTypes.get(edge.type);
          const inverse = type && type.inverse ? type.inverse : `${edge.type} (inverse)`;
          sentence(li, concept.name, inverse, edge.cardinality, true, edge.source);
        }),
      );
    }
  }

  root.OntologyPane = { render, kindIcon, badgeIcon };
})(window);

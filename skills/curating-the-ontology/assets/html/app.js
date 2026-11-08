// The ontology view. Reads the data contract embedded by `onto.py build` (see ontokit/build.py),
// builds the graph model (graph-model.js), draws it (graph-view.js) and the detail pane (pane.js),
// and keeps the interface state in one place: every change goes through setState().
(function () {
  "use strict";

  const data = JSON.parse(document.getElementById("ontology-data").textContent);
  const G = OntologyGraph;
  const SVG_NS = "http://www.w3.org/2000/svg";
  const HOPS = [1, 2, 3];

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function count(n, singular, plural) {
    return `${n} ${n === 1 ? singular : plural}`;
  }

  // --- Model and lookups ---------------------------------------------------------------

  const model = G.buildModel(data);
  const conceptsById = new Map(data.concepts.map((c) => [c.id, c]));
  const nodesById = new Map(model.nodes.map((n) => [n.id, n]));
  const adjacency = G.adjacency(model.nodes, model.edges);
  const incomingEdges = new Map(model.nodes.map((n) => [n.id, []]));
  for (const e of model.edges) incomingEdges.get(e.target).push(e);
  const findingsByConcept = new Map();
  for (const f of data.findings) {
    if (!f.concept) continue;
    if (!findingsByConcept.has(f.concept)) findingsByConcept.set(f.concept, []);
    findingsByConcept.get(f.concept).push(f);
  }
  const SEVERITY_RANK = { error: 0, warn: 1, info: 2 };
  const worstFinding = new Map(
    [...findingsByConcept].map(([id, list]) => [
      id,
      list.reduce((worst, f) => (SEVERITY_RANK[f.severity] < SEVERITY_RANK[worst] ? f.severity : worst), "info"),
    ]),
  );
  const encodingOf = (kind) => (model.kinds.get(kind) || {}).encoding || { slot: "fallback", shape: "circle" };

  // --- State ---------------------------------------------------------------------------

  const state = {
    selected: null,
    hops: 1,
  };

  // --- Layout --------------------------------------------------------------------------

  const summary = [count(data.concepts.length, "concept", "concepts"), count(model.edges.length, "relation", "relations")].join(
    " · ",
  );

  const toolbar = el("header", "toolbar");
  const brand = el("div", "brand", data.ontology.name);
  brand.append(el("span", "", "ontology"));
  const spacer = el("div", "spacer");
  toolbar.append(brand, el("div", "counts", summary), spacer);

  // A segmented control: one button per option, the current one pressed.
  function segmented(label, options, current, onPick, describe = String) {
    const group = el("div", "control");
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", label);
    group.append(el("span", "control-label", label));
    const seg = el("span", "seg");
    const buttons = options.map((option) => {
      const button = el("button", "", describe(option));
      button.type = "button";
      button.dataset.value = option;
      button.addEventListener("click", () => onPick(option));
      seg.append(button);
      return button;
    });
    group.append(seg);
    group.sync = (value) => {
      for (const b of buttons) b.setAttribute("aria-pressed", String(b.dataset.value === String(value)));
    };
    group.sync(current);
    return group;
  }

  const hopsControl = segmented("Hops", HOPS, state.hops, (hops) => setState({ hops }));
  hopsControl.classList.add("hops");
  toolbar.append(hopsControl);

  const workspace = el("div", "workspace");
  const canvas = el("main", "canvas");
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "graph");
  svg.setAttribute("role", "group");
  svg.setAttribute("aria-label", `Concept graph of ${data.ontology.name}: ${summary}`);
  canvas.append(svg);
  if (!data.concepts.length) {
    canvas.append(el("p", "empty", "No concepts yet. Add one with 'onto.py new', then build again."));
  }
  const preview = el("div", "preview");
  preview.setAttribute("role", "tooltip");
  preview.hidden = true;
  canvas.append(preview);

  const pane = el("aside", "pane");
  pane.setAttribute("aria-labelledby", "pane-title");
  pane.hidden = true;
  workspace.append(canvas, pane);

  const app = document.getElementById("app");
  app.className = "app";
  app.replaceChildren(toolbar, workspace);

  // --- Graph ---------------------------------------------------------------------------

  const view = OntologyGraphView.render(svg, model, {
    findings: worstFinding,
    on: {
      select: (id) => setState({ selected: id }),
      hover: showPreview,
    },
  });

  function showPreview(id, rect) {
    if (!id) {
      preview.hidden = true;
      return;
    }
    const concept = conceptsById.get(id);
    const meta = el("div", "meta");
    meta.append(OntologyPane.kindIcon(encodingOf(concept.kind), concept.status === "proposed"), `${concept.kind} · ${concept.status}`);
    const text = concept.definition ? G.firstSentence(concept.definition) : "Needs a definition.";
    preview.replaceChildren(meta, el("div", "preview-name", concept.name), el("div", "preview-text", text));
    preview.hidden = false;
    const box = canvas.getBoundingClientRect();
    const gap = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--space-2"));
    const left = Math.min(rect.left - box.left, box.width - preview.offsetWidth - gap);
    const below = rect.bottom - box.top + gap;
    const top = below + preview.offsetHeight > box.height ? rect.top - box.top - preview.offsetHeight - gap : below;
    preview.style.left = `${Math.max(gap, left)}px`;
    preview.style.top = `${Math.max(gap, top)}px`;
  }

  // --- Rendering state -----------------------------------------------------------------

  const paneContext = {
    conceptsById,
    encodingOf,
    relationTypes: model.relationTypes,
    incoming: (id) => incomingEdges.get(id) || [],
    findings: (id) => findingsByConcept.get(id) || [],
    pathToProject: data.ontology.path_to_project || "",
    select: (id) => setState({ selected: id }),
  };

  function setState(patch) {
    const previous = { ...state };
    Object.assign(state, patch);
    if (state.selected && !nodesById.has(state.selected)) state.selected = null;
    refresh(previous);
  }

  function refresh(previous) {
    hopsControl.sync(state.hops);
    const near = state.selected ? G.neighbourhood(adjacency, state.selected, state.hops) : null;
    view.update({ selected: state.selected, near });

    const paneChanged = state.selected !== previous.selected;
    if (paneChanged) {
      pane.hidden = !state.selected;
      workspace.classList.toggle("with-pane", Boolean(state.selected));
      OntologyPane.render(pane, conceptsById.get(state.selected), paneContext);
      pane.scrollTop = 0;
      if (state.selected) view.centreOn(state.selected);
    }
  }

  refresh({ selected: null });

  // Exposed for tests and for debugging in the browser console.
  window.ontologyView = {
    data,
    model,
    state,
    setState,
    view,
    d3Loaded: typeof d3 === "object" && typeof d3.forceSimulation === "function",
    positions: view.positions,
    ready: true,
  };
})();

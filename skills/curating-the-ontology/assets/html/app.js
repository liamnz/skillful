// The ontology view. Reads the data contract embedded by `onto.py build` (see ontokit/build.py),
// builds the graph model (graph-model.js), draws it (graph-view.js) and the detail pane (pane.js),
// and keeps the interface state in one place: every change goes through setState().
(function () {
  "use strict";

  const data = JSON.parse(document.getElementById("ontology-data").textContent);
  const G = OntologyGraph;
  const SVG_NS = "http://www.w3.org/2000/svg";
  const HOPS = [1, 2, 3];
  const OVERLAYS = ["none", "health", "mud", "drift"];
  const CRUMBS = 5; // breadcrumbs shown at most

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
    overlay: "none",
    trail: [], // concepts visited before the selected one, oldest first (breadcrumbs)
  };

  // --- Layout --------------------------------------------------------------------------

  const summary = [count(data.concepts.length, "concept", "concepts"), count(model.edges.length, "relation", "relations")].join(
    " · ",
  );

  const toolbar = el("header", "toolbar");
  const brand = el("div", "brand", data.ontology.name);
  brand.append(el("span", "", "ontology"));
  const spacer = el("div", "spacer");

  // Search: names, discouraged terms (shown as redirects) and definition text.
  const searchBox = el("div", "search");
  const searchInput = el("input");
  searchInput.type = "search";
  searchInput.placeholder = "Search concepts and terms";
  searchInput.setAttribute("aria-label", "Search concepts and terms");
  searchInput.setAttribute("role", "combobox");
  searchInput.setAttribute("aria-autocomplete", "list");
  searchInput.setAttribute("aria-expanded", "false");
  searchInput.setAttribute("aria-controls", "search-results");
  searchInput.autocomplete = "off";
  searchInput.spellcheck = false;
  const searchKey = el("kbd", "", "/");
  searchKey.setAttribute("aria-hidden", "true");
  const searchResults = el("ul", "search-results");
  searchResults.id = "search-results";
  searchResults.setAttribute("role", "listbox");
  searchResults.setAttribute("aria-label", "Search results");
  searchResults.hidden = true;
  searchBox.append(searchInput, searchKey, searchResults);

  toolbar.append(brand, searchBox, el("div", "counts", summary), spacer);

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
  svg.setAttribute("tabindex", "-1"); // the concepts inside are the tab stops, not the canvas
  svg.setAttribute("role", "group");
  svg.setAttribute("aria-label", `Concept graph of ${data.ontology.name}: ${summary}`);
  canvas.append(svg);
  if (!data.concepts.length) {
    canvas.append(el("p", "empty", "No concepts yet. Add one with 'onto.py new', then build again."));
  }
  const crumbs = el("nav", "crumbs");
  crumbs.setAttribute("aria-label", "Breadcrumbs");
  const zoomControls = el("div", "zoom");
  zoomControls.setAttribute("role", "group");
  zoomControls.setAttribute("aria-label", "Zoom");
  canvas.append(crumbs, zoomControls);
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

  // Zoom controls: small, neutral, out of the way.
  for (const [symbol, label, action] of [
    ["+", "Zoom in", () => view.zoomBy(1.25)],
    ["−", "Zoom out", () => view.zoomBy(0.8)],
    ["⤢", "Fit to view", () => view.fit()],
    ["↺", "Reset layout (unpin dragged concepts)", () => view.resetLayout()],
  ]) {
    const button = el("button", "", symbol);
    button.type = "button";
    button.title = label;
    button.setAttribute("aria-label", label);
    button.addEventListener("click", action);
    zoomControls.append(button);
  }

  // --- Keyboard ------------------------------------------------------------------------
  // Tab enters the graph at one concept. Arrow keys move to the connected concept that lies
  // most nearly in that direction; Tab and Shift+Tab step through the concepts connected to
  // the selected one (then leave the graph as usual); Enter or Space selects; Escape clears.

  const DIRECTIONS = { ArrowRight: [1, 0], ArrowLeft: [-1, 0], ArrowDown: [0, 1], ArrowUp: [0, -1] };

  function focusConcept(id) {
    view.setTabStop(id);
    view.ensureVisible(id);
    view.focusNode(id);
  }

  function byName(a, b) {
    return nodesById.get(a).name.localeCompare(nodesById.get(b).name);
  }

  function towards(fromId, [dx, dy]) {
    const positions = view.positions();
    const [x0, y0] = positions[fromId];
    let best = null;
    for (const id of adjacency.get(fromId) || []) {
      const [x, y] = positions[id];
      const distance = Math.hypot(x - x0, y - y0) || 1;
      const cos = ((x - x0) * dx + (y - y0) * dy) / distance;
      if (cos < 0.3) continue; // more than about 70 degrees off the arrow's direction
      const score = distance / cos;
      if (!best || score < best.score) best = { id, score };
    }
    return best && best.id;
  }

  svg.addEventListener("keydown", (event) => {
    const node = event.target.closest && event.target.closest(".node");
    if (!node) return;
    const id = node.dataset.id;
    if (event.key in DIRECTIONS) {
      event.preventDefault();
      const next = towards(id, DIRECTIONS[event.key]);
      if (next) focusConcept(next);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setState({ selected: id });
    } else if (event.key === "Escape") {
      setState({ selected: null });
    } else if (event.key === "Tab") {
      const anchor = state.selected || id;
      const ring = [anchor, ...[...(adjacency.get(anchor) || [])].sort(byName)];
      const at = ring.indexOf(id);
      const next = at + (event.shiftKey ? -1 : 1);
      if (at !== -1 && next >= 0 && next < ring.length) {
        event.preventDefault();
        focusConcept(ring[next]);
      }
    }
  });
  svg.addEventListener("focusin", (event) => {
    const node = event.target.closest && event.target.closest(".node");
    if (node) view.setTabStop(node.dataset.id);
  });

  // --- Search ------------------------------------------------------------------------

  let results = [];
  let active = -1;

  function showResults() {
    results = G.search(data.concepts, searchInput.value);
    active = results.length ? 0 : -1;
    searchResults.replaceChildren();
    for (const [i, r] of results.entries()) {
      const li = el("li", `result ${r.rank}`);
      li.id = `search-result-${i}`;
      li.setAttribute("role", "option");
      li.dataset.id = r.id;
      li.dataset.rank = r.rank;
      const concept = conceptsById.get(r.id);
      if (r.rank === "redirect") {
        li.append(el("span", "muted", `'${r.term}' →`), " use ", el("strong", "", r.name));
      } else {
        li.append(OntologyPane.kindIcon(encodingOf(concept.kind), concept.status === "proposed"), " ", r.name);
        if (concept.status !== "defined") li.append(el("span", "faint", ` · ${concept.status}`));
        if (r.rank === "definition") li.append(el("span", "faint", " · in definition"));
      }
      li.addEventListener("mousedown", (event) => {
        event.preventDefault(); // keep focus in the input until the choice is made
        choose(i);
      });
      searchResults.append(li);
    }
    if (searchInput.value.trim() && !results.length) {
      const none = el("li", "none", "No matching concepts");
      none.setAttribute("aria-disabled", "true");
      searchResults.append(none);
    }
    searchResults.hidden = !searchInput.value.trim();
    searchInput.setAttribute("aria-expanded", String(!searchResults.hidden));
    markActive();
  }

  function markActive() {
    for (const [i, li] of [...searchResults.querySelectorAll(".result")].entries()) {
      li.setAttribute("aria-selected", String(i === active));
    }
    if (active >= 0) searchInput.setAttribute("aria-activedescendant", `search-result-${active}`);
    else searchInput.removeAttribute("aria-activedescendant");
  }

  function closeResults() {
    searchResults.hidden = true;
    searchInput.setAttribute("aria-expanded", "false");
  }

  function choose(i) {
    const r = results[i];
    if (!r) return;
    closeResults();
    searchInput.value = "";
    setState({ selected: r.id });
    view.focusNode(r.id); // the graph now has focus, at the chosen concept
  }

  searchInput.addEventListener("input", showResults);
  searchInput.addEventListener("focus", () => searchInput.value.trim() && showResults());
  searchInput.addEventListener("blur", closeResults);
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!results.length) return;
      active = (active + (event.key === "ArrowDown" ? 1 : -1) + results.length) % results.length;
      markActive();
    } else if (event.key === "Enter") {
      event.preventDefault();
      choose(Math.max(active, 0));
    } else if (event.key === "Escape") {
      searchInput.value = "";
      closeResults();
    }
  });

  // "/" focuses search from anywhere except a text field.
  document.addEventListener("keydown", (event) => {
    const typing = event.target.closest && event.target.closest("input, textarea, select, [contenteditable]");
    if (event.key === "/" && !typing && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault();
      searchInput.focus();
      searchInput.select();
    }
  });

  // --- URL: #<concept-id>?hops=2&overlay=health ---------------------------------------

  function parseHash(hash) {
    const text = hash.replace(/^#/, "");
    const [idPart, query = ""] = text.split("?");
    const params = new URLSearchParams(query);
    const patch = { selected: idPart ? decodeURIComponent(idPart) : null };
    const hops = Number(params.get("hops"));
    patch.hops = HOPS.includes(hops) ? hops : 1;
    patch.overlay = OVERLAYS.includes(params.get("overlay")) ? params.get("overlay") : "none";
    return patch;
  }

  function hashFor(s) {
    const params = new URLSearchParams();
    if (s.hops !== 1) params.set("hops", s.hops);
    if (s.overlay !== "none") params.set("overlay", s.overlay);
    const query = params.toString();
    const id = s.selected ? encodeURIComponent(s.selected) : "";
    return id || query ? `#${id}${query ? `?${query}` : ""}` : "";
  }

  function syncUrl(previous) {
    const hash = hashFor(state);
    if (hash === location.hash || (!hash && !location.hash)) return;
    const url = `${location.pathname}${location.search}${hash || "#"}`;
    try {
      if (state.selected !== previous.selected) history.pushState(null, "", url);
      else history.replaceState(null, "", url);
    } catch {
      // Some browsers restrict the History API on file:// pages; the view still works.
    }
  }

  function restoreFromUrl() {
    const patch = parseHash(location.hash);
    if (patch.selected && !nodesById.has(patch.selected)) patch.selected = null;
    setState({ ...patch, trail: [] }, { fromUrl: true });
  }
  window.addEventListener("popstate", restoreFromUrl);
  window.addEventListener("hashchange", restoreFromUrl);

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

  // Selecting a new concept from another records a breadcrumb; going back to one trims the trail.
  function nextTrail(previous, patch) {
    if (patch.trail) return patch.trail;
    const next = patch.selected;
    if (next === undefined || next === previous.selected) return previous.trail;
    if (!next) return [];
    const back = previous.trail.indexOf(next);
    if (back !== -1) return previous.trail.slice(0, back);
    return previous.selected ? [...previous.trail, previous.selected].slice(-(CRUMBS - 1)) : [];
  }

  function setState(patch, options = {}) {
    const previous = { ...state };
    const trail = nextTrail(previous, patch);
    Object.assign(state, patch, { trail });
    if (state.selected && !nodesById.has(state.selected)) state.selected = null;
    refresh(previous);
    if (!options.fromUrl) syncUrl(previous);
  }

  function renderCrumbs() {
    crumbs.replaceChildren();
    crumbs.hidden = !state.selected;
    if (!state.selected) return;
    for (const id of state.trail) {
      const a = el("a", "", nodesById.get(id).name);
      a.href = `#${encodeURIComponent(id)}`;
      a.dataset.id = id;
      a.addEventListener("click", (event) => {
        event.preventDefault();
        setState({ selected: id });
      });
      crumbs.append(a, el("span", "sep", " › "));
    }
    const current = el("b", "", nodesById.get(state.selected).name);
    current.setAttribute("aria-current", "page");
    crumbs.append(current);
  }

  function refresh(previous) {
    hopsControl.sync(state.hops);
    const near = state.selected ? G.neighbourhood(adjacency, state.selected, state.hops) : null;
    view.update({ selected: state.selected, near });
    renderCrumbs();

    const paneChanged = state.selected !== previous.selected;
    if (paneChanged) {
      pane.hidden = !state.selected;
      workspace.classList.toggle("with-pane", Boolean(state.selected));
      OntologyPane.render(pane, conceptsById.get(state.selected), paneContext);
      pane.scrollTop = 0;
      if (state.selected) {
        view.centreOn(state.selected);
        view.setTabStop(state.selected);
      }
    }
  }

  refresh({ selected: null });
  if (location.hash) restoreFromUrl();

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

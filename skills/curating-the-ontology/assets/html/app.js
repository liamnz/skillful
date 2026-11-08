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
    tab: "graph",
    filters: { kinds: new Set(), statuses: new Set(), types: new Set() }, // what is hidden
    sort: { key: "name", dir: "asc" }, // list view
  };
  const refreshers = []; // panels that redraw on every state change (list, health, vocabulary)

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

  const tabs = el("nav", "tabs");
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "Views");
  const tabButtons = new Map();
  function addTab(id, label, panel) {
    const button = el("button", "tab", label);
    button.type = "button";
    button.id = `tab-${id}`;
    button.setAttribute("role", "tab");
    button.setAttribute("aria-controls", panel.id);
    button.addEventListener("click", () => setState({ tab: id }));
    tabs.append(button);
    tabButtons.set(id, { button, panel });
    panel.setAttribute("role", "tabpanel");
    panel.setAttribute("aria-labelledby", button.id);
    return button;
  }

  toolbar.append(brand, tabs, searchBox, el("div", "counts", summary), spacer);

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
  const overlayControl = segmented(
    "Overlay",
    OVERLAYS,
    state.overlay,
    (overlay) => setState({ overlay }),
    (o) => o[0].toUpperCase() + o.slice(1),
  );
  overlayControl.classList.add("overlay");
  toolbar.append(hopsControl, overlayControl);

  // Filters: kind, status and relation type. Checked means shown.
  const filterButton = el("button", "button filters-button", "Filters");
  filterButton.type = "button";
  filterButton.setAttribute("aria-expanded", "false");
  filterButton.setAttribute("aria-controls", "filters-panel");
  const filterPanel = el("div", "filters-panel");
  filterPanel.id = "filters-panel";
  filterPanel.hidden = true;
  filterPanel.setAttribute("role", "dialog");
  filterPanel.setAttribute("aria-label", "Filters");
  const filterWrap = el("div", "filters");
  filterWrap.append(filterButton, filterPanel);
  toolbar.append(filterWrap);
  filterButton.addEventListener("click", () => {
    filterPanel.hidden = !filterPanel.hidden;
    filterButton.setAttribute("aria-expanded", String(!filterPanel.hidden));
  });
  document.addEventListener("click", (event) => {
    if (!filterPanel.hidden && !filterWrap.contains(event.target)) {
      filterPanel.hidden = true;
      filterButton.setAttribute("aria-expanded", "false");
    }
  });

  const kindsInUse = [...new Set(data.concepts.map((c) => c.kind))].sort(
    (a, b) => (encodingOf(a).slot === "fallback" ? 99 : encodingOf(a).slot) - (encodingOf(b).slot === "fallback" ? 99 : encodingOf(b).slot) || a.localeCompare(b),
  );
  const typesInUse = [...new Set(model.edges.map((e) => e.type))].sort();
  const filterGroups = [
    ["kinds", "Kind", kindsInUse, (k) => [OntologyPane.kindIcon(encodingOf(k), false), ` ${k}`]],
    ["statuses", "Status", ["defined", "proposed", "deprecated"], (v) => [v]],
    ["types", "Relation type", typesInUse, (t) => [t.replace(/_/g, " ")]],
  ];
  const filterInputs = [];
  for (const [key, legend, values, label] of filterGroups) {
    const fieldset = el("fieldset");
    fieldset.append(el("legend", "", legend));
    for (const value of values) {
      const row = el("label", "check");
      const box = el("input");
      box.type = "checkbox";
      box.dataset.group = key;
      box.value = value;
      box.addEventListener("change", () => {
        const next = new Set(state.filters[key]);
        if (box.checked) next.delete(value);
        else next.add(value);
        setState({ filters: { ...state.filters, [key]: next } });
      });
      row.append(box, ...label(value));
      fieldset.append(row);
      filterInputs.push(box);
    }
    filterPanel.append(fieldset);
  }
  const showAll = el("button", "button", "Show all");
  showAll.type = "button";
  showAll.addEventListener("click", () =>
    setState({ filters: { kinds: new Set(), statuses: new Set(), types: new Set() } }),
  );
  filterPanel.append(showAll);
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
  canvas.id = "panel-graph";
  const listPanel = el("section", "list-panel");
  listPanel.id = "panel-list";
  listPanel.hidden = true; // hidden before the graph is laid out, so the first fit sees the whole canvas
  const main = el("div", "main");
  main.append(canvas, listPanel);
  workspace.append(main, pane);
  addTab("graph", "Graph", canvas);
  addTab("list", "List", listPanel);
  const healthPanel = el("section", "health-panel");
  healthPanel.id = "panel-health";
  healthPanel.hidden = true;
  main.append(healthPanel);
  const healthTab = addTab("health", "Health", healthPanel);
  const healthCount = el("span", "count", String(data.findings.length));
  healthCount.setAttribute("aria-label", count(data.findings.length, "finding", "findings"));
  healthTab.append(healthCount);
  const vocabPanel = el("section", "vocab-panel");
  vocabPanel.id = "panel-vocabulary";
  vocabPanel.hidden = true;
  main.append(vocabPanel);
  addTab("vocabulary", "Vocabulary", vocabPanel);

  const app = document.getElementById("app");
  app.className = "app";
  app.replaceChildren(toolbar, workspace);

  // --- Graph ---------------------------------------------------------------------------

  const view = OntologyGraphView.render(svg, model, {
    findings: worstFinding,
    // Fit-to-view keeps the graph clear of the legend in the canvas's bottom-left corner.
    reserveCorner: () => {
      const legendBox = canvas.querySelector(".legend");
      if (!legendBox) return { width: 0, height: 0 };
      const gap = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--space-3"));
      return { width: legendBox.offsetWidth + gap, height: legendBox.offsetHeight + gap };
    },
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
    for (const id of visibleAdjacency.get(fromId) || []) {
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
      const ring = [anchor, ...[...(visibleAdjacency.get(anchor) || [])].sort(byName)];
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

  // What the filters leave visible: hidden concepts, hidden relation types, and the edges
  // (and adjacency) between visible concepts.
  let visibleAdjacency = adjacency;
  function visibility() {
    const { kinds, statuses, types } = state.filters;
    const hidden = new Set(model.nodes.filter((n) => kinds.has(n.kind) || statuses.has(n.status)).map((n) => n.id));
    const edges = model.edges.filter((e) => !types.has(e.type) && !hidden.has(e.source) && !hidden.has(e.target));
    return { hidden, types, edges, nodes: model.nodes.filter((n) => !hidden.has(n.id)) };
  }

  function syncFilters(visible) {
    for (const box of filterInputs) box.checked = !state.filters[box.dataset.group].has(box.value);
    const active = state.filters.kinds.size + state.filters.statuses.size + state.filters.types.size;
    filterButton.textContent = active ? `Filters · ${active}` : "Filters";
    filterButton.classList.toggle("active", Boolean(active));
    filterButton.title = active ? `${visible.nodes.length} of ${model.nodes.length} concepts shown` : "";
  }

  function syncTabs() {
    for (const [id, { button, panel }] of tabButtons) {
      const on = id === state.tab;
      button.setAttribute("aria-selected", String(on));
      button.tabIndex = on ? 0 : -1;
      panel.hidden = !on;
    }
  }

  function refresh(previous) {
    const visible = visibility();
    if (state.selected && visible.hidden.has(state.selected)) state.selected = null;
    visibleAdjacency = G.adjacency(visible.nodes, visible.edges);
    hopsControl.sync(state.hops);
    syncFilters(visible);
    syncTabs();
    const near = state.selected ? G.neighbourhood(visibleAdjacency, state.selected, state.hops) : null;
    overlayControl.sync(state.overlay);
    const overlay = G.overlaySets(model, data, state.overlay);
    view.update({
      selected: state.selected,
      near,
      hidden: visible.hidden,
      hiddenEdges: visible.types,
      highlight: overlay ? overlay.nodes : null,
      highlightEdges: overlay ? overlay.edges : null,
    });
    svg.dataset.overlay = state.overlay;
    renderCrumbs();
    for (const redraw of refreshers) redraw(visible, previous);

    const onGraph = state.tab === "graph";
    const paneChanged = state.selected !== previous.selected;
    if (paneChanged) {
      pane.hidden = !state.selected;
      workspace.classList.toggle("with-pane", Boolean(state.selected));
      OntologyPane.render(pane, conceptsById.get(state.selected), paneContext);
      pane.scrollTop = 0;
    }
    if (state.selected && onGraph && (paneChanged || previous.tab !== "graph")) {
      view.centreOn(state.selected);
      view.setTabStop(state.selected);
    }
  }

  // --- List view: a sortable table of the visible concepts -----------------------------

  const LIST_COLUMNS = [
    { key: "name", label: "Name", value: (c) => c.name.toLowerCase() },
    { key: "kind", label: "Kind", value: (c) => c.kind },
    { key: "status", label: "Status", value: (c) => c.status },
    { key: "relations", label: "Relations", value: (c) => degreeOf(c.id), numeric: true },
    { key: "findings", label: "Findings", value: (c) => (findingsByConcept.get(c.id) || []).length, numeric: true },
    { key: "definition", label: "Definition", value: (c) => (c.definition ? G.firstSentence(c.definition).toLowerCase() : "") },
  ];
  let visibleDegree = new Map();
  const degreeOf = (id) => visibleDegree.get(id) || 0;

  function renderList(visible) {
    visibleDegree = new Map(visible.nodes.map((n) => [n.id, 0]));
    for (const e of visible.edges) {
      visibleDegree.set(e.source, visibleDegree.get(e.source) + 1);
      visibleDegree.set(e.target, visibleDegree.get(e.target) + 1);
    }
    const column = LIST_COLUMNS.find((c) => c.key === state.sort.key) || LIST_COLUMNS[0];
    const direction = state.sort.dir === "desc" ? -1 : 1;
    const rows = visible.nodes
      .map((n) => conceptsById.get(n.id))
      .sort((a, b) => {
        const x = column.value(a);
        const y = column.value(b);
        const order = column.numeric ? x - y : String(x).localeCompare(String(y));
        return order * direction || a.name.localeCompare(b.name) || (a.id < b.id ? -1 : 1);
      });

    const table = el("table", "concept-table");
    const caption = el("caption", "", `${count(rows.length, "concept", "concepts")}${rows.length < model.nodes.length ? ` of ${model.nodes.length} (filtered)` : ""}`);
    const head = el("thead");
    const headRow = el("tr");
    for (const c of LIST_COLUMNS) {
      const th = el("th");
      th.scope = "col";
      if (c.numeric) th.className = "num";
      const sorted = c.key === column.key;
      th.setAttribute("aria-sort", sorted ? (direction === 1 ? "ascending" : "descending") : "none");
      const button = el("button", "sort", c.label);
      button.type = "button";
      button.addEventListener("click", () =>
        setState({ sort: { key: c.key, dir: sorted && direction === 1 ? "desc" : "asc" } }),
      );
      th.append(button);
      headRow.append(th);
    }
    head.append(headRow);
    const body = el("tbody");
    for (const c of rows) {
      const tr = el("tr");
      tr.dataset.id = c.id;
      if (c.id === state.selected) tr.setAttribute("aria-selected", "true");
      const nameCell = el("th");
      nameCell.scope = "row";
      const link = el("a", "concept-link", c.name);
      link.href = `#${encodeURIComponent(c.id)}`;
      link.addEventListener("click", (event) => {
        event.preventDefault();
        setState({ selected: c.id });
      });
      nameCell.append(OntologyPane.kindIcon(encodingOf(c.kind), c.status === "proposed"), " ", link);
      const findings = findingsByConcept.get(c.id) || [];
      const findingCell = el("td", "num");
      if (findings.length) {
        const worst = worstFinding.get(c.id);
        findingCell.append(OntologyPane.badgeIcon(worst), ` ${findings.length}`);
        findingCell.setAttribute("aria-label", `${findings.length} (worst: ${worst === "warn" ? "warning" : worst})`);
      }
      tr.append(
        nameCell,
        el("td", "", c.kind),
        el("td", "", c.status),
        el("td", "num", String(degreeOf(c.id))),
        findingCell,
        el("td", c.definition ? "definition-cell" : "definition-cell faint", c.definition ? G.firstSentence(c.definition) : "Needs a definition"),
      );
      tr.addEventListener("click", (event) => {
        if (!event.target.closest("a")) setState({ selected: c.id });
      });
      body.append(tr);
    }
    table.append(caption, head, body);
    listPanel.replaceChildren(table);
  }
  refreshers.push(renderList);

  // --- Health panel: every finding, grouped by Gruber criterion ------------------------

  const CRITERIA = [
    ["clarity", "Clarity"],
    ["coherence", "Coherence"],
    ["extendibility", "Extendibility"],
    ["minimal-encoding-bias", "Minimal encoding bias"],
    ["minimal-commitment", "Minimal ontological commitment"],
    ["drift", "Drift"],
    ["staleness", "Staleness"],
    [null, "Structure"],
  ];

  function renderHealth() {
    healthPanel.replaceChildren();
    if (!data.findings.length) {
      healthPanel.append(el("p", "empty-note", "No findings. The validator found nothing to flag."));
      return;
    }
    const known = new Set(CRITERIA.map(([id]) => id));
    const groups = [...CRITERIA];
    for (const f of data.findings) {
      if (!known.has(f.criterion)) {
        known.add(f.criterion);
        groups.push([f.criterion, f.criterion]);
      }
    }
    for (const [criterion, title] of groups) {
      const items = data.findings.filter((f) => f.criterion === criterion);
      if (!items.length) continue;
      const section = el("section", "criterion");
      section.dataset.criterion = criterion || "structure";
      const heading = el("h2", "", title);
      heading.append(el("span", "count", String(items.length)));
      const ul = el("ul");
      for (const f of items) {
        const li = el("li", "finding");
        li.dataset.code = f.code;
        const text = el("div");
        const where = el("div", "code");
        where.append(f.code);
        if (f.concept && nodesById.has(f.concept)) {
          const a = el("a", "concept-link", nodesById.get(f.concept).name);
          a.href = `#${encodeURIComponent(f.concept)}`;
          a.dataset.id = f.concept;
          a.addEventListener("click", (event) => {
            event.preventDefault();
            setState({ selected: f.concept, tab: "graph" });
          });
          where.append(" · ", a);
        } else if (!f.concept) {
          where.append(" · ontology");
        }
        text.append(where, el("p", "", f.message));
        li.append(OntologyPane.badgeIcon(f.severity), text);
        ul.append(li);
      }
      section.append(heading, ul);
      healthPanel.append(section);
    }
  }
  renderHealth();

  // --- Vocabulary: usage counts, the legend and the Vocabulary panel --------------------

  const kindUsage = new Map();
  for (const c of data.concepts) kindUsage.set(c.kind, (kindUsage.get(c.kind) || 0) + 1);
  const typeUsage = new Map();
  for (const c of data.concepts) for (const r of c.relations) typeUsage.set(r.type, (typeUsage.get(r.type) || 0) + 1);
  const words = (id) => id.replace(/_/g, " ");
  const oneLine = (text) => (text || "").replace(/\s+/g, " ").trim();
  const allKinds = data.vocabulary.kinds.map((k) => k.id);
  const allTypes = data.vocabulary.relation_types.map((r) => r.id);

  // Show only one kind (or relation type) in the graph: the Vocabulary panel's click action.
  function filterTo(group, id) {
    const others = (group === "kinds" ? allKinds : allTypes).filter((x) => x !== id);
    const filters = { kinds: new Set(), statuses: new Set(), types: new Set() };
    filters[group] = new Set(others);
    setState({ filters, tab: "graph", selected: null });
  }

  // Legend tooltips: the definition of whatever the pointer (or keyboard focus) is on.
  const legendTip = el("div", "legend-tip");
  legendTip.setAttribute("role", "tooltip");
  legendTip.id = "legend-tip";
  legendTip.hidden = true;

  function explain(row, title, definition) {
    row.tabIndex = 0;
    row.dataset.definition = definition;
    const show = () => {
      legendTip.replaceChildren(el("div", "preview-name", title), el("div", "preview-text", definition));
      legendTip.hidden = false;
      const box = canvas.getBoundingClientRect();
      const r = row.getBoundingClientRect();
      const gap = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--space-2"));
      legendTip.style.left = `${r.left - box.left}px`;
      legendTip.style.top = `${Math.max(gap, r.top - box.top - legendTip.offsetHeight - gap)}px`;
      row.setAttribute("aria-describedby", legendTip.id);
    };
    const hide = () => {
      legendTip.hidden = true;
      row.removeAttribute("aria-describedby");
    };
    row.addEventListener("mouseenter", show);
    row.addEventListener("focus", show);
    row.addEventListener("mouseleave", hide);
    row.addEventListener("blur", hide);
  }

  function lineSample(dash, arrow) {
    const svgLine = document.createElementNS(SVG_NS, "svg");
    svgLine.setAttribute("class", "line-sample");
    svgLine.setAttribute("aria-hidden", "true");
    svgLine.setAttribute("viewBox", "0 0 28 10");
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("x1", "1");
    line.setAttribute("y1", "5");
    line.setAttribute("x2", arrow ? "21" : "27");
    line.setAttribute("y2", "5");
    line.setAttribute("class", `edge ${dash ? "dashed" : "solid"}`);
    svgLine.append(line);
    if (arrow) {
      const head = document.createElementNS(SVG_NS, "path");
      head.setAttribute("d", "M21,1.5 L27,5 L21,8.5 Z");
      head.setAttribute("class", arrow === "hollow" ? "arrow-hollow focus" : "arrow focus");
      svgLine.append(head);
    }
    return svgLine;
  }

  function statusSample(status) {
    const sample = document.createElementNS(SVG_NS, "svg");
    sample.setAttribute("class", `status-sample ${status === "deprecated" ? "deprecated" : ""}`);
    sample.setAttribute("aria-hidden", "true");
    sample.setAttribute("viewBox", "0 0 20 12");
    const rect = document.createElementNS(SVG_NS, "rect");
    rect.setAttribute("x", "0.5");
    rect.setAttribute("y", "0.5");
    rect.setAttribute("width", "19");
    rect.setAttribute("height", "11");
    rect.setAttribute("rx", "2");
    rect.setAttribute("class", `box ${status}`);
    sample.append(rect);
    return sample;
  }

  const STATUS_MEANING = {
    defined: "A human has written and agreed the definition.",
    proposed: "Needs a definition: proposed, usually by the agent, and not yet defined by a human.",
    deprecated: "No longer to be used. Follow replaced_by to the concept that took its place.",
  };
  const SEVERITY_MEANING = {
    error: "Error: the records are inconsistent and validate fails until it is fixed.",
    warn: "Warning: worth fixing; validate --strict fails on it.",
    info: "Info: a prompt to look, not a fault.",
  };

  const legend = el("aside", "legend");
  legend.setAttribute("aria-label", "Legend");
  {
    const kindsCol = el("div");
    kindsCol.append(el("h4", "", "Kinds"));
    for (const k of data.vocabulary.kinds) {
      const row = el("div", "row");
      row.dataset.kind = k.id;
      row.append(OntologyPane.kindIcon(k.encoding, false), words(k.id));
      explain(row, words(k.id), oneLine(k.definition) || "No definition yet (proposed).");
      kindsCol.append(row);
    }
    const relCol = el("div");
    relCol.append(el("h4", "", "Relations"));
    const styles = [
      ["directed, labelled", null, "filled", "A named, directed relation. Its label shows the relation type (and cardinality, if recorded)."],
      ["is a (subtype)", null, "hollow", oneLine((model.relationTypes.get("is_a") || {}).definition)],
      ["related to (vague)", "dash", null, oneLine((model.relationTypes.get("related_to") || {}).definition)],
    ];
    for (const [label, dash, arrow, meaning] of styles) {
      const row = el("div", "row");
      row.append(lineSample(dash, arrow), label);
      explain(row, label, meaning);
      relCol.append(row);
    }
    const typesRow = el("div", "row types");
    for (const [i, type] of data.vocabulary.relation_types.filter((r) => typeUsage.get(r.id)).entries()) {
      if (i) typesRow.append(" · ");
      const span = el("span", "type", words(type.id));
      span.dataset.type = type.id;
      explain(span, words(type.id), oneLine(type.definition) || "No definition yet (proposed).");
      typesRow.append(span);
    }
    relCol.append(typesRow);
    const statusCol = el("div");
    statusCol.append(el("h4", "", "Status"));
    for (const status of ["defined", "proposed", "deprecated"]) {
      const row = el("div", "row");
      row.dataset.status = status;
      row.append(statusSample(status), status);
      explain(row, status, STATUS_MEANING[status]);
      statusCol.append(row);
    }
    statusCol.append(el("h4", "", "Findings"));
    const badgeRow = el("div", "row badges");
    for (const severity of ["error", "warn", "info"]) {
      const item = el("span", "badge-item");
      item.dataset.severity = severity;
      item.append(OntologyPane.badgeIcon(severity), severity === "warn" ? "warning" : severity);
      explain(item, severity === "warn" ? "warning" : severity, SEVERITY_MEANING[severity]);
      badgeRow.append(item);
    }
    statusCol.append(badgeRow);
    legend.append(kindsCol, relCol, statusCol);
  }
  canvas.append(legend, legendTip);
  view.fit(); // again, now that the legend's space is known

  function renderVocabulary() {
    vocabPanel.replaceChildren();
    const section = (title, entries, group, usage) => {
      const wrap = el("section", "vocab-section");
      wrap.append(el("h2", "", title));
      const table = el("table", "vocab-table");
      const head = el("tr");
      for (const label of ["Term", "Status", "Used", group === "types" ? "From → to" : null, "Definition"]) {
        if (label === null) continue;
        const th = el("th", label === "Used" ? "num" : "", label);
        th.scope = "col";
        head.append(th);
      }
      const thead = el("thead");
      thead.append(head);
      const tbody = el("tbody");
      for (const entry of entries) {
        const tr = el("tr");
        tr.dataset.id = entry.id;
        const term = el("th");
        term.scope = "row";
        const button = el("button", "vocab-term", words(entry.id));
        button.type = "button";
        button.title = `Show only ${words(entry.id)} in the graph`;
        button.addEventListener("click", () => filterTo(group, entry.id));
        if (group === "kinds") term.append(OntologyPane.kindIcon(entry.encoding, entry.status === "proposed"), " ");
        term.append(button);
        if (group === "types" && entry.inverse) term.append(el("div", "faint", `inverse: ${words(entry.inverse)}`));
        const used = usage.get(entry.id) || 0;
        tr.append(term, el("td", "", entry.core ? "core" : entry.status), el("td", "num", String(used)));
        if (group === "types") {
          const from = (entry.from || []).join(", ") || "any";
          const to = (entry.to || []).join(", ") || "any";
          tr.append(el("td", "faint", entry.from || entry.to ? `${from} → ${to}` : "any"));
        }
        tr.append(el("td", entry.definition ? "definition-cell" : "definition-cell faint", oneLine(entry.definition) || "Needs a definition"));
        tbody.append(tr);
      }
      table.append(thead, tbody);
      wrap.append(table);
      return wrap;
    };
    vocabPanel.append(
      section("Kinds", data.vocabulary.kinds, "kinds", kindUsage),
      section("Relation types", data.vocabulary.relation_types, "types", typeUsage),
    );
  }
  renderVocabulary();

  refresh({ selected: null });
  if (location.hash) restoreFromUrl();

  // Exposed for tests and for debugging in the browser console.
  window.ontologyView = {
    data,
    model,
    state,
    setState,
    view,
    addTab,
    refreshers,
    d3Loaded: typeof d3 === "object" && typeof d3.forceSimulation === "function",
    positions: view.positions,
    ready: true,
  };
})();

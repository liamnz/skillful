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
  toolbar.append(hopsControl);

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
    view.update({ selected: state.selected, near, hidden: visible.hidden, hiddenEdges: visible.types });
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

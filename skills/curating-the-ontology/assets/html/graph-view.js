// Graph view: lays the model out with d3-force and draws it as SVG, then exposes a small
// controller. The layout is deterministic: positions are seeded from concept ids, the
// simulation uses a seeded random source, and a fixed number of ticks run synchronously
// before anything is drawn. Nothing is animated: state changes only toggle classes, and
// pan/zoom move the camera, never the concepts. Every size comes from tokens.css.
(function (root) {
  "use strict";

  const G = root.OntologyGraph;
  const SEED = 0x6f6e746f; // "onto"
  const TICKS = 300;
  // Physics only (unitless). Charge pushes concepts apart, but only within REPULSION_RANGE edge
  // lengths, so a loosely connected concept isn't pushed far out. The x/y pulls keep the graph
  // compact and wider than tall, to suit a landscape canvas. Tuned on the sample project so no
  // edge runs under an unrelated box.
  const CHARGE = -800;
  const REPULSION_RANGE = 8;
  const PULL_X = 0.03;
  const PULL_Y = 0.06;
  const COLLIDE = 0.8;
  // The pulls were tuned on a ~25-concept graph. They act on every concept, so in a larger
  // graph they would crush its clusters together; they shrink with the square root of size.
  const REFERENCE_SIZE = 25;
  const UNTANGLE_ABOVE = 2 * REFERENCE_SIZE; // larger graphs get an untangling phase first
  const UNTANGLE_TICKS = 200;
  // Hierarchy layout: each depth level is pulled hard onto its row.
  const LEVEL_PULL = 1;
  const HIERARCHY_PULL_X = 0.02;
  const HIERARCHY_LINK = 0.7; // parent-child links pull children under their parents ...
  const HIERARCHY_LINK_OTHER = 0.3; // ... other relations pull more gently
  // Zoom limits (scale factors) and the semantic-zoom thresholds.
  const MIN_ZOOM = 0.1;
  const MAX_ZOOM = 4;
  const GLYPH_ONLY_BELOW = 0.6; // boxes collapse to their kind glyph below this scale ...
  const ALL_LABELS_ABOVE = 1.6; // ... and every edge is labelled above this one
  // Hubs keep their box when zoomed out: at least HUB_DEGREE relations and in the top
  // HUB_SHARE of concepts by degree, so a large ontology keeps only its real hubs.
  const HUB_DEGREE = 4;
  const HUB_SHARE = 0.1;

  function tokens() {
    const style = getComputedStyle(document.documentElement);
    const px = (name) => parseFloat(style.getPropertyValue(name));
    return {
      nodeHeight: px("--node-height"),
      pad: px("--space-2"),
      glyph: px("--node-glyph-size"),
      glyphGap: px("--space-2"),
      radius: px("--radius-sm"),
      border: px("--border-width"),
      spacing: px("--node-spacing"),
      edgeLength: px("--edge-min-length"),
      clearance: px("--edge-clearance"),
      arrow: px("--arrow-size"),
      arrowHollow: px("--arrow-hollow-size"),
      labelPad: px("--space-1"),
      fitPad: px("--space-6"),
      badge: px("--badge-size"),
      stub: px("--edge-stub-length"),
      focusRing: px("--focus-ring-offset"),
      levelGap: px("--hierarchy-level-gap"),
    };
  }

  const round = (n) => Math.round(n * 100) / 100;

  // Kind glyphs, about `g` px across, centred on (0, 0). Core shapes match the approved mockup;
  // extension shapes use d3-shape's symbols, and the hexagon is drawn here (d3 has none).
  function glyphPath(shape, g) {
    const r = g / 2;
    const points = (pts) => "M" + pts.map(([x, y]) => `${round(x)},${round(y)}`).join("L") + "Z";
    switch (shape) {
      case "diamond":
        return points([[0, -r * 1.2], [r * 1.2, 0], [0, r * 1.2], [-r * 1.2, 0]]);
      case "square":
        return points([[-r * 0.9, -r * 0.9], [r * 0.9, -r * 0.9], [r * 0.9, r * 0.9], [-r * 0.9, r * 0.9]]);
      case "triangle":
        return points([[0, -r * 1.1], [r * 1.1, r * 0.9], [-r * 1.1, r * 0.9]]);
      case "hexagon":
        return points(
          Array.from({ length: 6 }, (_, i) => {
            const a = (Math.PI / 3) * i - Math.PI / 2;
            return [r * 1.1 * Math.cos(a), r * 1.1 * Math.sin(a)];
          }),
        );
      case "cross":
        return d3.symbol(d3.symbolCross, 5 * ((g + 1) / 3) ** 2)();
      case "star":
        return d3.symbol(d3.symbolStar, g * g * 0.55)();
      case "wye":
        return d3.symbol(d3.symbolWye, g * g * 0.7)();
      default: // circle, and the fallback for kinds beyond 8
        return `M${r},0A${r},${r} 0 1,1 ${-r},0A${r},${r} 0 1,1 ${r},0Z`;
    }
  }

  // Finding badge symbols, centred on (0, 0), for a disc of radius r: × error, ! warning, i info.
  function badgeSymbol(severity, r) {
    const a = r * 0.34;
    const s = r * 0.46;
    if (severity === "error") return `M${-a},${-a}L${a},${a}M${a},${-a}L${-a},${a}`;
    if (severity === "warn") return `M0,${-s}L0,${s * 0.15}M0,${s * 0.9}L0,${s * 0.95}`;
    return `M0,${-s}L0,${-s * 0.95}M0,${-s * 0.15}L0,${s}`;
  }

  function slotClass(slot) {
    return slot === "fallback" ? "k-fallback" : `k${slot}`;
  }

  // Text widths as the page will draw them, measured with a hidden probe element.
  function measurer(svg) {
    const probe = svg.append("text").attr("visibility", "hidden");
    const measure = (className, text) => probe.attr("class", className).text(text).node().getComputedTextLength();
    measure.remove = () => probe.remove();
    return measure;
  }

  // Box sizes. Widths use the selected (semibold) label so selecting never makes a box overflow.
  function sized(model, t, measure) {
    return model.nodes.map((n) => ({
      ...n,
      w: Math.ceil(measure("label selected", n.name)) + t.pad * 2 + t.glyph + t.glyphGap,
      h: t.nodeHeight,
    }));
  }

  // Positions for `nodes` (mutated in place): "force" or "hierarchy" (rows by depth level).
  function layout(nodes, model, t, mode) {
    const spread = Math.sqrt(nodes.length) * t.edgeLength;
    for (const n of nodes) {
      const seed = G.seedPosition(n.id, spread);
      n.x = seed.x;
      n.y = seed.y;
      n.vx = 0;
      n.vy = 0;
      n.fx = null;
      n.fy = null;
    }
    const linkDistance = (l) => (l.source.w + l.target.w) / 2 + t.edgeLength;
    const damping = Math.min(1, Math.sqrt(REFERENCE_SIZE / Math.max(1, nodes.length)));
    const simulation = d3.forceSimulation(nodes).stop().randomSource(G.random(SEED));
    if (mode === "hierarchy") {
      const levels = G.depthLevels(model);
      const rowGap = t.nodeHeight + t.levelGap;
      for (const n of nodes) n.y = levels.depth.get(n.id) * rowGap;
      const links = model.edges.map((e) => ({ source: e.source, target: e.target, acyclic: levels.acyclicTypes.has(e.type) }));
      simulation
        .force(
          "link",
          d3
            .forceLink(links)
            .id((d) => d.id)
            .distance(linkDistance)
            .strength((l) => (l.acyclic ? HIERARCHY_LINK : HIERARCHY_LINK_OTHER)),
        )
        .force("charge", d3.forceManyBody().strength(CHARGE).distanceMax(REPULSION_RANGE * t.edgeLength))
        .force("x", d3.forceX(0).strength(HIERARCHY_PULL_X))
        .force("y", d3.forceY((d) => levels.depth.get(d.id) * rowGap).strength(LEVEL_PULL))
        .force("collide", G.forceBoxCollide(t.spacing, COLLIDE, "x"));
    } else {
      simulation
        .force("link", d3.forceLink(model.edges.map((e) => ({ source: e.source, target: e.target }))).id((d) => d.id).distance(linkDistance))
        .force("charge", d3.forceManyBody().strength(CHARGE).distanceMax(REPULSION_RANGE * t.edgeLength))
        .force("x", d3.forceX(0).strength(PULL_X * damping))
        .force("y", d3.forceY(0).strength(PULL_Y * damping))
        .force("collide", G.forceBoxCollide(t.spacing, COLLIDE));
    }
    if (nodes.length > UNTANGLE_ABOVE) {
      // Large graphs: first let repulsion act at every range so clusters, seeded interleaved,
      // can pass through each other and separate; then settle with the local forces.
      const charge = simulation.force("charge");
      charge.distanceMax(Infinity);
      for (let i = 0; i < UNTANGLE_TICKS; i++) simulation.tick();
      charge.distanceMax(REPULSION_RANGE * t.edgeLength);
      simulation.alpha(1);
    }
    for (let i = 0; i < TICKS; i++) simulation.tick();
    if (mode === "hierarchy") {
      // Snap each concept onto its row, then resolve overlaps sideways only.
      const levels = G.depthLevels(model);
      const rowGap = t.nodeHeight + t.levelGap;
      for (const n of nodes) n.y = levels.depth.get(n.id) * rowGap;
      G.separate(nodes, t.spacing, 1000, "x");
    } else {
      G.separate(nodes, t.spacing);
    }
    for (const n of nodes) {
      n.x = round(n.x);
      n.y = round(n.y);
    }
  }

  function markers(defs, t) {
    const add = (id, size, path, className) =>
      defs
        .append("marker")
        .attr("id", id)
        .attr("viewBox", "0 0 10 10")
        .attr("refX", 9)
        .attr("refY", 5)
        .attr("markerWidth", size)
        .attr("markerHeight", size)
        .attr("markerUnits", "userSpaceOnUse")
        .attr("orient", "auto-start-reverse")
        .append("path")
        .attr("class", className)
        .attr("d", path);
    add("arrow-filled", t.arrow, "M0,1 L10,5 L0,9 z", "arrow");
    add("arrow-hollow", t.arrowHollow, "M1,1 L9,5 L1,9 z", "arrow-hollow");
    add("arrow-filled-focus", t.arrow, "M0,1 L10,5 L0,9 z", "arrow focus");
    add("arrow-hollow-focus", t.arrowHollow, "M1,1 L9,5 L1,9 z", "arrow-hollow focus");
  }

  function render(svgElement, model, options = {}) {
    const on = { select() {}, hover() {}, pin() {}, ...(options.on || {}) };
    const t = tokens();
    const svg = d3.select(svgElement);
    svg.selectAll("*").remove();
    const measure = measurer(svg);
    let mode = options.layout === "hierarchy" ? "hierarchy" : "force";
    const nodes = sized(model, t, measure);
    layout(nodes, model, t, mode);
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const degree = new Map(nodes.map((n) => [n.id, 0]));
    for (const e of model.edges) {
      degree.set(e.source, degree.get(e.source) + 1);
      degree.set(e.target, degree.get(e.target) + 1);
    }
    const ranked = [...degree.values()].sort((x, y) => y - x);
    const hubDegree = Math.max(HUB_DEGREE, ranked[Math.max(0, Math.ceil(ranked.length * HUB_SHARE) - 1)] || 0);
    const edges = model.edges.map((e) => ({
      ...e,
      text: G.edgeLabel(e),
    }));
    for (const e of edges) e.labelWidth = measure("edge-label", e.text) + t.labelPad * 2;
    measure.remove();
    const findings = options.findings || new Map(); // id -> worst severity

    markers(svg.append("defs"), t);
    const viewport = svg.append("g").attr("class", "viewport");

    const edgeGroups = viewport
      .append("g")
      .attr("class", "edges")
      .selectAll("g")
      .data(edges, (d) => d.id)
      .join("g")
      .attr("class", "edge-group")
      .attr("data-id", (d) => d.id);
    edgeGroups
      .append("line")
      .attr("class", (d) => `edge ${d.encoding.line}`)
      .attr("data-id", (d) => d.id)
      .attr("data-type", (d) => d.type);
    edgeGroups.append("line").attr("class", "edge-hit").attr("data-id", (d) => d.id);

    const nodeGroups = viewport
      .append("g")
      .attr("class", "nodes")
      .selectAll("g")
      .data(nodes, (d) => d.id)
      .join("g")
      .attr("class", (d) => `node ${d.status}${degree.get(d.id) >= hubDegree ? " hub" : ""}`)
      .attr("data-id", (d) => d.id)
      .attr("tabindex", -1)
      .attr("role", "button")
      .attr("aria-label", (d) => `${d.name} (${d.kind}, ${d.status})`);
    nodeGroups
      .append("rect")
      .attr("class", "focus-ring")
      .attr("x", -t.focusRing)
      .attr("y", -t.focusRing)
      .attr("width", (d) => d.w + 2 * t.focusRing)
      .attr("height", (d) => d.h + 2 * t.focusRing)
      .attr("rx", t.radius + t.focusRing);
    nodeGroups
      .append("rect")
      .attr("class", (d) => `box ${d.status}`)
      .attr("x", t.border / 2)
      .attr("y", t.border / 2)
      .attr("width", (d) => d.w - t.border)
      .attr("height", (d) => d.h - t.border)
      .attr("rx", t.radius);
    nodeGroups
      .append("path")
      .attr("class", (d) => `glyph ${slotClass(d.encoding.slot)}${d.status === "proposed" ? " proposed" : ""}`)
      .attr("data-shape", (d) => d.encoding.shape)
      .attr("d", (d) => glyphPath(d.encoding.shape, t.glyph))
      .attr("transform", (d) => `translate(${t.pad + t.glyph / 2},${d.h / 2})`);
    // Semantic zoom: when zoomed out, a minor concept collapses to this glyph at its centre.
    nodeGroups
      .append("path")
      .attr("class", (d) => `glyph-solo ${slotClass(d.encoding.slot)}${d.status === "proposed" ? " proposed" : ""}`)
      .attr("d", (d) => glyphPath(d.encoding.shape, t.glyph))
      .attr("transform", (d) => `translate(${d.w / 2},${d.h / 2})`);
    nodeGroups
      .append("text")
      .attr("class", "label")
      .attr("x", t.pad + t.glyph + t.glyphGap)
      .attr("y", (d) => d.h / 2)
      .attr("dominant-baseline", "central")
      .text((d) => d.name);
    const badges = nodeGroups
      .filter((d) => findings.has(d.id))
      .append("g")
      .attr("class", (d) => `finding-badge ${findings.get(d.id)}`)
      .attr("data-severity", (d) => findings.get(d.id))
      .attr("transform", (d) => `translate(${d.w - t.border},${t.border})`);
    badges.append("circle").attr("class", (d) => `badge ${findings.get(d.id)}`).attr("r", t.badge / 2);
    badges
      .append("path")
      .attr("class", "badge-glyph")
      .attr("d", (d) => badgeSymbol(findings.get(d.id), t.badge / 2));

    // Labels sit above the boxes, so they are drawn last. Hidden at rest.
    const labels = viewport
      .append("g")
      .attr("class", "edge-labels")
      .selectAll("text")
      .data(edges, (d) => d.id)
      .join("text")
      .attr("class", "edge-label")
      .attr("data-id", (d) => d.id)
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "central")
      .text((d) => d.text);

    // --- Geometry ------------------------------------------------------------------------

    let state = { hidden: new Set() };

    function placeNodes(selection) {
      selection.attr("transform", (d) => `translate(${round(d.x - d.w / 2)},${round(d.y - d.h / 2)})`);
    }

    // Edge end points, clipped to the boxes. An edge to a hidden concept is a short stub.
    function edgeGeometry(e) {
      const a = byId.get(e.source);
      const b = byId.get(e.target);
      const [x1, y1] = G.exitPoint(a, b.x, b.y, t.clearance);
      const [x2, y2] = G.exitPoint(b, a.x, a.y, t.clearance);
      const hiddenA = state.hidden.has(a.id);
      const hiddenB = state.hidden.has(b.id);
      if (hiddenA !== hiddenB) {
        const [sx, sy, ex, ey] = hiddenB ? [x1, y1, x2, y2] : [x2, y2, x1, y1];
        const length = Math.hypot(ex - sx, ey - sy) || 1;
        const k = Math.min(1, t.stub / length);
        return { x1: sx, y1: sy, x2: sx + (ex - sx) * k, y2: sy + (ey - sy) * k, stub: true, towardsSource: hiddenA };
      }
      return { x1, y1, x2, y2, stub: false };
    }

    function placeEdges(groups, labelSel) {
      groups.each(function (d) {
        d.geometry = edgeGeometry(d);
      });
      groups
        .selectAll("line")
        .attr("x1", (d) => round(d.geometry.x1))
        .attr("y1", (d) => round(d.geometry.y1))
        .attr("x2", (d) => round(d.geometry.x2))
        .attr("y2", (d) => round(d.geometry.y2));
      labelSel.each(function (d) {
        const g = d.geometry;
        d.label = G.placeLabel(g.x1, g.y1, g.x2, g.y2, d.labelWidth, t.nodeHeight, nodes);
      });
      labelSel.attr("x", (d) => round(d.label.x)).attr("y", (d) => round(d.label.y));
    }

    function placeAll() {
      placeNodes(nodeGroups);
      placeEdges(edgeGroups, labels);
    }

    function touching(id) {
      return [edgeGroups.filter((e) => e.source === id || e.target === id), labels.filter((e) => e.source === id || e.target === id)];
    }

    placeAll();
    const home = new Map(nodes.map((n) => [n.id, [n.x, n.y]]));

    // --- Camera (pan and zoom) ---------------------------------------------------------

    let scale = 1;
    const zoom = d3
      .zoom()
      .scaleExtent([MIN_ZOOM, MAX_ZOOM])
      .filter((event) => (!event.ctrlKey || event.type === "wheel") && !event.button)
      .on("zoom", (event) => {
        viewport.attr("transform", event.transform);
        scale = event.transform.k;
        svg.classed("zoomed-out", scale < GLYPH_ONLY_BELOW).classed("zoomed-in", scale > ALL_LABELS_ABOVE);
        svg.attr("data-scale", round(scale));
      });
    svg.call(zoom).on("dblclick.zoom", null);

    function bounds(ids) {
      const set = ids ? nodes.filter((n) => ids.has(n.id)) : nodes.filter((n) => !state.hidden.has(n.id));
      const list = set.length ? set : nodes;
      return [
        Math.min(...list.map((n) => n.x - n.w / 2)),
        Math.min(...list.map((n) => n.y - n.h / 2)),
        Math.max(...list.map((n) => n.x + n.w / 2)),
        Math.max(...list.map((n) => n.y + n.h / 2)),
      ];
    }

    // A bottom-left corner of the canvas kept clear for an overlaid control (the legend):
    // {width, height} in screen pixels.
    const reserved = options.reserveCorner || (() => ({ width: 0, height: 0 }));

    // Fit the visible graph in the canvas, never enlarging past 1:1 so text keeps its size.
    // With a reserved corner, the graph goes either above it or to its right, whichever
    // allows the larger scale.
    function fit() {
      if (!nodes.length) return;
      const width = svgElement.clientWidth;
      const height = svgElement.clientHeight;
      const corner = reserved();
      const [x0, y0, x1, y1] = bounds();
      const scaleFor = (w, h) =>
        Math.max(MIN_ZOOM, Math.min(1, (w - 2 * t.fitPad) / (x1 - x0 || 1), (h - 2 * t.fitPad) / (y1 - y0 || 1)));
      const areas = [
        { left: 0, width, height }, // the whole canvas, when nothing is reserved
        { left: 0, width, height: height - corner.height }, // above the corner
        { left: corner.width, width: width - corner.width, height }, // right of the corner
      ].filter((a, i) => (corner.width || corner.height ? i > 0 : i === 0) && a.width > 0 && a.height > 0);
      const area = areas.reduce((best, a) => (scaleFor(a.width, a.height) > scaleFor(best.width, best.height) ? a : best));
      const k = scaleFor(area.width, area.height);
      const transform = d3.zoomIdentity
        .translate(
          round(area.left + area.width / 2 - (k * (x0 + x1)) / 2),
          round(area.height / 2 - (k * (y0 + y1)) / 2),
        )
        .scale(round(k * 1000) / 1000);
      svg.call(zoom.transform, transform);
    }

    // Move the camera so a concept sits in the centre, keeping the current scale.
    // When `around` (ids, e.g. the neighbourhood) is given and the view is zoomed out so far
    // that boxes have collapsed, zoom in until those concepts fit around the centre (never past 1:1).
    function centreOn(id, around) {
      const n = byId.get(id);
      if (!n) return;
      const width = svgElement.clientWidth;
      const height = svgElement.clientHeight;
      let k = scale;
      if (around && scale < GLYPH_ONLY_BELOW) {
        let dx = n.w / 2;
        let dy = n.h / 2;
        for (const other of around) {
          const o = byId.get(other);
          if (!o || state.hidden.has(other)) continue;
          dx = Math.max(dx, Math.abs(o.x - n.x) + o.w / 2);
          dy = Math.max(dy, Math.abs(o.y - n.y) + o.h / 2);
        }
        const fitK = Math.min((width / 2 - t.fitPad) / dx, (height / 2 - t.fitPad) / dy);
        k = Math.min(1, Math.max(GLYPH_ONLY_BELOW, fitK));
      }
      const transform = d3.zoomIdentity.translate(round(width / 2 - k * n.x), round(height / 2 - k * n.y)).scale(k);
      svg.call(zoom.transform, transform);
    }

    // Pan just enough to bring a concept into view (used when the keyboard moves focus).
    function ensureVisible(id) {
      const n = byId.get(id);
      if (!n) return;
      const transform = d3.zoomTransform(svgElement);
      const [x, y] = transform.apply([n.x, n.y]);
      const margin = t.fitPad + n.w * transform.k;
      if (x < margin || y < margin || x > svgElement.clientWidth - margin || y > svgElement.clientHeight - margin) {
        centreOn(id);
      }
    }

    function zoomBy(factor) {
      svg.call(zoom.scaleBy, factor);
    }

    // --- Interaction -------------------------------------------------------------------

    nodeGroups
      .on("click", (event, d) => {
        event.stopPropagation();
        on.select(d.id);
      })
      .on("mouseenter", (event, d) => {
        nodeGroups.classed("hover", (n) => n.id === d.id);
        on.hover(d.id, event.currentTarget.getBoundingClientRect());
      })
      .on("mouseleave", () => {
        nodeGroups.classed("hover", false);
        on.hover(null);
      });
    svg.on("click", () => on.select(null));
    edgeGroups
      .on("mouseenter", (_, d) => labels.filter((l) => l.id === d.id).classed("hover", true))
      .on("mouseleave", (_, d) => labels.filter((l) => l.id === d.id).classed("hover", false));

    // Drag a concept to pin it where you drop it. Only that concept moves.
    const drag = d3
      .drag()
      .clickDistance(4)
      .on("start", (event) => event.sourceEvent.stopPropagation())
      .on("drag", function (event, d) {
        d.x = round(d.x + event.dx);
        d.y = round(d.y + event.dy);
        d.pinned = true;
        d3.select(this).classed("pinned", true);
        placeNodes(d3.select(this));
        const [groups, labelSel] = touching(d.id);
        placeEdges(groups, labelSel);
      })
      .on("end", (_, d) => {
        if (d.pinned) on.pin(d.id);
      });
    nodeGroups.call(drag);

    // Put every concept back where the layout placed it.
    function resetLayout() {
      for (const n of nodes) {
        [n.x, n.y] = home.get(n.id);
        n.pinned = false;
      }
      nodeGroups.classed("pinned", false);
      placeAll();
    }

    function setLayout(next) {
      if (next === mode) return;
      mode = next;
      layout(nodes, model, t, mode);
      for (const n of nodes) home.set(n.id, [n.x, n.y]);
      nodeGroups.classed("pinned", false);
      placeAll();
      fit();
    }

    // --- State --------------------------------------------------------------------------
    // state: {selected, near: Map id -> distance | null, hidden: Set, highlight: Set | null,
    //         highlightEdges: Set | null, hiddenEdges: Set}
    function update(next) {
      const previousHidden = state.hidden;
      state = { hidden: new Set(), hiddenEdges: new Set(), ...next };
      const near = state.near;
      const selected = state.selected;
      const isNear = (id) => !near || near.has(id);
      const highlight = state.highlight;

      nodeGroups
        .classed("selected", (d) => d.id === selected)
        .classed("near", (d) => Boolean(near) && near.has(d.id) && d.id !== selected)
        .classed("faded", (d) => !isNear(d.id) || (highlight !== null && highlight !== undefined && !highlight.has(d.id)))
        .classed("highlight", (d) => Boolean(highlight) && highlight.has(d.id))
        .classed("hidden", (d) => state.hidden.has(d.id))
        .attr("aria-current", (d) => (d.id === selected ? "true" : null));
      nodeGroups.selectAll(".label").classed("selected", (d) => d.id === selected);

      const edgeClass = (e) => {
        const bothHidden = state.hidden.has(e.source) && state.hidden.has(e.target);
        const typeHidden = state.hiddenEdges.has(e.type);
        const focus = Boolean(selected) && (e.source === selected || e.target === selected);
        const inNear = Boolean(near) && near.has(e.source) && near.has(e.target);
        const lit = !state.highlightEdges || state.highlightEdges.has(e.id);
        return { hidden: bothHidden || typeHidden, focus, near: inNear && !focus, faded: (near && !inNear) || !lit };
      };
      edgeGroups.each(function (e) {
        e.state = edgeClass(e);
      });
      edgeGroups
        .classed("hidden", (e) => e.state.hidden)
        .classed("focus", (e) => e.state.focus)
        .classed("near", (e) => e.state.near)
        .classed("faded", (e) => e.state.faded)
        .classed("highlight", (e) => Boolean(state.highlightEdges) && state.highlightEdges.has(e.id));
      edgeGroups
        .select("line.edge")
        .attr("marker-end", (e) => {
          if (e.encoding.arrow === "none" || (e.geometry && e.geometry.stub && e.geometry.towardsSource)) return null;
          const lit = e.state.focus || e.state.near;
          return `url(#arrow-${e.encoding.arrow}${lit ? "-focus" : ""})`;
        });
      labels
        .classed("focus", (e) => e.state.focus && !e.state.hidden)
        .classed("hidden", (e) => e.state.hidden);

      const hiddenChanged =
        previousHidden.size !== state.hidden.size || [...state.hidden].some((id) => !previousHidden.has(id));
      if (hiddenChanged) {
        placeEdges(edgeGroups, labels);
        edgeGroups.classed("stub", (e) => e.geometry.stub);
        edgeGroups
          .select("line.edge")
          .attr("marker-end", (e) =>
            e.encoding.arrow === "none" || (e.geometry.stub && e.geometry.towardsSource)
              ? null
              : `url(#arrow-${e.encoding.arrow}${e.state.focus || e.state.near ? "-focus" : ""})`,
          );
      }
    }

    function focusNode(id) {
      const node = nodeGroups.filter((d) => d.id === id).node();
      if (node) node.focus({ preventScroll: true });
    }

    function setTabStop(id) {
      nodeGroups.attr("tabindex", (d) => (d.id === id ? 0 : -1));
    }

    update({});
    fit();
    setTabStop(nodes.length ? [...nodes].sort((a, b) => degree.get(b.id) - degree.get(a.id) || a.id.localeCompare(b.id))[0].id : null);
    let resizeTimer = null;
    root.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(fit, 50);
    });

    return {
      update,
      fit,
      centreOn,
      ensureVisible,
      zoomBy,
      resetLayout,
      setLayout,
      focusNode,
      setTabStop,
      layoutMode: () => mode,
      scale: () => scale,
      degree: (id) => degree.get(id),
      // Layout coordinates (box centres), independent of the viewport. Used by tests.
      positions: () => Object.fromEntries(nodes.map((n) => [n.id, [n.x, n.y]])),
    };
  }

  root.OntologyGraphView = { render, glyphPath, badgeSymbol };
})(window);

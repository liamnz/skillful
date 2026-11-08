// Graph view: lays the model out with d3-force and draws it once as SVG.
// The layout is deterministic: positions are seeded from concept ids, the simulation uses a
// seeded random source, and a fixed number of ticks run synchronously before a single render.
// There is no animated settling. Every size comes from tokens.css.
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

  function layout(model, t, measure) {
    const spread = Math.sqrt(model.nodes.length) * t.edgeLength;
    const nodes = model.nodes.map((n) => {
      const seed = G.seedPosition(n.id, spread);
      const w = Math.ceil(measure("label", n.name)) + t.pad * 2 + t.glyph + t.glyphGap;
      return { ...n, w, h: t.nodeHeight, x: seed.x, y: seed.y };
    });
    const links = model.edges.map((e) => ({ source: e.source, target: e.target }));
    const simulation = d3
      .forceSimulation(nodes)
      .stop()
      .randomSource(G.random(SEED))
      .force(
        "link",
        d3
          .forceLink(links)
          .id((d) => d.id)
          .distance((l) => (l.source.w + l.target.w) / 2 + t.edgeLength),
      )
      .force("charge", d3.forceManyBody().strength(CHARGE).distanceMax(REPULSION_RANGE * t.edgeLength))
      .force("x", d3.forceX(0).strength(PULL_X))
      .force("y", d3.forceY(0).strength(PULL_Y))
      .force("collide", G.forceBoxCollide(t.spacing, COLLIDE));
    for (let i = 0; i < TICKS; i++) simulation.tick();
    G.separate(nodes, t.spacing);
    return nodes;
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
  }

  function render(svgElement, model) {
    const t = tokens();
    const svg = d3.select(svgElement);
    svg.selectAll("*").remove();
    const measure = measurer(svg);
    const nodes = layout(model, t, measure);
    const byId = new Map(nodes.map((n) => [n.id, n]));

    const edges = model.edges.map((e) => {
      const a = byId.get(e.source);
      const b = byId.get(e.target);
      const [x1, y1] = G.exitPoint(a, b.x, b.y, t.clearance);
      const [x2, y2] = G.exitPoint(b, a.x, a.y, t.clearance);
      const text = G.edgeLabel(e);
      const label = G.placeLabel(x1, y1, x2, y2, measure("edge-label", text) + t.labelPad * 2, t.nodeHeight, nodes);
      return { ...e, x1, y1, x2, y2, text, label };
    });
    measure.remove();

    markers(svg.append("defs"), t);
    const viewport = svg.append("g").attr("class", "viewport");

    const edgeGroups = viewport
      .append("g")
      .attr("class", "edges")
      .selectAll("g")
      .data(edges, (d) => d.id)
      .join("g")
      .attr("class", "edge-group");
    for (const className of ["edge", "edge-hit"]) {
      edgeGroups
        .append("line")
        .attr("class", (d) => (className === "edge" ? `edge ${d.encoding.line}` : className))
        .attr("data-id", (d) => d.id)
        .attr("x1", (d) => round(d.x1))
        .attr("y1", (d) => round(d.y1))
        .attr("x2", (d) => round(d.x2))
        .attr("y2", (d) => round(d.y2));
    }
    edgeGroups
      .select("line.edge")
      .attr("data-type", (d) => d.type)
      .attr("marker-end", (d) => (d.encoding.arrow === "none" ? null : `url(#arrow-${d.encoding.arrow})`));

    const nodeGroups = viewport
      .append("g")
      .attr("class", "nodes")
      .selectAll("g")
      .data(nodes, (d) => d.id)
      .join("g")
      .attr("class", (d) => `node ${d.status}`)
      .attr("data-id", (d) => d.id)
      .attr("transform", (d) => `translate(${round(d.x - d.w / 2)},${round(d.y - d.h / 2)})`);
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
    nodeGroups
      .append("text")
      .attr("class", "label")
      .attr("x", t.pad + t.glyph + t.glyphGap)
      .attr("y", (d) => d.h / 2)
      .attr("dominant-baseline", "central")
      .text((d) => d.name);

    // Labels sit above the boxes, so they are drawn last. Hidden at rest; shown on hover.
    const labels = viewport
      .append("g")
      .attr("class", "edge-labels")
      .selectAll("text")
      .data(edges, (d) => d.id)
      .join("text")
      .attr("class", "edge-label")
      .attr("data-id", (d) => d.id)
      .attr("x", (d) => round(d.label.x))
      .attr("y", (d) => round(d.label.y))
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "central")
      .text((d) => d.text);
    edgeGroups
      .on("mouseenter", (_, d) => labels.filter((l) => l.id === d.id).classed("hover", true))
      .on("mouseleave", (_, d) => labels.filter((l) => l.id === d.id).classed("hover", false));

    // Fit the whole graph in the canvas, never enlarging past 1:1 so text keeps its size.
    function fit() {
      if (!nodes.length) return;
      const width = svgElement.clientWidth;
      const height = svgElement.clientHeight;
      const x0 = Math.min(...nodes.map((n) => n.x - n.w / 2));
      const x1 = Math.max(...nodes.map((n) => n.x + n.w / 2));
      const y0 = Math.min(...nodes.map((n) => n.y - n.h / 2));
      const y1 = Math.max(...nodes.map((n) => n.y + n.h / 2));
      const scale = Math.min(1, (width - 2 * t.fitPad) / (x1 - x0), (height - 2 * t.fitPad) / (y1 - y0));
      const tx = width / 2 - scale * (x0 + x1) / 2;
      const ty = height / 2 - scale * (y0 + y1) / 2;
      viewport.attr("transform", `translate(${round(tx)},${round(ty)}) scale(${round(scale * 1000) / 1000})`);
    }
    fit();
    root.addEventListener("resize", fit);

    return {
      // Layout coordinates (box centres), independent of the viewport. Used by tests.
      positions: () => Object.fromEntries(nodes.map((n) => [n.id, [n.x, n.y]])),
    };
  }

  root.OntologyGraphView = { render, glyphPath };
})(window);

// Graph model: pure functions over the embedded data contract, with no D3 and no DOM.
// Turns concepts and relations into nodes and edges, and holds the deterministic geometry
// (seeded positions, box collision, edge clipping and label placement) the view relies on.
(function (root) {
  "use strict";

  const FALLBACK_KIND = { slot: "fallback", shape: "circle" };
  const FALLBACK_RELATION = { line: "solid", arrow: "filled" };

  // 32-bit FNV-1a hash of a string.
  function hash(text) {
    let h = 0x811c9dc5;
    for (const ch of text) {
      h ^= ch.codePointAt(0);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    return h >>> 0;
  }

  // A small seeded PRNG (mulberry32): the same seed always yields the same sequence.
  function random(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // A starting position derived only from the concept's id, inside a disc of radius `spread`.
  // Id seeding keeps familiar concepts roughly in place when others are added.
  function seedPosition(id, spread) {
    const h = hash(id);
    const angle = ((h & 0xffff) / 0x10000) * 2 * Math.PI;
    const radius = spread * Math.sqrt(((h >>> 16) + 1) / 0x10000);
    return { x: radius * Math.cos(angle), y: radius * Math.sin(angle) };
  }

  function edgeLabel(edge) {
    const name = edge.type.replace(/_/g, " ");
    return edge.cardinality ? `${name} · ${edge.cardinality}` : name;
  }

  // Nodes in concept (id) order; edges in concept order, then relation order. Relations to
  // unknown concepts and self-relations are left out: the validator reports those.
  function buildModel(data) {
    const kinds = new Map(data.vocabulary.kinds.map((k) => [k.id, k.encoding]));
    const relationTypes = new Map(data.vocabulary.relation_types.map((r) => [r.id, r.encoding]));
    const nodes = data.concepts.map((c) => ({
      id: c.id,
      name: c.name,
      kind: c.kind,
      status: c.status,
      encoding: kinds.get(c.kind) || FALLBACK_KIND,
    }));
    const ids = new Set(nodes.map((n) => n.id));
    const seen = new Map();
    const edges = [];
    for (const concept of data.concepts) {
      for (const relation of concept.relations) {
        if (!ids.has(relation.target) || relation.target === concept.id) continue;
        const key = `${concept.id}|${relation.type}|${relation.target}`;
        const count = seen.get(key) || 0;
        seen.set(key, count + 1);
        edges.push({
          id: count ? `${key}|${count}` : key,
          source: concept.id,
          target: relation.target,
          type: relation.type,
          cardinality: relation.cardinality || null,
          encoding: relationTypes.get(relation.type) || FALLBACK_RELATION,
        });
      }
    }
    return {
      nodes,
      edges,
      kinds: new Map(data.vocabulary.kinds.map((k) => [k.id, k])),
      relationTypes: new Map(data.vocabulary.relation_types.map((r) => [r.id, r])),
    };
  }

  // Depth levels for the hierarchy layout. Edges of `acyclic` relation types (core is_a and
  // part_of, plus extensions marked acyclic) point from child to parent, so a parent sits above
  // its children. A concept's depth is the length of its longest path up to a root, which puts a
  // concept with several parents below all of them. Cycles (E006) are cut off after
  // `nodes.length` rounds.
  // A concept in no acyclic relation hangs one row below the nearest concept it is related to
  // (an attribute below its entity, a metric below what it measures), found breadth-first over
  // the other relations; a group with no hierarchy at all starts its own tree at row 0.
  function depthLevels(model) {
    const acyclicTypes = new Set([...model.relationTypes.values()].filter((r) => r.acyclic).map((r) => r.id));
    const edges = model.edges.filter((e) => acyclicTypes.has(e.type));
    const inHierarchy = new Set(edges.flatMap((e) => [e.source, e.target]));
    const depth = new Map(model.nodes.map((n) => [n.id, 0]));
    for (let round = 0; round < model.nodes.length; round++) {
      let changed = false;
      for (const e of edges) {
        const below = depth.get(e.target) + 1;
        if (depth.get(e.source) < below) {
          depth.set(e.source, below);
          changed = true;
        }
      }
      if (!changed) break;
    }
    const adj = adjacency(model.nodes, model.edges);
    const placed = new Set(inHierarchy);
    const hang = (frontier) => {
      while (frontier.length) {
        const next = [];
        for (const id of frontier) {
          for (const other of adj.get(id) || []) {
            if (placed.has(other)) continue;
            placed.add(other);
            depth.set(other, depth.get(id) + 1);
            next.push(other);
          }
        }
        frontier = next.sort();
      }
    };
    hang([...inHierarchy].sort((a, b) => depth.get(a) - depth.get(b) || (a < b ? -1 : 1)));
    for (const n of [...model.nodes].sort((a, b) => (a.id < b.id ? -1 : 1))) {
      if (placed.has(n.id)) continue;
      placed.add(n.id);
      depth.set(n.id, 0);
      hang([n.id]);
    }
    return { depth, acyclicTypes };
  }

  // How far two centred boxes ({x, y, w, h}) overlap on each axis, including a gap.
  function overlap(a, b, gap) {
    return [(a.w + b.w) / 2 + gap - Math.abs(b.x - a.x), (a.h + b.h) / 2 + gap - Math.abs(b.y - a.y)];
  }

  // A d3-force compatible force that pushes overlapping boxes apart along the axis where
  // they overlap least (or only sideways, with axis "x", which keeps hierarchy rows level).
  // Uses each box's width and height, not a circle radius.
  function forceBoxCollide(gap, strength, axis) {
    let nodes = [];
    function force() {
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          const [ox, oy] = overlap(a, b, gap);
          if (ox <= 0 || oy <= 0) continue;
          if (axis === "x" || (axis !== "y" && ox < oy)) {
            const push = (b.x >= a.x ? 1 : -1) * ox * strength * 0.5;
            a.vx -= push;
            b.vx += push;
          } else {
            const push = (b.y >= a.y ? 1 : -1) * oy * strength * 0.5;
            a.vy -= push;
            b.vy += push;
          }
        }
      }
    }
    force.initialize = (n) => {
      nodes = n;
    };
    return force;
  }

  // Moves boxes directly until none overlap (with `gap` between them). Run after the
  // simulation so the "boxes never overlap" guarantee doesn't rest on the physics settling.
  // Returns the number of rounds it took.
  function separate(nodes, gap, maxRounds = 1000, axis) {
    for (let round = 0; round < maxRounds; round++) {
      let moved = false;
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          const [ox, oy] = overlap(a, b, gap);
          if (ox <= 0 || oy <= 0) continue;
          moved = true;
          if (axis === "x" || (axis !== "y" && ox < oy)) {
            const push = (b.x >= a.x ? 1 : -1) * (ox / 2 + 0.01);
            a.x -= push;
            b.x += push;
          } else {
            const push = (b.y >= a.y ? 1 : -1) * (oy / 2 + 0.01);
            a.y -= push;
            b.y += push;
          }
        }
      }
      if (!moved) return round;
    }
    return maxRounds;
  }

  // Where the line from a box's centre towards (tx, ty) leaves the box, plus a gap.
  function exitPoint(box, tx, ty, gap) {
    const dx = tx - box.x;
    const dy = ty - box.y;
    const t = Math.min((box.w / 2 + gap) / Math.abs(dx || 1e-9), (box.h / 2 + gap) / Math.abs(dy || 1e-9));
    return [box.x + dx * t, box.y + dy * t];
  }

  function intersects(a, b) {
    return Math.abs(a.x - b.x) * 2 < a.w + b.w && Math.abs(a.y - b.y) * 2 < a.h + b.h;
  }

  // The centre for a label of size (w, h) on the segment (x1, y1)-(x2, y2): the midpoint,
  // or the nearest point along the segment that clears every box.
  function placeLabel(x1, y1, x2, y2, w, h, boxes) {
    const at = (t) => ({ x: x1 + (x2 - x1) * t, y: y1 + (y2 - y1) * t, w, h });
    for (const t of [0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8]) {
      const label = at(t);
      if (!boxes.some((box) => intersects(label, box))) return label;
    }
    return at(0.5);
  }

  // --- Graph queries ------------------------------------------------------------------

  // Undirected adjacency: id -> sorted neighbour ids. `edges` may be a filtered subset.
  function adjacency(nodes, edges) {
    const out = new Map(nodes.map((n) => [n.id, new Set()]));
    for (const e of edges) {
      if (out.has(e.source) && out.has(e.target)) {
        out.get(e.source).add(e.target);
        out.get(e.target).add(e.source);
      }
    }
    return new Map([...out].map(([id, set]) => [id, [...set].sort()]));
  }

  // Concepts up to `hops` relations away from `id`, following relations in either direction.
  // Returns id -> distance (the concept itself is 0).
  function neighbourhood(adj, id, hops) {
    const distance = new Map([[id, 0]]);
    let frontier = [id];
    for (let d = 1; d <= hops && frontier.length; d++) {
      const next = [];
      for (const node of frontier) {
        for (const other of adj.get(node) || []) {
          if (!distance.has(other)) {
            distance.set(other, d);
            next.push(other);
          }
        }
      }
      frontier = next;
    }
    return distance;
  }

  // The first sentence of a definition, for previews.
  function firstSentence(text) {
    const trimmed = (text || "").trim().replace(/\s+/g, " ");
    const match = trimmed.match(/^.*?[.!?](?=\s|$)/);
    return match ? match[0] : trimmed;
  }

  // A plural for display only ("Order line" -> "Order lines"). Plain English rules on the last word.
  function plural(name) {
    if (/(s|x|z|ch|sh)$/i.test(name)) return `${name}es`;
    if (/[^aeiou]y$/i.test(name)) return `${name.slice(0, -1)}ies`;
    return `${name}s`;
  }

  // How a relation reads in prose. `cardinality` is read source:target ("1:N": one source, many
  // targets). From the source, the target side counts; from the target (`incoming`), the source side.
  function relationPhrase(label, cardinality, incoming) {
    const words = label.replace(/_/g, " ");
    if (!cardinality) return { verb: words, many: false };
    const [sourceSide, targetSide] = cardinality.split(":");
    const far = incoming ? sourceSide : targetSide;
    const many = far !== "1";
    return { verb: `${words} ${many ? "many" : "one"}`, many };
  }

  // --- Overlays -----------------------------------------------------------------------

  const DRIFT_CODES = new Set(["W105", "W106"]);

  // The concepts and relations an overlay highlights; everything else recedes.
  //   health  concepts with any finding;
  //   mud     proposed concepts, concepts with open questions, and relations that use
  //           related_to or a relation type that is still proposed;
  //   drift   concepts with W105 or W106 findings.
  // Returns null for "none".
  function overlaySets(model, data, overlay) {
    if (!overlay || overlay === "none") return null;
    const nodes = new Set();
    const edges = new Set();
    if (overlay === "health" || overlay === "drift") {
      for (const f of data.findings) {
        if (f.concept && (overlay === "health" || DRIFT_CODES.has(f.code))) nodes.add(f.concept);
      }
    } else if (overlay === "mud") {
      for (const c of data.concepts) {
        if (c.status === "proposed" || (c.open_questions || []).length) nodes.add(c.id);
      }
      for (const e of model.edges) {
        const type = model.relationTypes.get(e.type);
        if (e.type === "related_to" || (type && type.status === "proposed")) edges.add(e.id);
      }
    }
    const known = new Set(model.nodes.map((n) => n.id));
    return { nodes: new Set([...nodes].filter((id) => known.has(id))), edges };
  }

  // --- Search -------------------------------------------------------------------------

  const RANKS = ["exact", "prefix", "redirect", "definition"];

  function normalise(text) {
    return (text || "").toLowerCase().replace(/\s+/g, " ").trim();
  }

  // True if `text` starts with `q`, or any word in it does.
  function startsWord(text, q) {
    return text.startsWith(q) || text.split(/[\s\-_/]+/).some((word) => word.startsWith(q));
  }

  // Search results, best first, each concept at most once at its best rank:
  //   exact     the name equals the query;
  //   prefix    the name, or a word in it, starts with the query;
  //   redirect  a discouraged term matches: shown as "'term' -> use Name", never as an equal match;
  //   definition the definition (or, failing all else, the name) contains the query.
  // Ties are broken by name, then id, so the order is deterministic.
  function search(concepts, query, limit = 10) {
    const q = normalise(query);
    if (!q) return [];
    const results = [];
    for (const c of concepts) {
      const name = normalise(c.name);
      let hit = null;
      if (name === q) hit = { rank: "exact" };
      else if (startsWord(name, q)) hit = { rank: "prefix" };
      else {
        const term = (c.discouraged_terms || []).find((t) => startsWord(normalise(t.term), q));
        if (term) hit = { rank: "redirect", term: term.term };
        else if (normalise(c.definition).includes(q) || name.includes(q)) hit = { rank: "definition" };
      }
      if (hit) results.push({ id: c.id, name: c.name, ...hit });
    }
    results.sort(
      (a, b) =>
        RANKS.indexOf(a.rank) - RANKS.indexOf(b.rank) ||
        a.name.localeCompare(b.name) ||
        (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
    );
    return results.slice(0, limit);
  }

  root.OntologyGraph = {
    search,
    overlaySets,
    hash,
    random,
    seedPosition,
    edgeLabel,
    buildModel,
    depthLevels,
    adjacency,
    neighbourhood,
    firstSentence,
    plural,
    relationPhrase,
    forceBoxCollide,
    separate,
    exitPoint,
    placeLabel,
  };
})(window);

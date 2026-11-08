// The ontology view. Reads the data contract embedded by `onto.py build` (see ontokit/build.py),
// builds the graph model (graph-model.js) and draws it (graph-view.js).
(function () {
  "use strict";

  const data = JSON.parse(document.getElementById("ontology-data").textContent);
  const SVG_NS = "http://www.w3.org/2000/svg";

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function count(n, singular, plural) {
    return `${n} ${n === 1 ? singular : plural}`;
  }

  const model = OntologyGraph.buildModel(data);
  const summary = [
    count(data.concepts.length, "concept", "concepts"),
    count(model.edges.length, "relation", "relations"),
  ].join(" · ");

  const toolbar = element("header", "toolbar");
  const brand = element("div", "brand", data.ontology.name);
  brand.append(element("span", "", "ontology"));
  toolbar.append(brand, element("div", "counts", summary));

  const canvas = element("main", "canvas");
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "graph");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `Concept graph of ${data.ontology.name}: ${summary}`);
  canvas.append(svg);
  if (!data.concepts.length) {
    canvas.append(element("p", "empty", "No concepts yet. Add one with 'onto.py new', then build again."));
  }

  const app = document.getElementById("app");
  app.className = "app";
  app.replaceChildren(toolbar, canvas);

  const view = OntologyGraphView.render(svg, model);

  // Exposed for tests and for debugging in the browser console.
  window.ontologyView = {
    data,
    model,
    d3Loaded: typeof d3 === "object" && typeof d3.forceSimulation === "function",
    positions: view.positions,
    ready: true,
  };
})();

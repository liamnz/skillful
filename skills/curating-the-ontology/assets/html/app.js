// The ontology view. Reads the data contract embedded by `onto.py build` (see ontokit/build.py).
// Placeholder until the graph view lands: shows the ontology's name and what the data holds.
(function () {
  "use strict";

  const data = JSON.parse(document.getElementById("ontology-data").textContent);

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function count(n, singular, plural) {
    return `${n} ${n === 1 ? singular : plural}`;
  }

  const relations = data.concepts.reduce((sum, concept) => sum + concept.relations.length, 0);
  const page = element("main", "placeholder");
  page.append(
    element("h1", "", data.ontology.name),
    element("p", "", data.ontology.description),
    element(
      "p",
      "counts",
      [
        count(data.concepts.length, "concept", "concepts"),
        count(relations, "relation", "relations"),
        count(data.findings.length, "finding", "findings"),
      ].join(" · "),
    ),
    element("p", "", "The interactive graph is not built yet. This page confirms the data and libraries load."),
  );
  document.getElementById("app").replaceChildren(page);

  // Exposed for tests and for debugging in the browser console.
  window.ontologyView = { data, d3Loaded: typeof d3 === "object" && typeof d3.forceSimulation === "function" };
})();

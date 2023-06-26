import { html } from "https://esm.sh/htm/react/index.module.js";
import { useState } from "https://esm.sh/react";

function MotifSearch({ regions, initialResults, initalError}) {
  const nodes = ["A", "B", "C"];
  const nueropils = ["Any", ...regions];
  const NEURO_TRANSMITTER_NAMES = {
    DA: "dopamine",
    SER: "serotonin",
    GABA: "gabaergic",
    GLUT: "glutamate",
    ACH: "acetylcholine",
    OCT: "octopamine",
  };

  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(initialResults);
  const [error, setError] = useState(initalError);
  const [warning, setWarning] = useState();

  const attributes = {
    EdgeFields: {
      regions: {
        fieldSettings: {
          listValues: regions,
        },
        label: "Region",
        operators: ["multiselect_equals"],
        type: "multiselect",
      },
      min_synapse_count: {
        label: "Min Synapse Count",
        operators: ["equal"],
        type: "number",
      },
    },
    NodeFields: { search_query: { label: "Search Query", operators: ["equal"], type: "text" } },
  };

  return html`
    <div className="container-fluid h-100">
      <form className="mw-50">
        <div className="row">
          ${nodes.map(
            (n) => html`
              <div className="form-group col">
                <label for="node${n}">Node ${n} Query</label>
                <input type="text" className="form-control" name="query${n}" id="node${n}" placeholder="Enter node ${n}" />
              </div>
            `
          )}
        </div>
        ${[
          ["AB", "BA"],
          ["AC", "CA"],
          ["BC", "CB"],
        ].map(
          (edges) => html`
            <div className="row p-1">
              ${edges.map(
                (edge) => html`
                  <div className="col">
                    <div className="card">
                      <div className="card-header">
                        <div className="row">
                          <div className="col">Edge ${edge[0]} -> ${edge[1]}</div>
                          <div className="col">
                            <div class="custom-control custom-switch">
                              <input type="checkbox" class="custom-control-input" id="enabled${edge}" name="enabled${edge}" />
                              <label class="custom-control-label" for="enabled${edge}"></label>
                            </div>
                          </div>
                        </div>
                      </div>

                      <div className="card-body row">
                        <div className="form-group col">
                          <label for="neuropiljk${edge}">Region</label>
                          <select class="form-control" id="region${edge}" name="region${edge}">
                            ${nueropils.map((r) => html`<option value=${r}>${r}</option>`)}
                          </select>
                        </div>
                        <div className="form-group col">
                          <label for="minSynapseCount${edge}">Min Synapse Count</label>
                          <input type="number" className="form-control" name="minSynapseCount${edge}" id="minSynapseCount${edge}" placeholder="(Default=5)" />
                        </div>
                        <!-- Neurotransmitter type -->
                        <div className="form-group col">
                          <label for="ntType${edge}">Neurotransmitter Type</label>
                          <select class="form-control" id="ntType${edge}" name="ntType${edge}">
                            <option value="Any">Any</option>
                            ${Object.keys(NEURO_TRANSMITTER_NAMES).map((r) => html`<option value=${r}>${NEURO_TRANSMITTER_NAMES[r]}</option>`)}
                          </select>
                        </div>
                      </div>
                    </div>
                  </div>
                `
              )}
            </div>
          `
        )}
        <div className="d-flex justify-content-center">
          <button type="submit" className="btn btn-primary">Submit</button>
        </div>

      </form>

      ${warning && html`<div className="alert alert-warning" role="alert">${warning}</div>`}
      ${loading && html`<div className="spinner-border" role="status"><span className="sr-only">Loading...</span></div>`}
      ${error && html`<div className="alert alert-danger" role="alert">${error}</div>`}
    </div>
    <div className="container-fluid h-100">
      ${results &&
      html`<div>
        <${Results} results=${results} />
      </div>`}
    </div>
  `;
}

function Results({ results }) {
  const [selected, setSelected] = useState(0);
  const selectedResult = results[selected];

  if (results.length === 0) {
    return html`<p>No results found. Try widening your search.</p>`;
  }
  return html`
    <p>${results.length} Result${results.length > 1 ? "s" : ""}:</p>
    <div className="row h-75">
      <div className="col">
        <${ResultsTable} results=${results} selected=${selected} setSelected=${setSelected} onRowClick=${setSelected} />
      </div>
      <div className="col">
        <${ConnectivityCard} selectedResult=${selectedResult} />
        <${MorphologyCard} selectedResult=${selectedResult} />
      </div>
    </div>
  `;
}

function ResultsTable({ results, selected, setSelected }) {
  const [page, setPage] = useState(0);
  const resultsPerPage = 20;

  const totalPages = Math.ceil(results.length / resultsPerPage);

  const maxVisiblePages = 7;

  const handlePageChange = (newPage) => {
    if (newPage >= 0 && newPage < totalPages) {
      setPage(newPage);
      setSelected(0);
    }
  };

  const startIndex = page * resultsPerPage;
  const endIndex = startIndex + resultsPerPage;

  return html`
    <table className="table table-hover">
      <thead>
        <tr>
          ${Object.keys(results[0].nodes).map((k) => html`<th key=${k}>${k}</th>`)}
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${results.slice(startIndex, endIndex).map((r, i) => html`<${TableRow} key=${i} result=${r} index=${i} selected=${selected} onRowClick=${setSelected} />`)}
      </tbody>
    </table>
    <${PaginationControls} totalPages=${totalPages} currentPage=${page} onPageChange=${handlePageChange} maxVisiblePages=${maxVisiblePages} />
  `;
}

function TableRow({ result, index, selected, onRowClick }) {
  const isActive = index === selected;
  const rowClass = isActive ? "table-active" : "";
  const { nodes } = result;
  const cell_ids = Object.values(nodes).map((cell) => cell.id);

  return html`
    <tr key=${index} className=${rowClass} onClick=${() => onRowClick(index)}>
      ${Object.values(nodes).map(
        (cell) =>
          html`<td key=${cell.id}>
            <a title="Click to open in Cell Info" target="_blank" href="/app/cell_details?root_id=${cell.id}">${cell.name}</a>
            <p className="small">${cell.id}</p>
          </td>`
      )}
      <td>
        <button title="Copy Cell ID's" className="btn btn-outline-primary btn-sm" onClick=${() => navigator.clipboard.writeText(cell_ids.join(","))}>
          <i className="fas fa-copy"></i>
        </button>
      </td>
    </tr>
  `;
}

function PaginationControls({ totalPages, currentPage, onPageChange, maxVisiblePages }) {
  const visiblePages = (() => {
    const showFirst = currentPage > 1;
    const showLast = currentPage < totalPages - 2;
    const showEllipsisBefore = currentPage >= maxVisiblePages - 2;
    const showEllipsisAfter = currentPage <= totalPages - (maxVisiblePages - 1);

    const visiblePages = [];

    if (showFirst) {
      visiblePages.push(0);
    }
    if (showEllipsisBefore) {
      visiblePages.push(-1);
    }

    const startPage = Math.max(0, currentPage - Math.floor(maxVisiblePages / 2) + 1);
    const endPage = Math.min(totalPages, startPage + maxVisiblePages);

    for (let p = startPage; p < endPage; p++) {
      visiblePages.push(p);
    }

    if (showEllipsisAfter) {
      visiblePages.push(-2);
    }
    if (showLast) {
      visiblePages.push(totalPages - 1);
    }

    return visiblePages;
  })();

  return html`
    <nav aria-label="Page navigation">
      <ul className="pagination">
        <li className="page-item ${currentPage === 0 ? "disabled" : ""}">
          <button className="page-link" onClick=${() => onPageChange(currentPage - 1)}>
            <i className="fas fa-chevron-left"></i>
          </button>
        </li>
        ${visiblePages.map((page) =>
          page < 0
            ? html`<li key=${page} className="page-item disabled"><span className="page-link">...</span></li>`
            : html`<${PaginationButton} key=${page} page=${page} currentPage=${currentPage} onClick=${onPageChange} />`
        )}
        <li className="page-item ${currentPage === totalPages - 1 ? "disabled" : ""}">
          <button className="page-link" onClick=${() => onPageChange(currentPage + 1)}>
            <i className="fas fa-chevron-right"></i>
          </button>
        </li>
      </ul>
    </nav>
  `;
}

function PaginationButton({ page, currentPage, onClick }) {
  return html`
    <li className="page-item ${page === currentPage ? "active" : ""}">
      <button className="page-link" onClick=${() => onClick(page)}>${page + 1}</button>
    </li>
  `;
}

function rootIdsFromResult(result) {
  return Object.values(result.nodes).map((v) => v.id);
}

function morphologyURLForResult(result) {
  return `/app/flywire_url?root_ids=${rootIdsFromResult(result).join("&root_ids=")}`;
}

function connectivityURLForResult(result, headless = 1) {
  return `/app/connectivity?cell_names_or_ids=${rootIdsFromResult(result).join(",")}&headless=${headless}`;
}

function MorphologyCard({ selectedResult }) {
  return html`
    <div className="card mt-3" style=${{ height: "500px" }}>
      <div className="card-header">
        <a href=${morphologyURLForResult(selectedResult)}>3D Re</a>
      </div>
      <div className="card-body">
        <iframe className="w-100 h-100" src=${morphologyURLForResult(selectedResult)} title="neuroglancer"> </iframe>
      </div>
    </div>
  `;
}

function ConnectivityCard({ selectedResult }) {
  return html`
    <div className="card" style=${{ height: "500px" }}>
      <div className="card-header">
        <a target="_blank" href=${connectivityURLForResult(selectedResult, 0)}>Connections</a>
        <a target="_blank" className="btn btn-outline-primary btn-sm float-right" href="${connectivityURLForResult(selectedResult)}&download=csv" target="_blank">
          <i className="fa-solid fa-download"></i> CSV</a
        >
      </div>
      <div className="card-body">
        <iframe className="w-100 h-100" src=${connectivityURLForResult(selectedResult)}></iframe>
      </div>
    </div>
  `;
}

export default MotifSearch;

import { html } from "https://esm.sh/htm/react/index.module.js";
import { useState } from "https://esm.sh/react";

function MotifSearch({ results, query, show_explainer }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState();
  const [warning, setWarning] = useState();

  return html`
    <div className="container-fluid h-100">
      
      ${warning && html`<div className="alert alert-warning" role="alert">${warning}</div>`}
      ${loading && html`<div className="spinner-border" role="status"><span className="sr-only">Loading...</span></div>`}
      ${error && html`<div className="alert alert-danger" role="alert">${error}</div>`}
    </div>
    <div className="container-fluid h-100">
      <div>
        ${show_explainer ? ExplainerCard() : Results({results: results, query:query})}
            
          </div>
    </div>
  `;
}


function ExplainerCard() {
  return html`<div>
    <div class="card" style=${{ margin: "5px" }}>
      <div class="card-header" sttyle=${{ color: "purple" }}>What is this?</div>
      <div class="card-body">
        With this tool you can search for specific motifs (sub-graphs) of size 3 in the connectome network. With A, B, C
        denoting the motif node names, you can specify a filter for each node (same query language as in search) as well
        as connectivity of each pair of nodes (not connected, connected one way,
        connected both ways). Additionally you can apply neurotransmitter / brain region / min synapse count constraints
        for every pair of connected nodes. Matching
        motifs (if found) will be presented as a network along with 3D rendering of the corresponding cells.
        <br /><br />
        <a class="btn btn btn-outline-success my-2 my-sm-0" onClick=${() => loading(event)}
            href="/app/motifs/?queryA=720575940613052200&queryB=DL1_dorsal&queryC=DL1_dorsal&enabledAB=on&regionAB=Any&minSynapseCountAB=20&ntTypeAB=GLUT&enabledBA=on&regionBA=Any&minSynapseCountBA=20&ntTypeBA=GLUT&enabledAC=on&regionAC=Any&minSynapseCountAC=15&ntTypeAC=GLUT&enabledCA=on&regionCA=Any&minSynapseCountCA=15&ntTypeCA=GLUT&enabledBC=on&regionBC=Any&minSynapseCountBC=&ntTypeBC=GLUT&enabledCB=on&regionCB=Any&minSynapseCountCB=&ntTypeCB=GLUT">
            Try Example Query
        </a>
      </div>
    </div>
  </div>`;
}




function Results({ results, query }) {

  if (results.length === 0) {
    return html`<p>No results found. Try widening your search.</p>`;
  }
  const [selected, setSelected] = useState(0);
  const selectedResult = results[selected];


  return html`
    <h4 style=${{ color: "purple", margin: "15px;" }} >Matching motif${results.length > 1 ? "s" : ""}</h4>
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
  `;
   // TODO: show pagination controls only when >1 pages:
   // <${PaginationControls} totalPages=${totalPages} currentPage=${page} onPageChange=${handlePageChange} maxVisiblePages=${maxVisiblePages} />
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
  return `/app/flywire_url?root_ids=${rootIdsFromResult(result).join("&root_ids=")}&show_side_panel=0`;
}

function connectivityURLForResult(result, headless = 1) {
  return `/app/connectivity?cell_names_or_ids=${rootIdsFromResult(result).join(",")}&headless=${headless}&label_abc=1`;
}

function MorphologyCard({ selectedResult }) {
  return html`
    <div className="card mt-3" style=${{ height: "500px" }}>
      <div className="card-header">
        <a href=${morphologyURLForResult(selectedResult)}>3D Rendering</a>
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

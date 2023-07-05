from src.configuration import MIN_SYN_THRESHOLD
from src.data.structured_search_filters import (
    STRUCTURED_SEARCH_UNARY_OPERATORS,
    STRUCTURED_SEARCH_BINARY_OPERATORS,
    STRUCTURED_SEARCH_NARY_OPERATORS,
    STRUCTURED_SEARCH_ATTRIBUTES,
    SEARCH_ATTRIBUTE_NAMES,
)


def operators_list(ops):
    def _make_list_item(op):
        return f"<b>{op.name}</b> (short alternative <b>{op.shorthand}</b>) {op.description}"

    li = [_make_list_item(op) for op in ops]
    return "".join([f"<li>{i}</li>" for i in li])


def attr_list(attrs):
    def _make_list_item(a):
        res = f"<b>{a.name}</b> {a.description}"
        if a.value_range:
            res += f" [<small style='color: purple'>{', '.join(a.value_range)}</small>]"
        return res

    li = [_make_list_item(a) for a in attrs]
    return "".join([f"<li>{i}</li>" for i in li])


FAQ_QA_KB = {
    "data_version": {
        "q": "What version of FlyWire data is shown?",
        "a": "<b>Codex</b> provides access to static FlyWire connectome data releases (sometimes referred to as"
        " 'snapshots' or 'versions'). These releases include only cells that were marked as proofread. In addition, "
        "Codex excludes weak connections. Specifically, a pair of cells counts as connected if the number of synapses is "
        f"at least {MIN_SYN_THRESHOLD}. "
        "To switch from the default data snapshot one of the older releases use "
        "the <b>Data Version</b> selector under the search settings menu. And for live queries against the "
        "proofreading database tables use the "
        '<a href="https://github.com/seung-lab/CAVEclient">Cave Client Python library</a> instead.',
    },
    "connectome_graph": {
        "q": "How is the connectome modeled as a network graph?",
        "a": "The connectome forms a directed graph where nodes correspond to neurons and edges to synaptic "
             "connections. Edges have the following properties: number of synapses, region (neuropil), "
             "predicted neurotransmitter type. Nodes have various annotations, including hierarchical classification, "
             "identification labels, neurotransmitter predictions, side, and more. A pair of nodes can be connected "
             "with multiple edges corresponding to different brain regions.",
    },
    "data_download": {
        "q": "Can I download the connectome data?",
        "a": f"Yes, visit the <a href='/api/download'>data download portal</a> to review and "
             "download the FlyWire connectome data resources.",
    },
    "structured_search": {
        "q": "Is there an advanced search/filter? Can I search for specific attribute values?",
        "a": f"Yes, for certain attributes ({', '.join(SEARCH_ATTRIBUTE_NAMES)}) you can search using "
        f"structured query terms "
        "e.g. by typing into search box <b>class == JON</b> or <b>nt_type != GABA</b>. You can also chain the terms "
        "with and/or rules like so: <b>class == JON && nt_type != GABA</b> or similarly "
        "<b>class == JON || class == olfactory || class == dsx</b> etc. (but different chaining rules cannot be "
        "mixed)."
        f"<br> <b>Search attributes</b> <ul> {attr_list(STRUCTURED_SEARCH_ATTRIBUTES)} </ul>"
        f"<br> <b>Binary operators</b> <ul> {operators_list(STRUCTURED_SEARCH_BINARY_OPERATORS)} </ul>"
        f"<br> <b>Unary operators</b> <ul> {operators_list(STRUCTURED_SEARCH_UNARY_OPERATORS)} </ul>"
        f"<br> <b>Logical chaining operators</b> <ul> {operators_list(STRUCTURED_SEARCH_NARY_OPERATORS)} </ul>",
    },
    "names": {
        "q": "Where did the cell names originate?",
        "a": "Cell names were assigned automatically based on neuropils (brain regions) where the cells have most "
        "of their synapstic connections. Note of caution: this naming scheme "
        "will be carried forward with next releases, so as proofreading continues names of certain cells might "
        "change over time.",
    },
    "classes": {
        "q": "How are classes assigned to cells?",
        "a": "Sensory, ascending, descending and visual projection neurons were identified by the Jefferis Lab. "
        "The remaining neurons were assigned to the central brain if they had more than 100 connections in the "
        "central brain (vs the optic lobe), and to the optic lobe otherwise. As cell identification efforts "
        "progress, these classes will evolve too over time.",
    },
    "connectivity": {
        "q": "How is connectivity between a pair of cells determined?",
        "a": "A minimum threshold of 5 synapses is applied across the board to determine connectivity between pairs "
        "of cells.",
    },
    "nblast": {
        "q": "What is NBLAST?",
        "a": '<a href="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4961245/">NBLAST</a> is a method '
        "for assigning similarity scores to pairs of neurons. NBLAST scores are not "
        "necessarily symmetric, and they range from 1 (morphologically similar) to -1 (not similar).<br>"
        "The NBLAST scores used here were contributed by "
        '<a href="https://www.zoo.cam.ac.uk/directory/dr-philip-schlegel">Dr. Philipp Schlegel</a>.',
    },
    "paths": {
        "q": "What is a pathway length?",
        "a": "Shortest path length is equivalent to the minimum number of 'hops' "
        "required to reach from the source cell to the target via synaptic connections "
        f"in the connectome network.<br><b>NOTE</b> Only connections with {MIN_SYN_THRESHOLD}+ synapses are "
        "taken into account.",
    },
}

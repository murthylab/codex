from src.data.neuron_data import OPERATOR_METADATA, SEARCH_TERM_UNARY_OPERATORS, SEARCH_TERM_BINARY_OPERATORS, \
    SEARCH_CHAINING_OPERATORS, STRUCTURED_SEARCH_ATTRIBUTES


def operators_list(ops):
    def _make_list_item(op):
        op_short_and_desc = OPERATOR_METADATA[op]
        return f"<b>{op}</b> (short alternative <b>{op_short_and_desc[0]}</b>) {op_short_and_desc[1]}"
    li = [_make_list_item(op) for op in ops]
    return ''.join([f"<li>{i}</li>" for i in li])

def attr_list(attr_dict):
    def _make_list_item(attr_key, attr_meta):
        return f"<b>{attr_key}</b> {attr_meta[2]}"
    li = [_make_list_item(k, v) for k, v in attr_dict.items()]
    return ''.join([f"<li>{i}</li>" for i in li])


FAQ_QA_KB = {
    'data_version': {
        'q': 'What version of FlyWire data is shown?',
        'a': "<b>CoDEx</b> provides access to static FlyWire connectome data releases (sometimes referred to as"
             " 'snapshots' or 'versions'). The current most-recent snapshot release is from August 2022, and this "
             "is the one served by default. To switch from the most recent release to one of the older releases use "
             "the <b>Data Version</b> selector under the search settings menu. And for live queries against the "
             "proofreading database tables use the "
             "<a href=\"https://github.com/seung-lab/CAVEclient\">Cave Client Python library</a> instead."
    }, 'structured_search': {
        'q': 'Is there an advanced search/filter? Can I search for specific attribute values?',
        'a': f"Yes, for certain attributes ({', '.join(STRUCTURED_SEARCH_ATTRIBUTES.keys())}) you can search using "
             f"structured query terms "
             "e.g. by typing into search box <b>class == JON</b> or <b>nt != GABA</b>. You can also chain the terms "
             "with and/or rules like so: <b>class == JON && nt != GABA</b> or similarly "
             "<b>class == JON || class == olfactory || class == dsx</b> etc. (but different chaining rules cannot be "
             "mixed)."
             f"<br> <b>Binary operators</b> <ul> {operators_list(SEARCH_TERM_BINARY_OPERATORS)} </ul>"
             f"<br> <b>Unary operators</b> <ul> {operators_list(SEARCH_TERM_UNARY_OPERATORS)} </ul>"
             f"<br> <b>Chaining operators</b> <ul> {operators_list(SEARCH_CHAINING_OPERATORS)} </ul>"
             f"<br> <b>Search attributes</b> <ul> {attr_list(STRUCTURED_SEARCH_ATTRIBUTES)} </ul>"
    }, 'suggestions': {
        'q': 'How are labeling suggestions generated?',
        'a': 'Labeling suggestions are generated by finding similar neurons <b>A</b> and <b>B</b> such that <b>A</b> '
             'has an assigned label, while <b>B</b> does not. Similarity metric is both morphological as well as '
             'connectivity based.'
    }, 'nblast': {
        'q': "What is NBLAST?",
        'a': "<a href=\"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4961245/\">NBLAST</a> is a method "
             "for assigning similarity scores to pairs of neurons. NBLAST scores are not "
             "necessarily symmetric, and they range from 1 (morphologically similar) to -1 (not similar). "
             "The NBLAST scores shown here were contributed by "
             "<a href=\"https://www.zoo.cam.ac.uk/directory/dr-philip-schlegel\">Dr. Philipp Schlegel</a> "
             "and they cover the central brain cells (which is around 50k of the neurons in the dataset). "
    }, 'paths': {
        'q': "What is a path length?",
        'a': "Path length from neuron A to neuron B is the minimum number of steps / hops needed to reach "
             "neuron B from A via intermediate neurons."
    }
}
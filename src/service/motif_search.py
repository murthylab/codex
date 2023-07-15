from collections import namedtuple, defaultdict

from src.configuration import MIN_SYN_THRESHOLD
from src.data.brain_regions import REGIONS
from src.data.neuron_data_factory import NeuronDataFactory
from src.data.neurotransmitters import NEURO_TRANSMITTER_NAMES
from src.data.structured_search_filters import parse_search_query
from src.data.versions import DEFAULT_DATA_SNAPSHOT_VERSION
from src.data.neuron_data import NeuronDB

MAX_NODES = 3
DEFAULT_LIMIT = 10

EdgeConstraints = namedtuple("EdgeConstraints", "regions min_synapse_count nt_type")


class MotifSearchQuery(object):
    def __init__(self, neuron_data_factory=None):
        self.nodes = {}
        self.edges = {}
        self.neuron_data_factory = neuron_data_factory or NeuronDataFactory()

    def __repr__(self):
        return f"<MotifSearchQuery with {len(self.nodes)} nodes and {len(self.edges)} edges>"

    @classmethod
    def from_form_query(cls, form_query, neuron_data_factory=None):
        motif_search_query = cls(neuron_data_factory=neuron_data_factory)
        for node_name in ["A", "B", "C"]:
            node_query = form_query.get(f"query{node_name}") or "*"
            motif_search_query.add_node(node_name, node_query)
        for edge_name in ["AB", "BA", "BC", "CB", "CA", "AC"]:
            from_node, to_node = edge_name[0], edge_name[1]
            regions = None
            if form_query.get(f"enabled{edge_name}") == "on":
                region = form_query.get(f"region{edge_name}")
                if region != "Any":
                    if region not in REGIONS:
                        raise ValueError(
                            f"Region {region} for {edge_name} not recognized."
                        )
                    regions = [region]

                min_synapse_count = (
                    form_query.get(f"minSynapseCount{edge_name}") or MIN_SYN_THRESHOLD
                )
                nt_type = form_query.get(f"ntType{edge_name}")
                if nt_type == "Any":
                    nt_type = None
                elif nt_type not in NEURO_TRANSMITTER_NAMES:
                    raise ValueError(
                        f"NT type {nt_type} for {edge_name} not recognized."
                    )

                motif_search_query.add_edge(
                    from_node,
                    to_node,
                    regions=regions,
                    min_synapse_count=min_synapse_count,
                    nt_type=nt_type,
                )
        return motif_search_query

    def add_node(self, name, query):
        if not name or name in self.nodes:
            raise ValueError(f"Node name is empty or already exists: {name}")
        if len(self.nodes) >= MAX_NODES:
            raise ValueError(f"Max nodes limit of {MAX_NODES} exceeded")
        try:
            parse_search_query(query)
        except Exception as e:
            raise ValueError(f"Invalid query '{query}': {e}")
        self.nodes[name] = query

    def add_edge(
        self,
        from_node,
        to_node,
        regions,
        min_synapse_count,
        nt_type,
    ):
        if from_node not in self.nodes or to_node not in self.nodes:
            raise ValueError(
                f"Node(s) {from_node} and {to_node} need to be added first"
            )
        if from_node == to_node:
            raise ValueError("Self loops not allowed")
        if (from_node, to_node) in self.edges:
            raise ValueError(
                f"Edge {(from_node, to_node)} already exists. Parallel edges not allowed."
            )
        for region in regions or []:
            if region not in REGIONS:
                raise ValueError(f"Unknown region {region}")

        min_synapse_count = int(min_synapse_count)
        if min_synapse_count < 0:
            raise ValueError(f"Invalid min_synapse_count {min_synapse_count}")

        if nt_type and nt_type not in NEURO_TRANSMITTER_NAMES:
            raise ValueError(f"Unknown nt_type {nt_type}")

        self.edges[(from_node, to_node)] = EdgeConstraints(
            regions=regions, min_synapse_count=min_synapse_count, nt_type=nt_type
        )

    # returns a list of matching motifs in form of dictionaries (name -> cell ID)
    def search(
        self,
        data_version=DEFAULT_DATA_SNAPSHOT_VERSION,
        limit=DEFAULT_LIMIT,
        ids_as_strings=True,
    ):
        if not (0 < len(self.nodes) <= MAX_NODES):
            raise ValueError(
                f"Number of nodes has to be in the range [1, {MAX_NODES}]. Found {len(self.nodes)}"
            )
        if len(self.nodes) > 1 and not self.edges:
            raise ValueError("Need at least one edge for search")

        neuron_db = self.neuron_data_factory.get(data_version)
        node_candidates = {n: set(neuron_db.search(q)) for n, q in self.nodes.items()}
        if len(self.nodes) == 1:
            node_name = next(iter(node_candidates.keys()))
            matches = next(iter(node_candidates.values()))
            result = [
                MotifSearchQuery.make_match_dict(neuron_db, [(node_name, match_id)], [])
                for match_id in matches
            ][:limit]
        elif len(self.nodes) == 2:
            node_names = list(node_candidates.keys())
            x, y = node_names[0], node_names[1]
            x_candidates, y_candidates = node_candidates[x], node_candidates[y]
            xy_edge_constraints = self.edges.get((x, y))
            yx_edge_constraints = self.edges.get((y, x))
            result = MotifSearchQuery._search_pairs(
                neuron_db,
                x=x,
                x_candidates=x_candidates,
                y=y,
                y_candidates=y_candidates,
                xy_edge_constraints=xy_edge_constraints,
                yx_edge_constraints=yx_edge_constraints,
                limit=limit,
            )
        elif len(self.nodes) == 3:
            node_names = list(node_candidates.keys())
            x, y, z = node_names[0], node_names[1], node_names[2]
            x_candidates, y_candidates, z_candidates = (
                node_candidates[x],
                node_candidates[y],
                node_candidates[z],
            )
            xy_edge_constraints = self.edges.get((x, y))
            yx_edge_constraints = self.edges.get((y, x))
            xz_edge_constraints = self.edges.get((x, z))
            zx_edge_constraints = self.edges.get((z, x))
            zy_edge_constraints = self.edges.get((z, y))
            yz_edge_constraints = self.edges.get((y, z))

            result = MotifSearchQuery._search_triplets(
                neuron_db,
                x=x,
                x_candidates=x_candidates,
                y=y,
                y_candidates=y_candidates,
                z=z,
                z_candidates=z_candidates,
                xy_edge_constraints=xy_edge_constraints,
                yx_edge_constraints=yx_edge_constraints,
                xz_edge_constraints=xz_edge_constraints,
                zx_edge_constraints=zx_edge_constraints,
                zy_edge_constraints=zy_edge_constraints,
                yz_edge_constraints=yz_edge_constraints,
                limit=limit,
            )
        else:
            raise ValueError("Unexpected internal error.")

        if ids_as_strings:
            # convert long ints to strings (for json/frontend with limited data-types)
            for match in result:
                for node, meta in match["nodes"].items():
                    if "id" in meta:
                        meta["id"] = str(meta["id"])

        return result

    @staticmethod
    def _fetch_feasible_connections(
        neuron_db: NeuronDB, candidate_sets_list, edge_constraints_list
    ):
        # collect all relevant connections (matching the superset of edge constraints)
        regions = set()
        nt_type = None
        min_syn_count = None
        for ec in edge_constraints_list:
            if not ec:
                continue
            if ec.min_synapse_count:
                min_syn_count = (
                    ec.min_synapse_count
                    if min_syn_count is None
                    else min(min_syn_count, ec.min_synapse_count)
                )
            if ec.regions:
                regions |= set(ec.regions)
            if ec.nt_type:  # bit of a hack - we only support a single NT type for now
                nt_type = ec.nt_type
        candidate_connections = neuron_db.connections(
            ids=set.union(*candidate_sets_list),
            induced=True,
            min_syn_count=min_syn_count,
            regions=regions or None,
            nt_type=nt_type or None,
        )

        # further filter out connections where both endpoints are from the same candidate set
        def from_multiple_candidate_sets(from_id, to_id):
            hits = 0
            for c in candidate_sets_list:
                if from_id in c or to_id in c:
                    hits += 1
                    if hits > 1:
                        return True
            return False

        return [
            r for r in candidate_connections if from_multiple_candidate_sets(r[0], r[1])
        ]

    @staticmethod
    def _satisfies_edge_constraints(constraints, region, syn_count, nt_type):
        if constraints:
            if (
                constraints.min_synapse_count
                and syn_count < constraints.min_synapse_count
            ):
                return False
            if constraints.regions and region not in constraints.regions:
                return False
            if constraints.nt_type and nt_type != constraints.nt_type:
                return False
        return True

    @staticmethod
    def _make_node_match_dict(
        neuron_db,
        node_name,
        matching_cell_id,
    ):
        assert node_name
        assert isinstance(matching_cell_id, int)
        matching_cell_name = neuron_db.get_neuron_data(matching_cell_id)["name"]
        assert matching_cell_name

        return {
            node_name: {
                "id": matching_cell_id,
                "name": matching_cell_name,
            },
        }

    @staticmethod
    def _make_edge_match_dict(
        from_node_name,
        to_node_name,
        region,
        syn_count,
        nt_type,
    ):
        assert from_node_name and to_node_name and from_node_name != to_node_name
        if region:
            assert region in REGIONS
        if nt_type:
            assert nt_type in NEURO_TRANSMITTER_NAMES
        assert isinstance(syn_count, int) and syn_count > 0

        return {
            "from": from_node_name,
            "to": to_node_name,
            "region": region,
            "syn_count": syn_count,
            "nt_type": nt_type,
        }

    @staticmethod
    def make_match_dict(neuron_db, nodes, edges):
        res = {
            "nodes": {},
            "edges": [],
        }

        for node in nodes:
            res["nodes"].update(
                MotifSearchQuery._make_node_match_dict(neuron_db, *node)
            )
        for edge in edges:
            res["edges"].append(MotifSearchQuery._make_edge_match_dict(*edge))
        return res

    @staticmethod
    def _search_pairs(
        neuron_db,
        x,
        x_candidates,
        y,
        y_candidates,
        xy_edge_constraints,
        yx_edge_constraints,
        limit,
    ):
        assert all([isinstance(c, set) for c in [x_candidates, y_candidates]])
        feasible_connections = MotifSearchQuery._fetch_feasible_connections(
            neuron_db,
            [x_candidates, y_candidates],
            [xy_edge_constraints, yx_edge_constraints],
        )

        # filter down based on candidate endpoints and specific edge constraints
        matches = []
        xy_satisfied_connections = defaultdict(list)
        yx_satisfied_connections = defaultdict(list)
        for r in feasible_connections:
            _from_id, _to_id, _region, _syn_count, _nt_type = (
                r[0],
                r[1],
                r[2],
                r[3],
                r[4],
            )
            if (
                _from_id in x_candidates
                and _to_id in y_candidates
                and MotifSearchQuery._satisfies_edge_constraints(
                    xy_edge_constraints,
                    region=_region,
                    nt_type=_nt_type,
                    syn_count=_syn_count,
                )
            ):
                xy_satisfied_connections[(_from_id, _to_id)].append(
                    (
                        _region,
                        _syn_count,
                        _nt_type,
                    )
                )

            if (
                _from_id in y_candidates
                and _to_id in x_candidates
                and MotifSearchQuery._satisfies_edge_constraints(
                    yx_edge_constraints,
                    region=_region,
                    nt_type=_nt_type,
                    syn_count=_syn_count,
                )
            ):
                yx_satisfied_connections[(_from_id, _to_id)].append(
                    (
                        _region,
                        _syn_count,
                        _nt_type,
                    )
                )

        if xy_edge_constraints and yx_edge_constraints:
            for xy, xy_edge_matches in xy_satisfied_connections.items():
                yx_edge_matches = yx_satisfied_connections.get((xy[1], xy[0]))
                if yx_edge_matches:
                    matches.append(
                        MotifSearchQuery.make_match_dict(
                            neuron_db,
                            [(x, xy[0]), (y, xy[1])],
                            [
                                (x, y, xy_con_meta[0], xy_con_meta[1], xy_con_meta[2])
                                for xy_con_meta in xy_edge_matches
                            ]
                            + [
                                (y, x, yx_con_meta[0], yx_con_meta[1], yx_con_meta[2])
                                for yx_con_meta in yx_edge_matches
                            ],
                        )
                    )
                    if limit and len(matches) >= limit:
                        break
        elif xy_edge_constraints:
            for xy, xy_edge_matches in xy_satisfied_connections.items():
                matches.append(
                    MotifSearchQuery.make_match_dict(
                        neuron_db,
                        [(x, xy[0]), (y, xy[1])],
                        [
                            (x, y, xy_con_meta[0], xy_con_meta[1], xy_con_meta[2])
                            for xy_con_meta in xy_edge_matches
                        ],
                    )
                )
                if limit and len(matches) >= limit:
                    break
        elif yx_edge_constraints:
            for yx, yx_edge_matches in yx_satisfied_connections.items():
                matches.append(
                    MotifSearchQuery.make_match_dict(
                        neuron_db,
                        [(x, yx[1]), (y, yx[0])],
                        [
                            (y, x, yx_con_meta[0], yx_con_meta[1], yx_con_meta[2])
                            for yx_con_meta in yx_edge_matches
                        ],
                    )
                )
                if limit and len(matches) >= limit:
                    break
        else:
            # no edge constraints - return all pairs
            for xc in x_candidates:
                for yc in y_candidates:
                    matches.append(
                        MotifSearchQuery.make_match_dict(
                            neuron_db=neuron_db, nodes=[(x, xc), (y, yc)], edges=[]
                        )
                    )
                    if limit and len(matches) >= limit:
                        break

        return matches

    @staticmethod
    def row_satisfies_constraints(row, edge_constraints):
        if (
            edge_constraints.min_synapse_count
            and row[3] < edge_constraints.min_synapse_count
        ):
            return False
        if edge_constraints.regions and row[2] not in edge_constraints.regions:
            return False
        if edge_constraints.nt_type and row[4] != edge_constraints.nt_type:
            return False
        return True

    @staticmethod
    def _feasible_pairs(
        neuron_db, x_candidates, y_candidates, xy_constraints, yx_constraints
    ):
        print("+++ here!")
        ins, outs = neuron_db.input_output_partners_with_synapse_counts()

        if not xy_constraints and not yx_constraints:
            for x_rid in x_candidates:
                for y_rid in y_candidates - (
                    set(ins[x_rid].keys()) | set(outs[x_rid].keys())
                ):
                    yield x_rid, y_rid
            return

        elif not xy_constraints:
            for x_rid in x_candidates:
                y_candidates_filtered = y_candidates.intersection(
                    set(ins[x_rid].keys())
                ) - set(outs[x_rid].keys())
                rows = neuron_db.connections_.rows_for_cell(x_rid)
                to_x_tuples = defaultdict(list)
                for r in rows:
                    if r[1] == x_rid and r[0] in y_candidates_filtered:
                        to_x_tuples[r[0]].append(r)
                for y_rid in y_candidates_filtered:
                    if any(
                        [
                            MotifSearchQuery.row_satisfies_constraints(
                                row, yx_constraints
                            )
                            for row in to_x_tuples[y_rid]
                        ]
                    ):
                        yield x_rid, y_rid
            return

        elif not yx_constraints:
            for x_rid in x_candidates:
                y_candidates_filtered = y_candidates.intersection(
                    set(outs[x_rid].keys())
                ) - set(ins[x_rid].keys())
                rows = neuron_db.connections_.rows_for_cell(x_rid)
                from_x_tuples = defaultdict(list)
                for r in rows:
                    if r[0] == x_rid and r[1] in y_candidates_filtered:
                        from_x_tuples[r[1]].append(r)
                for y_rid in y_candidates_filtered:
                    if any(
                        [
                            MotifSearchQuery.row_satisfies_constraints(
                                row, xy_constraints
                            )
                            for row in from_x_tuples[y_rid]
                        ]
                    ):
                        yield x_rid, y_rid
            return

        else:  # both edges are specified
            for x_rid in x_candidates:
                y_candidates_filtered = y_candidates.intersection(
                    set(ins[x_rid].keys()).intersection(set(outs[x_rid]).keys())
                )
                rows = neuron_db.connections_.rows_for_cell(x_rid)
                from_x_tuples = defaultdict(list)
                to_x_tuples = defaultdict(list)
                for r in rows:
                    if r[0] == x_rid and r[1] in y_candidates_filtered:
                        from_x_tuples[r[1]].append(r)
                    elif r[1] == x_rid and r[0] in y_candidates_filtered:
                        to_x_tuples[r[0]].append(r)
                for y_rid in y_candidates_filtered:
                    if any(
                        [
                            MotifSearchQuery.row_satisfies_constraints(
                                row, xy_constraints
                            )
                            for row in from_x_tuples[y_rid]
                        ]
                    ) and any(
                        [
                            MotifSearchQuery.row_satisfies_constraints(
                                row, yx_constraints
                            )
                            for row in to_x_tuples[y_rid]
                        ]
                    ):
                        yield x_rid, y_rid
            return

    @staticmethod
    def append_edge_queries(edge_constraints, from_queries, to_queries):
        if edge_constraints:
            if edge_constraints.regions:
                rlist = ",".join(edge_constraints.regions)
                from_queries.append(f"output_neuropils == {rlist}")
                to_queries.append(f"input_neuropils == {rlist}")
            if edge_constraints.nt_type:
                from_queries.append(f"nt_type == {edge_constraints.nt_type}")

    @staticmethod
    def filter_by_query(neuron_db, candidates, queries):
        if queries:
            return candidates.intersection(set(neuron_db.search(" && ".join(queries))))
        else:
            return candidates

    @staticmethod
    def _search_triplets(
        neuron_db,
        x,
        x_candidates,
        y,
        y_candidates,
        z,
        z_candidates,
        xy_edge_constraints,
        yx_edge_constraints,
        xz_edge_constraints,
        zx_edge_constraints,
        zy_edge_constraints,
        yz_edge_constraints,
        limit,
    ):
        """
        Algo:
        1. collect matching connections for each one of the 3 pairs
        2. pick a pair so that the number of it's matching connections times the number of candidate nodes of the remaining node are minimized
        3. for every matching connection, check if it's endpoints extensions intersect within the candidate nodes set
        """
        assert all(
            [isinstance(c, set) for c in [x_candidates, y_candidates, z_candidates]]
        )
        print(
            f"+++ x, y, z: {len(x_candidates)}, {len(y_candidates)}, {len(z_candidates)}"
        )

        print(f"+++ xy_ec: {xy_edge_constraints}")
        print(f"+++ xz_ec: {xz_edge_constraints}")
        print(f"+++ yx_ec: {yx_edge_constraints}")
        print(f"+++ yz_ec: {yz_edge_constraints}")
        print(f"+++ zx_ec: {zx_edge_constraints}")
        print(f"+++ zy_ec: {zy_edge_constraints}")

        x_query, y_query, z_query = [], [], []
        MotifSearchQuery.append_edge_queries(xy_edge_constraints, x_query, y_query)
        MotifSearchQuery.append_edge_queries(yx_edge_constraints, y_query, x_query)
        MotifSearchQuery.append_edge_queries(xz_edge_constraints, x_query, z_query)
        MotifSearchQuery.append_edge_queries(zx_edge_constraints, z_query, x_query)
        MotifSearchQuery.append_edge_queries(yz_edge_constraints, y_query, z_query)
        MotifSearchQuery.append_edge_queries(zy_edge_constraints, z_query, y_query)

        x_candidates = MotifSearchQuery.filter_by_query(
            neuron_db, x_candidates, x_query
        )
        y_candidates = MotifSearchQuery.filter_by_query(
            neuron_db, y_candidates, y_query
        )
        z_candidates = MotifSearchQuery.filter_by_query(
            neuron_db, z_candidates, z_query
        )

        print(
            f"+++ x, y, z after edge queries: {len(x_candidates)}, {len(y_candidates)}, {len(z_candidates)}"
        )

        ins, outs = neuron_db.input_output_partner_sets()

        def z_satisfies_constraints(x_rid, y_rid, z_rid):
            constraints_satisfied = set()

            print("+++ checking if z satisfies constraints")
            if not xz_edge_constraints:
                if z_rid in outs[x_rid]:
                    print("+++ xz should not be an edge")
                    return False
                else:
                    constraints_satisfied.add("xz")
            if not zx_edge_constraints:
                if x_rid in outs[z_rid]:
                    print("+++ zx should not be an edge")
                    return False
                else:
                    constraints_satisfied.add("zx")
            if not yz_edge_constraints:
                if z_rid in outs[y_rid]:
                    print("+++ yz should not be an edge")
                    return False
                else:
                    constraints_satisfied.add("yz")
            if not zy_edge_constraints:
                if y_rid in outs[z_rid]:
                    print("+++ zy should not be an edge")
                    return False
                else:
                    constraints_satisfied.add("zy")

            if len(constraints_satisfied) == 4:
                return True

            z_rows = neuron_db.connections_.rows_for_cell(z_rid)
            print("+++ checking if z satisfies rows")
            for r in z_rows:
                if (
                    r[0] == x_rid
                    and r[1] == z_rid
                    and MotifSearchQuery.row_satisfies_constraints(
                        r, xz_edge_constraints
                    )
                ):
                    constraints_satisfied.add("xz")
                    if len(constraints_satisfied) == 4:
                        return True
                    continue
                if (
                    r[0] == y_rid
                    and r[1] == z_rid
                    and not MotifSearchQuery.row_satisfies_constraints(
                        r, yz_edge_constraints
                    )
                ):
                    constraints_satisfied.add("yz")
                    if len(constraints_satisfied) == 4:
                        return True
                    continue
                if (
                    r[0] == z_rid
                    and r[1] == x_rid
                    and not MotifSearchQuery.row_satisfies_constraints(
                        r, zx_edge_constraints
                    )
                ):
                    constraints_satisfied.add("zx")
                    if len(constraints_satisfied) == 4:
                        return True
                    continue
                if (
                    r[0] == z_rid
                    and r[1] == y_rid
                    and not MotifSearchQuery.row_satisfies_constraints(
                        r, zy_edge_constraints
                    )
                ):
                    constraints_satisfied.add("zy")
                    if len(constraints_satisfied) == 4:
                        return True
                    continue

            return False

        def filtered_z_candidates(x_rid, y_rid):
            res = z_candidates
            if xz_edge_constraints:
                res = res.intersection(outs[x_rid])
            if yz_edge_constraints:
                res = res.intersection(outs[y_rid])
            if zx_edge_constraints:
                res = res.intersection(ins[x_rid])
            if zy_edge_constraints:
                res = res.intersection(ins[y_rid])
            return res

        matches = []
        print("+++ starting the loop")
        for _x_rid, _y_rid in MotifSearchQuery._feasible_pairs(
            neuron_db=neuron_db,
            x_candidates=x_candidates,
            y_candidates=y_candidates,
            xy_constraints=xy_edge_constraints,
            yx_constraints=yx_edge_constraints,
        ):
            print(f"+++ examining {_x_rid}, {_y_rid}")

            z_candidates_filtered = filtered_z_candidates(_x_rid, _y_rid)

            for _z_rid in z_candidates_filtered:
                if _z_rid == _x_rid or _z_rid == _y_rid:
                    print("+++ z is equal to y or x")
                    continue
                if z_satisfies_constraints(x_rid=_x_rid, y_rid=_y_rid, z_rid=_z_rid):
                    print(f"+++ appending result, have {len(matches)} need {limit}")
                    matches.append(
                        MotifSearchQuery.make_match_dict(
                            neuron_db=neuron_db,
                            nodes=[(x, _x_rid), (y, _y_rid), (z, _z_rid)],
                            edges=[],
                        )
                    )
                    if len(matches) >= limit:
                        return matches

        return matches

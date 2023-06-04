import math
from collections import namedtuple

Norms = namedtuple("Norms", "up down up_down")


class Svd(object):
    def __init__(self, svd_table):
        self.up_vec_len = int((len(svd_table[0]) - 1) / 2)
        self.down_vec_len = int((len(svd_table[0]) - 1) / 2)

        assert svd_table[0] == ["root_id"] + [
            f"up{i + 1}" for i in range(0, self.up_vec_len)
        ] + [f"down{i + 1}" for i in range(0, self.down_vec_len)]

        self.vecs = {
            int(r[0]): [
                float(r[i + 1]) for i in range(0, self.up_vec_len + self.down_vec_len)
            ]
            for r in svd_table[1:]
        }
        self.norms = {
            rid: Norms(
                up=self._norm(vec, 0, self.up_vec_len),
                down=self._norm(
                    vec, self.up_vec_len, self.up_vec_len + self.down_vec_len
                ),
                up_down=self._norm(vec, 0, self.up_vec_len + self.down_vec_len),
            )
            for rid, vec in self.vecs.items()
        }

    def rid_score_pairs_sorted(self, rid, up, down):
        if rid not in self.vecs:
            return []
        pairs = []
        for rid2 in self.vecs.keys():
            score = self._cosine_similarity(rid, rid2, up, down)
            if score is not None:
                pairs.append((rid2, score))
        return sorted(pairs, key=lambda p: -p[1])

    def _cosine_similarity(self, rid1, rid2, up, down):
        v1, v2 = self.vecs.get(rid1), self.vecs.get(rid2)
        if not v1 or not v2:
            return None

        if up and down:
            from_i, to_i = 0, self.up_vec_len + self.down_vec_len
            norm1, norm2 = self.norms[rid1].up_down, self.norms[rid2].up_down
        elif up:
            from_i, to_i = 0, self.up_vec_len
            norm1, norm2 = self.norms[rid1].up, self.norms[rid2].up
        elif down:
            from_i, to_i = self.up_vec_len, self.up_vec_len + self.down_vec_len
            norm1, norm2 = self.norms[rid1].down, self.norms[rid2].down
        else:
            raise ValueError("Up or down has to be true for SVD cosine similarity")

        return self._dot(v1, v2, from_i, to_i) / (norm1 * norm2)

    @staticmethod
    def _dot(v1, v2, from_i, to_i):
        return sum([v1[i] * v2[i] for i in range(from_i, to_i)])

    @staticmethod
    def _norm(v, from_i, to_i):
        return math.sqrt(sum([pow(v[i], 2) for i in range(from_i, to_i)]))

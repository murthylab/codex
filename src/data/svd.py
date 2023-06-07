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

    def get_vec_copy(self, rid, up, down):
        v = self.vecs.get(rid)
        from_i, to_i = self._get_from_i_to_i(up, down)
        return (
            list(v[from_i:to_i]) if v else None
        )  # make a copy to prevent mutation by caller

    def get_norm(self, rid, up, down):
        if up and down:
            return self.norms[rid].up_down
        elif up:
            return self.norms[rid].up
        else:
            return self.norms[rid].down

    def calculate_cosine_similarity(self, rid1, rid2, up, down):
        vec1, vec2 = self.vecs.get(rid1), self.vecs.get(rid2)
        if not vec1 or not vec2:
            return None
        norm1, norm2 = self.get_norm(rid=rid1, up=up, down=down), self.get_norm(
            rid=rid2, up=up, down=down
        )
        return self._cosine_similarity(
            v1=vec1, v2=vec2, norm1=norm1, norm2=norm2, up=up, down=down
        )

    def rid_score_pairs_sorted(self, rid, up, down):
        vec = self.vecs.get(rid)
        if not vec:
            return []
        norm = self.get_norm(rid=rid, up=up, down=down)
        return self.vec_score_pairs_sorted(vec=vec, norm=norm, up=up, down=down)

    def vec_score_pairs_sorted(self, vec, norm, up, down):
        pairs = []
        for rid2, v2 in self.vecs.items():
            score = self._cosine_similarity(
                v1=vec,
                v2=v2,
                norm1=norm,
                norm2=self.get_norm(rid2, up=up, down=down),
                up=up,
                down=down,
            )
            pairs.append((rid2, score))
        return sorted(pairs, key=lambda p: -p[1])

    @staticmethod
    def calculate_norm(v):
        return Svd._norm(v, 0, len(v))

    def _get_from_i_to_i(self, up, down):
        if up and down:
            return 0, self.up_vec_len + self.down_vec_len
        elif up:
            return 0, self.up_vec_len
        elif down:
            return self.up_vec_len, self.up_vec_len + self.down_vec_len
        else:
            raise ValueError("Up or down has to be true for SVD cosine similarity")

    def _cosine_similarity(self, v1, v2, norm1, norm2, up, down):
        from_i, to_i = self._get_from_i_to_i(up, down)
        return self._dot(v1, v2, from_i, to_i) / (norm1 * norm2)

    @staticmethod
    def _dot(v1, v2, from_i, to_i):
        return sum([v1[i] * v2[i] for i in range(from_i, to_i)])

    @staticmethod
    def _norm(v, from_i, to_i):
        return math.sqrt(sum([pow(v[i], 2) for i in range(from_i, to_i)]))

from unittest import TestCase

from codex.data.neuron_data_initializer import (
    HEATMAP_GROUP_BY_ATTRIBUTES,
    NEURON_DATA_ATTRIBUTE_TYPES,
    NETWORK_GROUP_BY_ATTRIBUTES,
)


class Test(TestCase):
    def test_group_by_attribute_types(self):
        for k in HEATMAP_GROUP_BY_ATTRIBUTES + NETWORK_GROUP_BY_ATTRIBUTES:
            self.assertEqual(NEURON_DATA_ATTRIBUTE_TYPES[k], str)

import random
import urllib.parse
from nglui import statebuilder
import json

from src.data.brain_regions import REGIONS, COLORS


def url_for_root_ids(
    root_ids, version, point_to_proofreading_flywire=False, position=None
):
    if point_to_proofreading_flywire:
        img_layer = statebuilder.ImageLayerConfig(
            name="EM",
            source="precomputed://gs://microns-seunglab/drosophila_v0/alignment/vector_fixer30_faster_v01/v4/image_stitch_v02",
        )

        seg_layer = statebuilder.SegmentationLayerConfig(
            name="Production segmentation",
            source="graphene://https://prodv1.flywire-daf.com/segmentation/table/fly_v31",
            fixed_ids=root_ids,
        )

        view_options = {
            "layout": "xy-3d",
            "show_slices": False,
            "zoom_3d": 2500,
            "zoom_image": 50,
        }

        if position is not None:
            view_options["position"] = [position[0] / 4, position[1] / 4, position[2]]

        sb = statebuilder.StateBuilder(
            layers=[img_layer, seg_layer],
            view_kws=view_options,
        )

        config = sb.render_state(return_as="dict")
        config["selectedLayer"] = {"layer": "Production segmentation", "visible": True}

        return f"https://ngl.flywire.ai/#!{urllib.parse.quote(json.dumps(config))}"
    else:
        return url_for_cells(segment_ids=root_ids, data_version=version)


def url_for_random_sample(root_ids, version, sample_size=50):
    # make the random subset selections deterministic across executions
    random.seed(420)
    if len(root_ids) > sample_size:
        root_ids = random.sample(root_ids, sample_size)
    return url_for_root_ids(root_ids, version=version)


def can_be_flywire_root_id(txt):
    try:
        return len(txt) == 18 and txt.startswith("72") and int(txt)
    except Exception:
        return False


def url_for_cells(segment_ids, data_version):
    config = {
        "dimensions": {"x": [1.6e-8, "m"], "y": [1.6e-8, "m"], "z": [4e-8, "m"]},
        "projectionScale": 30000,
        "layers": [
            {
                "type": "image",
                "source": "precomputed://https://bossdb-open-data.s3.amazonaws.com/flywire/fafbv14",
                "tab": "source",
                "name": "EM",
            },
            {
                "source": "precomputed://gs://flywire_neuropil_meshes/whole_neuropil/brain_mesh_v3",
                "type": "segmentation",
                "objectAlpha": 0.05,
                "hideSegmentZero": False,
                "segments": ["1"],
                "segmentColors": {"1": "#b5b5b5"},
                "skeletonRendering": {"mode2d": "lines_and_points", "mode3d": "lines"},
                "name": "brain_mesh_v3",
            },
            {
                "type": "segmentation",
                "source": f"precomputed://gs://flywire_v141_m{data_version}",
                "tab": "source",
                "segments": [
                    str(sid) for sid in segment_ids
                ],  # BEWARE: JSON can't handle big ints
                "name": f"flywire_v141_m{data_version}",
            },
        ],
        "showSlices": False,
        "perspectiveViewBackgroundColor": "#ffffff",
        "showDefaultAnnotations": False,
        "selectedLayer": {"visible": False, "layer": f"flywire_v141_m{data_version}"},
        "layout": "3d",
    }

    return f"https://neuroglancer-demo.appspot.com/#!{urllib.parse.quote(json.dumps(config))}"


def url_for_neuropils(segment_ids=None):
    config = {
        "layers": [
            {
                "source": "precomputed://gs://flywire_neuropil_meshes/whole_neuropil/brain_mesh_v3",
                "type": "segmentation",
                "objectAlpha": 0.1,
                "hideSegmentZero": False,
                "segments": ["1"],
                "segmentColors": {"1": "#b5b5b5"},
                "skeletonRendering": {"mode2d": "lines_and_points", "mode3d": "lines"},
                "name": "brain_mesh_v3",
            },
            {
                "type": "segmentation",
                "mesh": "precomputed://gs://flywire_neuropil_meshes/neuropils/neuropil_mesh_v141_v3",
                "objectAlpha": 0.90,
                "tab": "source",
                "segments": segment_ids,
                "segmentColors": {
                    seg_id: COLORS[key] for key, (seg_id, _) in REGIONS.items()
                },
                "skeletonRendering": {"mode2d": "lines_and_points", "mode3d": "lines"},
                "name": "neuropil-regions-surface",
            },
        ],
        "navigation": {
            "pose": {
                "position": {
                    "voxelSize": [4, 4, 40],
                    "voxelCoordinates": [144710, 55390, 512],
                }
            },
            "zoomFactor": 40.875984234132744,
        },
        "showAxisLines": False,
        "perspectiveViewBackgroundColor": "#ffffff",
        "perspectiveZoom": 3000,
        "showSlices": False,
        "gpuMemoryLimit": 2000000000,
        "showDefaultAnnotations": False,
        "selectedLayer": {"layer": "neuropil-regions-surface", "visible": False},
        "layout": "3d",
    }

    return f"https://neuroglancer-demo.appspot.com/#!{urllib.parse.quote(json.dumps(config))}"

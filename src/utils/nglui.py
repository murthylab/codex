import random
import urllib.parse

_BASE_URL = "https://neuroglancer-demo.appspot.com"
_PREFIX = (
    '{"dimensions":{"x":[1.6e-8,"m"],"y":[1.6e-8,"m"],"z":[4e-8,"m"]},"projectionScale":30000,'
    '"layers":['
    '{"type":"image","source":"precomputed://https://bossdb-open-data.s3.amazonaws.com/flywire/fafbv14","tab":"source","name":"EM"},'
    '{"source":"precomputed://gs://flywire_neuropil_meshes/whole_neuropil/brain_mesh_v141.surf",'
    '"type":"segmentation","selectedAlpha":0,"saturation":0,"objectAlpha":0.1,"segmentColors":{"1":"#b5b5b5"},'
    '"segments":["1"],"skeletonRendering":{"mode2d":"lines_and_points","mode3d":"lines"},"name":"tissue"},'
    '{"type":"segmentation","source":"precomputed://gs://flywire_v141_m447"'
    ',"tab":"source","segments":['
)
_SUFFIX = (
    '],"name":"flywire_v141_m447"}],"showSlices":false,"perspectiveViewBackgroundColor":"#ffffff",'
    '"showDefaultAnnotations":false, "selectedLayer":{"visible":false,"layer":"flywire_v141_m447"},'
    '"layout":"3d"}'
)

PROOFREADFW = (
    "https://neuromancer-seung-import.appspot.com/#!%7B%22layers%22:%5B%7B%22tab%22:%22"
    "annotations%22%2C%22selectedAnnotation%22:%7B%22id%22:%22data-bounds%22%7D%2C%22source%22"
    ":%22precomputed://https://tigerdata.princeton.edu/sseung-test1/fafb-v15-alignment-temp/"
    "fine_final/z0_7063/v1/aligned/mip1%22%2C%22crossSectionRenderScale%22:2%2C%22type%22:%22"
    "image%22%2C%22blend%22:%22default%22%2C%22shaderControls%22:%7B%7D%2C%22name%22:%22MIP1+%22"
    "%2C%22visible%22:false%7D%2C%7B%22source%22:%22"
    "precomputed://gs://flywire_neuropil_meshes/whole_neuropil/brain_mesh_v141.surf"
    "%22%2C%22type%22:%22segmentation%22%2C%22selectedAlpha%22"
    ":0%2C%22saturation%22:0%2C%22objectAlpha%22:0.1%2C%22segmentColors%22:%7B%221%22:%22#b5b5b5%22"
    "%7D%2C%22segments%22:%5B%221%22%5D%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22"
    "%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22tissue%22%7D%2C%7B%22source%22:%22graphene://"
    "https://prodv1.flywire-daf.com/segmentation/table/fly_v31%22%2C%22type%22:%22segmentation_with_graph%22"
    "%2C%22segments%22:%5B%22{}%22%5D%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%"
    "2C%22mode3d%22:%22lines%22%7D%2C%22graphOperationMarker%22:%5B%7B%22annotations%22:%5B%5D%2C%22tags%22"
    ":%5B%5D%7D%2C%7B%22annotations%22:%5B%5D%2C%22tags%22:%5B%5D%7D%5D%2C%22pathFinder%22:%7B%22color%22:"
    "%22#ffff00%22%2C%22pathObject%22:%7B%22annotationPath%22:%7B%22annotations%22:%5B%5D%2C%22tags%22:"
    "%5B%5D%7D%2C%22hasPath%22:false%7D%7D%2C%22name%22:%22fly_v31%22%7D%5D%2C%22navigation%22:%7B%22pose%22"
    ":%7B%22position%22:%7B%22voxelSize%22:%5B32%2C32%2C40%5D%2C%22voxelCoordinates%22"
    ":%5B15764.8935546875%2C2596.16552734375%2C2435.556396484375%5D%7D%7D%2C%22zoomFactor%22"
    ":463.48584732654984%7D%2C%22showDefaultAnnotations%22:false%2C%22perspectiveOrientation%22"
    ":%5B0.058571770787239075%2C0.5669599771499634%2C0.8209267258644104%2C0.034712888300418854%5D%2C%22"
    "perspectiveZoom%22:4641.209227099396%2C%22showSlices%22:false%2C%22jsonStateServer%22:%22https:"
    "//globalv1.daf-apis.com/nglstate/post%22%2C%22selectedLayer%22:%7B%22layer%22:%22fly_v31%22%7D%2C%22"
    "perspectiveViewBackgroundColor%22:%22#ffffff%22%2C%22layout%22:%223d%22%7D"
)

_NEUROPIL_BASE_URL = "https://neuroglancer-demo.appspot.com/#!"
_NEUROPIL_PREFIX = (
    '{"layers":[{"type":"segmentation","source":"precomputed://gs://flywire_neuropil_meshes/'
    'whole_neuropil/brain_mesh_v141.surf","tab":"source","selectedAlpha":0,"saturation":0,"objectAlpha":'
    '0.1,"segments":["1"],"segmentColors":{"1":"#b5b5b5"},"name":"tissue"},{"type":"segmentation",'
    '"mesh":"precomputed://gs://neuroglancer-fafb-data/elmr-data/FAFBNP.surf/mesh","objectAlpha":0.90,'
    '"tab":"source","segments":'
)
_NEUROPIL_SUFFIX = (
    ',"skeletonRendering":{"mode2d":"lines_and_points","mode3d":"lines"},"name":'
    '"neuropil-regions-surface"}],"navigation":{"pose":{"position":{"voxelSize":[4,4,40],'
    '"voxelCoordinates":[144710,55390,512]}},"zoomFactor":4.875984234132744},"showAxisLines":false,'
    '"perspectiveViewBackgroundColor":"#ffffff","perspectiveZoom":7804.061655381219,"showSlices":false,'
    '"gpuMemoryLimit":2000000000,"selectedLayer":{"layer":"neuropil-regions-surface","visible":false},'
    '"layout":"3d"}'
)


def url_for_root_ids(root_ids, point_to_proofreading_flywire=False):
    if point_to_proofreading_flywire:
        return PROOFREADFW.format("%22%2C%22".join([str(seg) for seg in root_ids]))
    else:
        seg_ids = ",".join([f'"{rid}"' for rid in root_ids])
        payload = urllib.parse.quote(f"{_PREFIX}{seg_ids}{_SUFFIX}")
        return f"{_BASE_URL}/#!{payload}"


def url_for_random_sample(root_ids, sample_size=50):
    # make the random subset selections deterministic across executions
    random.seed(420)
    if len(root_ids) > sample_size:
        root_ids = random.sample(root_ids, sample_size)
    return url_for_root_ids(root_ids)


def can_be_flywire_root_id(txt):
    try:
        return len(txt) == 18 and txt.startswith("72") and int(txt)
    except Exception as e:
        return False


def url_for_neuropils(segment_ids=None):
    seg_ids = "[" + ",".join([f'"{rid}"' for rid in segment_ids or []]) + "]"
    return _NEUROPIL_BASE_URL + urllib.parse.quote(
        _NEUROPIL_PREFIX + seg_ids + _NEUROPIL_SUFFIX
    )

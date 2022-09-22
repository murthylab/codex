import random

SINGLE_TMPL = "https://neuromancer-seung-import.appspot.com/#!%7B%22layers%22:%5B%7B%22tab%22:%22" \
              "annotations%22%2C%22selectedAnnotation%22:%7B%22id%22:%22data-bounds%22%7D%2C%22source%22" \
              ":%22precomputed://https://tigerdata.princeton.edu/sseung-test1/fafb-v15-alignment-temp/" \
              "fine_final/z0_7063/v1/aligned/mip1%22%2C%22crossSectionRenderScale%22:2%2C%22type%22:%22" \
              "image%22%2C%22blend%22:%22default%22%2C%22shaderControls%22:%7B%7D%2C%22name%22:%22MIP1+%22" \
              "%2C%22visible%22:false%7D%2C%7B%22source%22:%22" \
              "precomputed://gs://flywire_neuropil_meshes/whole_neuropil/brain_mesh_v141.surf" \
              "%22%2C%22type%22:%22segmentation%22%2C%22selectedAlpha%22" \
              ":0%2C%22saturation%22:0%2C%22objectAlpha%22:0.1%2C%22segmentColors%22:%7B%221%22:%22#b5b5b5%22" \
              "%7D%2C%22segments%22:%5B%221%22%5D%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22" \
              "%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22tissue%22%7D%2C%7B%22source%22:%22graphene://" \
              "https://prodv1.flywire-daf.com/segmentation/table/fly_v31%22%2C%22type%22:%22segmentation_with_graph%22" \
              "%2C%22segments%22:%5B%22{}%22%5D%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%" \
              "2C%22mode3d%22:%22lines%22%7D%2C%22graphOperationMarker%22:%5B%7B%22annotations%22:%5B%5D%2C%22tags%22" \
              ":%5B%5D%7D%2C%7B%22annotations%22:%5B%5D%2C%22tags%22:%5B%5D%7D%5D%2C%22pathFinder%22:%7B%22color%22:" \
              "%22#ffff00%22%2C%22pathObject%22:%7B%22annotationPath%22:%7B%22annotations%22:%5B%5D%2C%22tags%22:" \
              "%5B%5D%7D%2C%22hasPath%22:false%7D%7D%2C%22name%22:%22fly_v31%22%7D%5D%2C%22navigation%22:%7B%22pose%22" \
              ":%7B%22position%22:%7B%22voxelSize%22:%5B32%2C32%2C40%5D%2C%22voxelCoordinates%22" \
              ":%5B15764.8935546875%2C2596.16552734375%2C2435.556396484375%5D%7D%7D%2C%22zoomFactor%22" \
              ":463.48584732654984%7D%2C%22showDefaultAnnotations%22:false%2C%22perspectiveOrientation%22" \
              ":%5B0.058571770787239075%2C0.5669599771499634%2C0.8209267258644104%2C0.034712888300418854%5D%2C%22" \
              "perspectiveZoom%22:4641.209227099396%2C%22showSlices%22:false%2C%22jsonStateServer%22:%22https:" \
              "//globalv1.daf-apis.com/nglstate/post%22%2C%22selectedLayer%22:%7B%22layer%22:%22fly_v31%22%7D%2C%22" \
              "perspectiveViewBackgroundColor%22:%22#ffffff%22%2C%22layout%22:%223d%22%7D"

DOUBLE_TMPL = "https://neuromancer-seung-import.appspot.com/#!%7B%22layers%22:%5B%7B%22source%22:%22" \
         "precomputed://gs://flywire_neuropil_meshes/whole_neuropil/brain_mesh_v141.surf%22%2C%22type%22:%22" \
         "segmentation%22%2C%22selectedAlpha%22:0%2C%22saturation%22:0%2C%22objectAlpha%22:0.1%2C%22segmentColors%22" \
         ":%7B%221%22:%22#b5b5b5%22%7D%2C%22segments%22:%5B%221%22%5D%2C%22skeletonRendering%22:%7B%22mode2d%22:%22" \
         "lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22tissue%22%7D%2C%7B%22source%22:%22" \
         "graphene://https://prodv1.flywire-daf.com/segmentation/table/fly_v31%22%2C%22type%22:%22" \
         "segmentation_with_graph%22%2C%22segments%22:%5B%22{}%22%5D%2C%22skeletonRendering%22:%7B%22mode2d%22:%22" \
         "lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22graphOperationMarker%22:%5B%7B%22" \
         "annotations%22:%5B%5D%2C%22tags%22:%5B%5D%7D%2C%7B%22annotations%22:%5B%5D%2C%22tags%22:%5B%5D%7D%5D%2C%22" \
         "pathFinder%22:%7B%22color%22:%22#ffff00%22%2C%22pathObject%22:%7B%22annotationPath%22:%7B%22" \
         "annotations%22:%5B%5D%2C%22tags%22:%5B%5D%7D%2C%22hasPath%22:false%7D%7D%2C%22name%22:%22mod0%22%7D%2C%7B%22" \
         "source%22:%22graphene://https://prodv1.flywire-daf.com/segmentation/table/fly_v31%22%2C%22type%22:%22" \
         "segmentation_with_graph%22%2C%22segments%22:%5B%22{}%22%5D%2C%22skeletonRendering%22:%7B%22mode2d%22:%22" \
         "lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22graphOperationMarker%22:%5B%7B%22" \
         "annotations%22:%5B%5D%2C%22tags%22:%5B%5D%7D%2C%7B%22annotations%22:%5B%5D%2C%22tags%22:%5B%5D%7D%5D%2C%22" \
         "pathFinder%22:%7B%22color%22:%22#ffff00%22%2C%22pathObject%22:%7B%22annotationPath%22:%7B%22annotations%22" \
         ":%5B%5D%2C%22tags%22:%5B%5D%7D%2C%22hasPath%22:false%7D%7D%2C%22name%22:%22mod1%22%7D%5D%2C%22navigation%22" \
         ":%7B%22pose%22:%7B%22position%22:%7B%22voxelSize%22:%5B32%2C32%2C40%5D%2C%22voxelCoordinates%22" \
         ":%5B11486.916015625%2C3243.79150390625%2C2650.819091796875%5D%7D%7D%2C%22zoomFactor%22" \
         ":463.48584732654984%7D%2C%22showDefaultAnnotations%22:false%2C%22perspectiveOrientation%22" \
         ":%5B0.16562478244304657%2C0.4803096354007721%2C0.8530711531639099%2C0.11891447752714157%5D%2C%22" \
         "perspectiveZoom%22:3226.4862513671537%2C%22showSlices%22:false%2C%22jsonStateServer%22:%22" \
         "https://globalv1.daf-apis.com/nglstate/post%22%2C%22selectedLayer%22:%7B%22layer%22:%22" \
         "mod1%22%7D%2C%22perspectiveViewBackgroundColor%22:%22#ffffff%22%2C%22layout%22:%7B%22type%22" \
         ":%22column%22%2C%22children%22:%5B%7B%22type%22:%22viewer%22%2C%22layers%22:%5B%22tissue%22%2C%22" \
         "mod0%22%2C%22mod1%22%5D%2C%22layout%22:%223d%22%7D%2C%7B%22type%22:%22row%22%2C%22children%22:%5B%7B%22" \
         "type%22:%22viewer%22%2C%22layers%22:%5B%22tissue%22%2C%22mod0%22%5D%2C%22layout%22:%223d%22%7D%2C%7B%22" \
         "type%22:%22viewer%22%2C%22layers%22:%5B%22tissue%22%2C%22mod1%22%5D%2C%22layout%22:%223d%22%7D%5D%7D%5D%7D%7D"


def url_for_root_ids(root_ids):
    return SINGLE_TMPL.format("%22%2C%22".join([str(seg) for seg in root_ids]))


def url_for_pair_of_root_ids(root_ids_1, root_ids_2):
    return DOUBLE_TMPL.format(
        "%22%2C%22".join([str(seg) for seg in root_ids_1]),
        "%22%2C%22".join([str(seg) for seg in root_ids_2])
    )

def url_for_random_sample(root_ids, sample_size=10):
    if len(root_ids) > sample_size:
        root_ids = random.sample(root_ids, sample_size)
    return url_for_root_ids(root_ids)

import os

import numpy as np
from PIL import Image
from meshparty import skeleton_io, trimesh_vtk, trimesh_io

"""
Generates thumbnails for a set of .h5 skeleton files.

Instructions:
- Place your skeleton files in subfolder DATA_PATH (see below).
    - These are available from https://drive.google.com/drive/folders/1NA7lq5Arj5sqVnWUKAPc4KHkIjV0K8ba
- Place the full brain mesh file in the local folder, named `brain_mesh_v141.obj` (or anything else, and update `BRAIN_MESH_PATH` accordingly).
    - This is already included
- Make sure you have meshparty, Pillow, and numpy installed (`pip install meshparty` etc. - may need a fresh Conda environment).
- Run `python generate_thumbnails.py`. For each `<root_id>.h5` skeleton file, a corresponding thumbnail in the thumbnails folder named `<root_id>.png` will be created.
"""

DATA_PATH = os.path.join("flywire_resource_data_files", "l2_skeletons")
BRAIN_MESH_PATH = "brain_mesh_v141.obj"

SEGMENT_COLOR = (160 / 255, 42 / 255, 250 / 255)

REGIONS = {
    1: "AME_R",
    2: "LO_R",
    3: "NO",
    4: "BU_R",
    5: "PB",
    6: "LH_R",
    7: "LAL_R",
    8: "SAD",
    9: "CAN_R",
    10: "AMMC_R",
    11: "ICL_R",
    12: "VES_R",
    13: "IB_R",
    14: "ATL_R",
    15: "CRE_R",
    16: "MB_PED_R",
    17: "MB_VL_R",
    18: "MB_ML_R",
    19: "FLA_R",
    20: "LOP_R",
    21: "EB",
    22: "AL_R",
    23: "ME_R",
    24: "FB",
    25: "SLP_R",
    26: "SIP_R",
    27: "SMP_R",
    28: "AVLP_R",
    29: "PVLP_R",
    30: "WED_R",
    31: "PLP_R",
    32: "AOTU_R",
    33: "GOR_R",
    34: "MB_CA_R",
    35: "SPS_R",
    36: "IPS_R",
    37: "SCL_R",
    38: "EPA_R",
    39: "GNG",
    40: "PRW",
    41: "GA_R",
    42: "AME_L",
    43: "LO_L",
    44: "BU_L",
    45: "LH_L",
    46: "LAL_L",
    47: "CAN_L",
    48: "AMMC_L",
    49: "ICL_L",
    50: "VES_L",
    51: "IB_L",
    52: "ATL_L",
    53: "CRE_L",
    54: "MB_PED_L",
    55: "MB_VL_L",
    56: "MB_ML_L",
    57: "FLA_L",
    58: "LOP_L",
    59: "AL_L",
    60: "ME_L",
    61: "SLP_L",
    62: "SIP_L",
    63: "SMP_L",
    64: "AVLP_L",
    65: "PVLP_L",
    66: "WED_L",
    67: "PLP_L",
    68: "AOTU_L",
    69: "GOR_L",
    70: "MB_CA_L",
    71: "SPS_L",
    72: "IPS_L",
    73: "SCL_L",
    74: "EPA_L",
    75: "GA_L",
}

full_brain = trimesh_io.read_mesh(BRAIN_MESH_PATH)
full_brain_mesh = trimesh_io.Mesh(full_brain[0], full_brain[1], full_brain[2])
full_brain_mesh_actor = trimesh_vtk.mesh_actor(
    full_brain_mesh, color=(0, 0, 0), opacity=0.025
)

ngl_state = {
    "navigation": {
        "pose": {
            "position": {
                "voxelSize": [4, 4, 40],
                "voxelCoordinates": [131529, 53923, 2000],
            }
        }
    },
    "perspectiveZoom": 2500,
}
cam = trimesh_vtk.camera_from_ngl_state(ngl_state)


def render(filename, out_path=None):
    if out_path is None:
        out_path = os.path.join("thumbnails", filename)
    skeleton = skeleton_io.read_skeleton_h5(os.path.join(DATA_PATH, filename))
    skeleton_actor = trimesh_vtk.skeleton_actor(
        skeleton, color=SEGMENT_COLOR, opacity=0.75
    )
    out_filename = out_path.replace(".h5", ".png")
    trimesh_vtk.render_actors(
        [full_brain_mesh_actor, skeleton_actor],
        filename=out_filename,
        camera=cam,
        scale=1,
        do_save=True,
    )
    add_transparency(out_filename)


def add_transparency(path):
    # from https://stackoverflow.com/a/54148416
    img = Image.open(path)
    x = np.asarray(img.convert("RGBA")).copy()
    x[:, :, 3] = (255 * (x[:, :, :3] != 255).any(axis=2)).astype(np.uint8)
    img2 = Image.fromarray(x)
    img2.save(path, "PNG")


def generate_thumbnails():
    filenames = os.listdir(DATA_PATH)
    num_ids = len(filenames)
    for i, filename in enumerate(filenames):
        render(filename)
        print(f"[{i + 1}/{num_ids} ({(i + 1) / num_ids * 100}%)] Rendered {filename}")
    # Next step: upload thumbnails to GCS bucket:
    # flywire-data/codex/skeleton_thumbnails/{root_id}.png


def generate_neuropil_thumbnails():
    import cloudvolume

    cv = cloudvolume.CloudVolume(
        "precomputed://gs://neuroglancer-fafb-data/elmr-data/FAFBNP.surf",
        use_https=True,
    )

    for mesh_id in REGIONS:
        np_mesh_cv = cv.mesh.get(mesh_id)
        np_mesh = trimesh_io.Mesh(
            np_mesh_cv.vertices, np_mesh_cv.faces, np_mesh_cv.normals
        )
        np_mesh_actor = trimesh_vtk.mesh_actor(
            np_mesh, color=SEGMENT_COLOR, opacity=0.75
        )
        np_name = REGIONS[mesh_id]
        out_path = os.path.join("thumbnails", f"{np_name}.png")
        trimesh_vtk.render_actors(
            [full_brain_mesh_actor, np_mesh_actor],
            filename=out_path,
            camera=cam,
            scale=1,
            do_save=True,
        )
        add_transparency(out_path)


if __name__ == "__main__":
    # generate_thumbnails()
    generate_neuropil_thumbnails()

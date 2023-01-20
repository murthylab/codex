import os

import numpy as np
from src.data.brain_regions import REGIONS
from PIL import Image
from meshparty import skeleton_io, trimesh_vtk, trimesh_io

"""
Generates thumbnails for a set of .h5 skeleton files.

Instructions:
- Place your skeleton files in subfolder DATA_PATH (see below).
    - These are available from https://drive.google.com/drive/folders/1NA7lq5Arj5sqVnWUKAPc4KHkIjV0K8ba
- Place the full brain mesh file in the local folder, named `brain_mesh_v141.obj` (or anything else, and update `BRAIN_MESH_PATH` accordingly).
    - This is already included
- Make sure you have meshparty, Pillow, and numpy installed, as well as the project's requirements.txt (`pip install meshparty` etc. - may need a fresh Conda environment).
- From the project root folder, run `python -m src.etl.generate_thumbnails`. For each `<root_id>.h5` skeleton file, a corresponding thumbnail in the thumbnails folder named `<root_id>.png` will be created.
"""

BASE_PATH = os.path.join("src", "etl")
DATA_PATH = os.path.join(BASE_PATH, "flywire_resource_data_files", "l2_skeletons")
BRAIN_MESH_PATH = os.path.join(BASE_PATH, "brain_mesh_v141.obj")
THUMBNAILS_PATH = os.path.join(BASE_PATH, "thumbnails")

SEGMENT_COLOR = (160 / 255, 42 / 255, 250 / 255)


if not os.path.exists(THUMBNAILS_PATH):
    os.makedirs(THUMBNAILS_PATH)


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
        out_path = os.path.join(THUMBNAILS_PATH, filename)
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
    # flywire-data/{LATEST_DATA_SNAPSHOT_VERSION}/skeleton_thumbnails/{root_id}.png


def generate_neuropil_thumbnails():
    import cloudvolume

    cv = cloudvolume.CloudVolume(
        "precomputed://gs://neuroglancer-fafb-data/elmr-data/FAFBNP.surf",
        use_https=True,
    )

    for np_name, np_attrs in REGIONS.items():
        np_id = np_attrs[0]
        np_mesh_cv = cv.mesh.get(np_id)
        np_mesh = trimesh_io.Mesh(
            np_mesh_cv.vertices, np_mesh_cv.faces, np_mesh_cv.normals
        )
        np_mesh_actor = trimesh_vtk.mesh_actor(
            np_mesh, color=SEGMENT_COLOR, opacity=0.75
        )
        out_path = os.path.join(THUMBNAILS_PATH, f"{np_name}.png")
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

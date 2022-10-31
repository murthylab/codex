import os

import numpy as np
from PIL import Image
from meshparty import skeleton_io, trimesh_vtk, trimesh_io

from src.data.versions import LATEST_DATA_SNAPSHOT_VERSION

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

DATA_PATH = os.path.join("flywire_resource_data_files", LATEST_DATA_SNAPSHOT_VERSION, "l2_skeletons")
BRAIN_MESH_PATH = "brain_mesh_v141.obj"

SEGMENT_COLOR = (160 / 255, 42 / 255, 250 / 255)

full_brain = trimesh_io.read_mesh(BRAIN_MESH_PATH)
full_brain_mesh = trimesh_io.Mesh(full_brain[0], full_brain[1], full_brain[2])
full_brain_mesh_actor = trimesh_vtk.mesh_actor(full_brain_mesh, color=(0, 0, 0), opacity=0.025)

ngl_state = {
    "navigation": {
        "pose": {
            "position": {
                "voxelSize": [4, 4, 40],
                "voxelCoordinates": [131529, 53923, 2000]
            }
        }
    },
    "perspectiveZoom": 2500
}
cam = trimesh_vtk.camera_from_ngl_state(ngl_state)


def render(filename, out_path=None):
    if out_path is None:
        out_path = os.path.join("thumbnails", filename)
    skeleton = skeleton_io.read_skeleton_h5(os.path.join(DATA_PATH, filename))
    skeleton_actor = trimesh_vtk.skeleton_actor(skeleton, color=SEGMENT_COLOR, opacity=0.75)
    out_filename = out_path.replace(".h5", ".png")
    trimesh_vtk.render_actors([full_brain_mesh_actor, skeleton_actor], filename=out_filename, camera=cam, scale=1,
                              do_save=True)
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


if __name__ == "__main__":
    generate_thumbnails()

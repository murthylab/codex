import glob
import os
import shutil
import sys

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
- For animated thumbnails, make sure ImageMagick is installed with the `convert` command- https://imagemagick.org/script/download.php
- From the project root folder, run `python -m src.etl.generate_thumbnails`. For each `<root_id>.h5` skeleton file, a corresponding thumbnail in the thumbnails folder named `<root_id>.png` will be created.
    - For animated thumbnails: run `python -m src.etl.generate_thumbnails animated`
    - For neuropil thumbnails: run `python -m src.etl.generate_thumbnails neuropils`
"""

BASE_PATH = os.path.join("src", "etl")
DATA_PATH = os.path.join(BASE_PATH, "flywire_resource_data_files", "l2_skeletons")
BRAIN_MESH_PATH = os.path.join(BASE_PATH, "brain_mesh_v141.obj")
THUMBNAILS_PATH = os.path.join(BASE_PATH, "thumbnails")
PREV_THUMBNAILS_PATH = os.path.join(BASE_PATH, "thumbnails_prev")

SEGMENT_COLOR = (160 / 255, 42 / 255, 250 / 255)


if not os.path.exists(THUMBNAILS_PATH):
    os.makedirs(THUMBNAILS_PATH)


full_brain = trimesh_io.read_mesh(BRAIN_MESH_PATH)
full_brain_mesh = trimesh_io.Mesh(full_brain[0], full_brain[1], full_brain[2])
full_brain_mesh_actor = trimesh_vtk.mesh_actor(
    full_brain_mesh, color=(0, 0, 0), opacity=0.025
)


class HiddenPrints:
    # https://stackoverflow.com/a/45669280
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout


def generate_cam(perspective_orientation=[0.0, 0.0, 0.0, 1.0]):
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
        "perspectiveOrientation": perspective_orientation,
    }
    return trimesh_vtk.camera_from_ngl_state(ngl_state)


cam = generate_cam()


def render(filename, out_path=None, camera=cam, downscale_factor=1):
    if out_path is None:
        out_path = os.path.join(THUMBNAILS_PATH, filename)
    skeleton = skeleton_io.read_skeleton_h5(os.path.join(DATA_PATH, filename))
    skeleton_actor = trimesh_vtk.skeleton_actor(
        skeleton, color=SEGMENT_COLOR, opacity=0.75
    )
    out_filename = out_path.replace(".h5", ".png")
    with HiddenPrints():
        trimesh_vtk.render_actors(
            [full_brain_mesh_actor, skeleton_actor],
            filename=out_filename,
            camera=camera,
            scale=1,
            do_save=True,
            video_width=1080 // downscale_factor,
            video_height=720 // downscale_factor,
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
        if os.path.exists(
            os.path.join(THUMBNAILS_PATH, filename.replace(".h5", ".png"))
        ):
            print(
                f"[{i + 1}/{num_ids} ({(i + 1) / num_ids * 100}%)] Already exists {filename}"
            )
        elif os.path.exists(
            os.path.join(PREV_THUMBNAILS_PATH, filename.replace(".h5", ".png"))
        ):
            print(
                f"[{i + 1}/{num_ids} ({(i + 1) / num_ids * 100}%)] Exists in previous version {filename}"
            )
        else:
            render(filename)
            print(
                f"[{i + 1}/{num_ids} ({(i + 1) / num_ids * 100}%)] Rendered {filename}"
            )
    # Next step: upload thumbnails to GCS bucket:
    # flywire-data/codex/skeleton_thumbnails/{root_id}.png


def compile_gif(root_id, cleanup=True):
    input_path = os.path.join(THUMBNAILS_PATH, f"*_{root_id}.png")
    output_path = os.path.join(THUMBNAILS_PATH, f"{root_id}.gif")
    print("Compiling gif", output_path)
    os.system(f"convert -delay 10 -dispose background {input_path} {output_path}")
    if cleanup:
        for f in glob.glob(input_path):
            os.remove(f)


def generate_thumbnail_animated(filename):
    root_id = filename.replace(".h5", "")

    angle = 0.4
    smoothness = 3
    increment = angle / smoothness
    frames = {}
    frames[0] = [0, 2 * smoothness]
    for i in range(1, smoothness):
        a = i * increment
        frames[a] = [i, 2 * smoothness - i]
        frames[-a] = [2 * smoothness + i, 4 * smoothness - i]
    frames[angle] = [smoothness]
    frames[-angle] = [3 * smoothness]

    for f in frames:
        cam = generate_cam(perspective_orientation=[0, f, 0, 1])
        base_i = frames[f][0]
        render(
            filename,
            out_path=os.path.join(THUMBNAILS_PATH, f"{base_i:02}_{filename}"),
            camera=cam,
            downscale_factor=4,
        )
        for i in range(1, len(frames[f])):
            shutil.copyfile(
                os.path.join(THUMBNAILS_PATH, f"{base_i:02}_{root_id}.png"),
                os.path.join(THUMBNAILS_PATH, f"{(frames[f][i]):02}_{root_id}.png"),
            )
    compile_gif(root_id)


def generate_thumbnails_animated():
    filenames = os.listdir(DATA_PATH)
    num_ids = len(filenames)
    for i, filename in enumerate(filenames):
        if os.path.exists(
            os.path.join(THUMBNAILS_PATH, filename.replace(".h5", ".gif"))
        ):
            print(
                f"[{i + 1}/{num_ids} ({(i + 1) / num_ids * 100}%)] Already exists {filename}"
            )
        elif os.path.exists(
            os.path.join(PREV_THUMBNAILS_PATH, filename.replace(".h5", ".gif"))
        ):
            print(
                f"[{i + 1}/{num_ids} ({(i + 1) / num_ids * 100}%)] Exists in previous version {filename}"
            )
        else:
            generate_thumbnail_animated(filename)
            print(
                f"[{i + 1}/{num_ids} ({(i + 1) / num_ids * 100}%)] Rendered {filename}"
            )


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
    if len(sys.argv) > 1:
        if sys.argv[1] == "neuropils":
            generate_neuropil_thumbnails()
        elif sys.argv[1] == "animated":
            generate_thumbnails_animated()
        else:
            generate_thumbnails()
    else:
        generate_thumbnails()

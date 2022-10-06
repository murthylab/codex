import os
from meshparty import skeleton_io, trimesh_vtk, trimesh_io

"""
Generates thumbnails for a set of .h5 skeleton files.

Instructions:
- Place your skeleton files in subfolder `flywire_resource_data_files\447\l2_skeletons` (or any other subfolder and update `mesh_path` accordingly).
- Place the full brain mesh file in the local folder, named `brain_mesh_v141.obj` (or anything else, and update `brain_mesh_path` accordingly).
- Make sure you have meshparty installed (`pip install meshparty` - may need a fresh Conda environment).
- Run `python generate_thumbnails.py`. For each `<root_id>.h5` skeleton file, a corresponding thumbnail in the thumbnails folder named `<root_id>.h5.png` will be created.
- If you want to rename the thumbnails to `<root_id>.png` without the `.h5`, use the rename_thumbnails() function.
"""

mesh_path = "flywire_resource_data_files\\447\\l2_skeletons\\"
brain_mesh_path = "brain_mesh_v141.obj"

segment_color = (160/255, 42/255, 250/255)

full_brain = trimesh_io.read_mesh(brain_mesh_path)
full_brain_mesh = trimesh_io.Mesh(full_brain[0], full_brain[1], full_brain[2])
full_brain_mesh_actor = trimesh_vtk.mesh_actor(full_brain_mesh, color=(0,0,0), opacity=0.05)

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
        out_path = "thumbnails\\" + filename
    skeleton = skeleton_io.read_skeleton_h5(mesh_path + filename)
    skeleton_actor = trimesh_vtk.skeleton_actor(skeleton, color=segment_color, opacity=0.75)
    trimesh_vtk.render_actors([full_brain_mesh_actor, skeleton_actor], filename=out_path + ".png", camera=cam, scale=1, do_save=True)

def rename_thumbnails():
    filenames = os.listdir("thumbnails")
    num_ids = len(filenames)
    for i in range(num_ids):
        filename = filenames[i]
        filename_split = filename.split(".")
        if len(filename_split) < 3:
            print("Skipping", filename)
            continue
        new_filename = filename_split[0] + "." + filename_split[2]
        if os.path.isfile("thumbnails\\" + new_filename):
            print("Removing old", new_filename)
            os.remove("thumbnails\\" + new_filename)
        os.rename("thumbnails\\" + filename, "thumbnails\\" + new_filename)
        print(f"[{i+1}/{num_ids} ({(i+1)/num_ids*100}%)] Renamed {filename} to {new_filename}")

def main():
    filenames = os.listdir("flywire_resource_data_files\\447\\l2_skeletons")
    num_ids = len(filenames)
    for i in range(num_ids):
        filename = filenames[i]
        render(filename)
        print(f"[{i+1}/{num_ids} ({(i+1)/num_ids*100}%)] Rendered {filename}")

if __name__ == "__main__":
    main()
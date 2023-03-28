import os
from meshparty import skeleton_io

BASE_PATH = os.path.join("src", "etl")
DATA_PATH = os.path.join(BASE_PATH, "flywire_resource_data_files", "l2_skeletons")
SWC_PATH = os.path.join(BASE_PATH, "skeletons_swc")


def convert_skeletons():
    filenames = os.listdir(DATA_PATH)
    num_ids = len(filenames)
    for i, filename in enumerate(filenames):
        if os.path.exists(os.path.join(SWC_PATH, filename.replace(".h5", ".swc"))):
            print(
                f"[{i + 1}/{num_ids} ({(i + 1) / num_ids * 100}%)] Already exists {filename}"
            )
        else:
            convert(filename)
            print(
                f"[{i + 1}/{num_ids} ({(i + 1) / num_ids * 100}%)] Converted {filename}"
            )


def convert(filename):
    out_filename = filename.replace(".h5", ".swc")
    out_path = os.path.join(SWC_PATH, out_filename)

    skeleton = skeleton_io.read_skeleton_h5(os.path.join(DATA_PATH, filename))
    skeleton_io.export_to_swc(skeleton, out_path)


if __name__ == "__main__":
    convert_skeletons()

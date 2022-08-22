import os
import pytest
import tempfile
import numpy as np
import pandas as pd
import json
from tifffile import imwrite
from segmentation_data_prep import SegmentationTFRecords


def prep_object(
    data_folders=["path"], cell_table_path="path",
    conversion_matrix_path="path", normalization_dict_path="path",
    tf_record_path="path",
):
    data_prep = SegmentationTFRecords(
        data_folders=data_folders,
        cell_table_path=cell_table_path,
        conversion_matrix_path=conversion_matrix_path,
        imaging_platform="imaging_platform",
        dataset="dataset",
        tile_size=[256, 256],
        tf_record_path=tf_record_path,
        normalization_dict_path=normalization_dict_path,
    )
    return data_prep


def prepare_conversion_matrix():
    col_names = ["CD11c", "CD14", "CD56", "CD57"]
    row_names = ["stromal", "FAP", "NK", "CD4T", "CD14", "CD163"]
    conversion_matrix = pd.DataFrame(
        np.random.randint(0, 2, size=(len(row_names), len(col_names))),
        columns=col_names,
        index=row_names,
    )
    return conversion_matrix


def test_get_image():
    data_prep = prep_object()
    with tempfile.TemporaryDirectory() as temp_dir:
        test_img_1 = np.random.rand(256, 256)
        test_img_2 = np.random.rand(256, 256)
        imwrite(os.path.join(temp_dir, "CD8.tiff"), test_img_1)
        imwrite(os.path.join(temp_dir, "CD4.tiff"), test_img_2)
        CD8_img = data_prep.get_image(data_folder=temp_dir, marker="CD8")
        CD4_img = data_prep.get_image(data_folder=temp_dir, marker="CD4")
        assert np.array_equal(test_img_1, CD8_img)
        assert np.array_equal(test_img_2, CD4_img)
        assert not np.array_equal(CD8_img, CD4_img)


def prepare_test_data_folders(num_folders, temp_dir, selected_markers, random=False, scale=[1.0]):
    data_folders = []
    if len(scale) != num_folders:
        scale = [1.0] * num_folders
    for i in range(num_folders):
        folder = os.path.join(temp_dir, "fov_1" + str(i))
        os.mkdir(folder)
        data_folders.append(folder)
        for marker, std in zip(selected_markers, scale):
            if random:
                img = np.random.rand(256, 256) * std
            else:
                img = np.ones([256, 256])
            imwrite(
                os.path.join(temp_dir, "fov_1" + str(i), marker + ".tiff"),
                img,
            )
    return data_folders


def prepare_cell_type_table():

    # prepare cell_table
    cell_type_table = pd.DataFrame(
        {
            "SampleID": ["fov_1"]*6 + ["fov_2"]*6,
            "label": [1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6],
            "cluster_labels": ["stromal", "FAP", "NK"]*2 +
            ["CD4T", "CD14", "CD163"]*2
        }
    )

    return cell_type_table


def test_calculate_normalization_matrix():

    # instantiate data_prep, conversion_matrix and markers
    data_prep = prep_object()
    selected_markers = ["CD11c", "CD14", "CD56", "CD57"]
    scale = [1.0, 2.0, 8.512, 0.25]

    # create temporary folders with data and do tests
    with tempfile.TemporaryDirectory() as temp_dir:

        # check normalization_dict for different stochastic images
        data_folders = prepare_test_data_folders(
            4, temp_dir, selected_markers, random=True, scale=scale
        )
        data_prep = prep_object(
            normalization_dict_path=os.path.join(temp_dir, "norm_dict_test.json")
        )
        norm_dict = data_prep.calculate_normalization_matrix(
            data_folders=data_folders, selected_markers=selected_markers
        )

        # check if the normalization_dict has the correct values for stochastic images
        for marker, std in zip(norm_dict.keys(), scale):
            assert norm_dict[marker] - 1 / (0.5 * std) < 0.001

        # check if the normalization_dict is correctly written to the json file
        norm_dict_loaded = json.load(open(os.path.join(temp_dir, "norm_dict_test.json")))
        assert norm_dict_loaded == norm_dict

        # check if the normalization_dict has the correct keys
        for marker in selected_markers:
            assert marker in norm_dict.keys()


def test_check_input():
    with tempfile.TemporaryDirectory() as temp_dir:
        # create temporary folders with data for the tests
        conversion_matrix = prepare_conversion_matrix()
        conversion_matrix_path = os.path.join(temp_dir, "conversion_matrix.csv")
        conversion_matrix.to_csv(conversion_matrix_path, index=False)
        norm_dict = {"CD11c": 1.0, "CD14": 1.0, "CD56": 1.0, "CD57": 1.0}
        data_folders = prepare_test_data_folders(5, temp_dir, norm_dict.keys())
        cell_table_path = os.path.join(temp_dir, "cell_type_table.csv")
        cell_table = prepare_cell_type_table()
        cell_table.to_csv(cell_table_path, index=False)

        # check if the normalization_dict is loaded correctly in check_input
        # when normalization_dict_path is given to init
        with open(os.path.join(temp_dir, "norm_dict.json"), "w") as f:
            json.dump(norm_dict, f)
        data_prep = prep_object(
            conversion_matrix_path=conversion_matrix_path,
            tf_record_path=os.path.join(temp_dir, "tf_record_path"),
            normalization_dict_path=os.path.join(temp_dir, "norm_dict.json"),
            cell_table_path=cell_table_path,
        )
        data_prep.check_input()
        assert norm_dict == data_prep.normalization_dict

        # check if the normalization_dict is calculated in check_input when
        # data_folders but no normalization_dict_path is given to init
        data_prep = prep_object(
            data_folders=data_folders,
            conversion_matrix_path=conversion_matrix_path,
            tf_record_path=os.path.join(temp_dir, "tf_record_path"),
            cell_table_path=cell_table_path,
        )
        data_prep.check_input()
        assert norm_dict == data_prep.normalization_dict


def test_get_inst_binary_masks():
    instance_mask = np.zeros([256, 256], dtype=np.uint16)
    instance_mask[0:32, 0:32] = 1
    instance_mask[0:32, 32:64] = 2
    instance_mask[0:32, 64:96] = 3
    instance_mask[32:64, 0:32] = 4
    instance_mask[64:96, 64:96] = 5

    instance_mask_eroded = np.zeros([256, 256], dtype=np.uint8)
    instance_mask_eroded[0:31, 0:31] = 1
    instance_mask_eroded[0:31, 33:63] = 1
    instance_mask_eroded[0:31, 65:95] = 1
    instance_mask_eroded[33:63, 0:31] = 1
    instance_mask_eroded[65:95, 65:95] = 1
    with tempfile.TemporaryDirectory() as temp_dir:

        # check if the instance_mask is correctly loaded
        imwrite(os.path.join(temp_dir, "cell_segmentation.tiff"), instance_mask)
        data_prep = prep_object()
        loaded_binary_img, loaded_img = data_prep.get_inst_binary_masks(data_folder=temp_dir)
        assert np.array_equal(loaded_img, instance_mask)

        # check if binary mask is binarized correctly
        assert np.array_equal(np.unique(loaded_binary_img), np.array([0, 1]))

        # check if binary mask is eroded correctly
        assert np.array_equal(loaded_binary_img, instance_mask_eroded)


def test_get_cell_types():

    data_prep = prep_object()
    cell_table = prepare_cell_type_table()
    data_prep.cell_type_table = cell_table
    fov_1_subset = data_prep.get_cell_types("fov_1")

    # check if the we get the right cell types for fov_1
    for cell_type in fov_1_subset["cluster_labels"]:
        assert cell_type in ["stromal", "FAP", "NK"]
    assert np.unique(fov_1_subset["SampleID"]) == ["fov_1"]


def test_get_marker_activity():
    data_prep = prep_object()
    cell_table = prepare_cell_type_table()
    conversion_matrix = prepare_conversion_matrix()
    data_prep.cell_type_table = cell_table
    fov_1_subset = data_prep.get_cell_types("fov_1")
    markers = ["CD11c", "CD14"]
    out_dict = data_prep.get_marker_activity(
        fov_1_subset.cluster_labels, conversion_matrix, markers
    )

    # check if the right markers are returned and dimensions fit
    assert list(out_dict.keys()) == markers
    assert len(out_dict["CD11c"]) == len(fov_1_subset.label)
    assert len(out_dict["CD14"]) == len(fov_1_subset.label)

    # check if the out_dict has the right marker activity values for a given cell
    for i in range(len(fov_1_subset.label)):
        assert (
            out_dict["CD11c"][i] == conversion_matrix.loc[fov_1_subset.cluster_labels[i], "CD11c"]
        )
        assert out_dict["CD14"][i] == conversion_matrix.loc[fov_1_subset.cluster_labels[i], "CD14"]


def test_get_marker_activity_mask():
    data_prep = prep_object()
    markers = ["CD11c", "CD14"]
    marker_activity = {"CD11c": [1, 0, 0, 0, 0, 1], "CD14": [0, 1, 1, 1, 1, 0]}
    instance_mask = np.zeros([256, 256], dtype=np.uint16)
    instance_mask[0:32, 0:32] = 1
    instance_mask[0:32, 32:64] = 2
    instance_mask[0:32, 64:96] = 3
    instance_mask[32:64, 0:32] = 4
    instance_mask[64:96, 64:96] = 5
    instance_mask[128:160, 128:160] = 6
    binary_mask = (instance_mask > 0).astype(np.uint8)

    marker_activity_mask = data_prep.get_marker_activity_mask(
        instance_mask, binary_mask, marker_activity, markers
    )

    # check if the right spatial dimensions got returned
    assert marker_activity_mask.shape[:-1] == (256, 256)

    # check if for each marker one channel got returned
    assert marker_activity_mask.shape[-1] == len(markers)

    # check if the right marker activity values are returned
    instance_mask[binary_mask < 1] = 0
    for i in np.unique(instance_mask):
        if i == 0:
            continue
        assert (
            marker_activity_mask[instance_mask == i, 0] == marker_activity[markers[0]][i - 1]
        ).all()
        assert (
            marker_activity_mask[instance_mask == i, 1] == marker_activity[markers[1]][i - 1]
        ).any()


def test_prepare_example():
    pass

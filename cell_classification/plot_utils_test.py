from segmentation_data_prep import parse_dict, feature_description
from segmentation_data_prep_test import prep_object_and_inputs
import pytest
import tempfile
from plot_utils import plot_overlay, plot_together
import os
import tensorflow as tf


def prepare_dataset(temp_dir):
    data_prep, _, _, _ = prep_object_and_inputs(temp_dir)
    data_prep.tf_record_path = temp_dir
    data_prep.make_tf_record()
    tf_record_path = os.path.join(temp_dir, data_prep.dataset + ".tfrecord")
    dataset = tf.data.TFRecordDataset(tf_record_path)
    return dataset


def test_plot_overlay():
    with tempfile.TemporaryDirectory() as temp_dir:
        dataset = iter(prepare_dataset(temp_dir))
        plot_path = os.path.join(temp_dir, "plots")
        os.makedirs(plot_path, exist_ok=True)
        record = next(dataset)
        example_encoded = tf.io.parse_single_example(record, feature_description)
        example = parse_dict(example_encoded)
        plot_overlay(
            example, save_dir=plot_path, save_file=f"{example['folder_name']}_overlay.png"
        )

        # check if plot was saved
        assert os.path.exists(os.path.join(plot_path, f"{example['folder_name']}_overlay.png"))


def test_plot_together():
    with tempfile.TemporaryDirectory() as temp_dir:
        dataset = iter(prepare_dataset(temp_dir))
        plot_path = os.path.join(temp_dir, "plots")
        os.makedirs(plot_path, exist_ok=True)
        record = next(dataset)
        example_encoded = tf.io.parse_single_example(record, feature_description)
        example = parse_dict(example_encoded)
        plot_together(
            example, save_dir=plot_path, save_file=f"{example['folder_name']}_together.png"
        )

        # check if plot was saved
        assert os.path.exists(os.path.join(plot_path, f"{example['folder_name']}_together.png"))
import pytest
import tempfile
import numpy as np
import tensorflow as tf
from segmentation_data_prep_test import prep_object_and_inputs
import os
import toml
from model_builder import ModelBuilder
import h5py


def test_prep_loss():
    with tempfile.TemporaryDirectory() as temp_dir:
        params = toml.load("cell_classification/configs/params.toml")
        trainer = ModelBuilder(params)
        loss_fn = trainer.prep_loss()

        # sanity check outputs of loss function
        loss = loss_fn(
            tf.constant(np.random.randint(0, 2, (1, 256, 256, 1))),
            tf.sigmoid(tf.constant(np.random.rand(1, 256, 256, 1), dtype=tf.float32)),
        )
        assert loss.shape == (1, 256, 256)
        assert loss.dtype == tf.float32
        assert tf.reduce_mean(loss) > 0
        assert tf.reduce_min(loss) >= 0


def test_prep_data():
    with tempfile.TemporaryDirectory() as temp_dir:
        # trainer, params = prep_trainer(temp_dir)
        data_prep, _, _, _ = prep_object_and_inputs(temp_dir)
        data_prep.tf_record_path = temp_dir
        data_prep.make_tf_record()
        tf_record_path = os.path.join(data_prep.tf_record_path, data_prep.dataset + ".tfrecord")
        params = toml.load("cell_classification/configs/params.toml")
        params["record_path"] = tf_record_path
        params["path"] = temp_dir
        params["experiment"] = "test"
        params["num_epochs"] = 1
        params["num_validation"] = 2
        params["batch_size"] = 2
        trainer = ModelBuilder(params)
        trainer.prep_data()

        # check if correct number of samples per batch is returned
        trainer.validation_dataset = trainer.validation_dataset.map(
                trainer.prep_batches, num_parallel_calls=tf.data.AUTOTUNE
        )
        assert next(iter(trainer.train_dataset))[0].shape[0] == params["batch_size"]
        assert next(iter(trainer.validation_dataset))[0].shape[0] == \
            params["batch_size"]

        # check if samples only contains two files (inputs, targets)
        assert len(next(iter(trainer.train_dataset))) == 2
        assert len(next(iter(trainer.validation_dataset))) == 2

        # check if in eval mode validation samples contain all original example keys
        trainer.params["eval"] = True
        trainer.prep_data()
        val_dset = iter(trainer.validation_dataset)
        val_batch = next(val_dset)
        assert set(val_batch.keys()) == set(
            [
                "mplex_img", "binary_mask", "instance_mask", "folder_name", "marker", "dataset",
                "imaging_platform", "marker_activity_mask", "activity_df",
            ]
        )


def test_prep_model():
    with tempfile.TemporaryDirectory() as temp_dir:
        params = toml.load("cell_classification/configs/params.toml")
        params["path"] = temp_dir

        trainer = ModelBuilder(params)
        trainer.prep_model()

        # check if right objects are instantiated
        assert isinstance(trainer.model, tf.keras.Model)
        assert isinstance(trainer.optimizer, tf.keras.optimizers.Optimizer)

        # check if all the directories were created
        assert os.path.exists(trainer.params['log_dir'])
        assert os.path.exists(trainer.params['model_dir'])

        # check if callbacks were created
        assert isinstance(trainer.train_callbacks[0], tf.keras.callbacks.ModelCheckpoint)
        assert isinstance(trainer.train_callbacks[1], tf.keras.callbacks.TensorBoard)
        assert isinstance(trainer.train_callbacks[2], tf.keras.callbacks.LearningRateScheduler)

        # check if model path is taken from params.toml if it exists
        trainer.params["model_path"] = os.path.join(temp_dir, "test_dir", "test.h5")
        trainer.prep_model()
        assert trainer.params["model_path"] == os.path.join(temp_dir, "test_dir", "test.h5")


def test_train():
    with tempfile.TemporaryDirectory() as temp_dir:
        data_prep, _, _, _ = prep_object_and_inputs(temp_dir)
        data_prep.tf_record_path = temp_dir
        data_prep.make_tf_record()
        tf_record_path = os.path.join(data_prep.tf_record_path, data_prep.dataset + ".tfrecord")
        params = toml.load("cell_classification/configs/params.toml")
        params["record_path"] = tf_record_path
        params["path"] = temp_dir
        params["experiment"] = "test"
        params["num_epochs"] = 2
        params["num_validation"] = 2
        params["batch_size"] = 2
        params["test"] = True
        params["weight_decay"] = 1e-4
        params["steps_per_epoch"] = 5000

        trainer = ModelBuilder(params)
        trainer.train()

        # check if loss_history is of type tf.keras.callbacks.History
        assert isinstance(trainer.loss_history, tf.keras.callbacks.History)

        # check if model is trained for correct number of epochs
        assert len(trainer.loss_history.history["loss"]) == params["num_epochs"]

        # check if loss history is written to file
        assert "tfevents" in os.listdir(os.path.join(trainer.params['log_dir'], "train"))[0]
        assert "tfevents" in os.listdir(os.path.join(trainer.params['log_dir'], "validation"))[0]

        # check if model checkpoint is written to file
        assert os.path.split(trainer.params['model_path'])[-1] in os.listdir(
            trainer.params['model_dir']
        )

        # check params.toml is dumped to file and contains the created paths
        assert "params.toml" in os.listdir(trainer.params['model_dir'])
        loaded_params = toml.load(os.path.join(trainer.params['model_dir'], "params.toml"))
        for key in ["model_dir", "log_dir", "model_path"]:
            assert key in list(loaded_params.keys())

        # check if model is saved to file
        assert os.path.split(trainer.params['model_path'])[-1] in os.listdir(
            trainer.params['model_dir']
        )

        # check if model can be loaded from file
        trainer.model = None
        trainer.load_model(trainer.params['model_path'])
        assert isinstance(trainer.model, tf.keras.Model)


def test_predict():
    with tempfile.TemporaryDirectory() as temp_dir:
        data_prep, _, _, _ = prep_object_and_inputs(temp_dir)
        data_prep.tf_record_path = temp_dir
        data_prep.make_tf_record()
        tf_record_path = os.path.join(data_prep.tf_record_path, data_prep.dataset + ".tfrecord")
        params = toml.load("cell_classification/configs/params.toml")
        params["record_path"] = tf_record_path
        params["path"] = temp_dir
        params["experiment"] = "test"
        params["num_epochs"] = 2
        params["num_validation"] = 2
        params["batch_size"] = 2
        params["test"] = True
        trainer = ModelBuilder(params)
        trainer.train()
        val_dset = trainer.validation_dataset.map(
            trainer.prep_batches, num_parallel_calls=tf.data.AUTOTUNE
        )
        val_batch = next(iter(val_dset))
        predictions = trainer.predict(val_batch[0])

        # check if predictions have the right shape, format and range
        assert predictions.shape == (2, 256, 256, 1)
        assert predictions.dtype == np.float32
        assert np.max(predictions) <= 1
        assert np.min(predictions) >= 0

        # check if predictions work for a single image
        predictions = trainer.predict(val_batch[0][0])
        assert predictions.shape == (1, 256, 256, 1)


def test_predict_dataset():
    with tempfile.TemporaryDirectory() as temp_dir:
        data_prep, _, _, _ = prep_object_and_inputs(temp_dir)
        data_prep.tf_record_path = temp_dir
        data_prep.make_tf_record()
        tf_record_path = os.path.join(data_prep.tf_record_path, data_prep.dataset + ".tfrecord")
        params = toml.load("cell_classification/configs/params.toml")
        params["record_path"] = tf_record_path
        params["path"] = temp_dir
        params["experiment"] = "test"
        params["num_epochs"] = 2
        params["num_validation"] = 2
        params["batch_size"] = 2
        trainer = ModelBuilder(params)
        trainer.train()
        val_dset = trainer.validation_dataset
        single_example_list = trainer.predict_dataset(val_dset)

        # check if predict returns a list with the right number of items
        assert len(single_example_list) == params["num_validation"]

        # check if params were saved to file
        assert "params.toml" in os.listdir(params["model_dir"])

        # check if examples get serialized correctly
        single_example_list = trainer.predict_dataset(val_dset, save_predictions=True)
        params = trainer.params
        for i in range(params["num_validation"]):
            assert str(i).zfill(4)+'_pred.hdf' in list(os.listdir(params['eval_dir']))

        with h5py.File(os.path.join(params['eval_dir'], str(0).zfill(4)+'_pred.hdf'), 'r') as f:
            assert f['prediction'].shape == (256, 256, 1)
            assert f['marker_activity_mask'].shape == (256, 256, 1)
            assert set(list(f.keys())) == set(list(single_example_list[0].keys()))


def test_add_weight_decay():
    with tempfile.TemporaryDirectory() as temp_dir:
        data_prep, _, _, _ = prep_object_and_inputs(temp_dir)
        data_prep.tf_record_path = temp_dir
        data_prep.make_tf_record()
        tf_record_path = os.path.join(data_prep.tf_record_path, data_prep.dataset + ".tfrecord")
        params = toml.load("cell_classification/configs/params.toml")
        params["record_path"] = tf_record_path
        params["path"] = temp_dir
        params["experiment"] = "test"
        params["num_epochs"] = 2
        params["num_validation"] = 2
        params["batch_size"] = 2
        params["test"] = True
        params["weight_decay"] = 1e-3

        trainer = ModelBuilder(params)
        trainer.prep_model()

        # check if weight decay is added to the model losses
        assert len(trainer.model.losses) > 1

        # check if loss is higher with weight decay than without weight decay
        trainer = ModelBuilder(params)
        trainer.prep_data()
        tf.random.set_seed(42)
        trainer.prep_model()
        loss_with_weight_decay = trainer.validate(trainer.validation_dataset)

        params["weight_decay"] = False
        trainer_no_decay = ModelBuilder(params)
        trainer_no_decay.prep_data()
        tf.random.set_seed(42)
        trainer_no_decay.prep_model()
        loss_without_weight_decay = trainer_no_decay.validate(trainer.validation_dataset)

        assert loss_with_weight_decay > loss_without_weight_decay

import numpy as np
from deepcell.applications import Application


def cell_preprocess(image, **kwargs):
    """Preprocess input data for CellClassification model.
    Args:
        image: array to be processed
    Returns:
        np.array: processed image array
    """
    if len(image.shape) != 4:
        raise ValueError("Image data must be 4D, got image of shape {}".format(image.shape))

    normalize = kwargs.get('normalize', True)
    marker = kwargs.get('marker')
    normalization_dict = kwargs.get('normalization_dict')
    if normalize:
        if marker in normalization_dict.keys():
            norm_factor = normalization_dict[marker]
        else:
            print("Norm_factor not found for marker {}".format(marker))
            norm_factor = np.quantile(image[..., 0], 0.999)
        image[..., 0] /= norm_factor
        image = image.clip(0, 1)
    return image


def cell_postprocess(model_output):
    return model_output


def format_output(model_output):
    return model_output[0]


class CellClassification(Application):
    """Cell Classification Application class for predicting marker activity for cells in multi-
    plexed images.
    """
    def __init__(self, model):
        """Initializes a CellClassification Application.
        Args:
            model (tensorflow.keras.Model): Model to load weights into.
        """
        super(CellClassification, self).__init__(
            model,
            model_image_shape=model.input_shape[1:],
            preprocessing_fn=cell_preprocess,
            postprocessing_fn=cell_postprocess,
            format_model_output_fn=format_output,
        )

    def predict(self, input_data, normalize=True, marker=None, normalization_dict=None):
        """Predicts cell classification for input data.
        Args:
            input_data (np.array): Input data to predict on.
            normalize (bool): Whether to normalize input data.
            marker (str): Name of marker to normalize.
            normalization_dict (dict): Dictionary of normalization factors.
        Returns:
            np.array: Predicted cell classification.
        """
        return self._predict_segmentation(input_data, preprocess_kwargs={
            'normalize': normalize, 'marker': marker, 'normalization_dict': normalization_dict
        })
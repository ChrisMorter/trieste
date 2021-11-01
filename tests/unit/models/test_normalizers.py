import pytest
import tensorflow as tf
import gpflow
from gpflow import default_float
from gpflow.models import GPR
from trieste.models.gpflow import GaussianProcessRegression
from trieste.models.normalization import DataTransformWrapper, transformers

from tests.util.trieste.utils.objectives import hartmann_6_dataset
from trieste.types import TensorType

# Verify that functions in transformed space and untransformed space are same.

@pytest.fixture
def random_data() -> TensorType:
    """Tensor of shape [10, 6] with data sampled uniformly at random in [-100, 100]."""
    return 200 * tf.random.uniform((10, 6), dtype=default_float()) - 50


@pytest.mark.parametrize('transformer_type', ['Identity', 'Standard', 'MinMax'])
def test_inverse_forward_transform(random_data: TensorType, transformer_type: str) -> None:
    transfomer_class = getattr(transformers, f'{transformer_type}Transformer')
    transformer = transfomer_class(data=random_data)
    identity_transformed_data = transformer.inverse_transform(
        transformer.transform(random_data)
    )
    tf.debugging.assert_near(random_data, identity_transformed_data)


@pytest.mark.parametrize('transformer_type', ['Identity', 'Standard', 'MinMax'])
def test_variance_inverse_forward_transform(
    random_data: TensorType, transformer_type: str
) -> None:
    transfomer_class = getattr(transformers, f'{transformer_type}Transformer')
    transformer = transfomer_class(data=random_data)
    variance = tf.math.reduce_variance(random_data, axis=0)
    identity_transformed_data = transformer.inverse_transform_variance(
        transformer.transform_variance(variance)
    )
    tf.debugging.assert_near(variance, identity_transformed_data)


def test_data_transformer_wrapper(random_data: TensorType) -> None:
    dataset = hartmann_6_dataset(num_query_points=10)
    random_data = (random_data + 50) / 200

    class NormalizedModel(DataTransformWrapper, GaussianProcessRegression):
        pass

    query_point_transformer = transformers.IdentityTransformer(dataset.query_points)
    observation_transformer = transformers.StandardTransformer(dataset.observations)

    model = GPR(dataset.astuple(), gpflow.kernels.Matern32(lengthscales=[1] * 6))
    model.likelihood.variance.assign(1e-5)
    
    normalized_model = NormalizedModel(
        dataset,
        model,
        query_point_transformer=query_point_transformer,
        observation_transformer=observation_transformer,
        update_parameters=True
    )

    tf.debugging.assert_near(
        tf.math.reduce_mean(normalized_model._model.data[1]), tf.constant(0, dtype=default_float())
    )
    tf.debugging.assert_near(
        tf.math.reduce_std(normalized_model._model.data[1]), tf.constant(1, dtype=default_float())
    )

    tf.debugging.assert_near(
        normalized_model.predict(dataset.query_points)[0], dataset.observations, rtol=1e-2
    )

    updated_dataset = dataset + hartmann_6_dataset(num_query_points=5)
    normalized_model.update(updated_dataset)

    tf.debugging.assert_near(
        tf.math.reduce_mean(normalized_model._model.data[1]), tf.constant(0, dtype=default_float())
    )
    tf.debugging.assert_near(
        tf.math.reduce_std(normalized_model._model.data[1]), tf.constant(1, dtype=default_float())
    )

    tf.debugging.assert_near(
        normalized_model.predict(updated_dataset.query_points)[0],
        updated_dataset.observations,
        rtol=1e-2
    )
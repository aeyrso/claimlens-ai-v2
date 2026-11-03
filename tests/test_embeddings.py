
"""
ClaimLens AI - Semantic embedding regression tests.

Validate E5 vector shapes, normalization, basic
semantic ranking, caching and input handling.
"""

import numpy as np
import pytest

from backend.retrieval.embeddings import (
    EMBEDDING_DIM,
    encode_texts,
    load_embedding_model,
)


@pytest.fixture(scope="module")
def semantic_vectors():
    """Generate embeddings once for the test module."""

    queries = [
        "On m'a vole ma bicyclette dans le garage collectif.",
        "Mon velo a ete vole sur la voie publique.",
    ]

    passages = [
        "Vol de v\u00e9lo en local commun.",
        "Vol de v\u00e9lo sur voie publique.",
        "D\u00e9g\u00e2t des eaux dans le logement.",
    ]

    query_vectors = encode_texts(
        queries,
        role="query",
        batch_size=1,
    )

    passage_vectors = encode_texts(
        passages,
        role="passage",
        batch_size=2,
    )

    return query_vectors, passage_vectors


def test_embedding_dimensions_and_normalization(
    semantic_vectors,
):
    """Embeddings must be finite normalized float32 vectors."""

    queries, passages = semantic_vectors

    assert queries.shape == (2, EMBEDDING_DIM)
    assert passages.shape == (3, EMBEDDING_DIM)

    assert queries.dtype == np.float32
    assert passages.dtype == np.float32

    assert np.isfinite(queries).all()
    assert np.isfinite(passages).all()

    assert np.allclose(
        np.linalg.norm(queries, axis=1),
        1.0,
        atol=1e-5,
    )

    assert np.allclose(
        np.linalg.norm(passages, axis=1),
        1.0,
        atol=1e-5,
    )


def test_semantic_ranking_distinguishes_locations(
    semantic_vectors,
):
    """Simple bicycle queries should favor the correct location."""

    queries, passages = semantic_vectors

    similarities = queries @ passages.T

    # Garage collectif -> local commun.
    assert similarities[0, 0] > similarities[0, 1]
    assert similarities[0, 0] > similarities[0, 2]

    # Voie publique -> voie publique.
    assert similarities[1, 1] > similarities[1, 0]
    assert similarities[1, 1] > similarities[1, 2]


def test_embedding_model_is_reused():
    """The same model instance must be cached."""

    first_tokenizer, first_model = load_embedding_model()
    second_tokenizer, second_model = load_embedding_model()

    assert first_tokenizer is second_tokenizer
    assert first_model is second_model

    assert not first_model.training


def test_embedding_input_validation():
    """Reject invalid inputs and handle an empty batch."""

    empty = encode_texts(
        [],
        role="passage",
    )

    assert empty.shape == (0, EMBEDDING_DIM)
    assert empty.dtype == np.float32

    with pytest.raises(ValueError):
        encode_texts(
            ["example"],
            role="invalid",
        )

    with pytest.raises(ValueError):
        encode_texts(
            ["example"],
            role="query",
            batch_size=0,
        )

    with pytest.raises(ValueError):
        encode_texts(
            ["example"],
            role="query",
            batch_size=True,
        )

    with pytest.raises(ValueError):
        encode_texts(
            "example",
            role="query",
        )

    with pytest.raises(ValueError):
        encode_texts(
            ["example", ""],
            role="passage",
        )

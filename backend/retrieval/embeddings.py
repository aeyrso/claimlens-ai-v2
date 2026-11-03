
"""
ClaimLens AI - Multilingual semantic embeddings.

Generate normalized E5 embeddings locally on CPU.

This module only creates vectors.
SQL document filtering remains the responsibility
of the retrieval layer.
"""

from functools import lru_cache
from typing import Literal

import numpy as np
import torch
import torch.nn.functional as F

from transformers import AutoModel, AutoTokenizer


MODEL_ID = "intfloat/multilingual-e5-small"
EMBEDDING_DIM = 384

EmbeddingRole = Literal["query", "passage"]


@lru_cache(maxsize=1)
def load_embedding_model():
    """
    Load the tokenizer and model only once.

    Use conservative CPU threading for Windows.
    """

    torch.set_num_threads(1)

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ID
    )

    model = AutoModel.from_pretrained(
        MODEL_ID
    )

    model.to("cpu")
    model.eval()

    return tokenizer, model


def encode_texts(
    texts: list[str],
    role: EmbeddingRole,
    batch_size: int = 16,
) -> np.ndarray:
    """
    Encode texts into normalized 384-dimensional vectors.

    E5 requires:
    - 'query:' for user questions
    - 'passage:' for documentary evidence

    Returns a float32 NumPy matrix of shape
    (number_of_texts, 384).
    """

    if role not in ("query", "passage"):
        raise ValueError(
            "Role must be 'query' or 'passage'"
        )

    if type(batch_size) is not int or batch_size < 1:
        raise ValueError(
            "Batch size must be a positive integer"
        )

    if not isinstance(texts, list):
        raise ValueError(
            "Texts must be provided as a list"
        )

    if any(
        not isinstance(text, str) or not text.strip()
        for text in texts
    ):
        raise ValueError(
            "Every text must be a non-empty string"
        )

    if not texts:
        return np.empty(
            (0, EMBEDDING_DIM),
            dtype=np.float32,
        )

    tokenizer, model = load_embedding_model()

    batches = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]

        prepared = [
            f"{role}: {text}"
            for text in batch
        ]

        encoded = tokenizer(
            prepared,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )

        with torch.inference_mode():
            outputs = model(**encoded)

            hidden = outputs.last_hidden_state

            mask = (
                encoded["attention_mask"]
                .unsqueeze(-1)
                .to(hidden.dtype)
            )

            pooled = (
                (hidden * mask).sum(dim=1)
                / mask.sum(dim=1).clamp(min=1)
            )

            normalized = F.normalize(
                pooled,
                p=2,
                dim=1,
            )

        vectors = normalized.cpu().numpy().astype(
            np.float32,
            copy=False,
        )

        if vectors.shape[1] != EMBEDDING_DIM:
            raise ValueError(
                f"Unexpected embedding dimension: "
                f"{vectors.shape[1]}"
            )

        batches.append(vectors)

    return np.concatenate(
        batches,
        axis=0,
    )

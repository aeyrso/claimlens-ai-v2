
"""
ClaimLens AI - Automated retrieval evaluation.

Evaluate expected evidence retrieval across
the synthetic insurance policy corpus.

These tests measure retrieval quality only.
They do not determine insurance coverage.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from backend.database.importer import import_synthetic_corpus
from backend.retrieval.hybrid import search_policy_hybrid


EVALUATION_DIRECTORY = Path("data/evaluation")

EVALUATION_FILES = (
    "retrieval_cases.json",
    "validation_cases.json",
)


def load_evaluation_cases():
    """Load both evaluation datasets as UTF-8 JSON."""

    cases = []

    for filename in EVALUATION_FILES:
        path = EVALUATION_DIRECTORY / filename

        data = json.loads(
            path.read_text(encoding="utf-8")
        )

        assert isinstance(data["cases"], list)

        cases.extend(data["cases"])

    return cases


@pytest.fixture(scope="module")
def evaluation_results():
    """
    Run hybrid retrieval once for all evaluation cases.

    Cache results for the evaluation tests.
    """

    cases = load_evaluation_cases()

    assert len(cases) == 24

    case_ids = [case["id"] for case in cases]

    assert len(case_ids) == len(set(case_ids))

    connection = sqlite3.connect(":memory:")

    results = {}

    try:
        import_synthetic_corpus(connection)

        for case in cases:
            targets = case["target_evidence_ids"]

            assert targets, (
                f"Missing targets for {case['id']}"
            )

            response = search_policy_hybrid(
                connection,
                case["policy_number"],
                case["query"],
                limit=50,
            )

            assert response["policy_found"] is True

            positions = {
                item["evidence_id"]: rank
                for rank, item in enumerate(
                    response["results"],
                    start=1,
                )
            }

            ranks = [
                positions.get(target)
                for target in targets
            ]

            results[case["id"]] = {
                "policy_number": case["policy_number"],
                "targets": targets,
                "ranks": ranks,
            }

    finally:
        connection.close()

    return results


def calculate_recall_at_k(results, k):
    """
    Calculate macro-average Recall@k.

    Each scenario contributes equally.
    """

    recalls = []

    for case in results.values():
        ranks = case["ranks"]

        retrieved = sum(
            rank is not None and rank <= k
            for rank in ranks
        )

        recalls.append(retrieved / len(ranks))

    return sum(recalls) / len(recalls)


def test_evaluation_corpus_contains_24_cases(
    evaluation_results,
):
    """Ensure both evaluation datasets are included."""

    assert len(evaluation_results) == 24


def test_recall_at_5_meets_baseline(
    evaluation_results,
):
    """Protect the expected Top-5 retrieval quality."""

    recall_at_5 = calculate_recall_at_k(
        evaluation_results,
        5,
    )

    assert recall_at_5 >= 0.97, (
        f"Recall@5 too low: {recall_at_5:.1%}"
    )


def test_recall_at_10_is_complete(
    evaluation_results,
):
    """All expected evidence must appear in the Top 10."""

    recall_at_10 = calculate_recall_at_k(
        evaluation_results,
        10,
    )

    missing = [
        (case_id, target, rank)
        for case_id, case in evaluation_results.items()
        for target, rank in zip(
            case["targets"],
            case["ranks"],
        )
        if rank is None or rank > 10
    ]

    assert recall_at_10 == 1.0, (
        f"Recall@10: {recall_at_10:.1%}; "
        f"missing evidence: {missing}"
    )


def test_garden_furniture_evidence_in_top_5(
    evaluation_results,
):
    """Protect the improvement to garden furniture."""

    case = evaluation_results["B_MOBILIER_JARDIN"]

    assert len(case["ranks"]) == 1

    rank = case["ranks"][0]

    assert rank is not None
    assert rank <= 5, (
        f"Garden furniture evidence ranked {rank}"
    )


def test_garden_furniture_evidence_in_top_3(
    evaluation_results,
):
    """
    The contractual garden furniture reference
    should appear among the first three results.

    This tests retrieval priority, not coverage.
    """

    case = evaluation_results["B_MOBILIER_JARDIN"]

    assert len(case["ranks"]) == 1

    rank = case["ranks"][0]

    assert rank is not None
    assert rank <= 3, (
        "Garden furniture reference should rank "
        f"in Top 3, but was ranked {rank}"
    )


def test_garden_claim_excludes_unrelated_bicycle_evidence():
    """
    Garden damage retrieval should not include
    unrelated bicycle or MOBILITE+ evidence
    in the displayed Top 10.
    """
    from backend.retrieval.search import normalize_phrase

    query = (
        "Une bougie était posée sur ma table de jardin, "
        "mais elle n'a pas fondu sous l'effet de la chaleur. "
        "La table a été cassée par un objet tombé dessus. "
        "Suis-je couvert ?"
    )

    connection = sqlite3.connect(":memory:")

    try:
        import_synthetic_corpus(connection)

        response = search_policy_hybrid(
            connection,
            "SIM-B-0002",
            query,
            limit=10,
        )
    finally:
        connection.close()

    unrelated = []

    for item in response["results"]:
        words = set(normalize_phrase(item["text"]).split())

    
        if (
            ("velo" in words or "mobilite" in words)
            and not ("jardin" in words or "table" in words)
        ):

            unrelated.append(
                {
                    "reference": item["document_reference"],
                    "evidence_id": item["evidence_id"],
                    "excerpt": item["text"][:100],
                }
            )

    assert not unrelated, (
        "Unrelated bicycle evidence in garden retrieval: "
        f"{unrelated}"
    )


"""
ClaimLens AI - FastAPI endpoint tests.

Verify:
- Health endpoint.
- Contractual evidence isolation.
- Input validation and boundary values.
- Controlled HTTP errors.
- Preservation of unverified information.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import backend.main as api_module
from backend.database import connection as db_module
from backend.database.connection import get_db
from backend.database.importer import import_synthetic_corpus
from backend.main import app


# --------------------------------------------------
# Reusable test fixtures
# --------------------------------------------------

@pytest.fixture
def client():
    """Provide a FastAPI test client."""

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client_with_corpus(client):
    """
    Provide an isolated in-memory synthetic database.

    Restore the original dependency configuration
    and close the database after each test.
    """

    db = sqlite3.connect(
        ":memory:",
        check_same_thread=False,
    )

    try:
        import_synthetic_corpus(db)

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            yield client
        finally:
            app.dependency_overrides.pop(get_db, None)

    finally:
        db.close()


# --------------------------------------------------
# Health endpoint
# --------------------------------------------------

def test_health_endpoint_returns_ok(client):
    """The health endpoint must respond successfully."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --------------------------------------------------
# Contractual evidence isolation
# --------------------------------------------------

def test_dossier_endpoint_only_returns_policy_documents(
    client_with_corpus,
):
    """Evidence must belong to the requested policy."""

    response = client_with_corpus.post(
        "/analysis/dossier",
        json={
            "policy_number": "SIM-B-0002",
            "query": "Ma table de jardin a ete endommagee.",
            "limit": 10,
        },
    )

    assert response.status_code == 200

    data = response.json()

    allowed_pdfs = {
        document["pdf_relative_path"]
        for document in data["documents"]
    }

    assert allowed_pdfs == {
        "contracts/contrat_B_mobilite_habitation.pdf",
        "policy_schedules/conditions_particulieres_B.pdf",
    }

    assert data["evidence"]

    assert all(
        evidence["source_pdf"] in allowed_pdfs
        for evidence in data["evidence"]
    )


# --------------------------------------------------
# Unknown policy handling
# --------------------------------------------------

def test_dossier_endpoint_returns_404_for_unknown_policy(
    client_with_corpus,
):
    """An unknown policy must not expose contractual data."""

    response = client_with_corpus.post(
        "/analysis/dossier",
        json={
            "policy_number": "SIM-X-9999",
            "query": "Mon velo a ete vole.",
            "limit": 10,
        },
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Policy not found",
    }


# --------------------------------------------------
# Invalid request validation
# --------------------------------------------------

@pytest.mark.parametrize(
    "invalid_fields",
    [
        pytest.param(
            {"policy_number": ""},
            id="empty-policy-number",
        ),
        pytest.param(
            {"policy_number": "   "},
            id="whitespace-policy-number",
        ),
        pytest.param(
            {"policy_number": "P" * 65},
            id="policy-number-too-long",
        ),
        pytest.param(
            {"policy_number": 123},
            id="numeric-policy-number",
        ),
        pytest.param(
            {"policy_number": None},
            id="null-policy-number",
        ),
        pytest.param(
            {"query": ""},
            id="empty-query",
        ),
        pytest.param(
            {"query": "   "},
            id="whitespace-query",
        ),
        pytest.param(
            {"query": "Q" * 1001},
            id="query-too-long",
        ),
        pytest.param(
            {"query": 42},
            id="numeric-query",
        ),
        pytest.param(
            {"query": None},
            id="null-query",
        ),
        pytest.param(
            {"limit": 0},
            id="limit-below-minimum",
        ),
        pytest.param(
            {"limit": 51},
            id="limit-above-maximum",
        ),
        pytest.param(
            {"limit": True},
            id="boolean-limit",
        ),
        pytest.param(
            {"limit": "10"},
            id="string-limit",
        ),
        pytest.param(
            {"limit": 1.5},
            id="fractional-limit",
        ),
        pytest.param(
            {"unexpected_field": "value"},
            id="unexpected-field",
        ),
    ],
)
def test_dossier_endpoint_rejects_invalid_requests(
    client,
    invalid_fields,
):
    """Invalid requests must receive HTTP 422."""

    payload = {
        "policy_number": "SIM-B-0002",
        "query": "Mon velo a ete vole.",
        "limit": 10,
    }

    payload.update(invalid_fields)

    # Input validation must not require a database.
    app.dependency_overrides[get_db] = lambda: None

    try:
        response = client.post(
            "/analysis/dossier",
            json=payload,
        )

    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    "missing_field",
    [
        "policy_number",
        "query",
    ],
)
def test_dossier_endpoint_rejects_missing_fields(
    client,
    missing_field,
):
    """Required request fields must not be omitted."""

    payload = {
        "policy_number": "SIM-B-0002",
        "query": "Mon velo a ete vole.",
        "limit": 10,
    }

    payload.pop(missing_field)

    app.dependency_overrides[get_db] = lambda: None

    try:
        response = client.post(
            "/analysis/dossier",
            json=payload,
        )

    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 422


# --------------------------------------------------
# Accepted boundary values
# --------------------------------------------------

@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        pytest.param(
            {
                "policy_number": "P" * 64,
                "query": "Q" * 1000,
                "limit": 1,
            },
            ("P" * 64, "Q" * 1000, 1),
            id="maximum-text-lengths",
        ),
        pytest.param(
            {
                "policy_number": "  SIM-B-0002  ",
                "query": "  Mon velo a ete vole.  ",
                "limit": 50,
            },
            (
                "SIM-B-0002",
                "Mon velo a ete vole.",
                50,
            ),
            id="whitespace-trimming-and-maximum-limit",
        ),
    ],
)
def test_dossier_endpoint_accepts_valid_boundaries(
    client,
    monkeypatch,
    payload,
    expected,
):
    """
    Valid boundary values must reach the dossier builder.

    Replace the builder so validation can be checked
    without running the retrieval pipeline.
    """

    received = []

    def fake_dossier_builder(
        connection,
        policy_number,
        query,
        *,
        limit,
    ):
        received.append(
            (policy_number, query, limit)
        )

        # Simulate an unknown policy after validation.
        return None

    monkeypatch.setattr(
        api_module,
        "build_contractual_evidence_dossier",
        fake_dossier_builder,
    )

    app.dependency_overrides[get_db] = lambda: None

    try:
        response = client.post(
            "/analysis/dossier",
            json=payload,
        )

    finally:
        app.dependency_overrides.pop(get_db, None)

    # 404 means validation was accepted and the
    # mocked dossier builder was called.
    assert response.status_code == 404
    assert received == [expected]


# --------------------------------------------------
# Database availability
# --------------------------------------------------

def test_dossier_endpoint_returns_503_when_database_missing(
    client,
    monkeypatch,
    tmp_path,
):
    """A missing database must return a controlled HTTP error."""

    missing_database = tmp_path / "missing.sqlite3"

    monkeypatch.setattr(
        db_module,
        "SQLITE_DB_PATH",
        missing_database,
    )

    response = client.post(
        "/analysis/dossier",
        json={
            "policy_number": "SIM-B-0002",
            "query": "Ma table de jardin a ete endommagee.",
            "limit": 10,
        },
    )

    assert response.status_code == 503

    assert response.json() == {
        "detail": "Database unavailable",
    }

    assert not missing_database.exists()


# --------------------------------------------------
# Unverified contractual information
# --------------------------------------------------

def test_dossier_endpoint_preserves_unverified_garage(
    client_with_corpus,
):
    """
    A garage collectif must not automatically
    be considered a covered local commun.
    """

    query = "Mon velo a ete vole dans un garage collectif."

    response = client_with_corpus.post(
        "/analysis/dossier",
        json={
            "policy_number": "SIM-B-0002",
            "query": query,
            "limit": 10,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["policy"]["policy_number"] == "SIM-B-0002"

    assert "garage collectif" in data["unverified_locations"]

    assert data["expanded_query"] == query
    assert data["applied_rules"] == []

    allowed_pdfs = {
        document["pdf_relative_path"]
        for document in data["documents"]
    }

    assert data["evidence"]

    assert all(
        evidence["source_pdf"] in allowed_pdfs
        for evidence in data["evidence"]
    )


"""
ClaimLens AI - Controlled query expansion tests.

Validate SQL document isolation, contractual provenance,
linguistic synonyms and unknown claim circumstances.

Verify contextual fire, glass and garden furniture
expansion, including protection against false positives.
"""

import sqlite3

import pytest

from backend.database.importer import import_synthetic_corpus
from backend.retrieval.query_expansion import expand_policy_query
from backend.retrieval.search import normalize_phrase


@pytest.fixture
def connection():
    """Create an isolated database for each test."""

    db = sqlite3.connect(":memory:")

    try:
        import_synthetic_corpus(db)
        yield db
    finally:
        db.close()


# --------------------------------------------------
# 1. Contractual equivalence and provenance
# --------------------------------------------------

def test_contractual_equivalence_has_provenance(connection):
    """Policy B can use its explicitly documented definition."""

    result = expand_policy_query(
        connection,
        "SIM-B-0002",
        "Ma bicyclette a disparu dans un local collectif.",
    )

    assert result["policy_found"] is True
    assert "velo" in result["expanded_query"]
    assert "local commun" in result["expanded_query"]

    contractual = [
        rule
        for rule in result["applied_rules"]
        if rule["type"] == "contractual"
    ]

    assert len(contractual) == 1

    source = contractual[0]["source"]

    assert source["source_pdf"] == (
        "contracts/contrat_B_mobilite_habitation.pdf"
    )
    assert source["page_number"] == 1
    assert source["locations"]
    assert source["document_reference"]

    normalized = normalize_phrase(source["text"])

    assert "local collectif" in normalized
    assert "local commun" in normalized


def test_contractual_equivalence_does_not_leak(connection):
    """Policy A must not inherit policy B's definitions."""

    result = expand_policy_query(
        connection,
        "SIM-A-0001",
        "Ma bicyclette a disparu dans un local collectif.",
    )

    assert result["policy_found"] is True
    assert result["expanded_query"].endswith(" velo")
    assert "local commun" not in result["expanded_query"]

    assert not any(
        rule["type"] == "contractual"
        for rule in result["applied_rules"]
    )


# --------------------------------------------------
# 2. Unknown or ambiguous locations
# --------------------------------------------------

def test_garage_collectif_remains_unverified(connection):
    """A garage must not be automatically classified."""

    result = expand_policy_query(
        connection,
        "SIM-B-0002",
        "On m'a pris ma bicyclette dans le garage collectif.",
    )

    assert result["unverified_locations"] == [
        "garage collectif"
    ]

    assert "velo" in result["expanded_query"]
    assert "local commun" not in result["expanded_query"]

    assert all(
        rule["type"] == "linguistic"
        for rule in result["applied_rules"]
    )


def test_trottoir_does_not_imply_public_road(connection):
    """A sidewalk does not automatically prove public-road status."""

    query = "Mon velo a ete vole sur le trottoir."

    result = expand_policy_query(
        connection,
        "SIM-B-0002",
        query,
    )

    assert result["expanded_query"] == query
    assert result["unverified_locations"] == ["trottoir"]
    assert "voie publique" not in result["expanded_query"]
    assert result["applied_rules"] == []


def test_unknown_location_is_preserved(connection):
    """Do not manufacture a theft location."""

    query = "Mon velo a disparu, je ne sais pas ou."

    result = expand_policy_query(
        connection,
        "SIM-B-0002",
        query,
    )

    assert result["expanded_query"] == query
    assert result["applied_rules"] == []
    assert result["unverified_locations"] == []


# --------------------------------------------------
# 3. Unknown policy and invalid queries
# --------------------------------------------------

def test_unknown_policy_cannot_expand(connection):
    """Unknown policies provide no contractual authorization."""

    query = "Ma bicyclette a disparu dans un local collectif."

    result = expand_policy_query(
        connection,
        "POLICE-INCONNUE",
        query,
    )

    assert result["policy_found"] is False
    assert result["expanded_query"] == query
    assert result["applied_rules"] == []
    assert result["unverified_locations"] == []


@pytest.mark.parametrize(
    "query",
    ["", "   ", None],
)
def test_invalid_queries_are_rejected(connection, query):
    """Reject missing or empty questions."""

    with pytest.raises(ValueError):
        expand_policy_query(
            connection,
            "SIM-B-0002",
            query,
        )


# --------------------------------------------------
# 4. Contextual fire synonym
# --------------------------------------------------

@pytest.mark.parametrize(
    ("query", "expected_expansion"),
    [
        (
            "Un feu a cause des dommages dans mon logement.",
            True,
        ),
        (
            "Le feu a endommage mon appartement.",
            True,
        ),
        (
            "Le feu de circulation etait rouge.",
            False,
        ),
        (
            (
                "Le feu de circulation est rouge. "
                "Des dommages ont ete signales dans mon logement."
            ),
            False,
        ),
        (
            "Un incendie a cause des dommages dans mon logement.",
            False,
        ),
        (
            "Mon velo a disparu.",
            False,
        ),
    ],
)
def test_fire_synonym_requires_residential_damage_context(
    connection,
    query,
    expected_expansion,
):
    """Do not confuse residential fire with unrelated uses of feu."""

    result = expand_policy_query(
        connection,
        "SIM-C-0003",
        query,
    )

    fire_rules = [
        rule
        for rule in result["applied_rules"]
        if (
            rule["type"] == "linguistic"
            and rule["from"] == "feu"
            and rule["to"] == "incendie"
        )
    ]

    assert bool(fire_rules) is expected_expansion

    if expected_expansion:
        assert result["expanded_query"].endswith(
            " incendie"
        )
        assert len(fire_rules) == 1
        assert fire_rules[0]["source"] is None
    else:
        assert result["expanded_query"] == query


def test_fire_synonym_respects_unknown_policy(connection):
    """An unknown policy must not trigger query expansion."""

    query = "Un feu a cause des dommages dans mon logement."

    result = expand_policy_query(
        connection,
        "POLICE-INCONNUE",
        query,
    )

    assert result["policy_found"] is False
    assert result["expanded_query"] == query
    assert result["applied_rules"] == []


# --------------------------------------------------
# 5. Bay window and glass damage
# --------------------------------------------------

@pytest.mark.parametrize(
    ("query", "expected_expansion"),
    [
        (
            (
                "Ma baie vitree a eclate apres avoir "
                "ete heurtee par un objet."
            ),
            True,
        ),
        (
            "Ma baie vitree est fissuree a la suite d'un choc.",
            True,
        ),
        (
            "La baie vitree de ma cuisine s'est brisee.",
            True,
        ),
        (
            "Ma baie vitree est intacte.",
            False,
        ),
        (
            (
                "Un verre a eclate. "
                "Ma baie vitree est intacte."
            ),
            False,
        ),
        (
            "Mon velo a ete vole devant une baie vitree.",
            False,
        ),
        (
            "Ma baie vitree n'a pas eclate.",
            False,
        ),
    ],
)
def test_bay_window_damage_expansion(
    connection,
    query,
    expected_expansion,
):
    """
    Expand damaged bay-window descriptions to 'bris de glace'.

    Do not invent glass damage when the window is intact,
    merely mentioned, or explicitly described as undamaged.
    """

    result = expand_policy_query(
        connection,
        "SIM-C-0003",
        query,
    )

    glass_rules = [
        rule
        for rule in result["applied_rules"]
        if (
            rule["type"] == "linguistic"
            and rule["from"] == "baie vitree endommagee"
            and rule["to"] == "bris de glace"
        )
    ]

    assert bool(glass_rules) is expected_expansion

    if expected_expansion:
        assert result["expanded_query"].endswith(
            " bris de glace"
        )
        assert len(glass_rules) == 1
        assert glass_rules[0]["source"] is None
    else:
        assert result["expanded_query"] == query


def test_glass_expansion_respects_unknown_policy(connection):
    """An unknown policy cannot trigger glass query expansion."""

    query = "Ma baie vitree a eclate."

    result = expand_policy_query(
        connection,
        "POLICE-INCONNUE",
        query,
    )

    assert result["policy_found"] is False
    assert result["expanded_query"] == query
    assert result["applied_rules"] == []


# --------------------------------------------------
# 6. Garden table and garden furniture
# --------------------------------------------------

@pytest.mark.parametrize(
    ("query", "expected_expansion"),
    [
        (
            "Ma table de jardin a ete endommagee.",
            True,
        ),
        (
            "La table de jardin est cassee.",
            True,
        ),
        (
            "Ma table de jardin a subi des dommages.",
            True,
        ),
        (
            "La table de jardin s'est brisee.",
            True,
        ),
        (
            "Ma table de jardin est intacte.",
            False,
        ),
        (
            "Ma table de jardin n'est pas endommagee.",
            False,
        ),
        (
            "Ma table de jardin n'a pas ete cassee.",
            False,
        ),
        (
            (
                "Une fenetre est brisee. "
                "Ma table de jardin est intacte."
            ),
            False,
        ),
        (
            "Mon velo a ete vole devant ma table de jardin.",
            False,
        ),
    ],
)
def test_garden_table_damage_expansion(
    connection,
    query,
    expected_expansion,
):
    """
    Link a damaged garden table to garden furniture.

    Do not infer damage from a simple mention,
    an intact object or an explicitly negated event.
    """

    result = expand_policy_query(
        connection,
        "SIM-B-0002",
        query,
    )

    garden_rules = [
        rule
        for rule in result["applied_rules"]
        if (
            rule["type"] == "linguistic"
            and rule["from"] == "table de jardin endommagee"
            and rule["to"] == "mobilier de jardin"
        )
    ]

    assert bool(garden_rules) is expected_expansion

    if expected_expansion:
        assert result["expanded_query"].endswith(
            " mobilier de jardin"
        )
        assert len(garden_rules) == 1
        assert garden_rules[0]["source"] is None
    else:
        assert result["expanded_query"] == query


def test_garden_expansion_respects_unknown_policy(connection):
    """An unknown policy must not trigger garden expansion."""

    query = "Ma table de jardin a ete endommagee."

    result = expand_policy_query(
        connection,
        "POLICE-INCONNUE",
        query,
    )

    assert result["policy_found"] is False
    assert result["expanded_query"] == query
    assert result["applied_rules"] == []


# --------------------------------------------------
# 7. Garden furniture false-positive regression tests
# --------------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "Ma table de jardin n'a jamais ete endommagee.",
        "La fenetre est brisee pres de ma table de jardin.",
    ],
)
def test_garden_expansion_rejects_false_positives(
    connection,
    query,
):
    """
    Garden furniture expansion must not trigger
    when damage is negated or concerns another object.
    """

    result = expand_policy_query(
        connection,
        "SIM-B-0002",
        query,
    )

    assert result["policy_found"] is True
    assert result["expanded_query"] == query

    assert not any(
        rule["type"] == "linguistic"
        and rule["from"] == "table de jardin endommagee"
        and rule["to"] == "mobilier de jardin"
        for rule in result["applied_rules"]
    )

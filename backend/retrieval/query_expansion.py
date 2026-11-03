
"""
ClaimLens AI - Controlled query expansion.

Expand search terminology without inventing claim facts.

Contractual equivalences must be verified in the
SQL-authorized documents before being applied.
"""

import sqlite3

from backend.database.queries import get_policy_context
from backend.retrieval.search import (
    load_authorized_export,
    normalize_phrase,
)


LOCAL_EQUIVALENCE = (
    "les termes local collectif et local commun "
    "designent ici le meme espace"
)


def contains_phrase(text: str, phrase: str) -> bool:
    """Match complete normalized words or expressions."""

    normalized = normalize_phrase(text)
    expected = normalize_phrase(phrase)

    return f" {expected} " in f" {normalized} "


def find_local_equivalence(
    authorized_documents: list[dict],
) -> dict | None:
    """
    Find explicit contractual proof that local collectif
    and local commun are equivalent.

    Only inspect SQL-authorized documents.
    """

    for document in authorized_documents:
        source_pdf = document["pdf_relative_path"]

        data = load_authorized_export(source_pdf)

        for element in data["text_elements"]:
            normalized = normalize_phrase(
                element["text"]
            )

            if LOCAL_EQUIVALENCE not in normalized:
                continue

            locations = element["locations"]

            if not locations:
                raise ValueError(
                    "Contractual definition has no provenance"
                )

            return {
                "source_pdf": source_pdf,
                "document_reference": document[
                    "document_reference"
                ],
                "evidence_id": element["element_id"],
                "page_number": locations[0]["page_number"],
                "locations": locations,
                "text": element["text"],
            }

    return None


def expand_policy_query(
    connection: sqlite3.Connection,
    policy_number: str,
    query: str,
) -> dict:
    """
    Produce a search-only expanded query.

    Rules:
    - Bicyclette -> velo: linguistic synonym.
    - Feu -> incendie: residential damage context.
    - Damaged baie vitree -> bris de glace.
    - Damaged table de jardin -> mobilier de jardin.
    - Local collectif -> local commun: only with
      contractual evidence from authorized documents.
    - Garage collectif and trottoir remain unverified.

    Query expansion never establishes coverage.
    """

    if not isinstance(query, str) or not query.strip():
        raise ValueError(
            "Search query cannot be empty"
        )

    # SQL-first: authorization before expansion.
    context = get_policy_context(
        connection,
        policy_number,
    )

    result = {
        "policy_found": context is not None,
        "original_query": query,
        "expanded_query": query,
        "applied_rules": [],
        "unverified_locations": [],
    }

    if context is None:
        return result

    additions = []

    # Reuse sentence segmentation for contextual rules.
    sentences = (
        query.replace("!", ".")
        .replace("?", ".")
        .split(".")
    )

    # --------------------------------------------------
    # 1. Linguistic synonym: bicyclette -> velo
    # --------------------------------------------------

    if (
        contains_phrase(query, "bicyclette")
        and not contains_phrase(query, "velo")
    ):
        additions.append("velo")

        result["applied_rules"].append(
            {
                "type": "linguistic",
                "from": "bicyclette",
                "to": "velo",
                "source": None,
            }
        )

    # --------------------------------------------------
    # 2. Contextual synonym: feu -> incendie
    # --------------------------------------------------

    # Search expansion only.
    # This does not establish claim facts.

    residential_terms = (
        "logement",
        "appartement",
        "maison",
        "habitation",
    )

    damage_terms = (
        "dommage",
        "dommages",
        "degat",
        "degats",
        "endommage",
        "brule",
        "brulee",
        "detruit",
    )

    fire_in_residential_context = any(
        contains_phrase(sentence, "feu")
        and not contains_phrase(
            sentence,
            "feu de circulation",
        )
        and not contains_phrase(
            sentence,
            "feu rouge",
        )
        and any(
            contains_phrase(sentence, term)
            for term in residential_terms
        )
        and any(
            contains_phrase(sentence, term)
            for term in damage_terms
        )
        for sentence in sentences
    )

    if (
        fire_in_residential_context
        and not contains_phrase(query, "incendie")
    ):
        additions.append("incendie")

        result["applied_rules"].append(
            {
                "type": "linguistic",
                "from": "feu",
                "to": "incendie",
                "source": None,
            }
        )

    # --------------------------------------------------
    # 3. Contextual synonym:
    #    damaged baie vitree -> bris de glace
    # --------------------------------------------------

    # These words describe possible glass damage.
    # They must appear in a sentence mentioning
    # a bay window.

    bay_damage_terms = (
        "eclate",
        "eclatee",
        "fissure",
        "fissuree",
        "brise",
        "brisee",
        "casse",
        "cassee",
        "endommage",
        "endommagee",
    )

    # Conservative exclusions for explicit absence
    # of damage or negated damage descriptions.

    bay_negative_terms = (
        "intact",
        "intacte",
        "n a pas eclate",
        "n a pas eclatee",
        "n est pas fissuree",
        "n est pas brisee",
        "n est pas cassee",
        "n a pas ete endommagee",
        "pas endommagee",
        "aucun dommage",
        "sans dommage",
        "pas de degat",
    )

    bay_window_damage_detected = any(
        contains_phrase(sentence, "baie vitree")
        and any(
            contains_phrase(sentence, term)
            for term in bay_damage_terms
        )
        and not any(
            contains_phrase(sentence, negative)
            for negative in bay_negative_terms
        )
        for sentence in sentences
    )

    if (
        bay_window_damage_detected
        and not contains_phrase(query, "bris de glace")
    ):
        additions.append("bris de glace")

        result["applied_rules"].append(
            {
                "type": "linguistic",
                "from": "baie vitree endommagee",
                "to": "bris de glace",
                "source": None,
            }
        )

   
    # --------------------------------------------------
    # 3b. Contextual synonym:
    #     damaged garden table -> garden furniture
    # --------------------------------------------------

    # Expand only when an affirmative damage expression
    # directly describes the garden table.
    #
    # This prevents:
    # - explicit negations such as "n'a jamais ete"
    # - damage to another object near the garden table
    #
    # Conservative matching: unsupported formulations
    # are deliberately left unchanged.

    garden_damage_predicates = (
        "a ete endommagee",
        "a ete endommage",
        "est endommagee",
        "est endommage",
        "est cassee",
        "est casse",
        "s est cassee",
        "s est casse",
        "est brisee",
        "est brise",
        "s est brisee",
        "s est brise",
        "est fissuree",
        "est fissure",
        "a subi des dommages",
        "a subi un dommage",
        "a subi des degats",
        "a subi un degat",
    )

    garden_table_damage_detected = any(
        contains_phrase(
            sentence,
            f"table de jardin {predicate}",
        )
        for sentence in sentences
        for predicate in garden_damage_predicates
    )

    if (
        garden_table_damage_detected
        and not contains_phrase(query, "mobilier de jardin")
    ):
        additions.append("mobilier de jardin")

        result["applied_rules"].append(
            {
                "type": "linguistic",
                "from": "table de jardin endommagee",
                "to": "mobilier de jardin",
                "source": None,
            }
        )


    # --------------------------------------------------
    # 4. Contractual equivalence:
    #    local collectif -> local commun
    # --------------------------------------------------

    # An equivalence is accepted only after locating
    # its exact evidence in authorized documents.

    if (
        contains_phrase(query, "local collectif")
        and not contains_phrase(query, "local commun")
    ):
        definition = find_local_equivalence(
            context["documents"]
        )

        if definition is not None:
            additions.append("local commun")

            result["applied_rules"].append(
                {
                    "type": "contractual",
                    "from": "local collectif",
                    "to": "local commun",
                    "source": definition,
                }
            )

    # --------------------------------------------------
    # 5. Locations requiring clarification
    # --------------------------------------------------

    # These expressions do not establish a contractual
    # location category by themselves.

    for expression in (
        "garage collectif",
        "trottoir",
    ):
        if contains_phrase(query, expression):
            result["unverified_locations"].append(
                expression
            )

    # --------------------------------------------------
    # 6. Build the expanded search query
    # --------------------------------------------------

    if additions:
        result["expanded_query"] = (
            query + " " + " ".join(additions)
        )

    return result

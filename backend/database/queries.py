
"""
ClaimLens AI - SQL-first policy queries.

Retrieve an insurance policy, its associated documents,
and its coverage subscriptions before RAG retrieval.

Security principles:
- Parameterized SQL queries.
- Strict policy-level document isolation.
- Validation of contractual evidence provenance.
- Fail-closed behavior for inconsistent document links.
- Explicit validation of coverage subscription values.

Policy scoping does not authenticate API users.
"""

import sqlite3


EXPECTED_DOCUMENT_KINDS = frozenset(
    {
        "GENERAL_CONDITIONS",
        "POLICY_SCHEDULE",
    }
)


def get_policy_context(
    connection: sqlite3.Connection,
    policy_number: str,
) -> dict | None:
    """
    Retrieve the contractual context of one policy.

    Return None when the policy does not exist.

    Raise ValueError when stored documentary
    relationships or subscription values are invalid.

    This function retrieves contractual evidence.
    It does not determine whether a claim is covered.
    """

    # --------------------------------------------------
    # 1. Validate the requested policy number
    # --------------------------------------------------

    if not isinstance(policy_number, str):
        raise ValueError(
            "Policy number must be a string"
        )

    policy_number = policy_number.strip()

    if not policy_number:
        raise ValueError(
            "Policy number cannot be empty"
        )

    # --------------------------------------------------
    # 2. Retrieve the requested policy
    # --------------------------------------------------

    policy_cursor = connection.execute(
        """
        SELECT
            policy_number,
            holder_reference,
            product_name,
            plan_name,
            valid_from,
            valid_to
        FROM policies
        WHERE policy_number = ?
        """,
        (policy_number,),
    )

    policy_row = policy_cursor.fetchone()

    if policy_row is None:
        return None

    policy_columns = [
        column[0]
        for column in policy_cursor.description
    ]

    policy = dict(
        zip(
            policy_columns,
            policy_row,
            strict=True,
        )
    )

    # --------------------------------------------------
    # 3. Retrieve documents belonging to this policy
    # --------------------------------------------------

    documents_cursor = connection.execute(
        """
        SELECT
            document_kind,
            document_reference,
            pdf_relative_path
        FROM policy_documents
        WHERE policy_number = ?
        ORDER BY document_kind
        """,
        (policy_number,),
    )

    document_columns = [
        column[0]
        for column in documents_cursor.description
    ]

    documents = [
        dict(
            zip(
                document_columns,
                row,
                strict=True,
            )
        )
        for row in documents_cursor.fetchall()
    ]

    document_kinds = {
        document["document_kind"]
        for document in documents
    }

    # Require exactly one general-conditions document
    # and exactly one policy-schedule document.
    if (
        document_kinds != EXPECTED_DOCUMENT_KINDS
        or len(documents) != 2
    ):
        raise ValueError(
            "Incomplete or inconsistent document pair "
            f"for policy {policy_number}"
        )

    # --------------------------------------------------
    # 4. Retrieve coverage subscriptions and sources
    # --------------------------------------------------

    coverages_cursor = connection.execute(
        """
        SELECT
            c.coverage_label,
            c.is_subscribed,
            c.source_status,
            c.observation,
            d.document_reference,
            d.pdf_relative_path,
            d.document_kind AS source_document_kind
        FROM policy_coverages AS c
        LEFT JOIN policy_documents AS d
            ON d.id = c.source_document_id
            AND d.policy_number = c.policy_number
        WHERE c.policy_number = ?
        ORDER BY c.coverage_label
        """,
        (policy_number,),
    )

    coverage_columns = [
        column[0]
        for column in coverages_cursor.description
    ]

    coverages = []

    for row in coverages_cursor.fetchall():
        coverage = dict(
            zip(
                coverage_columns,
                row,
                strict=True,
            )
        )

        # The source must be the policy schedule
        # belonging to the requested policy.
        #
        # A LEFT JOIN makes missing or mismatched
        # document references visible as NULL values,
        # instead of silently discarding those rows.
        source_kind = coverage.pop(
            "source_document_kind"
        )

        if source_kind != "POLICY_SCHEDULE":
            raise ValueError(
                "Invalid coverage source document "
                f"for policy {policy_number}"
            )

        # SQLite represents boolean subscriptions
        # as integers. Reject invalid values instead
        # of silently converting them with bool().
        subscription_value = coverage["is_subscribed"]

        if (
            type(subscription_value) is not int
            or subscription_value not in (0, 1)
        ):
            raise ValueError(
                "Invalid coverage subscription value "
                f"for policy {policy_number}"
            )

        coverage["is_subscribed"] = bool(
            subscription_value
        )

        coverages.append(coverage)

    # --------------------------------------------------
    # 5. Return the policy-scoped contractual context
    # --------------------------------------------------

    return {
        "policy": policy,
        "documents": documents,
        "coverages": coverages,
    }

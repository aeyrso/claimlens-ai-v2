
"""
ClaimLens AI - Structured evidence schemas.

Define the data structures used to represent
retrieved contractual evidence and PDF provenance.

These schemas validate data structures only.
They do not determine insurance coverage.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat


class EvidenceLocation(BaseModel):
    """
    Location of evidence within a PDF page.

    Coordinates originate from Docling.
    """

    model_config = ConfigDict(extra="allow")

    page_number: int = Field(ge=1)

    bbox: tuple[
        FiniteFloat,
        FiniteFloat,
        FiniteFloat,
        FiniteFloat,
    ]

    coord_origin: Literal[
        "TOPLEFT",
        "BOTTOMLEFT",
    ]

    column_index: int | None = None


class EvidenceCell(BaseModel):
    """
    A cell extracted from a contractual PDF table.

    Preserve the cell value, column heading,
    and original PDF location.
    """

    model_config = ConfigDict(extra="allow")

    column_header: str

    value: str

    location: EvidenceLocation


class RetrievedEvidence(BaseModel):
    """
    One evidence item returned by hybrid retrieval.

    Preserve source identity, textual content,
    PDF provenance and retrieval metadata.

    Retrieval scores are not coverage probabilities.
    """

    model_config = ConfigDict(extra="allow")

    # Documentary identity
    evidence_id: str
    source_pdf: str
    document_reference: str

    # Evidence content
    evidence_type: str
    text: str
    page_number: int = Field(ge=1)

    # PDF provenance
    locations: list[EvidenceLocation] = Field(
        default_factory=list
    )

    cells: list[EvidenceCell] = Field(
        default_factory=list
    )

    # Retrieval scores
    # Reject NaN and infinite values.
    score: float = Field(
        allow_inf_nan=False
    )

    hybrid_score: float = Field(
        allow_inf_nan=False
    )

    lexical_score: float | None = Field(
        default=None,
        allow_inf_nan=False,
    )

    semantic_score: float | None = Field(
        default=None,
        allow_inf_nan=False,
    )

    # Positions in the original rankings
    lexical_rank: int | None = Field(
        default=None,
        ge=1,
    )

    semantic_rank: int | None = Field(
        default=None,
        ge=1,
    )

    # Terms matched during lexical retrieval
    matched_terms: list[str] = Field(
        default_factory=list
    )


# --------------------------------------------------
# 4. Insurance policy metadata
# --------------------------------------------------

class PolicyMetadata(BaseModel):
    """
    Metadata of the insurance policy retrieved
    from the SQL database.

    These fields describe the policy.
    They do not establish claim coverage.
    """

    model_config = ConfigDict(extra="forbid")

    policy_number: str = Field(min_length=1)
    holder_reference: str
    product_name: str
    plan_name: str
    valid_from: str
    valid_to: str


# --------------------------------------------------
# 5. SQL-authorized contractual document
# --------------------------------------------------

class AuthorizedDocument(BaseModel):
    """
    A document linked to the selected policy.

    Authorization must be established by
    get_policy_context before dossier creation.
    """

    model_config = ConfigDict(extra="forbid")

    document_kind: Literal[
        "GENERAL_CONDITIONS",
        "POLICY_SCHEDULE",
    ]

    document_reference: str = Field(min_length=1)
    pdf_relative_path: str = Field(min_length=1)


# --------------------------------------------------
# 6. Insurance coverage subscription
# --------------------------------------------------

class CoverageSubscription(BaseModel):
    """
    A coverage subscription recorded in SQLite.

    Subscription status is not a claim decision.
    Exclusions and contractual conditions must
    be evaluated separately.
    """

    model_config = ConfigDict(extra="forbid")

    coverage_label: str = Field(min_length=1)
    is_subscribed: bool
    source_status: str

    observation: str | None = None

    document_reference: str = Field(min_length=1)
    pdf_relative_path: str = Field(min_length=1)


# --------------------------------------------------
# 7. Structured contractual evidence dossier
# --------------------------------------------------

class ContractualEvidenceDossier(BaseModel):
    """
    Structured evidence dossier for one policy.

    Combines:
    - SQL policy metadata
    - Authorized documents
    - Coverage subscription records
    - Retrieved PDF evidence
    - Query expansion information
    - Unverified location descriptions

    This model organizes evidence only.

    It does not:
    - determine insurance coverage
    - calculate indemnification
    - assign claim approval probabilities

    Document authorization must be verified
    before the dossier is constructed.
    """

    model_config = ConfigDict(extra="forbid")

    # SQL policy context
    policy: PolicyMetadata

    documents: list[AuthorizedDocument] = Field(
        min_length=2,
        max_length=2,
    )

    coverages: list[CoverageSubscription] = Field(
        default_factory=list
    )

    # Claim description and controlled expansion
    original_query: str = Field(min_length=1)
    expanded_query: str = Field(min_length=1)

    applied_rules: list[dict] = Field(
        default_factory=list
    )

    unverified_locations: list[str] = Field(
        default_factory=list
    )

    # Ranked evidence with PDF provenance
    evidence: list[RetrievedEvidence] = Field(
        default_factory=list
    )


"""
ClaimLens AI - FastAPI application.

Local API for synthetic insurance contract analysis.

Security scope:
- Validated and bounded request inputs.
- Structured API responses.
- SQL-scoped contractual evidence retrieval.
- Intended for local, trusted demonstration only.

This application does not implement user authentication.
It must not be exposed publicly without additional
security controls.
"""

import sqlite3
from typing import Annotated
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    status,
    Response,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

from backend.analysis.coverage import (
    build_contractual_evidence_dossier,
)
from backend.database.connection import get_db
from backend.schemas import ContractualEvidenceDossier
from backend.analysis.decision import DecisionResult, evaluate_claim
from backend.config import PROJECT_ROOT


# --------------------------------------------------
# Application configuration
# --------------------------------------------------

app = FastAPI(
    title="ClaimLens AI",
    description=(
        "API de démonstration pour l'analyse "
        "de contrats d'assurance synthétiques, "
        "avec recherche de preuves documentaires "
        "et citations vérifiables."
    ),
    version="0.1.0",
    debug=False,
)


# --------------------------------------------------
# Input validation
# --------------------------------------------------

PolicyNumber = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=64,
    ),
]


QueryText = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=1000,
    ),
]


class DossierRequest(BaseModel):
    """
    Validated input for contractual evidence analysis.

    Constraints:
    - Policy number: 1 to 64 characters.
    - Query: 1 to 1000 characters.
    - Result limit: integer between 1 and 50.
    - Unexpected request fields are rejected.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    policy_number: PolicyNumber
    query: QueryText

    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        strict=True,
    )


# --------------------------------------------------
# Health endpoint
# --------------------------------------------------

@app.get(
    "/health",
    tags=["system"],
)
def healthcheck() -> dict[str, str]:
    """
    Report whether the API process is responding.

    This endpoint does not verify database
    or embedding-model availability.
    """

    return {"status": "ok"}


# --------------------------------------------------
# Contractual evidence analysis
# --------------------------------------------------

@app.post(
    "/analysis/dossier",
    response_model=ContractualEvidenceDossier,
    tags=["analysis"],
)
def analyze_contract(
    request: DossierRequest,
    connection: sqlite3.Connection = Depends(get_db),
) -> ContractualEvidenceDossier:
    """
    Retrieve contractual evidence for one synthetic policy.

    The dossier builder is responsible for:
    - SQL-based policy and document scoping.
    - Retrieval of relevant contractual evidence.
    - Evidence provenance and consistency checks.

    SQL-based document scoping is not equivalent
    to authenticating an API user.
    """

    dossier = build_contractual_evidence_dossier(
        connection,
        request.policy_number,
        request.query,
        limit=request.limit,
    )

    if dossier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )

    return dossier


# --------------------------------------------------
# V2 - Explainable indicative assessment
# --------------------------------------------------


class DecisionResponse(BaseModel):
    dossier: ContractualEvidenceDossier
    decision: DecisionResult


@app.post(
    "/analysis/decision",
    response_model=DecisionResponse,
    tags=["analysis"],
)
def analyze_decision(
    request: DossierRequest,
    connection: sqlite3.Connection = Depends(get_db),
) -> DecisionResponse:
    """Return an auditable, conservative assessment plus the source dossier."""
    dossier = build_contractual_evidence_dossier(
        connection, request.policy_number, request.query, limit=request.limit
    )
    if dossier is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return DecisionResponse(dossier=dossier, decision=evaluate_claim(dossier))


class PreviewRequest(DossierRequest):
    evidence_id: str = Field(min_length=1, max_length=256)


@app.post("/analysis/preview", tags=["analysis"], response_class=Response)
def preview_evidence(
    request: PreviewRequest,
    connection: sqlite3.Connection = Depends(get_db),
) -> Response:
    """Render only an evidence location re-verified from SQL-scoped retrieval.

    Never trusts source PDF paths or rectangles provided by the browser.
    """
    from backend.analysis.pdf_preview import render_authorized_evidence_page
    dossier = build_contractual_evidence_dossier(
        connection, request.policy_number, request.query, limit=request.limit
    )
    if dossier is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    matches = [e for e in dossier.evidence if e.evidence_id == request.evidence_id]
    if len(matches) != 1:
        raise HTTPException(status_code=404, detail="Evidence not found in authorized results")
    evidence = matches[0]
    if not evidence.locations:
        raise HTTPException(status_code=422, detail="Evidence has no PDF location")
    locations = [loc for loc in evidence.locations if loc.page_number == evidence.page_number]
    if not locations:
        raise HTTPException(status_code=422, detail="Evidence has no matching page coordinates")
    try:
        content = render_authorized_evidence_page(
            evidence.source_pdf,
            evidence.document_reference,
            evidence.page_number,
            locations,
            dossier.documents,
        )
    except (OSError, ValueError, RuntimeError, FileNotFoundError):
        raise HTTPException(status_code=422, detail="Could not render authorized evidence") from None
    return Response(content=content, media_type="image/png", headers={"Cache-Control": "no-store"})


# Serve the optional production-built frontend from the same origin.
# The Vite development server proxies requests to this API instead.
web_dist = PROJECT_ROOT / "frontend-web" / "dist"
if web_dist.is_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="web")

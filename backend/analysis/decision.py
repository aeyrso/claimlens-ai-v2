"""Traceable, conservative insurance-rule demonstrator for the synthetic corpus.

Important: this is NOT a legal coverage determination. Conditions are manually
curated from versioned synthetic PDFs; unknown document editions fail closed.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import pymupdf
from pydantic import BaseModel, ConfigDict, Field

from backend.config import PROJECT_ROOT
from backend.schemas import ContractualEvidenceDossier


class DecisionCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_reference: str
    document_kind: Literal["GENERAL_CONDITIONS", "POLICY_SCHEDULE"]
    source_pdf: str
    page_number: int = Field(ge=1)
    clause: str
    excerpt: str


class DecisionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["covered", "not_covered", "undetermined"]
    scenario: Literal["bike_theft", "candle_damage", "other"]
    title: str
    explanation: str
    established_facts: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    citations: list[DecisionCitation] = Field(default_factory=list)
    limitation: str = (
        "Avis technique illustratif fondé sur des contrats fictifs et sur les faits déclarés. "
        "Ne constitue pas une décision d'indemnisation."
    )


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)
def _rules() -> dict:
    path = PROJECT_ROOT / "data" / "rules" / "demo_rules.json"
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _manifest_entries() -> dict[str, dict]:
    manifest = json.loads((PROJECT_ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    return {item["relative_path"]: item for item in manifest["files"]}


def _source_integrity(relative_path: str, source: Path) -> bool:
    """Fail closed if an indexed PDF differs from its original manifest."""
    entry = _manifest_entries().get(relative_path)
    if entry is None or not source.is_file():
        return False
    try:
        if source.stat().st_size != entry["size_bytes"]:
            return False
        return hashlib.sha256(source.read_bytes()).hexdigest() == entry["sha256"]
    except OSError:
        return False


@lru_cache(maxsize=32)
def _page_text(path: str, page_number: int) -> str:
    # Read the source page, never invent an excerpt or cite another policy.
    with pymupdf.open(path) as pdf:
        if page_number < 1 or page_number > len(pdf):
            raise ValueError("Invalid citation page")
        return pdf[page_number - 1].get_text("text")


def _validated_citation(dossier: ContractualEvidenceDossier, scenario: str) -> DecisionCitation | None:
    references = {doc.document_reference: doc for doc in dossier.documents}
    items = [item for item in _rules()["citations"] if item["scenario"] == scenario and item["reference"] in references]
    if len(items) != 1:
        return None
    item = items[0]
    document = references[item["reference"]]
    if document.document_kind != "GENERAL_CONDITIONS":
        return None
    # Only fixed, already SQL-scoped paths; do not accept a user-supplied file path.
    source = (PROJECT_ROOT / "data" / document.pdf_relative_path).resolve()
    root = (PROJECT_ROOT / "data").resolve()
    if not source.is_relative_to(root) or source.suffix.lower() != ".pdf":
        return None
    if not _source_integrity(document.pdf_relative_path, source):
        return None
    try:
        actual_page = _page_text(str(source), item["page"])
    except (OSError, RuntimeError, ValueError):
        return None
    if _fold(item["anchor"]) not in _fold(actual_page):
        return None
    return DecisionCitation(
        document_reference=document.document_reference,
        document_kind="GENERAL_CONDITIONS",
        source_pdf=document.pdf_relative_path,
        page_number=item["page"],
        clause=item["section"],
        excerpt=item["anchor"],
    )


def _schedule_citation(dossier: ContractualEvidenceDossier, subscription) -> DecisionCitation | None:
    """Resolve the SQL-backed subscription to its original schedule PDF, page 1."""
    docs = [d for d in dossier.documents if d.document_kind == "POLICY_SCHEDULE"
            and d.document_reference == subscription.document_reference
            and d.pdf_relative_path == subscription.pdf_relative_path]
    if len(docs) != 1:
        return None
    document = docs[0]
    root = (PROJECT_ROOT / "data").resolve()
    pdf_path = (root / document.pdf_relative_path).resolve()
    if not pdf_path.is_relative_to(root) or pdf_path.suffix.lower() != ".pdf":
        return None
    if not _source_integrity(document.pdf_relative_path, pdf_path):
        return None
    try:
        page = _page_text(str(pdf_path), 1)
    except (OSError, RuntimeError, ValueError):
        return None
    if _fold(subscription.coverage_label) not in _fold(page):
        return None
    return DecisionCitation(
        document_reference=document.document_reference,
        document_kind="POLICY_SCHEDULE", source_pdf=document.pdf_relative_path,
        page_number=1, clause="2", excerpt=subscription.coverage_label,
    )


def _detect_scenario(query: str) -> Literal["bike_theft", "candle_damage", "other"]:
    q = _fold(query)
    bike = bool(re.search(r"\bvelo\b", q) and re.search(r"\b(vol|vole|volee|derobe|derobe|cambriol)", q))
    candle = ("bougie" in q or "cire" in q) and ("table" in q or "mobilier" in q)
    if bike and not candle:
        return "bike_theft"
    if candle and not bike:
        return "candle_damage"
    return "other"


def _extract_facts(query: str) -> dict[str, bool | float | date | None]:
    q = _fold(query)
    facts: dict[str, bool | float | date | None] = {
        "door_locked": None,
        "bike_fixed": None,
        "lock_m2": None,
        "working_lock": None,
        "purchase_proof": None,
        "irreversible_damage": None,
        "unattended_hours": None,
        "event_date": None,
    }

    # Classify only explicit positive and negative claims; do not assume
    # the absence of a phrase means the opposite fact is true.
    unlocked = bool(re.search(r"(?:pas|non|jamais)\s+(?:(?:bien|completement|correctement)\s+)?(?:ferme|verrouille|fermee|verrouillee)", q)
                    or re.search(r"(?:sans verrouillage|porte ouverte|porte non verrouillee|local ouvert)", q))
    locked = bool(re.search(r"(?:porte|local(?:\s+commun)?)\s+(?:etait\s+|est\s+|a ete\s+)?(?:bien\s+)?(?:ferme|verrouille)(?:e)?\s+a\s+cle", q))
    if unlocked != locked:
        facts["door_locked"] = locked

    not_fixed = bool(re.search(r"(?:pas|non)\s+(?:ete\s+)?(?:attache|fixe|accroche)", q)
                     or re.search(r"(?:sans antivol|sans attache|sans fixation)", q))
    fixed = bool(re.search(r"(?:velo|cadre)\s+(?:etait\s+|est\s+|a ete\s+)?(?:bien\s+)?(?:attache|fixe|accroche)\s+a\s+(?:un\s+)?point\s+fixe", q)
                 or re.search(r"(?:cadre|velo).{0,60}(?:point\s+(?:fixe|immobile)|ancrage\s+immobile)", q))
    if fixed != not_fixed:
        facts["bike_fixed"] = fixed
    if re.search(r"antivol\s+(?:de\s+niveau\s+)?m2", q):
        facts["lock_m2"] = True
        facts["working_lock"] = True
    elif re.search(r"antivol\s+(?:en\s+)?(?:bon\s+etat|fonctionnel|en\s+etat\s+d.usage)", q):
        facts["working_lock"] = True
    if re.search(r"(?:pas\s+de\s+|sans\s+)(?:facture|preuve\s+d.achat)", q):
        facts["purchase_proof"] = False
    elif re.search(r"(?:preuve\s+d.achat|facture)\s+(?:disponible|fournie|presentee|jointe)", q):
        facts["purchase_proof"] = True

    if re.search(r"(?:pas\s+irreversible|nettoyable|simple\s+salissure|sans\s+degradation)", q):
        facts["irreversible_damage"] = False
    elif re.search(r"(?:irreversible|indelebile|definitif|ne\s+part\s+pas\s+au\s+nettoyage)", q):
        facts["irreversible_damage"] = True

    # Duration must explicitly refer to the candle being left unattended.
    if ("bougie" in q or "cire" in q) and re.search(r"(?:laissee|laisse|sans\s+surveillance)", q):
        matches = re.findall(r"\b(\d{1,3})\s*(heures?|jours?)\b", q)
        if len(matches) == 1:
            qty, unit = matches[0]
            facts["unattended_hours"] = float(qty) * (24 if unit.startswith("jour") else 1)

    dates = re.findall(r"\b(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})\b", q)
    if len(dates) == 1:
        try:
            facts["event_date"] = date.fromisoformat(dates[0]) if "-" in dates[0] else datetime.strptime(dates[0], "%d/%m/%Y").date()
        except ValueError:
            pass
    return facts


def _result(status: str, scenario: str, explanation: str, *, facts: list[str] | None = None,
            missing: list[str] | None = None, citations: list[DecisionCitation] | None = None) -> DecisionResult:
    titles = {
        "covered": "Couverture potentiellement applicable",
        "not_covered": "Garantie non applicable au scénario décrit",
        "undetermined": "Informations insuffisantes pour conclure",
    }
    return DecisionResult(status=status, scenario=scenario, title=titles[status],
                          explanation=explanation, established_facts=facts or [],
                          missing_information=missing or [], citations=citations or [])


def evaluate_claim(dossier: ContractualEvidenceDossier) -> DecisionResult:
    """Give a conservative, traceable indicative assessment for the curated demo cases.

    Never turns missing facts into negative facts. Unrecognised products/scenarios,
    unverifiable citations or conflicting conditions yield an indeterminate result.
    """
    scenario = _detect_scenario(dossier.original_query)
    kind = "bike" if scenario == "bike_theft" else "candle" if scenario == "candle_damage" else None
    if kind is None:
        return _result("undetermined", scenario, "Scénario hors périmètre de cette première grille de règles vérifiées.",
                       missing=["Qualifier le type de sinistre et les clauses pertinentes."])

    refs = {d.document_kind: d.document_reference for d in dossier.documents}
    matches = [r for r in _rules()["products"] if r["general_reference"] == refs.get("GENERAL_CONDITIONS")
               and r["schedule_reference"] == refs.get("POLICY_SCHEDULE")]
    if len(matches) != 1:
        return _result("undetermined", scenario, "Édition documentaire inconnue : aucune règle vérifiée n'est disponible.")
    rule = matches[0]
    citation = _validated_citation(dossier, kind)
    if citation is None:
        return _result("undetermined", scenario, "Impossible de vérifier la clause dans le PDF autorisé.")
    citations = [citation]
    needed_coverage = rule["bike_coverage"] if kind == "bike" else rule["garden_coverage"]
    subscriptions = [c for c in dossier.coverages if _fold(c.coverage_label) == _fold(needed_coverage)]
    if len(subscriptions) != 1:
        return _result("undetermined", scenario, "Le statut de la garantie requise n'a pas été confirmé dans les conditions particulières.", citations=citations)
    subscription = subscriptions[0]
    schedule = refs["POLICY_SCHEDULE"]
    if subscription.document_reference != schedule:
        return _result("undetermined", scenario, "Source de souscription incohérente.", citations=citations)
    # Verify the scheduled coverage is genuinely present in its source PDF.
    schedule_citation = _schedule_citation(dossier, subscription)
    if schedule_citation is None:
        return _result("undetermined", scenario, "Impossible de vérifier la garantie dans les conditions particulières.", citations=citations)
    citations.append(schedule_citation)
    if not subscription.is_subscribed:
        return _result("not_covered", scenario,
                       f"L'option « {needed_coverage} » n'est pas souscrite dans les conditions particulières.",
                       facts=[f"Garantie {needed_coverage} : non souscrite"], citations=citations)

    facts = _extract_facts(dossier.original_query)
    event_date = facts["event_date"]
    if isinstance(event_date, date):
        try:
            start, end = date.fromisoformat(dossier.policy.valid_from), date.fromisoformat(dossier.policy.valid_to)
        except ValueError:
            return _result("undetermined", scenario, "Les dates contractuelles ne sont pas valides.", citations=citations)
        if event_date < start or event_date > end:
            return _result("not_covered", scenario, "La date déclarée est en dehors de la période indiquée au contrat.",
                           facts=[f"Date du sinistre : {event_date.isoformat()}"], citations=citations)

    if kind == "bike":
        if facts["door_locked"] is False and rule["general_reference"].startswith("HAB-A-"):
            return _result("not_covered", scenario, "La clause 3.2 impose un local fermé à clé ; la déclaration précise que cette condition n'est pas respectée.",
                           facts=["Porte du local non verrouillée"], citations=citations)
        if facts["bike_fixed"] is False:
            return _result("not_covered", scenario, "La condition contractuelle d'attache du vélo à un point fixe n'est pas satisfaite.",
                           facts=["Vélo non fixé à un point fixe"], citations=citations)
        conditions = rule["bike"].get("required", [])
    else:
        exclusion = rule["candle"].get("excluded")
        q = _fold(dossier.original_query)
        
        # A negated melting event cannot establish
        # the melted-wax exclusion.
        negated_melting = bool(
            re.search(
                r"\b(?:n['’]a|n['’]ont|ne\s+s['’]est)"
                r"\s+(?:pas|jamais)\s+"
                r"(?:\w+\s+){0,3}"
                r"(?:fondu|fondue|fondus|fondues|fondre|fonte)\b"
                r"|\bne\s+(?:\w+\s+){0,2}"
                r"fond(?:s|ait|ent)?\s+(?:pas|jamais)\b"
                r"|\b(?:sans|aucune|pas\s+de)"
                r"\s+(?:fonte|cire\s+fondue)\b",
                q,
            )
        )

        if negated_melting:
            return _result(
                "undetermined",
                scenario,
                (
                    "La déclaration nie la fonte de cire. "
                    "L'exclusion relative à cette fonte ne peut "
                    "donc pas être appliquée sur cette seule base. "
                    "Les circonstances du dommage doivent être "
                    "examinées séparément."
                ),
                facts=[
                    f"Option {needed_coverage} : souscrite"
                ],
                missing=[
                    "Préciser les circonstances du dommage "
                    "et les conditions de garantie applicables.",
                    "Confirmer la date du sinistre et fournir "
                    "les justificatifs du dommage.",
                ],
                citations=citations,
            )

        
        # Do not apply the wax exclusion when the
        # declaration explicitly denies damage by wax.
        wax_causality_denied = bool(
            re.search(
                r"\bsans\s+toucher\s+ni\s+ab[iî]mer\b"
                r"|\bsans\s+(?:ab[iî]mer|endommager|toucher)\b"
                r"|\bn['’]a\s+pas\s+"
                r"(?:ab[iî]m[eé]|endommag[eé]|touch[eé])\b",
                q,
            )
        )

        if (
            exclusion == "slow_melted_wax"
            and wax_causality_denied
            and ("cire" in q or "bougie" in q)
        ):
            return _result(
                "undetermined",
                scenario,
                (
                    "La déclaration mentionne une fonte de cire, "
                    "mais indique qu'elle n'a pas causé le dommage. "
                    "L'exclusion correspondante ne peut donc pas "
                    "justifier un refus sur cette seule base."
                ),
                facts=[
                    f"Option {needed_coverage} : souscrite"
                ],
                missing=[
                    "Préciser les circonstances du dommage par choc.",
                    "Confirmer la date du sinistre et fournir "
                    "les justificatifs du dommage.",
                ],
                citations=citations,
            )

        if (
            exclusion == "slow_melted_wax"
            and ("cire" in q or "bougie" in q)
            and ("fond" in q or "fonte" in q)
            and ("chaleur" in q or "soleil" in q)
        ):
            return _result(
                "not_covered",
                scenario,
                "La clause 4.2 exclut les dommages liés à la "
                "fonte lente de cire sous l'effet de la chaleur.",
                facts=["Fonte de cire liée à la chaleur déclarée"],
                citations=citations,
            )

        hours = facts["unattended_hours"]
        if exclusion is None and isinstance(hours, (int, float)) and hours > 48:
            return _result("not_covered", scenario, "L'absence sans surveillance dépasse les 48 heures autorisées par la clause 4.3.",
                           facts=[f"Bougie laissée {hours:g} heures"], citations=citations)
        conditions = rule["candle"].get("required", [])

    names = {
        "door_locked": "La porte du local était-elle fermée à clé ?",
        "bike_fixed": "Le vélo était-il fixé par son cadre à un point immobile ?",
        "lock_m2": "L'antivol était-il de niveau M2 ?",
        "working_lock": "L'antivol était-il en état d'usage ?",
        "purchase_proof": "Une preuve d'achat du vélo est-elle disponible ?",
        "irreversible_damage": "Le dommage à la table est-il irréversible, et non une salissure nettoyable ?",
        "under_48_hours": "Combien d'heures la bougie est-elle restée sans surveillance (maximum 48 h) ?",
    }
    missing: list[str] = []
    for condition in conditions:
        if condition == "under_48_hours":
            if facts["unattended_hours"] is None:
                missing.append(names[condition])
        elif facts.get(condition) is not True:
            missing.append(names[condition])
    if event_date is None:
        missing.append("Quelle est la date précise du sinistre (pour vérifier la période garantie) ?")
    if missing:
        return _result("undetermined", scenario,
                       "La garantie est souscrite, mais les conditions contractuelles ne sont pas toutes documentées. Aucune condition manquante n'est présumée satisfaite.",
                       facts=[f"Option {needed_coverage} : souscrite"], missing=missing, citations=citations)
    return _result("covered", scenario,
                   "Sur la base des informations déclarées, les conditions documentées sont satisfaites et aucune exclusion du scénario n'a été identifiée. Avis provisoire, soumis à vérification humaine.",
                   facts=[f"Option {needed_coverage} : souscrite", "Conditions spécifiques déclarées comme satisfaites"], citations=citations)

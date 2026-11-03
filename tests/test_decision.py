"""Regression matrix against the exact synthetic policy editions."""
import pytest

from backend.analysis.decision import evaluate_claim
from backend.schemas import ContractualEvidenceDossier


LABELS = {
    'A': ('Vol de vélo en local commun', True, 'Mobilier extérieur / Jardin', False),
    'B': ('MOBILITÉ+', True, 'JARDIN+', True),
    'C': ('VÉLO-SÉCURITÉ', False, 'TERRASSE-ACCIDENT', True),
}


def dossier(letter, claim):
    bike, bike_ok, garden, garden_ok = LABELS[letter]
    cp_ref = f'HAB-{letter}-CP-2026'
    cg_ref = f'HAB-{letter}-CG-2026'
    general_path = {
        'A':'contracts/contrat_A_protection_essentielle.pdf',
        'B':'contracts/contrat_B_mobilite_habitation.pdf',
        'C':'contracts/contrat_C_serenite_etendue.pdf',
    }[letter]
    schedule_path = f'policy_schedules/conditions_particulieres_{letter}.pdf'
    return ContractualEvidenceDossier.model_validate({
        'policy': {'policy_number':f'SIM-{letter}-000{ord(letter)-64}', 'holder_reference':'SYNTHETIC',
                   'product_name':'Demo', 'plan_name':'Demo', 'valid_from':'2026-01-01','valid_to':'2026-12-31'},
        'documents':[
            {'document_kind':'GENERAL_CONDITIONS','document_reference':cg_ref,'pdf_relative_path':general_path},
            {'document_kind':'POLICY_SCHEDULE','document_reference':cp_ref,'pdf_relative_path':schedule_path},
        ],
        'coverages':[
            {'coverage_label':bike,'is_subscribed':bike_ok,'source_status':'SOUSCRIT' if bike_ok else 'NON SOUSCRIT',
             'document_reference':cp_ref,'pdf_relative_path':schedule_path},
            {'coverage_label':garden,'is_subscribed':garden_ok,'source_status':'SOUSCRIT' if garden_ok else 'NON SOUSCRIT',
             'document_reference':cp_ref,'pdf_relative_path':schedule_path},
        ],
        'original_query':claim,'expanded_query':claim,
    })


BIKE = "Je me fais voler mon vélo dans le local commun de l'immeuble, qui n'était pas fermé à clé."
CANDLE = "Un assuré laisse une bougie sur la table de son jardin pendant ses vacances. Avec la chaleur, la bougie fond et abîme la table."

@pytest.mark.parametrize('letter,statement,expected', [
    ('A',BIKE,'not_covered'),('B',BIKE,'undetermined'),('C',BIKE,'not_covered'),
    ('A',CANDLE,'not_covered'),('B',CANDLE,'not_covered'),('C',CANDLE,'undetermined'),
])
def test_recruitment_scenarios(letter,statement,expected):
    result = evaluate_claim(dossier(letter,statement))
    assert result.status == expected
    assert result.citations
    assert result.citations[0].document_reference == f'HAB-{letter}-CG-2026'


def test_unknown_scenario_abstains():
    assert evaluate_claim(dossier('A', 'Je suis tombée de vélo')).status == 'undetermined'


def test_no_false_positive_on_missing_date():
    statement = "Mon vélo a été volé dans un local commun fermé à clé. Le vélo était attaché à un point fixe."
    result = evaluate_claim(dossier('A',statement))
    assert result.status == 'undetermined'
    assert result.missing_information


def test_candle_duration_above_48_rejected():
    statement = "Ma bougie laissée sans surveillance pendant 72 heures sur la table de jardin a laissé une trace irréversible."
    result = evaluate_claim(dossier('C',statement))
    assert result.status == 'not_covered'


def test_candle_no_inferred_duration_from_holiday():
    assert evaluate_claim(dossier('C',CANDLE)).status == 'undetermined'


def test_positive_bike_requires_all_facts_and_date():
    statement = "Mon vélo a été volé le 02/05/2026 dans un local commun fermé à clé. Le vélo était attaché à un point fixe."
    assert evaluate_claim(dossier('A',statement)).status == 'covered'


def test_policy_document_scope_mismatch_abstains():
    item = dossier('B',BIKE)
    item.documents[0].document_reference='HAB-A-CG-2026'
    assert evaluate_claim(item).status == 'undetermined'


def test_b_does_not_require_locked_door_if_other_conditions_confirmed():
    claim = ("Mon vélo a été volé le 02/05/2026 dans un local commun non fermé à clé. "
             "Le vélo était attaché à un point fixe avec antivol M2. Preuve d'achat disponible.")
    assert evaluate_claim(dossier('B',claim)).status == 'covered'


def test_c_positive_candle_with_all_explicit_conditions():
    claim = ("Le 02/05/2026, une bougie laissée sans surveillance pendant 24 heures sur ma table "
             "de jardin a causé une trace irréversible.")
    assert evaluate_claim(dossier('C',claim)).status == 'covered'


def test_claim_date_outside_contract_is_not_covered():
    claim = "Mon vélo a été volé le 02/05/2027 dans un local commun fermé à clé. Le vélo était attaché à un point fixe."
    assert evaluate_claim(dossier('A',claim)).status == 'not_covered'


def test_negated_wax_melt_does_not_trigger_exclusion():
    """
    A negated wax-melting event must not trigger
    the melted-wax exclusion.
    """
    claim = (
        "Une bougie était posée sur ma table de jardin, "
        "mais elle n'a pas fondu sous l'effet de la chaleur. "
        "La table a été cassée par un objet tombé dessus. "
        "Suis-je couvert ?"
    )

    result = evaluate_claim(dossier("B", claim))

    assert result.status == "undetermined"
    assert (
        "Fonte de cire liée à la chaleur déclarée"
        not in result.established_facts
    )


def test_unrelated_wax_melting_does_not_exclude_impact_damage():
    """
    Wax melting must not trigger an exclusion
    when it did not cause the claimed damage.
    """
    claim = (
        "Une bougie a fondu au soleil dans un récipient, "
        "sans toucher ni abîmer ma table de jardin. "
        "Plus tard, un objet est tombé sur la table "
        "et l'a cassée. Est-ce couvert ?"
    )

    result = evaluate_claim(dossier("B", claim))

    assert result.status == "undetermined", (
        "An unrelated candle event must not exclude "
        "damage caused by a falling object."
    )

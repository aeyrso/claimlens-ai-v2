export type Verdict = 'covered' | 'not_covered' | 'undetermined';
export type Scenario = 'bike_theft' | 'candle_damage' | 'other';

export interface Policy {
  policy_number: string;
  holder_reference: string;
  product_name: string;
  plan_name: string;
  valid_from: string;
  valid_to: string;
}
export interface DocumentSource {
  document_kind: 'GENERAL_CONDITIONS' | 'POLICY_SCHEDULE';
  document_reference: string;
  pdf_relative_path: string;
}
export interface Coverage {
  coverage_label: string;
  is_subscribed: boolean;
  source_status: string;
  observation: string | null;
  document_reference: string;
  pdf_relative_path: string;
}
export interface Evidence {
  evidence_id: string;
  source_pdf: string;
  document_reference: string;
  evidence_type: string;
  text: string;
  page_number: number;
  score: number;
  hybrid_score: number;
}
export interface Dossier {
  policy: Policy;
  documents: DocumentSource[];
  coverages: Coverage[];
  original_query: string;
  expanded_query: string;
  evidence: Evidence[];
}
export interface Citation {
  document_reference: string;
  source_pdf: string;
  document_kind: string;
  page_number: number;
  clause: string;
  excerpt: string;
}
export interface Decision {
  status: Verdict;
  scenario: Scenario;
  title: string;
  explanation: string;
  established_facts: string[];
  missing_information: string[];
  citations: Citation[];
  limitation: string;
}
export interface AnalysisResponse {
  dossier: Dossier;
  decision: Decision;
}

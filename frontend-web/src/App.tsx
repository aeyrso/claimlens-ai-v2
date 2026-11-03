import { useEffect, useMemo, useState, type FormEvent } from 'react';
import {
  ArrowRight, BookOpen, Check, ChevronDown, ChevronRight,
  CircleAlert, ClipboardCheck, FileCheck2, FileSearch, FileText,
  Info, Layers3, LockKeyhole, Search, ShieldCheck, X, Zap,
} from 'lucide-react';
import type { AnalysisResponse, Evidence, Verdict } from './types';

const scenarios = {
  bike: "Je me fais voler mon vélo dans le local commun de l'immeuble, qui n'était pas fermé à clé. Suis-je couvert ?",
  candle: "Un assuré laisse une bougie sur la table de son jardin pendant ses vacances. Avec la chaleur, la bougie fond et abîme la table. Est-ce couvert ?",
};
const policies = [
  { id: 'SIM-A-0001', name: 'Protection Essentielle', short: 'A' },
  { id: 'SIM-B-0002', name: 'Mobilité & Habitation', short: 'B' },
  { id: 'SIM-C-0003', name: 'Sérénité Étendue', short: 'C' },
];
const wording: Record<Verdict, string> = {
  covered: 'Potentiellement couvert',
  not_covered: 'Non couvert selon les clauses',
  undetermined: 'Informations insuffisantes',
};

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 404) throw new Error('Cette police est introuvable dans le corpus synthétique.');
    if (response.status === 422) throw new Error('Veuillez vérifier les champs saisis.');
    throw new Error('Le serveur ne peut pas terminer l’analyse. Consultez les journaux FastAPI.');
  }
  return response.json() as Promise<T>;
}

function SectionHeading({ icon, eyebrow, title }: { icon: React.ReactNode; eyebrow: string; title: string }) {
  return <div className="section-heading"><div className="heading-icon">{icon}</div><div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2></div></div>;
}

export function App() {
  const [policy, setPolicy] = useState('SIM-B-0002');
  const [query, setQuery] = useState(scenarios.bike);
  const [limit, setLimit] = useState(10);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [image, setImage] = useState<string | null>(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [lastRequest, setLastRequest] = useState<{policy_number:string; query:string; limit:number} | null>(null);
  const [apiReady, setApiReady] = useState<boolean | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch('/health', { signal: controller.signal })
      .then(r => setApiReady(r.ok)).catch(() => setApiReady(false));
    return () => controller.abort();
  }, []);

  const active = useMemo(() => policies.find(item => item.id === policy), [policy]);

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true); setError(null); setResult(null); setSelected(null);
    setImage(null);
    try {
      const body = { policy_number: policy.trim(), query: query.trim(), limit };
      const outcome = await postJson<AnalysisResponse>('/analysis/decision', body);
      setResult(outcome); setLastRequest(body);
      setApiReady(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  }

  async function openPreview(evidence: Evidence) {
    if (!lastRequest) return;
    setSelected(evidence.evidence_id);
    if (image) URL.revokeObjectURL(image);
    setImage(null); setImageLoading(true);
    try {
      const response = await fetch('/analysis/preview', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...lastRequest, evidence_id: evidence.evidence_id }),
      });
      if (!response.ok) throw new Error('Prévisualisation non disponible');
      setImage(URL.createObjectURL(await response.blob()));
    } catch {
      setImage(null);
    } finally {
      setImageLoading(false);
    }
  }

  function closePreview() {
    setSelected(null);
    if (image) URL.revokeObjectURL(image);
    setImage(null);
  }

  const currentEvidence = result?.dossier.evidence.find(item => item.evidence_id === selected);
  const verdict = result?.decision.status;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><Layers3 size={23} strokeWidth={2.4} /></div><div><strong>ClaimLens<span>AI</span></strong><small>CONTRACT INTELLIGENCE</small></div></div>
        <div className="nav-caption">ESPACE DE TRAVAIL</div>
        <div className="nav-active"><FileSearch size={18} /> Analyse de sinistre <ChevronRight size={17} className="nav-arrow" /></div>
        <div className="sidebar-info"><div className="info-icon"><ShieldCheck size={19}/></div><b>Preuves vérifiables</b><p>Chaque avis s'appuie sur les documents du contrat sélectionné.</p></div>
        <div className="sidebar-bottom"><span className="status-indicator"><i className={apiReady === false ? 'offline' : ''}/> {apiReady === false ? 'API indisponible' : apiReady === true ? 'API connectée' : 'Vérification de l’API'}</span><small>V2 expérimentale · corpus fictif</small></div>
      </aside>
      <main className="workspace">
        <header className="topbar"><div className="breadcrumbs">Espace de travail <ChevronRight size={15}/> <strong>Analyse contractuelle</strong></div><span className="topbar-tag"><LockKeyhole size={13}/> Démonstration locale</span></header>
        <div className="content">
          <div className="hero"><span className="hero-overline"><Zap size={13}/> INSURANCE DOCUMENT AI</span><h1>Analyser un sinistre.<br/><em>Vérifier chaque conclusion.</em></h1><p>Un dossier contractuel, une analyse motivée et des clauses traçables jusqu'aux PDF d'origine.</p></div>
          <div className="demo-note"><Info size={18}/><span><strong>Environnement de démonstration.</strong> Documents entièrement synthétiques. Les avis sont indicatifs et ne constituent jamais une décision d'indemnisation.</span></div>
          <div className="columns">
            <section className="panel input-panel">
              <SectionHeading icon={<FileSearch size={20}/>} eyebrow="01 · DOSSIER" title="Votre demande" />
              <form onSubmit={analyze}>
                <label htmlFor="policy">Numéro de police</label>
                <div className="select-wrap"><select id="policy" value={policy} onChange={e => setPolicy(e.target.value)}>
                  {policies.map(item => <option key={item.id} value={item.id}>{item.id} — {item.name}</option>)}
                </select><ChevronDown size={17}/></div>
                <div className="policy-meta"><span>Contrat synthétique {active?.short}</span><span><ShieldCheck size={13}/> Périmètre SQL isolé</span></div>
                <label htmlFor="query">Description du sinistre</label>
                <textarea id="query" value={query} maxLength={1000} onChange={e => setQuery(e.target.value)} placeholder="Décrivez les circonstances, les dommages et les justificatifs disponibles…" rows={6} required />
                <div className="char-count">{query.length} / 1 000 caractères</div>
                <div className="examples-title">EXEMPLES DE CAS RÉELS DU SUJET</div>
                <div className="examples">
                  <button type="button" onClick={() => setQuery(scenarios.bike)}><span>01</span> Vol de vélo en local commun <ArrowRight size={15}/></button>
                  <button type="button" onClick={() => setQuery(scenarios.candle)}><span>02</span> Bougie et mobilier extérieur <ArrowRight size={15}/></button>
                </div>
                <label className="limit-label" htmlFor="limit">Nombre maximum de preuves <b>{limit}</b></label>
                <input type="range" id="limit" min={1} max={20} value={limit} onChange={e => setLimit(Number(e.target.value))}/>
                <button className="submit-button" disabled={loading || !query.trim()} type="submit">{loading ? <span className="spinner"/> : <Search size={19}/>} {loading ? 'Analyse des documents…' : 'Analyser le contrat'} <ArrowRight size={18}/></button>
              </form>
              {error && <div className="error-message"><CircleAlert size={18}/>{error}</div>}
            </section>

            <section className="panel results-panel">
              <SectionHeading icon={<ClipboardCheck size={20}/>} eyebrow="02 · INTERPRÉTATION" title="Avis contractuel" />
              {!result && !loading && <div className="empty-state"><div><BookOpen size={42} strokeWidth={1.3}/></div><h3>Vos preuves, pas des suppositions.</h3><p>Lancez une analyse pour visualiser un avis motivé, les conditions manquantes et les références PDF.</p></div>}
              {loading && <div className="empty-state"><span className="spinner large"/><h3>Analyse en cours</h3><p>Vérification des conditions particulières et recherche des clauses contractuelles…</p></div>}
              {result && verdict && <div className="result-body">
                <div className={`verdict ${verdict}`}><span className="verdict-label">AVIS INDICATIF</span><h3>{wording[verdict]}</h3><p>{result.decision.explanation}</p></div>
                <div className="result-stats"><div><small>POLICE</small><strong>{result.dossier.policy.policy_number}</strong></div><div><small>GARANTIES</small><strong>{result.dossier.coverages.length}</strong></div><div><small>PREUVES</small><strong>{result.dossier.evidence.length}</strong></div></div>
                {result.decision.established_facts.length > 0 && <div className="result-block"><h4><Check size={16}/> Éléments établis</h4>{result.decision.established_facts.map((fact, i) => <p className="fact" key={i}>{fact}</p>)}</div>}
                {result.decision.missing_information.length > 0 && <div className="result-block question-block"><h4><CircleAlert size={17}/> Informations à confirmer</h4>{result.decision.missing_information.map((q, i) => <p className="missing" key={i}>{q}</p>)}</div>}
                <div className="result-block"><h4><FileText size={17}/> Clauses citées</h4>{result.decision.citations.length > 0 ? result.decision.citations.map((item, i) => <div className="citation" key={i}><strong>{item.document_reference} · § {item.clause}</strong>
<small>
  Page {item.page_number} · {
    (() => {
      const document = result.dossier.documents.find(
        doc => doc.document_reference === item.document_reference
      );

      if (document?.document_kind === 'GENERAL_CONDITIONS') {
        return 'Conditions générales';
      }

      if (document?.document_kind === 'POLICY_SCHEDULE') {
        return 'Conditions particulières';
      }

      return 'Type de document non identifié';
    })()
  }
</small>
<p>« {item.excerpt}… »</p></div>) : <p className="muted">Aucune clause validée pour ce scénario.</p>}</div>
                <p className="legal-note">{result.decision.limitation}</p>
              </div>}
            </section>
          </div>
          {result && <section className="panel evidence-panel"><div className="evidence-header"><SectionHeading icon={<FileCheck2 size={20}/>} eyebrow="03 · TRAÇABILITÉ" title="Bibliothèque de preuves" /><span>{result.dossier.evidence.length} éléments trouvés</span></div><div className="evidence-grid">{result.dossier.evidence.map((item, index) => <article className="evidence-item" key={item.evidence_id}><div className="evidence-number">{String(index + 1).padStart(2,'0')}</div><div className="evidence-content"><p>{item.text}</p><div className="evidence-ref"><span><FileText size={13}/> {item.document_reference}</span><span>Page {item.page_number}</span></div></div><button onClick={() => openPreview(item)} className="view-btn" type="button">Voir la page <ArrowRight size={14}/></button></article>)}</div></section>}
          <footer><span>ClaimLens AI · Architecture modulaire Python / FastAPI / RAG hybride</span><span>V2 · Contrats d'assurance fictifs</span></footer>
        </div>
      </main>
      {selected && <div className="modal-overlay" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget) closePreview(); }}><section className="modal" role="dialog" aria-modal="true" aria-label="Prévisualisation PDF"><div className="modal-header"><div><span className="eyebrow">JUSTIFICATIF ORIGINAL</span><h3>{currentEvidence?.document_reference} · Page {currentEvidence?.page_number}</h3></div><button type="button" onClick={closePreview} aria-label="Fermer"><X size={20}/></button></div><div className="modal-body">{imageLoading && <span className="spinner large"/>}{!imageLoading && image ? <img alt="Page PDF avec zones documentaires surlignées" src={image}/> : !imageLoading && <div className="error-message">Impossible d'afficher la page. La preuve ou la localisation peut être indisponible.</div>}</div></section></div>}
    </div>
  );
}

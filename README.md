# ClaimLens AI — Analyse explicable de contrats d'assurance

**Version V2 · React + TypeScript + FastAPI · Recherche documentaire hybride · Citations PDF vérifiables**

ClaimLens AI est un démonstrateur d'assistance à l'analyse de contrats d'assurance **entièrement synthétiques**. À partir d'un numéro de police et d'une déclaration de sinistre en français, l'application rassemble les informations du contrat, recherche les clauses pertinentes et produit, pour certains scénarios documentés, un **avis contractuel indicatif et motivé**. L'utilisateur peut consulter les références des conditions générales et particulières ainsi que les extraits surlignés sur leurs pages PDF d'origine.

> **Important — périmètre de la démonstration.** Les trois polices, les six PDF, les garanties et les situations contractuelles sont fictifs. Les règles d'interprétation sont **rédigées manuellement à partir de ce corpus** ; elles ne sont pas extraites automatiquement de contrats arbitraires. Un avis « potentiellement couvert » ou « non couvert selon les clauses » n'est **ni une décision juridique, ni une décision d'indemnisation**. Le prototype ne doit pas être utilisé avec de véritables dossiers d'assurés et ne remplace pas une expertise humaine.

**Statut de validation au 2 novembre 2026 :** application locale V2 exécutée sous Windows ; interface React compilée ; scénarios principaux et plusieurs contre-exemples testés dans le navigateur ; **206 tests Python réussis, 1 ignoré, 0 échec, 12 avertissements**. **Aucun hébergement public sécurisé ni audit complet de production n'est validé à ce stade.**

---

## 1. Présentation et objectifs

ClaimLens AI associe une base de données relationnelle SQLite, une extraction documentaire avec Docling, une recherche lexicale et sémantique multilingue, une fusion des classements et une traçabilité des preuves jusqu'aux PDF. La V2 ajoute une interface React et un moteur d'avis explicable pour les scénarios de démonstration.

À partir d'une police et d'une description, l'application permet de :

- Identifier la police sélectionnée et son produit d'assurance synthétique.
- Consulter les garanties souscrites et non souscrites, ainsi que leurs références dans les conditions particulières.
- Identifier les conditions générales et particulières associées à la police ; **ne pas mélanger les documents de polices différentes**.
- Rejeter les numéros de police inconnus et les demandes invalides.
- Reconnaître certaines localisations contractuelles ambiguës et indiquer celles qui doivent être vérifiées.
- Retrouver et classer les passages pertinents dans les textes et les tableaux des PDF.
- Conserver les références documentaires, numéros de page, coordonnées et, pour les tableaux, références de cellules.
- Consulter une page PDF surlignée pour confronter une preuve à son document d'origine.
- Produire, sur les scénarios couverts par les règles de démonstration, un **avis indicatif** avec justification, faits reconnus, informations manquantes et clauses citées.
- Répondre **« informations insuffisantes »** lorsqu'une conclusion ne peut pas être établie de façon justifiable.

La conception distingue **trois responsabilités** : retrouver des preuves, vérifier leurs sources et interpréter des règles contractuelles limitées. Un bon score de recherche **ne constitue jamais** une preuve de couverture.

---

## 2. Fonctionnalités de la V2

### 2.1 Analyse contractuelle et garanties

- Sélection d'une police parmi trois polices synthétiques.
- Vérification du périmètre des documents en base SQLite **avant** toute recherche dans les exports documentaires.
- Consultation des garanties et des statuts de souscription ; rejet des références incohérentes.
- Comparaison entre les conditions générales et les conditions particulières lorsqu'une garantie ou une exclusion est examinée.
- Prise en compte de certaines dates, conditions d'attache, justificatifs ou durées explicitement déclarés ; les faits manquants ne sont pas supposés vrais.
- Identification de lieux non vérifiés lorsqu'une équivalence contractuelle n'est pas documentée.

### 2.2 Recherche documentaire hybride

- Extraction de PDF via **Docling** : éléments textuels, tableaux, lignes et métadonnées de provenance.
- Recherche **lexicale contextualisée** dans les documents rattachés à la police.
- Recherche **sémantique multilingue** avec `intfloat/multilingual-e5-small` et des embeddings normalisés de 384 dimensions.
- Expansion de requête **contrôlée** : synonymes linguistiques, expressions contextuelles et équivalences contractuelles vérifiées dans les sources autorisées.
- Fusion par **Weighted Reciprocal Rank Fusion (RRF)** ; pondération lexicale et sémantique sans interpréter les scores comme des probabilités.
- Classement reproductible, avec vérification des sources et de la cohérence des preuves fusionnées.
- Filtrage lexical de certains mots peu informatifs pour diminuer le bruit documentaire, tout en conservant la recherche sémantique.

Une expansion de requête aide **uniquement** à retrouver des documents : elle ne crée pas de nouveaux faits sur le sinistre.

### 2.3 Avis contractuel indicatif

L'API `/analysis/decision` fournit l'un des trois statuts suivants :

| Code API | Libellé de l'interface | Signification dans la démonstration |
|---|---|---|
| `covered` | **Potentiellement couvert** | Les conditions pertinentes sont déclarées comme satisfaites sur le scénario pris en charge, sous réserve de vérification humaine. |
| `not_covered` | **Non couvert selon les clauses** | Une exclusion vérifiée, une garantie non souscrite ou une condition explicitement non respectée est identifiée sur le scénario démonstratif. |
| `undetermined` | **Informations insuffisantes** | Des faits, références, conditions ou éléments de causalité manquent ; le scénario ou l'édition n'est pas pris en charge de façon vérifiable. |

Le moteur est implémenté dans `backend/analysis/decision.py` et s'appuie sur un catalogue **manuel et limité** dans `data/rules/demo_rules.json` : **deux familles de sinistres** (vol de vélo dans un local commun ; dommages associés à une bougie et au mobilier de jardin) au travers de **trois éditions contractuelles fictives**.

Il vérifie notamment les références de clauses, l'édition documentaire et la souscription correspondante. Une édition inconnue, un passage introuvable ou une source non vérifiable conduit à une réponse indéterminée. Certaines négations explicites et certains cas d'absence de lien causal ont été ajoutés aux tests ; il ne s'agit **pas d'une compréhension générale du langage naturel**.

### 2.4 Traçabilité, citations et aperçu PDF

- Référence du document, type de document (**conditions générales** ou **conditions particulières**), section, page et extrait de clause.
- Éléments de preuve numérotés et consultables, accompagnés des termes ou scores de recherche lorsque fournis par le backend.
- Conservation des coordonnées d'extraction PDF et des cellules de tableaux pour des références précises.
- Aperçu d'une **page originale rendue en image PNG et surlignée en mémoire** avec PyMuPDF, sans modifier le PDF enregistré.
- Vérification côté serveur de l'identifiant de preuve et du document avant le rendu : le navigateur ne fournit ni chemin de fichier PDF arbitraire ni rectangles de sélection à accepter directement.
- Réinitialisation de la sélection et de l'aperçu lors d'une nouvelle analyse.

**Limite connue :** la visualisation surlignée a été conçue et testée pour les pages non pivotées. Elle n'est pas un moteur de lecture universel de tous les PDF.

### 2.5 Interface utilisateur

La V2 utilise **React 19, TypeScript et Vite 6**, avec une interface de travail comportant : choix de police, description libre (jusqu'à 1 000 caractères), exemples de scénarios, réglage du nombre de preuves, indicateur de disponibilité de l'API, avis explicatif, informations manquantes, citations et bibliothèque de preuves.

Le frontend **affiche** l'avis calculé par FastAPI ; il n'effectue pas lui-même de décision d'assurance.

L'ancien frontend **Streamlit** (`frontend/app.py`) reste un composant hérité de la V1 ; **React est l'interface de référence de la V2**.

---

## 3. Démonstrations guidées

Les deux scénarios centraux et les contre-exemples ci-dessous utilisent la police synthétique `SIM-B-0002` (**Mobilité & Habitation**). Les résultats indiqués sont ceux attendus pour **les déclarations précisées**, et ne se généralisent pas automatiquement à d'autres faits.

### Scénario A — Vol de vélo dans un local commun non verrouillé

Sélectionner `SIM-B-0002` et saisir :

> Je me fais voler mon vélo dans le local commun de l'immeuble, qui n'était pas fermé à clé. Suis-je couvert ?

**Comportement attendu :** avis **« Informations insuffisantes »** pour cette police, car la souscription du module ne suffit pas à elle seule ; les conditions d'attache du vélo, d'antivol et de justificatifs doivent être vérifiées. L'application cite les clauses pertinentes des conditions générales et particulières. D'autres éditions fictives peuvent appliquer des conditions différentes.

### Scénario B — Bougie fondue ayant endommagé la table

Sélectionner `SIM-B-0002` et saisir :

> Un assuré laisse une bougie sur la table de son jardin pendant ses vacances. Avec la chaleur, la bougie fond et abîme la table. Est-ce couvert ?

**Comportement attendu :** avis **« Non couvert selon les clauses »** dans les conditions du contrat B synthétique, avec référence à l'exclusion de la section **4.2** relative à la fonte lente de cire et à la chaleur. La conclusion provient des règles manuelles vérifiées, pas d'une inférence juridique générale.

### Contre-exemple 1 — Négation explicite de la fonte

> Une bougie était posée sur ma table de jardin, mais elle n'a pas fondu sous l'effet de la chaleur. La table a été cassée par un objet tombé dessus. Suis-je couvert ?

**Comportement attendu :** **« Informations insuffisantes »**. La simple présence des mots « bougie », « fondu » et « chaleur » ne doit pas déclencher une exclusion lorsque la fonte est niée.

### Contre-exemple 2 — Fonte réelle, sans lien causal avec le dommage

> Une bougie a fondu au soleil dans un récipient, sans toucher ni abîmer ma table de jardin. Plus tard, un objet est tombé sur la table et l'a cassée. Est-ce couvert ?

**Comportement attendu :** **« Informations insuffisantes »**. L'événement de fonte est distinct du dommage par choc. Cette protection a été testée sur **cette formulation précise** ; les généralisations linguistiques exigent une évaluation plus large.

### Exemple documentaire simple — Mobilier extérieur

> Ma table de jardin a été endommagée.

La recherche doit retrouver notamment le module `JARDIN+` souscrit et la référence à la table dans les conditions particulières. **La souscription d'une garantie ne prouve pas l'indemnisation du sinistre** : exclusions, circonstances, durée de validité et justificatifs sont à examiner séparément.

### Cas négatif — Police inconnue

Identifiant de test : `SIM-INCONNUE-9999`.

L'API doit rejeter la police inconnue (réponse `404` sur les routes d'analyse) et ne jamais restituer le dossier ou les preuves d'une autre police. L'interface React limite normalement la sélection aux trois polices de démonstration ; ce test peut être réalisé via l'API ou les tests automatisés. Le rejet d'une police inconnue avait également été vérifié visuellement sur la V1.

### Vérifier une preuve sur le document d'origine

1. Lancer une analyse.
2. Consulter les **clauses citées**, le type de document, sa référence et sa page.
3. Ouvrir un élément de la **bibliothèque de preuves** et demander l'aperçu de sa page.
4. Examiner l'extrait surligné ; confronter la preuve à la déclaration et vérifier qu'elle s'y applique réellement.

Le nombre de preuves affichées n'est **pas** un indicateur de couverture. Une preuve retrouvée peut être une exclusion à écarter si elle ne concerne pas la cause du sinistre.

---

## 4. Architecture technique

| Couche / composant | Technologie | Responsabilité |
|---|---|---|
| Langage backend | Python 3.12 | API, ingestion, recherche, règles et tests |
| Interface V2 | React 19, TypeScript, Vite 6 | Formulaire, avis, références, consultation des pages |
| Interface historique V1 | Streamlit | Prototype antérieur conservé à titre de référence |
| API HTTP | FastAPI | Routes typées, appels d'analyse et prévisualisation |
| Validation | Pydantic | Schémas stricts, contrôles des entrées et sorties |
| Base relationnelle | SQLite | Polices, garanties, documents et statuts de souscription |
| Ingestion | Docling | Conversion PDF vers des exports structurés |
| Visualisation des preuves | PyMuPDF | Consultation des PDF et rendu des passages surlignés |
| Recherche lexicale | Correspondance contextualisée de termes | Priorité documentaire et concordances |
| Recherche sémantique | E5 multilingue, PyTorch, Transformers, NumPy | Similarité entre question et passages |
| Fusion | Weighted RRF | Combinaison des classements lexicaux et sémantiques |
| Avis indicatif | Règles déclaratives manuelles + vérifications des sources | Décision de démonstration limitée, explicable |
| Évaluation | pytest + jeux synthétiques | Intégrité, isolation, classement, API et règles |
| Versionnement | Git | Historique du code ; publication non encore effectuée pour la V2 |

### 4.1 Pipeline de préparation des documents (hors ligne)

```text
6 PDF synthétiques + data/manifest.json
                |
                v
      Contrôle taille + SHA-256
                |
                v
       Docling / extraction PDF
                |
                v
   JSON structurés (data/parsed/)
    - textes, tableaux, cellules
    - pages, positions, références
                |
                v
   Initialisation SQLite (bootstrap)
    - 3 polices fictives
    - 6 documents rattachés
    - garanties et souscriptions
```

L'indexeur préserve les exports valides existants et ne les écrase pas automatiquement. Le processus d'initialisation SQLite refuse de remplacer une base déjà créée.

### 4.2 Pipeline d'analyse (requête)

```text
Utilisateur
   |
   v
React / TypeScript (ou client HTTP)
   |
   v
POST /analysis/decision (FastAPI)
   |
   v
Validation Pydantic + sélection de police dans SQLite
   |
   v
Périmètre des PDF rattachés à la police
   |
   +-------------------------------+
   |                               |
   v                               v
Recherche lexicale          Recherche sémantique
+ expansion contrôlée       E5 multilingue / CPU
   |                               |
   +---------------+---------------+
                   |
                   v
     Fusion pondérée des rangs (RRF)
                   |
                   v
     Dossier de preuves documentaires
      (sources, pages, positions)
                   |
                   v
  Vérification des clauses et souscriptions
        + règles manuelles V2
                   |
                   v
         Avis indicatif motivé
      + faits + conditions manquantes
      + citations CG/CP + preuves
```

Les opérations documentaires précèdent l'avis. Le code de récupération de preuves **ne décide pas**, à lui seul, si un sinistre est couvert.

### 4.3 Pipeline de vérification PDF

```text
Clic « Voir la page »
   |
   v
POST /analysis/preview
   |
   v
Reconstruction du dossier / contrôle SQL
   |
   v
Revérification de evidence_id et du PDF autorisé
   |
   v
PyMuPDF : page rendue en PNG avec surlignage
   |
   v
Aperçu dans React
```

L'aperçu est généré en mémoire. Aucune modification du PDF source n'est enregistrée.

### 4.4 Détails de recherche

- **SQL-first** : `get_policy_context` identifie d'abord la police et ses documents. L'isolation documentaire **ne représente pas** une authentification utilisateur.
- **Expansion contrôlée** (`query_expansion.py`) : notamment `bicyclette → vélo`, certains contextes de `feu → incendie`, `baie vitrée endommagée → bris de glace`, `table de jardin endommagée → mobilier de jardin`, et `local collectif → local commun` **uniquement si l'équivalence est retrouvée dans les documents de la police**. Les lieux ambigus comme « garage collectif » et « trottoir » sont signalés lorsqu'ils ne sont pas établis.
- **Recherche lexicale** (`search.py`) : rapprochement de termes normalisés, protection pour certaines expressions contextuelles, pénalité pour lieux incompatibles, conservation de la provenance des textes et des tableaux. Certains mots peu informatifs tels que « couvert », « était » et « sous » ont été écartés du classement lexical lorsque des termes plus spécifiques existent.
- **Recherche sémantique** (`semantic.py`, `embeddings.py`) : E5 multilingue, préfixes `query:` et `passage:`, vecteurs de 384 dimensions normalisés, calcul sur CPU ; produit des scores de similarité, **pas des probabilités calibrées**.
- **Fusion** (`fusion.py`) : RRF pondéré avec `LEXICAL_WEIGHT = 2.0`, `SEMANTIC_WEIGHT = 1.0` et `RRF_K = 60` dans la version locale examinée ; les candidats sont plafonnés avant fusion, puis classés de manière déterministe. Les sources hors police sont rejetées.

**Limite de pertinence connue :** certains passages faibles ou hors sujet peuvent toujours entrer dans les dix résultats sur des formulations nouvelles. Le filtrage lexical a corrigé un cas vérifié concernant une table de jardin, mais un autre cas de causalité montre encore ponctuellement des passages sur le vélo. La réduction du bruit documentaire doit être évaluée plus largement ; ne pas interpréter les premiers résultats comme une justification automatique du verdict.

---

## 5. Structure du projet

```text
claimlens-ai-v2/
├── backend/
│   ├── analysis/
│   │   ├── citations.py        # Coordonnées et références PDF
│   │   ├── coverage.py         # Construction du dossier de preuves
│   │   ├── decision.py         # Avis indicatif V2
│   │   ├── pdf_access.py       # Résolution sûre des chemins
│   │   └── pdf_preview.py      # Aperçu surligné
│   ├── database/
│   │   ├── bootstrap.py        # Initialisation non destructive
│   │   ├── connection.py       # Connexions SQLite
│   │   ├── importer.py         # Import du corpus
│   │   ├── queries.py          # Recherche SQL
│   │   └── schema.sql          # Schéma relationnel
│   ├── ingestion/
│   │   ├── docling_factory.py
│   │   ├── indexer.py
│   │   ├── pdf_parser.py
│   │   ├── structured_export.py
│   │   └── table_extractor.py
│   ├── retrieval/
│   │   ├── embeddings.py
│   │   ├── fusion.py
│   │   ├── hybrid.py
│   │   ├── query_expansion.py
│   │   ├── search.py
│   │   └── semantic.py
│   ├── config.py
│   ├── main.py              # FastAPI + interface React compilée
│   └── schemas.py
├── frontend-web/           # Interface V2 React / TypeScript / Vite
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── styles.css
│   │   └── types.ts
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── frontend/
│   └── app.py              # Ancienne interface Streamlit (V1)
├── data/
│   ├── contracts/          # 3 PDF de conditions générales
│   ├── policy_schedules/   # 3 PDF de conditions particulières
│   ├── evaluation/         # Scénarios de recherche
│   ├── rules/
│   │   └── demo_rules.json # Règles manuelles de démonstration
│   ├── manifest.json       # Association et empreintes SHA-256
│   ├── LISEZ_MOI.txt
│   └── parsed/             # Exports générés, ignorés par Git
├── docs/
│   ├── architecture.md
│   └── evaluation.md
├── scripts/
│   └── ingest.py
├── tests/                  # Tests automatisés conservés
├── requirements.txt
├── README.md
├── V2_DEV_NOTES.md         # Notes de développement historiques
└── .gitignore
```

Cette arborescence présente les fichiers du **paquet candidat V2 initial** et les modules V2 étudiés. Des fichiers générés localement peuvent s'y ajouter (`.venv/`, `frontend-web/node_modules/`, `frontend-web/dist/`, `data/claimlens.sqlite3`, `data/parsed/`, caches). Les chemins exacts doivent être revérifiés dans la copie finale destinée au dépôt.

Les fichiers `docs/` et `V2_DEV_NOTES.md` ont été rédigés avant certaines validations récentes : leurs indications historiques de tests doivent être **synchronisées avant publication** si elles restent présentes dans le dépôt.

---

## 6. Corpus synthétique et intégrité documentaire

Le corpus contient **trois polices fictives** et **six PDF**, chaque police étant associée à ses conditions générales et particulières :

| Police | Produit fictif | Conditions générales | Conditions particulières |
|---|---|---|---|
| `SIM-A-0001` | Protection Essentielle | `data/contracts/contrat_A_protection_essentielle.pdf` | `data/policy_schedules/conditions_particulieres_A.pdf` |
| `SIM-B-0002` | Mobilité & Habitation | `data/contracts/contrat_B_mobilite_habitation.pdf` | `data/policy_schedules/conditions_particulieres_B.pdf` |
| `SIM-C-0003` | Sérénité Étendue | `data/contracts/contrat_C_serenite_etendue.pdf` | `data/policy_schedules/conditions_particulieres_C.pdf` |

Le manifeste `data/manifest.json` contient les **chemins relatifs, tailles, empreintes SHA-256 et associations** de ces documents. Il est utilisé pour contrôler leur intégrité avant extraction ; le moteur de règles vérifie également les sources documentaires de ses citations.

Le corpus couvre notamment des exemples synthétiques de **vol**, **incendie**, **dégât des eaux**, **bris de glace** et **mobilier extérieur**. Il sert à évaluer la recherche et les différences entre éditions et souscriptions. **Seuls les scénarios explicitement décrits dans le catalogue de règles bénéficient d'un avis contractuel spécifique V2** : une clause retrouvée dans un autre domaine ne suffit pas à produire un verdict automatisé.

Les PDF ont été créés pour cette démonstration, sans reproduction de contrats réels ni utilisation de données personnelles réelles. Les montants, plafonds, franchises et obligations qu'ils présentent sont fictifs et **n'ont aucune valeur juridique**. Le fichier `data/LISEZ_MOI.txt` détaille l'origine et l'usage du corpus. Si une licence publique devait être attribuée au dépôt ou aux PDF, son choix devrait être explicite ; aucune licence libre irrévocable n'est présumée ici.

---

## 7. Installation locale : Windows / PowerShell

### 7.1 Prérequis

- **Python 3.12** et `pip` ; **Node.js** et `npm` pour le frontend React.
- **Git** si le code est récupéré depuis un dépôt distant ; inutile si l'on extrait un ZIP.
- Windows / PowerShell pour les commandes ci-dessous. L'exécution sur Linux/macOS nécessiterait les équivalents de chemins et **n'a pas été qualifiée comme installation neuve V2**.
- Une connexion Internet lors du téléchargement initial des dépendances, du modèle E5 et de certains modèles de Docling.
- Des ressources CPU/RAM compatibles avec Docling, PyTorch et Transformers.

**Toutes les commandes sont à lancer à la racine `claimlens-ai-v2/`**, sauf indication contraire. Le dossier de la V1 doit rester séparé pour ne pas écraser une version précédemment validée.

### 7.2 Créer et utiliser l'environnement virtuel

```powershell
python -m venv .venv
```

L'activation est facultative, car les commandes proposées appellent explicitement le Python de l'environnement :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Pour utiliser la méthode historique avec activation :

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Le premier chargement d'E5 (`intfloat/multilingual-e5-small`) et certains traitements Docling peuvent déclencher des téléchargements supplémentaires. Ne pas supposer que l'installation fonctionne hors connexion dès la première exécution.

### 7.3 Contrôler et extraire les six PDF

```powershell
.\.venv\Scripts\python.exe -m backend.ingestion.indexer
```

L'indexeur doit :

1. Lire `data/manifest.json` et vérifier les chemins PDF, la taille et les empreintes SHA-256.
2. Convertir les documents synthétiques avec Docling.
3. Produire les exports JSON structurés sous `data/parsed/` : textes, tableaux, coordonnées et références de pages.
4. Conserver les exports existants valides sans les écraser inutilement.

Sur une première installation, l'extraction documentaire peut prendre nettement plus de temps qu'une analyse interactive ultérieure.

### 7.4 Initialiser la base SQLite

Après la création des exports JSON :

```powershell
.\.venv\Scripts\python.exe -m backend.database.bootstrap
```

L'initialisation importe **3 polices, 6 documents et leurs garanties/souscriptions**. Le schéma est dans `backend/database/schema.sql` et le chemin de base est défini dans `backend/config.py` (`data/claimlens.sqlite3` dans la version examinée).

**Attention :** `bootstrap.py` **refuse d'écraser une base SQLite existante**. Ne pas le relancer sur une installation déjà initialisée, sauf procédure de réinitialisation volontaire et sauvegardée. Il est normal que la base ne soit pas présente dans le dépôt : elle est générée localement.

### 7.5 Installer et compiler l'interface React

Depuis la racine :

```powershell
npm --prefix .\frontend-web install
npm --prefix .\frontend-web run build
```

La compilation vérifie TypeScript via `tsc --noEmit`, puis exécute `vite build`. Le résultat statique est généré sous `frontend-web/dist/` ; ce dossier ne doit pas être ajouté aux sources suivies par Git.

Si `node` n'est pas reconnu après installation de Node.js, ouvrir un **nouveau** terminal pour actualiser `PATH`. Sur le poste Windows utilisé pendant la validation, il a également fallu ajouter temporairement `C:\Program Files\nodejs` au `PATH` d'un terminal déjà ouvert.

### 7.6 Démarrer la V2 compilée avec un seul serveur

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Lorsque `frontend-web/dist/` existe, FastAPI sert la version compilée de React **sur la même origine que l'API**.

- Application : **http://127.0.0.1:8000/**
- Documentation FastAPI : **http://127.0.0.1:8000/docs**
- Vérification du processus : **http://127.0.0.1:8000/health**

La route `/health` indique uniquement que le processus répond ; elle ne teste pas entièrement la base de données, les fichiers ou le modèle d'embeddings.

### 7.7 Mode développement avec deux terminaux (facultatif)

Démarrer FastAPI comme ci-dessus dans un premier terminal. Dans un **second** terminal à la racine :

```powershell
npm --prefix .\frontend-web run dev
```

Puis ouvrir **http://127.0.0.1:5173/**. Le serveur Vite relaie `/analysis` et `/health` vers FastAPI sur `127.0.0.1:8000`, évitant une configuration CORS permissive pour le développement.

**Les deux terminaux doivent rester ouverts** pendant l'utilisation de ce mode. Après le build de production, un seul serveur FastAPI suffit pour la démonstration locale compilée.

### 7.8 Ancienne interface Streamlit (V1 uniquement)

Le prototype V1 utilisait deux services, FastAPI et Streamlit. La commande historique était :

```powershell
.\.venv\Scripts\python.exe -m streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501
```

Adresse historique : **http://127.0.0.1:8501/**. Cette interface est **héritée** et ne représente pas la démonstration V2 attendue. La conserver dans le dépôt est facultatif selon la stratégie de nettoyage, mais ne pas la présenter comme point d'entrée principal de la V2.

### 7.9 Tests de bon démarrage

1. Vérifier que l'API répond sur `/health`.
2. Ouvrir l'interface React et choisir `SIM-B-0002`.
3. Exécuter les deux scénarios de la section 3.
4. Vérifier les avis, les citations des **conditions générales et particulières** et les aperçus surlignés.
5. Tester une police inexistante via l'API : aucun document d'une autre police ne doit être retourné.

Une installation Windows **neuve et isolée de la V2** reste à revalider avant de déclarer le dépôt entièrement reproductible. Une telle installation avait été vérifiée pour la **V1** antérieure, mais elle ne se substitue pas à une validation V2.

---

## 8. API FastAPI

### 8.1 Routes exposées

| Méthode | Endpoint | Rôle |
|---|---|---|
| `GET` | `/health` | Santé minimale du processus |
| `POST` | `/analysis/dossier` | Dossier de preuves contractuelles, sans verdict |
| `POST` | `/analysis/decision` | Dossier et avis indicatif motivé |
| `POST` | `/analysis/preview` | Rendu PNG d'une page PDF avec surlignage, après contrôles serveur |

### 8.2 Exemple de demande d'analyse

```json
{
  "policy_number": "SIM-B-0002",
  "query": "Ma table de jardin a été endommagée. Suis-je couvert ?",
  "limit": 10
}
```

La requête est validée par `DossierRequest` :

- `policy_number` : chaîne non vide, au plus **64 caractères**.
- `query` : chaîne non vide, au plus **1 000 caractères**.
- `limit` : entier strict entre **1 et 50** ; valeur par défaut **10**.
- Les champs inattendus sont rejetés ; les données incorrectes peuvent produire une erreur `422`.
- Une police inconnue donne une erreur `404` sur les routes d'analyse.

### 8.3 Structure de la réponse

`POST /analysis/decision` renvoie :

- `dossier` : police, documents, garanties, requête d'origine, requête enrichie, règles d'expansion, lieux non vérifiés et éléments `evidence`.
- `decision` : `status`, `scenario`, `title`, `explanation`, `established_facts`, `missing_information`, `citations` et mention des limites du résultat.

Chaque preuve peut comprendre `evidence_id`, `source_pdf`, `document_reference`, `evidence_type`, `text`, `page_number`, `locations`, `cells`, `score`, `hybrid_score`, `lexical_score`, `semantic_score`, `lexical_rank`, `semantic_rank` et `matched_terms`.

Les trois scores **ne représentent ni des probabilités d'indemnisation ni une confiance juridique calibrée**.

### 8.4 Aperçu PDF

La route `/analysis/preview` reprend les champs de la requête d'analyse et ajoute `evidence_id` :

```json
{
  "policy_number": "SIM-B-0002",
  "query": "Ma table de jardin a été endommagée. Suis-je couvert ?",
  "limit": 10,
  "evidence_id": "IDENTIFIANT_RENVOYÉ_PAR_LE_DOSSIER"
}
```

L'identifiant doit provenir d'une preuve **effectivement retrouvée** dans le dossier ; la route vérifie à nouveau l'accès documentaire, les coordonnées et les pages avant de renvoyer un PNG. Le serveur retourne des erreurs lorsqu'un identifiant ou une source ne peut pas être vérifié. **Aucun chemin PDF absolu envoyé par le navigateur ne doit être accepté.**

---

## 9. Évaluation de la recherche documentaire

### 9.1 Jeux d'évaluation

Les deux fichiers `data/evaluation/retrieval_cases.json` et `data/evaluation/validation_cases.json` forment **24 cas synthétiques d'évaluation**. Ils incluent notamment des exemples d'incendie, dégât des eaux, vol, bris de glace et mobilier de jardin.

Pour chaque cas, une liste de preuves documentaires attendues est comparée aux positions retrouvées par `search_policy_hybrid`. Le **rappel à K (Recall@K)** mesure la proportion des preuves attendues retrouvées parmi les K premiers résultats ; les scénarios participent à une moyenne macro.

### 9.2 Métriques historiques de la V1

Les mesures publiées dans l'ancien README pour l'évaluation d'**octobre 2026** étaient :

| Indicateur | Résultat historique V1 |
|---|---:|
| Recall@3 | 83,33 % |
| Recall@5 | 97,92 % |
| Recall@10 | 100 % |

**Ces chiffres exacts sont historiques** : ils ne doivent pas être présentés comme de nouvelles mesures V2 après les corrections du classement, car ces pourcentages exacts n'ont pas été recalculés dans les sorties fournies.

### 9.3 Vérification V2 du 2 novembre 2026

Les tests actuels de `tests/test_retrieval_evaluation.py` imposent notamment :

- **Recall@5 ≥ 97 %** sur les 24 scénarios ;
- **Recall@10 = 100 %** sur les 24 scénarios ;
- présence de la référence attendue au mobilier de jardin dans le **Top 3** ;
- absence de passages **exclusivement dédiés au vélo** dans les dix résultats d'un scénario ciblé de table de jardin.

**Résultat communiqué : 6 tests d'évaluation réussis** (`6 passed in 54.79s`). Cela confirme le respect de ces seuils sur le corpus, pas une précision parfaite ni l'absence de bruit sur toutes les formulations.

**Attention :** le rappel mesure la présence des éléments attendus, **pas** la pertinence de tous les résultats supplémentaires ni la qualité juridique d'un avis. Le jeu synthétique ne permet pas d'extrapoler des résultats sur des contrats d'assureurs réels ou des centaines de documents inédits.

---

## 10. Tests automatisés et validation

### 10.1 Exécuter les tests

Depuis la racine du projet :

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Avec un environnement préalablement activé :

```powershell
python -m pytest -q
```

Pour les tests du moteur d'avis :

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_decision.py -q
```

Pour les tests d'évaluation documentaire :

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_retrieval_evaluation.py -q
```

Pour compiler React et vérifier TypeScript :

```powershell
npm --prefix .\frontend-web run build
```

### 10.2 Dernière suite complète V2

**Date de validation communiquée : 2 novembre 2026**  
**Environnement : Windows, Python 3.12**

| Résultat | Nombre |
|---|---:|
| Tests Python réussis | **206** |
| Tests ignorés | **1** |
| Tests échoués | **0** |
| Avertissements | **12** |

La dernière exécution a indiqué : `206 passed, 1 skipped, 12 warnings in 116.69s`.

Le test ignoré concerne un scénario de liens symboliques soumis aux permissions Windows. Les avertissements proviennent principalement de dépréciations dans Starlette/httpx, Docling, Pydantic et le traitement OCR ; ils n'ont pas fait échouer les tests. **Ils restent à surveiller lors des mises à jour des dépendances.**

La suite de décision a donné **17 tests réussis**, dont des protections sur les négations et le lien causal. La suite d'évaluation documentaire a donné **6 tests réussis**. Le frontend a compilé sous Vite avec TypeScript sans erreur ; une validation manuelle de plusieurs parcours React / FastAPI a été réalisée sur le poste local.

### 10.3 Périmètre des tests

Les tests existants couvrent notamment :

- L'extraction et l'indexation des six documents synthétiques.
- La vérification des empreintes, le manifeste et la cohérence des exports.
- La création/import non destructif de la base SQLite, ses contraintes et son intégrité.
- L'isolation des documents par police et le rejet des références non autorisées.
- Le contrôle de cohérence des garanties et des documents associés.
- La recherche lexicale et sémantique, l'expansion de requête, le classement et la fusion RRF.
- La provenance des preuves, les passages textuels et les cellules de tableaux.
- La correspondance entre citations, coordonnées et PDF d'origine.
- Les chemins d'accès PDF autorisés et le rendu des pages surlignées.
- Les modèles Pydantic, réponses FastAPI, entrées invalides et polices inconnues.
- Le rejet de scores de recherche non finis et de coordonnées géométriques non finies.
- Les règles contractuelles documentées, les dates hors période, les faits manquants et des conditions contradictoires.
- Des formulations négatives et un contre-exemple de causalité.
- Les 24 scénarios synthétiques de qualité de la recherche.

**Un test réussi n'est pas une certification de sécurité, un avis juridique, une preuve de généralisation ou une garantie d'absence de défauts.**

### 10.4 Historique V1 — conservé à titre de référence

La **V1**, avec frontend Streamlit, avait été validée séparément le 2 novembre 2026 : **188 tests réussis, 1 ignoré, 0 échec, 12 avertissements**. Une installation propre de la V1 dans un dossier Windows indépendant avait aussi été exécutée avec indexation des six PDF, import SQLite et tests réussis. Ces chiffres et cette installation concernent **la V1, pas la V2**.

---

## 11. Performances et consommation de ressources

Les mesures ponctuelles suivantes ont été relevées en **démonstration locale Windows**, après chargement du modèle :

| Mesure | Observation |
|---|---|
| Réponse de `/analysis/decision` | **1,84 s** pour une requête testée |
| Nombre de preuves demandé / retourné | **10 / 10** sur ce test |
| Mémoire résidente du processus Python FastAPI | **1 253 Mo** (environ 1,22 Gio) |
| Calcul de l'embedding de la requête | À la demande |
| Calcul des embeddings des passages | **À nouveau à chaque recherche** dans l'implémentation examinée |
| Chargement du modèle E5 | Une fois par processus, en cache mémoire (`lru_cache`) |

Ces données ne sont **pas** un benchmark représentatif de charge, de démarrage à froid, d'accès concurrents ni de performances cloud. Une machine disposant d'environ **4 Go de RAM** peut constituer un point de départ à évaluer pour une démonstration hébergée, **sans garantie de suffisance** selon le système, le serveur et la concurrence.

L'aperçu PDF reconstruit actuellement le dossier, ce qui peut relancer la recherche et les encodages. Un cache persistant de vecteurs et un index préconstruit amélioreraient les coûts et la montée en charge.

---

## 12. Sécurité et contrôles documentaires

### 12.1 Protections présentes dans le prototype

- Validation des champs par Pydantic (types, longueurs, bornes et rejet des paramètres inattendus).
- Requêtes SQL paramétrées, contraintes d'intégrité et isolation documentaire par police.
- Vérification des références, pages, sources PDF et chemins de fichiers autorisés.
- Contrôle des empreintes et tailles des fichiers du corpus via manifeste SHA-256.
- Refus d'ouvrir des chemins PDF non autorisés ou de citer un passage qui ne correspond pas à la source attendue.
- Vérification des preuves récupérées et de leur provenance avant de générer une prévisualisation.
- Conservation d'une sortie structurée et explicable ; réponse indéterminée lorsqu'un contrôle essentiel échoue.
- Rejet des nombres non finis dans les scores et coordonnées soumis aux validations correspondantes.
- Initialisation de SQLite sans remplacement silencieux d'une base existante.
- Frontend de développement configuré avec un proxy local ; interface compilée servie par FastAPI sur la même origine.
- `debug=False` pour l'instance FastAPI examinée.

### 12.2 Limites de sécurité et risques ouverts

**Le serveur actuel est conçu pour un environnement local de confiance : il ne doit pas être publié tel quel sur Internet.** Il manque notamment :

- **Authentification utilisateur** et autorisation fondée sur l'identité ; la sélection SQL d'une police n'est pas un contrôle d'accès individuel.
- **Limitation de débit**, quotas, contrôle des coûts et limitation des analyses simultanées consommant CPU et RAM.
- Une stratégie explicite de reverse proxy / HTTPS, filtrage réseau, supervision, journaux sûrs et alertes.
- Des tests de charge et une revue des dépendances, secrets, entrées et surfaces d'attaque avant un service exposé.
- Un cadre de confidentialité et de conformité adapté à de véritables documents d'assurance ; le corpus de démonstration ne doit pas recevoir de données personnelles réelles.

Le fait de n'utiliser que des contrats fictifs limite le risque lié aux contenus du corpus, **mais ne sécurise pas à lui seul une API publique**. Une protection au niveau de l'hébergement pourrait rendre une démonstration accessible à un recruteur, sous réserve de vérifications supplémentaires.

### 12.3 Fichiers exclus de Git

Le `.gitignore` de la V2 prévoit notamment :

```gitignore
.venv/
venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.env
.env.*
!.env.example
*.pem
*.key
*.p12
*.pfx
*.log
.DS_Store
Thumbs.db
data/parsed/
data/processed/
data/embeddings/
*.db
*.sqlite
*.sqlite3
*.db-*
*.sqlite-*
*.sqlite3-*
.streamlit/secrets.toml
frontend-web/node_modules/
frontend-web/dist/
```

Le fichier contient aussi l'exclusion de `.vscode/settings.local.json`. **Vérifier `git status` et `git ls-files` avant de publier** : `.gitignore` n'efface pas automatiquement un secret ou une base qui aurait déjà été ajouté à l'historique Git.

Les **six PDF synthétiques, leur manifeste, le schéma SQLite, les règles manuelles, le frontend, la documentation et les tests** constituent en revanche des ressources pertinentes à conserver dans un dépôt de démonstration.

---

## 13. Limites fonctionnelles connues

ClaimLens AI **ne réalise pas** automatiquement les opérations suivantes :

- Prendre une décision définitive de couverture ou d'indemnisation.
- Accepter/refuser une demande réelle d'assurance, établir une responsabilité ou calculer une indemnité.
- Vérifier dans le monde réel l'authenticité, l'exactitude et l'exhaustivité des faits déclarés.
- Interpréter juridiquement n'importe quelle clause ou gérer les conflits de règles sur tous les produits.
- Extraire et valider automatiquement les règles de centaines de contrats nouveaux.
- Fournir un moteur complet de compréhension des négations, de causalité, de temporalité ou de coréférences en langue naturelle.
- Assurer que toutes les preuves du Top 10 sont pertinentes sur toute formulation (du bruit documentaire subsiste dans certains cas).
- Fournir un contrôle d'accès sécurisé à de véritables dossiers d'assurés.
- Garantir le traitement de PDF arbitraires, dégradés, pivotés ou de mises en page inédites avec la même précision.
- Remplacer un professionnel de l'assurance ou un contrôle humain.

La qualité de recherche dépend de la qualité des extractions, de la disponibilité des fichiers, du corpus indexé et des critères d'évaluation. Les valeurs RRF et de similarité E5 **ne sont pas** des probabilités d'indemnisation.

---

## 14. Industrialisation et évolution vers davantage de contrats

La structure V2 montre comment séparer les données, les documents et l'interprétation, mais **n'implémente pas encore** une chaîne industrielle pour des centaines de contrats.

Une évolution nécessiterait notamment :

1. **Préparation documentaire hors ligne** : extraction incrémentale, contrôle qualité OCR, hachage, versionnement des PDF et historique d'édition.
2. **Référentiel de clauses structuré** : conditions, exclusions, dépendances, périodes de validité et documents de référence, avec une validation métier humaine.
3. **Embeddings persistants** : encoder les passages une fois, les stocker et indexer la recherche vectorielle ; conserver un index lexical adapté (par exemple BM25), toujours filtré par police et édition.
4. **Recherche et reranking évalués** : jeux de pertinence positifs/négatifs, Precision@K en complément du Recall@K, mesure du bruit et suivi des régressions.
5. **Interprétation prudente** : règles versionnées, conflits résolus explicitement, analyse de négation et de causalité vérifiée, abstention lorsqu'une conclusion n'est pas établie.
6. **Sécurité applicative** : authentification, droits sur les contrats, limitation de requêtes, HTTPS, surveillance et audits.
7. **Évaluation de production** : performance à froid et sous charge, tests de panne, reproductibilité de l'installation, traitements des nouvelles pièces et revue juridique/métier.

L'utilisation d'un LLM ne suffirait pas, à elle seule, à garantir la fidélité aux clauses : toute extraction automatique de règles devrait être **contrôlée et approuvée avant d'influencer une décision**.

---

## 15. État de validation et préparation à la diffusion

### 15.1 Vérifications réellement effectuées sur la V2

- Indexation des **six PDF synthétiques** et initialisation SQLite dans le dossier local V2.
- Vérification des trois polices, six documents et garanties importées dans le corpus local.
- Installation du frontend et compilation TypeScript/Vite sans erreur.
- Démarrage de FastAPI et de React, avec communication fonctionnelle dans le navigateur.
- Démonstration des deux scénarios principaux, consultations des CG/CP et aperçus PDF surlignés.
- Vérification de l'étiquetage distinct « Conditions générales » et « Conditions particulières ».
- Tests supplémentaires ayant identifié puis reproduit des erreurs de négation et de lien causal, corrigées sur leurs formulations ciblées.
- Correction lexicale d'un cas de bruit documentaire sur le mobilier de jardin, avec non-régression évaluée sur les cas synthétiques existants.
- Suite complète : **206 tests réussis, 1 ignoré, 12 avertissements** (2 novembre 2026).
- Mesure ponctuelle locale de temps de réponse et de mémoire du processus.

### 15.2 Vérifications restant à effectuer avant une diffusion plus large

- **Installation V2 propre à partir du dépôt ou d'un ZIP final** : installation des dépendances, extraction, import SQLite, build React et tests sur un dossier vierge.
- **Audit du contenu réellement publié** : fichiers suivis par Git, historiques, secrets, données générées, pertinence et actualité des documents `docs/` et `V2_DEV_NOTES.md`.
- Revue finale des dépendances Python/Node et de leurs versions, tests de sécurité et analyse de charge si exposition réseau.
- Vérification complémentaire des décisions sur des formulations nouvelles et de la pertinence des preuves sur les scénarios adversariaux.
- Tests de lisibilité sur petits écrans et navigateurs supplémentaires, si ce périmètre est revendiqué.
- **Déploiement HTTPS**, contrôle d'accès et limitation des requêtes **si** une URL publique ou semi-publique est proposée.

**Aucune URL hébergée n'est fournie par cette documentation.** À défaut de déploiement sûr, le projet doit être partagé sous forme de dépôt/ZIP reproductible, éventuellement avec captures et instructions de démonstration locale. Ne pas laisser croire à une disponibilité en ligne non vérifiée.

### 15.3 Statut de la V1 historique

La **V1** est un prototype Streamlit de recherche documentaire hybride. Elle reste conservée séparément et son ancien bilan de **188 tests réussis, 1 ignoré** est présenté à titre d'historique. La version remise pour la démonstration actuelle doit être **la V2 React**, et non la V1.

---

## 16. Références internes et positionnement

- `docs/architecture.md` — architecture et compromis initiaux de la V2 ; vérifier sa synchronisation avec les évolutions récentes.
- `docs/evaluation.md` — protocole et risques ; les validations indiquées dans la version initiale sont parfois antérieures aux derniers tests.
- `V2_DEV_NOTES.md` — historique de préparation, **pas** le statut actuel de livraison.
- `frontend-web/README.md` — notes de démarrage spécifiques à l'interface React.
- `data/LISEZ_MOI.txt` — origine, usages et limites du corpus synthétique.
- `data/manifest.json` — inventaire et intégrité des six PDF.
- `data/rules/demo_rules.json` — catalogue de règles de démonstration manuelles.

**Positionnement du projet :** démontrer une démarche d'AI engineering fondée sur une extraction documentaire contrôlée, un filtrage SQL du corpus, une recherche hybride évaluée, des références PDF vérifiables, des avis indicatifs explicables et la capacité du système à **ne pas conclure lorsque les preuves manquent**.

**Statut final documenté : ClaimLens AI V2 — prototype local fonctionnel et testé sur corpus synthétique, non qualifié comme service d'assurance public ou moteur généraliste d'indemnisation.**

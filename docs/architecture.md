# Architecture technique — ClaimLens AI V2

## 1. Objet et périmètre

ClaimLens AI V2 est un démonstrateur local d'assistance à l'analyse de contrats d'assurance **synthétiques**. À partir d'un numéro de police et d'une description de sinistre, il assemble les informations structurées du contrat, recherche des preuves dans les PDF autorisés et produit un **avis indicatif fondé sur des règles explicites**. Cet avis n'est ni une décision juridique ni une décision d'indemnisation.

Le système n'utilise **pas de LLM génératif** pour conclure. La composante « IA » correspond principalement à la recherche sémantique par embeddings, associée à une recherche lexicale et à une fusion des classements.

## 2. Vue d'ensemble

```text
Navigateur
   |
   v
Interface React + TypeScript (frontend-web/src/)
   | HTTP : /analysis, /health et consultation de preuves
   v
FastAPI (backend/main.py)
   |-- Schémas Pydantic (backend/schemas.py)
   |-- Assemblage du dossier (backend/analysis/coverage.py)
   |     |-- SQLite : police, garanties, documents autorisés
   |     |-- Recherche hybride : lexical + embeddings E5 + RRF
   |     `-- Vérification et attribution des preuves
   |-- Avis indicatif (backend/analysis/decision.py)
   |     `-- Règles explicites (data/rules/demo_rules.json)
   `-- Accès et aperçu PDF (pdf_access.py, pdf_preview.py, citations.py)

Préparation hors requête : PDF synthétiques
   -> extraction Docling -> exports JSON (data/parsed/)
   -> initialisation/import SQLite (data/claimlens.sqlite3)
```

Cette représentation est fonctionnelle, pas un diagramme exhaustif des imports. Le backend est un ensemble de modules Python dans un même processus FastAPI, et non une architecture de microservices.

## 3. Interface utilisateur et mode d'exécution

La V2 utilise **React, TypeScript et Vite** dans `frontend-web/`. Les principaux fichiers sources sont `src/App.tsx`, `src/main.tsx`, `src/styles.css` et `src/types.ts`.

- **Mode compilé** : `npm --prefix .\frontend-web run build` génère `frontend-web/dist/`. Si ce répertoire est présent, FastAPI sert l'interface sur `http://127.0.0.1:8000/`, sur la même origine que l'API.
- **Mode développement** : `npm --prefix .\frontend-web run dev` démarre Vite sur `http://127.0.0.1:5173/` ; les requêtes `/analysis` et `/health` sont relayées au backend local.
- `frontend/app.py` est l'ancienne interface **Streamlit V1** ; elle ne constitue pas l'entrée principale de V2.

`package.json` et `package-lock.json` doivent être versionnés. `node_modules/` et `dist/` sont régénérables et normalement exclus de Git.

## 4. API et modèles

`backend/main.py` porte l'application FastAPI et les routes d'analyse, de contrôle de disponibilité et de consultation des éléments PDF. Les modèles d'entrée et de sortie sont définis dans `backend/schemas.py` à l'aide de Pydantic. La route `/health` confirme seulement que le processus répond ; elle ne constitue pas un contrôle complet de la base, du modèle sémantique ou du corpus.

Les endpoints liés aux preuves doivent vérifier les identifiants documentaires autorisés : le navigateur ne transmet pas un chemin absolu arbitraire vers un PDF.

## 5. Ingestion des documents

Le corpus comporte **trois polices fictives et six PDF** (trois documents de conditions générales et trois de conditions particulières), décrits par `data/manifest.json` avec des informations de provenance et des empreintes SHA-256.

L'indexeur `backend/ingestion/indexer.py` s'appuie notamment sur `docling_factory.py`, `structured_export.py` et `table_extractor.py` pour transformer les PDF en passages structurés et conserver les références aux pages et zones de preuves. Les exports se trouvent dans `data/parsed/` et sont régénérables. `backend/database/bootstrap.py` prépare ensuite le stockage SQLite à partir du corpus et des exports : ce programme comporte une protection contre l'écrasement d'une base existante.

## 6. Stockage relationnel et périmètre contractuel

SQLite conserve les métadonnées de police, de garanties et les associations entre police et documents. `backend/database/schema.sql` définit les contraintes d'intégrité ; `connection.py`, `importer.py` et `queries.py` assurent l'accès, l'import et les requêtes.

Le choix **SQL-first** limite les documents candidats à ceux associés à la police sélectionnée avant la recherche documentaire. Ce cloisonnement fonctionnel empêche normalement de mélanger les preuves de polices différentes. Il **ne remplace pas** une authentification ni un contrôle d'accès lié à l'identité de l'utilisateur.

## 7. Recherche documentaire hybride

Les principaux modules sont :

- `backend/retrieval/search.py` : recherche lexicale et classement fondé sur les termes du texte.
- `backend/retrieval/query_expansion.py` : expansion contrôlée des formulations.
- `backend/retrieval/embeddings.py` et `semantic.py` : représentations vectorielles multilingues E5 et similarité sémantique ; préfixes de type `query:` et `passage:` et vecteurs normalisés de 384 dimensions dans la version documentée.
- `backend/retrieval/fusion.py` : **Weighted Reciprocal Rank Fusion (RRF)** ; paramètres documentés pour la version locale examinée : poids lexical 2, poids sémantique 1 et constante RRF de 60.
- `backend/retrieval/hybrid.py` : orchestration de la recherche dans le périmètre autorisé.

Les scores ordonnent des passages. Ils ne sont **ni des probabilités de garantie ni des probabilités d'indemnisation**. Les paramètres mentionnés doivent être revérifiés dans le code si le moteur est modifié.

## 8. Assemblage du dossier et avis indicatif

`backend/analysis/coverage.py` assemble les informations contractuelles, les garanties et les preuves pertinentes. Les références de preuve sont associées à leur document, leur page et, lorsque disponibles, leurs coordonnées.

La nouveauté V2 est `backend/analysis/decision.py`, qui utilise des règles explicites stockées dans `data/rules/demo_rules.json` pour établir un **avis de démonstration** à partir des éléments structurés et de la description du sinistre. Les contrôles de formulations négatives et de causalité font partie des cas testés. L'avis dépend des hypothèses et limites des règles ; une preuve bien classée ne suffit pas à décider de la prise en charge.

Aucun LLM génératif ne produit de verdict, et l'application ne remplace pas une instruction humaine du sinistre.

## 9. Traçabilité et visualisation PDF

Les modules `backend/analysis/citations.py`, `pdf_access.py` et `pdf_preview.py` assurent l'identification des preuves, la vérification des chemins et l'aperçu surligné. Le rendu exploite les informations de page et de coordonnées conservées lors de l'extraction, avec des contrôles sur le périmètre documentaire et les paramètres de rendu.

Une preuve affichée doit pouvoir être rattachée à un document autorisé et vérifiable. L'identifiant d'une preuve ne doit pas être traité comme un mécanisme d'authentification.

## 10. Tests et reproductibilité

Les tests Python se trouvent dans `tests/` ; ils couvrent notamment les schémas, l'import, les contraintes SQL, la recherche, la sécurité d'accès aux PDF, les prévisualisations et le moteur d'avis. Les cas de recherche sont dans `data/evaluation/`.

Dernière validation **communiquée** le 2 novembre 2026 : **206 tests réussis, 1 ignoré, 12 avertissements et 0 échec** (`206 passed, 1 skipped, 12 warnings in 116.69s`). La compilation TypeScript/Vite a également été rapportée comme réussie. Ces résultats ne représentent pas une nouvelle exécution au moment de la rédaction de ce document.

Commandes principales depuis la racine sous Windows :

```powershell
.\.venv\Scripts\python.exe -m backend.ingestion.indexer
.\.venv\Scripts\python.exe -m backend.database.bootstrap
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix .\frontend-web install
npm --prefix .\frontend-web run build
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

**Attention :** ne pas relancer `bootstrap` sans tenir compte de la base déjà initialisée. Les étapes initiales présupposent l'installation des dépendances Python et la présence du corpus. Les répertoires `.venv/`, `frontend-web/node_modules/`, `frontend-web/dist/`, `data/parsed/` et le fichier SQLite local sont des artefacts régénérables à exclure normalement de Git.

## 11. Limites et perspectives

- Prototype local sur données synthétiques, **sans authentification ni autorisation par utilisateur** ; non destiné à une exposition publique ou à des données assurantielles réelles.
- L'analyse documentaire peut retourner des passages hors sujet ; des cas de bruit résiduel ont été constatés sur des formulations nouvelles.
- Les scénarios d'évaluation sont limités et ne valident ni la généralisation à d'autres assureurs ni la qualité juridique des avis.
- Les embeddings peuvent induire une latence ; un index vectoriel pré-calculé, du cache et des mesures de performance seraient nécessaires pour un changement d'échelle.
- Avant toute exploitation réelle : contrôle d'accès par identité, sécurité réseau, confidentialité, journalisation, tests de robustesse et évaluation indépendante.

## 12. Statut documentaire

Ce document décrit l'architecture **V2 telle que rapportée dans le dernier README du projet**. Les chemins, paramètres et résultats devront être comparés au dépôt Git final avant publication. Il ne constitue pas un audit indépendant du code ni une certification de sécurité.

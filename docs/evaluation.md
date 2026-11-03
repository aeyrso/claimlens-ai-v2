# Évaluation et validation — ClaimLens AI V2

## 1. Objet

Cette note présente les protocoles d'évaluation, les métriques documentées et les validations communiquées pour **ClaimLens AI V2**. Elle distingue les mesures historiques V1, les critères effectivement testés en V2 et les limites d'interprétation.

ClaimLens AI est un démonstrateur local sur **contrats d'assurance synthétiques**. La recherche documentaire, l'assemblage de preuves et l'avis indicatif par règles doivent être évalués séparément. Aucun taux de réussite de tests ne constitue une garantie de qualité juridique ou une preuve d'aptitude à la production.

## 2. Corpus d'évaluation

Le corpus contient trois polices fictives et six PDF (trois conditions générales et trois conditions particulières). Les données de recherche sont consignées dans :

- `data/evaluation/retrieval_cases.json`
- `data/evaluation/validation_cases.json`

Ces deux fichiers rassemblent **24 scénarios synthétiques**, couvrant notamment incendie, dégâts des eaux, vol, bris de glace et mobilier de jardin. Les scénarios répertorient des identifiants de preuves attendues afin de comparer les résultats produits par la recherche hybride aux références cibles.

Le corpus de test est limité et n'est pas un jeu indépendant de nouveaux contrats d'assureurs.

## 3. Mesure de la qualité de recherche

Pour un cas donné :

```text
Recall@K(cas) = nombre de preuves attendues présentes dans les K premiers résultats
                 / nombre total de preuves attendues pour ce cas

Recall@K macro = moyenne des Recall@K(cas) sur les scénarios
```

La moyenne est effectuée par scénario : chaque scénario pèse autant, indépendamment du nombre de preuves attendues. Les identifiants de preuve sont recherchés dans le classement produit par le moteur hybride, avec un périmètre documentaire restreint à la police.

Le **Recall@K mesure le rappel des preuves attendues**. Il ne mesure pas directement la précision des résultats, la part des passages hors sujet, la fidélité d'une éventuelle interprétation, la qualité juridique de l'avis ou la pertinence sur des contrats inédits.

## 4. Mesures historiques V1 — ne pas attribuer à la V2

| Indicateur | Valeur historique V1 |
|---|---:|
| Recall@3 | 83,33 % |
| Recall@5 | 97,92 % |
| Recall@10 | 100 % |

Ces chiffres sont issus de l'évaluation V1 signalée pour **octobre 2026**. Ils restent des repères historiques ; les sorties de vérification V2 consultées ne fournissent pas de nouveaux pourcentages exacts équivalents. **Ne pas les présenter comme de nouvelles mesures V2.**

## 5. Critères de validation V2 communiqués le 2 novembre 2026

`tests/test_retrieval_evaluation.py` impose notamment :

1. **Recall@5 ≥ 97 %** sur le jeu des 24 scénarios.
2. **Recall@10 = 100 %** sur le même jeu.
3. Présence d'une référence attendue au mobilier de jardin dans le **Top 3** du scénario ciblé.
4. Absence de passages **exclusivement consacrés au vélo** dans le Top 10 du scénario ciblé de table de jardin.

Dernier résultat communiqué pour ce module : **6 tests réussis** (`6 passed in 54.79s`). Il confirme que les critères de tests précédents ont été satisfaits lors de cette exécution, mais ne démontre pas une précision parfaite sur des questions inédites.

Une limite qualitative connue demeure : certaines nouvelles formulations peuvent produire des preuves faibles ou hors sujet. Le filtrage a corrigé un cas ciblé lié à la table de jardin, mais d'autres formulations causales peuvent encore faire remonter des passages relatifs au vélo.

## 6. Validation de l'avis indicatif par règles

La V2 ajoute un moteur d'avis dans `backend/analysis/decision.py`, reposant sur `data/rules/demo_rules.json` et des contrôles explicites plutôt que sur une génération libre de texte par LLM.

La suite `tests/test_decision.py` a obtenu **17 tests réussis**, y compris des scénarios portant sur les négations et le lien causal. Ce résultat atteste la conformité aux exemples spécifiés dans les tests ; il ne constitue pas une validation actuarielle ou juridique indépendante, ni une mesure de précision métier sur un échantillon représentatif.

Pour aller plus loin, il faudrait annoter indépendamment des scénarios positifs, négatifs, ambigus et contradictoires, puis mesurer les erreurs d'avis par type de garantie et circonstance.

## 7. Résultats de validation de la V2

### 7.1 Première validation — 2 novembre 2026

Une première exécution complète des tests avait donné les résultats suivants :

| Indicateur | Résultat |
|---|---:|
| Tests Python réussis | 206 |
| Tests ignorés | 1 |
| Tests échoués | 0 |
| Avertissements | 12 |

Sortie rapportée :

```text
206 passed, 1 skipped, 12 warnings in 116.69s
```

### 7.2 Installation indépendante — 3 novembre 2026

Une nouvelle validation a été effectuée à partir du commit Git `5cfbb85`, dans une copie propre créée avec `git clone`.

**Environnement :** Windows, Python 3.12.10 et environnement virtuel indépendant.

Les opérations suivantes ont réussi :

- Installation des dépendances Python et vérification `pip check` : aucune incompatibilité détectée.
- Indexation des six contrats PDF synthétiques : six exports générés.
- Initialisation SQLite : trois polices, six documents et douze garanties.
- Exécution de la suite complète Python.
- Installation du frontend avec `npm ci` : 70 packages installés et aucune vulnérabilité signalée par npm.
- Compilation TypeScript et Vite : réussie, avec 1 579 modules transformés.
- Démarrage de FastAPI et affichage de l'interface React compilée.
- Vérification manuelle d'un scénario d'analyse de sinistre avec avis indicatif, dix preuves documentaires et aperçu PDF surligné.

**Résultat de la nouvelle exécution Python :**

```text
206 passed, 1 skipped, 12 warnings in 117.38s
```

Les 206 tests ont réussi, aucun n'a échoué et un test a été ignoré.

Le test ignoré concerne un scénario de lien symbolique soumis aux permissions Windows. Les avertissements sont principalement liés à des fonctionnalités dépréciées dans certaines dépendances, notamment Starlette/httpx, Docling, Pydantic et les composants OCR.

### 7.3 Interprétation

Cette seconde validation confirme que ClaimLens AI V2 peut être reconstruit, testé et exécuté sur l'environnement Windows utilisé, à partir des sources enregistrées dans Git.

Elle ne démontre pas une reproductibilité universelle sur tous les systèmes d'exploitation, ni une aptitude à la production.

Les tests automatisés vérifient des comportements définis, mais ne constituent pas une validation indépendante de la qualité juridique des avis, de la pertinence documentaire sur des contrats réels ou de la sécurité d'un service exposé sur Internet.

## 8. Commandes de reproduction

Exécuter depuis la racine du projet sous Windows, après installation des dépendances et préparation du corpus :

```powershell
# Suite complète Python
.\.venv\Scripts\python.exe -m pytest -q

# Recherche documentaire
.\.venv\Scripts\python.exe -m pytest tests/test_retrieval_evaluation.py -q

# Avis indicatif
.\.venv\Scripts\python.exe -m pytest tests/test_decision.py -q

# Compilation React + vérification TypeScript
npm --prefix .\frontend-web run build
```

Pour refaire une installation complète, suivre la procédure du README V2, notamment l'indexation et l'initialisation SQLite. **Ne pas lancer aveuglément l'initialisation sur une base déjà existante** : la procédure est volontairement non destructive.

En cas de modification du corpus, des règles, du moteur de classement, des dépendances ou des tests, archiver les nouvelles sorties et dater les nouvelles mesures au lieu de conserver les chiffres historiques comme s'ils étaient inchangés.

## 9. Couverture des validations et limites

Les suites automatisées incluent notamment des contrôles d'intégrité d'import, de schémas de données, de périmètre SQL, de recherche lexicale et sémantique, de références et d'accès aux PDF ainsi que des régressions sur les avis.

Elles ne remplacent pas :

- une mesure systématique de précision (Precision@K), de classement (MRR/nDCG), de taux de passages hors sujet et de qualité des citations ;
- une évaluation sur des contrats inédits annotés indépendamment, incluant scans, tableaux complexes et erreurs OCR ;
- une analyse de robustesse aux formulations négatives, ambiguës ou adversariales ;
- une évaluation métier de l'avis par des spécialistes de l'assurance ;
- des mesures de latence, consommation mémoire, charge et résilience ;
- des audits de sécurité, de confidentialité et d'autorisation fondés sur des identités réelles.

Le numéro de police sert à définir le périmètre documentaire de ce prototype, **pas à authentifier un utilisateur**. Les tests de cloisonnement ne permettent donc pas de revendiquer une sécurité de production.

## 10. Priorités de prochaine évaluation

1. Constituer un jeu de contrats et de questions **nouveaux**, séparé des exemples de développement.
2. Mesurer simultanément Recall@K, Precision@K, nDCG/MRR et le taux de preuves hors sujet.
3. Évaluer les avis sur des scénarios annotés indépendamment, notamment les exclusions, les négations et les causalités.
4. Chronométrer ingestion, démarrage du modèle, requêtes répétées et génération d'aperçus PDF.
5. Ajouter des tests de sécurité et des validations sur des documents non fiables avant tout élargissement du périmètre.

## 11. Conclusion

ClaimLens AI V2 dispose d'un socle de tests automatisés couvrant notamment l'intégrité des données, la recherche documentaire hybride, le périmètre contractuel, les preuves PDF et le moteur d'avis indicatif.

Une première validation a été réalisée le **2 novembre 2026**, puis confirmée le **3 novembre 2026** dans une installation indépendante reconstruite à partir du dépôt Git.

La dernière exécution complète a donné les résultats suivants : **206 tests réussis, 1 ignoré, 0 échec et 12 avertissements**.

L'installation des dépendances, l'indexation des six PDF, l'initialisation SQLite, la compilation React et un scénario d'analyse avec visualisation des preuves ont également été vérifiés.

Ces résultats démontrent le bon fonctionnement du prototype sur l'environnement Windows testé. Ils ne constituent pas une validation de production, une évaluation juridique des avis ou une garantie de généralisation à des contrats réels.

Les prochaines priorités concernent l'évaluation indépendante de la pertinence documentaire, la robustesse du moteur d'avis, les performances et la sécurité.

**ClaimLens AI V2 reste un démonstrateur technique local utilisant exclusivement des données synthétiques.**
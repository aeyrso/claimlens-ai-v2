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

## 7. Résultat de la suite complète V2

**Validation communiquée : 2 novembre 2026 — Windows, Python 3.12.**

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

Le test ignoré porte sur un cas de lien symbolique soumis aux permissions Windows. Les avertissements sont essentiellement associés à des dépréciations de dépendances (dont Starlette/httpx, Docling, Pydantic et traitements OCR) et restent à surveiller. Le frontend React/TypeScript a été compilé avec Vite sans erreur, et plusieurs parcours React/FastAPI ont été vérifiés manuellement sur le poste local.

Ces résultats sont **rapportés à partir du README V2** ; la présente note ne prétend pas avoir exécuté de nouveaux tests.

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

La V2 dispose d'un socle de tests automatisés significatif et de seuils de rappel vérifiés sur son corpus synthétique. Les **206 tests réussis** témoignent de l'état de validation rapporté le 2 novembre 2026, **pas** d'une validation de production. La priorité est désormais la mesure indépendante de la pertinence, des erreurs d'avis et de la robustesse sur des données non vues.

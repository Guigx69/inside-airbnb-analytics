# Audit de livraison — 12 octobre 2026

## Synthèse

**Objectif :** transmettre un dépôt exploitable, lisible en français, sans prétendre que le compte du responsable a été déployé.

### Constats confirmés

| Contrôle | Constat | Traitement |
|---|---|---|
| README | En anglais et ancien résultat (445 tests) | Réécrit en français, benchmark V1.3 exact |
| Guide V1.3 | Mentionne encore la branche et PR #3 avant fusion | Statut et commandes corrigés |
| Dépendances | `requirements-dev.txt` présent ; dbt-core 1.12.4 fixé, dbt-snowflake non fixé | Version validée 1.12.1 documentée ; verrouillage complet à réaliser avant livraison reproductible |
| Manifeste `main` | 1 629 lignes de données depuis le commit `167cc5f` | Écart résolu : trois nouvelles archives Lyon du 17/09/2026, committées et poussées sur `main` |
| Lyon dans le manifeste `main` | 15 archives, 5 dates, 3 types par date sur `main` | Périmètre de départ confirmé sur GitHub |
| Orchestration | `run_pipeline.py` propose un mode aperçu par défaut | Préserver ; le dry-run RAW se connecte à Snowflake |
| Infrastructure Snowflake | Scripts de bootstrap sur PR #5 | Pas encore fusionnés ni testés sur un compte vierge |
| Documentation des deux scénarios | PR #4 | À rapprocher du guide français et du bootstrap |
| Workflow CI | Aucun `.github/workflows/ci.yml` trouvé | Contrôles Python hors réseau ajoutés dans cette PR |

### Historique Lyon présent dans `main`

- 2025-09-18 : listings, calendar, reviews
- 2025-12-22 : listings, calendar, reviews
- 2026-03-25 : listings, calendar, reviews
- 2026-06-22 : listings, calendar, reviews

La cinquième date (2026-09-17, trois fichiers) a été confirmée par `git diff`, puis publiée sur `main` au commit `167cc5f`. Les cinq dates de `main` sont présentes dans le **manifeste GitHub**, pas dans les archives elles-mêmes. L'utilisateur a effectué séparément un contrôle local SHA-256 réussi sur 1 629 archives. La synchronisation du manifeste a été effectuée par commit ciblé, sans remplacement aveugle ni modification des archives.

### Nettoyage du dépôt — politique

- Conserver le code métier, les modèles, les tests et les scripts expérimentaux sur leurs branches respectives.
- Ne pas supprimer de fichiers sur simple présomption d'inutilité.
- Ne pas versionner les 35,16 Gio d'archives ni les mots de passe.
- Conserver les PR #4, #5 et #6 distinctes jusqu'à revue des dépendances ; **aucune fusion automatique**.
- La documentation utilisateur est rédigée en français ; les noms de fichiers, variables d'environnement, identifiants SQL et commandes conservent leur orthographe technique.

### Contrôles de qualité ajoutés

Le workflow `verification-hors-ligne.yml` installe uniquement `country_converter` pour les tests géographiques, puis exécute `python -m compileall` et les tests Python `unittest` dans GitHub Actions, sans accès Snowflake. Il ne valide pas l'ingestion réelle, le dbt build ou le provisionnement d'un compte vierge. Les résultats de ce workflow doivent être consultés après ouverture de la PR.

### Risques ouverts

1. **Statut manifeste Git/local :** 1 629 entrées GitHub après le push du commit `167cc5f`, correspondant aux 1 629 archives vérifiées localement. Le `git diff` initial identifiait trois ajouts, sans suppression ni modification : `data/raw/france/lyon/2026-09-17/{calendar,listings,reviews}.csv.gz`. L'outil de comparaison **en lecture seule** `python scripts/comparer_manifestes.py --reference origin/main` reste disponible. Les trois archives sont vérifiées localement par SHA-256, mais leur ingestion et leurs transformations dbt ne sont pas validées.
2. **Dépendances Python :** absence de lock complet ; les nouvelles installations peuvent résoudre d'autres versions de `dbt-snowflake`.
3. **Compte vierge :** absence de test réel des scripts SQL, des rôles, du warehouse et des données.
4. **Accès du responsable :** droits de lecture des marts, Streamlit et éventuels objets BI à définir selon le besoin.
5. **Conservation :** les archives locales n'ont pas de seconde sauvegarde confirmée.

### Critère de clôture

Une PR n'est « prête » que lorsque les tests pertinents passent, les commandes sont relues, les secrets sont absents et les limites non testées sont explicites. La réussite du build V1.3 de développement ne vaut pas homologation de l'environnement du responsable.

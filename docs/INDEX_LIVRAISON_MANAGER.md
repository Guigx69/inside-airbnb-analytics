# Index de livraison au manager — Inside Airbnb V1.3

## Ordre de lecture et d'exécution

1. **[Manuel manager A à Z](MANUEL_MANAGER_A_Z.md)** — point d'entrée unique : installation, configuration, scénarios A/B, lancement, helpers, diagnostics et réception.
2. **[Guide d'exploitation](guide_livraison_fr.md)** — contexte, sécurité, contraintes et références de validation.
3. **[Déploiement V1.3](v1_3_manager_deployment.md)** — benchmark, modèles et particularités dbt.
4. **[Contrôle RAW Lyon](controle_raw_lyon_2026-10-12.md)** — preuve des cinq snapshots et des 15 lots sur le compte source.
5. **[Audit de livraison](audit_livraison_2026-10-12.md)** — statut vérifié et limites.
6. **[Scénarios de déploiement](manager_deployment_two_scenarios.md)** — document de la PR #4, non encore intégré à cette branche.
7. **[Bootstrap compte vierge](bootstrap_manager_lyon.md)** — document de la PR #5, non encore intégré à cette branche.

## Scripts et aides

| Chemin | Usage | Risque |
|---|---|---|
| `scripts/check_archives.py` | Vérifie tailles et SHA-256 des archives | Lecture locale seule |
| `scripts/download_inside_airbnb.py` | Découvre / synchronise les archives depuis la source | Téléchargement et mise à jour du manifeste avec `--sync` |
| `scripts/load_raw_to_snowflake.py` | Compare journal/RAW puis charge les lots manquants | Écritures Snowflake hors `--dry-run` |
| `scripts/run_pipeline.py` | Enchaîne collecte, vérification, RAW et dbt facultatif | `--execute` autorise les écritures RAW |
| `scripts/comparer_manifestes.py` | Compare les versions du manifeste | Lecture seule |
| `config/geography.lyon.example.json` | Exemple de sélection Lyon | Vérifier le périmètre avant exécution |
| `sql/bootstrap_manager_*.sql` | Provisionnement du compte Snowflake neuf | PR #5, DDL/grants, revue admin requise |

## Situation de livraison

- `main` contient V1.3 et le manifeste à 1 629 entrées (commit `167cc5f`).
- Les archives CSV.GZ sont stockées localement, pas dans GitHub ; copie indépendante encore à organiser.
- Le compte Snowflake source contient cinq snapshots Lyon journalisés et 17 692 229 lignes RAW Lyon ; la fraîcheur des marts après le dernier snapshot n'est pas établie.
- La validation dbt de référence date du 9 octobre 2026 : 480 PASS, 1 WARN, 0 ERROR.
- Les PR #4, #5 et #6 doivent être relues et intégrées explicitement avant de considérer `main` comme une livraison documentaire complète.
- Le bootstrap d'un compte vierge et le déploiement chez le manager ne sont pas encore testés.

## Condition de réception

Le manager doit pouvoir : installer le projet, renseigner les secrets hors Git, confirmer le périmètre et les droits, sélectionner le scénario A ou B, exécuter les contrôles préalables, lancer un pilote si nécessaire, construire dbt avec accord de coût, consulter les marts, diagnostiquer un échec et conserver les preuves d'exécution. Les étapes non vérifiées doivent être signalées, pas présumées réussies.

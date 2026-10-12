# Initialiser un environnement RAW Snowflake neuf

Le fichier `sql/bootstrap_raw.sql` prépare le schéma RAW minimal, les trois tables sources contenant des données `VARIANT`, le journal d'ingestion et le stage interne requis par `scripts/load_raw_to_snowflake.py`.

**Ce n'est pas un installateur automatique.** Il suppose une base `AIRBNB` existante, un entrepôt dimensionné et des rôles déjà configurés. Adapter les identifiants avant exécution dans un autre compte. Exécuter uniquement dans un environnement neuf dédié avec les droits DDL autorisés. `IF NOT EXISTS` évite la suppression d'objets existants, mais ne répare pas une structure incompatible.

Le rôle d'ingestion doit disposer de `USAGE` sur base, schéma et entrepôt, des droits DML sur RAW et le journal, et des autorisations sur le stage. Le rôle dbt doit lire RAW et pouvoir créer ses schémas et modèles. **Les droits dépendent de l'environnement et ne sont pas accordés par ce script.**

## Dépendance aux archives

Le dépôt Git ne contient pas `data/raw`. Les chemins d'archives sélectionnés dans `data_manifest.csv` doivent exister localement avec la taille et l'empreinte SHA-256 attendues. Le collecteur `scripts/download_inside_airbnb.py` découvre les snapshots encore publiés, télécharge une sélection et met à jour le manifeste. Les archives historiques sorties du catalogue doivent être conservées séparément.

Le chargeur filtre le manifeste **avant** la validation des archives : un chargement limité à une ville et une date n'exige que les fichiers correspondants. Le pilote Lyon du 17/09/2026 a été vérifié sur le compte de développement ; la restauration historique intégrale et le déploiement sur compte vierge restent non validés.

## Ordre d'exécution contrôlé

1. Vérifier les identifiants, rôles, coûts de calcul et volumes attendus.
2. Exécuter `sql/bootstrap_raw.sql` sur une nouvelle base Snowflake adaptée.
3. Accorder les droits nécessaires et contrôler les objets créés.
4. Restaurer puis vérifier les archives dans `data/raw`.
5. Exporter les variables d'environnement d'ingestion de manière sécurisée ; `.env` n'est pas chargé automatiquement.
6. Lancer `python scripts/load_raw_to_snowflake.py --dry-run`, examiner le plan, puis n'autoriser le chargement réel qu'après validation.
7. Configurer `~/.dbt/profiles.yml` et les variables sources RAW ; exécuter `dbt debug`, `dbt parse`, `dbt compile`, puis un build autorisé.

**Le bootstrap RAW et la procédure d'ingestion ne sont pas encore validés sur un compte Snowflake vierge.** Ne pas les présenter comme un déploiement opérationnel en un clic.

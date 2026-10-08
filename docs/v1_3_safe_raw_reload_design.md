# V1.3 — Conception du rechargement RAW sécurisé

Statut : **conception uniquement — aucune exécution de remplacement autorisée**.

## 1. Périmètre et invariants

Clé physique de lot : `(SOURCE_COUNTRY, SOURCE_CITY, SNAPSHOT_DATE, SOURCE_FILE, TARGET_TABLE)`.
Un seul lot peut être remplacé par opération ; `TARGET_TABLE` est choisi exclusivement dans la liste blanche `FILE_TO_TABLE`.

Invariants :
- Ne jamais modifier RAW pour un fichier dont le SHA-256 historique est `NULL` sans décision explicite et procédure de certification séparée.
- Ne jamais inférer le SHA-256 original à partir du `RAW_DATA` JSON ; l'audit logique ne prouve pas l'identité binaire CSV.GZ.
- Refuser toute incohérence `RAW / INGESTION_LOG`, doublon de journal ou lot RAW orphelin.
- Vérifier à nouveau taille et SHA-256 du fichier local juste avant la préparation, et empêcher qu'il change entre la vérification et la conversion (copie immuable vérifiée, ou seconde vérification).
- Exiger `--allow-replace` explicite, une sélection d'un seul fichier et un plan de remplacement actualisé ; le mode par défaut reste **read-only**.
- Ne pas recharger automatiquement sur différence d'empreinte.
- Ne pas toucher à `data_manifest.csv` localement ni réécrire des données historiques par défaut.

## 2. Machine à états

| Statut du plan | Action |
| --- | --- |
| `UNCHANGED` | Ignorer |
| `NEW` | Flux d'ingestion existant, sans remplacement |
| `RELOAD_CANDIDATE` | Autoriser seulement une préparation, puis confirmation explicite |
| `LEGACY_UNCERTIFIED` | Bloquer le remplacement ; audit logique et décision métier distincts |
| `BLOCKED_RAW_ORPHAN` | Bloquer |
| `BLOCKED_COUNT_MISMATCH` | Bloquer |

Le planificateur actuel fournit des **candidats** d'impact dbt, pas un graphe exhaustif de dépendances. Aucun déclenchement automatique de dbt avant validation de ce graphe.

## 3. Algorithme de remplacement proposé

1. Acquérir un verrou applicatif inter-processus pour la clé de lot ; **ce verrou local ne protège pas des exécutions depuis une autre machine**. Avant production, imposer un mécanisme distribué / une exécution unique côté plateforme, ou une procédure stockée avec garde-fous transactionnels testés.
2. Charger `INGESTION_LOG` et vérifier l'état réel du lot RAW ; refuser si le SHA-256 a changé depuis le plan. Les contrôles doivent être répétés dans la phase critique pour réduire le risque de concurrence.
3. Vérifier le fichier local contre le manifeste, puis convertir en JSON.GZ dans un répertoire de travail isolé. Vérifier le contenu converti et son nombre de lignes.
4. Créer une table de préparation dédiée (structure compatible RAW). Exécuter `PUT` puis `COPY INTO` **dans cette table de préparation uniquement**, avant toute transaction de remplacement ; vérifier `COPY`, `COUNT(*)`, la clé de partition et, si nécessaire, l'équivalence logique avec le fichier source.
5. Après préparation, démarrer une transaction explicite **sans DDL ni COPY** dans la section critique. Vérifier à nouveau la version du journal sous contrôle de concurrence, puis effectuer dans la même transaction :
   - `DELETE` ciblé de l'ancien lot RAW ;
   - `INSERT INTO RAW (...) SELECT ... FROM staging_table` ;
   - validation des nombres de lignes et de la clé du lot ;
   - `UPDATE` ciblé de `INGESTION_LOG` avec nouveau nombre de lignes, `LOADED_AT`, `SOURCE_SHA256` ; contrôler qu'une seule entrée est affectée.
6. `COMMIT` uniquement si toutes les validations réussissent ; sinon `ROLLBACK`.
7. Nettoyer la table de préparation et les objets de stage **après** `COMMIT` ou `ROLLBACK`. Ne jamais exécuter de DDL dans la transaction critique.
8. Après succès, émettre un événement d'invalidation des partitions `(source_country, source_city, snapshot_date)` et un identifiant de transaction ; le recalcul dbt est une étape distincte, contrôlée.

**Attention Snowflake :** les instructions DDL provoquent des commits implicites et certaines opérations de chargement ont des sémantiques transactionnelles spécifiques. La garantie attendue doit être vérifiée par des tests d'intégration isolés, notamment avec autocommit, `COPY`, `DELETE`, `INSERT` et `UPDATE`. Ne pas annoncer une atomicité démontrée avant ces tests.

## 4. Cas d'échec à tester avant activation

- Fichier modifié après calcul de l'empreinte.
- Échec `PUT` ou `COPY` vers la préparation : ancien RAW et journal inchangés.
- Nombre de lignes préparées incorrect ou clé de partition inattendue : refus.
- Échec entre `DELETE` et `INSERT` : `ROLLBACK` vérifié.
- Échec entre `INSERT` RAW et `UPDATE` journal : `ROLLBACK` vérifié.
- Journal modifié simultanément : refuser, sans écraser l'autre exécution.
- Perte de connexion avant `COMMIT` et résultat incertain après `COMMIT` : réconciliation à partir de RAW/journal, pas de répétition aveugle.
- Zéro ligne source, doublons de données, exécution concurrente sur deux machines.
- Vérification que les vues et marts existants restent cohérents tant que dbt n'a pas reconstruit les partitions impactées.

## 5. Points à trancher avant implémentation

1. **Concurrence distribuée :** quelle garantie d'exécution unique existe dans l'environnement cible ?
2. **Politique historique :** autoriser ou non un remplacement exceptionnel d'un lot `SOURCE_SHA256 IS NULL` et selon quelle validation métier ?
3. **Stratégie dbt :** inventaire exhaustif des modèles dépendants, règles d'invalidation et comportement des agrégats historiques.
4. **Traçabilité :** table d'événements d'invalidation et statut `PENDING / REBUILT / FAILED` ; ne pas confondre succès RAW et succès dbt.
5. **Validation transactionnelle :** environnement de test isolé, sans manipulation des lots RAW de production.

## 6. Prochaine livraison recommandée

Implémenter un **simulateur hors Snowflake** et des tests unitaires du planificateur (`NEW`, `UNCHANGED`, `RELOAD_CANDIDATE`, `LEGACY_UNCERTIFIED`, anomalies, zéro ligne), puis un prototype de préparation seule sur table de test isolée. Ne pas ajouter de drapeau `--execute-reload` tant que les tests d'intégration transactionnels et le verrouillage distribué ne sont pas validés.

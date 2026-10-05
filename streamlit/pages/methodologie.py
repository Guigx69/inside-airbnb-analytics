import streamlit as st


st.title("ℹ️ Méthodologie")

st.caption(
    "Sources, périmètre, construction des indicateurs et limites "
    "d'interprétation de l'application Inside Airbnb Analytics."
)

# ============================================================
# Périmètre
# ============================================================

st.header("Périmètre de l'analyse")

st.markdown(
    """
    Cette application analyse l'évolution de l'offre Airbnb sur plusieurs
    territoires à partir d'extractions historiques publiées par
    **Inside Airbnb**.

    Le périmètre actuel couvre :

    - **Lyon** ;
    - **Paris** ;
    - **Bordeaux** ;
    - **Pays Basque** ;
    - **Bruxelles**.

    Chaque territoire dispose de plusieurs **snapshots historiques**.
    Le nombre de dates et leur calendrier peuvent différer selon la
    destination.

    Chaque date constitue un **snapshot indépendant** du marché tel qu'il
    était observable dans les données Inside Airbnb à cette date.

    L'objectif n'est donc pas de reconstituer des transactions Airbnb,
    mais d'analyser l'évolution de l'**offre observable**, des prix,
    de la disponibilité déclarée, de la structure géographique et
    de la structure des hôtes.
    """
)

st.divider()

# ============================================================
# Architecture
# ============================================================

st.header("Architecture des données")

st.markdown(
    """
    Les données suivent une chaîne de transformation complète :

    **Inside Airbnb → Snowflake RAW → dbt → Marts analytiques → Streamlit**

    Les fichiers sources sont d'abord chargés dans une couche **RAW**
    dans Snowflake avec leurs métadonnées d'origine.

    dbt assure ensuite :

    - la normalisation et le typage des données ;
    - la reconstruction des observations historiques ;
    - les contrôles de qualité ;
    - le calcul des métriques intermédiaires ;
    - la production des marts utilisés par cette application.

    L'interface Streamlit interroge uniquement les **marts analytiques**.
    Les données RAW ne sont pas interrogées directement par le dashboard.
    """
)

st.info(
    "La séparation entre ingestion, transformation et restitution permet "
    "de conserver une logique analytique reproductible et testable."
)

st.divider()

# ============================================================
# Snapshots
# ============================================================

st.header("Comment interpréter les snapshots ?")

st.markdown(
    """
    Une annonce présente à une date d'observation est considérée comme
    **observée dans le snapshot**.

    Entre deux snapshots, une annonce peut être :

    - **conservée** : présente dans les deux observations consécutives ;
    - **disparue** : présente dans l'observation précédente mais absente
      de l'observation actuelle ;
    - **nouvellement observée** : observée pour la première fois ;
    - **de retour après absence** : déjà observée historiquement,
      absente d'au moins un snapshot, puis observée de nouveau.

    Cette distinction est essentielle.

    Une hausse du nombre d'annonces entre deux snapshots représente une
    **variation nette de la population observée**.

    Elle ne signifie pas nécessairement qu'un nombre équivalent de nouvelles
    annonces Airbnb a été créé.
    """
)

st.warning(
    "Une absence dans un snapshot ne permet pas, à elle seule, de conclure "
    "qu'une annonce a été définitivement supprimée ou retirée d'Airbnb."
)

st.divider()

# ============================================================
# Prix
# ============================================================

st.header("Prix")

st.markdown(
    """
    Les indicateurs tarifaires sont calculés uniquement pour les annonces
    disposant d'une information de prix exploitable dans le snapshot.

    Les principaux indicateurs présentés sont :

    - le **prix moyen** ;
    - le **prix médian** ;
    - la distribution par tranche de prix ;
    - la couverture tarifaire ;
    - l'évolution du prix des annonces comparables entre deux observations.

    La **couverture tarifaire** correspond à la part des annonces observées
    pour lesquelles un prix est disponible.
    """
)

st.warning(
    "La couverture tarifaire peut varier selon le territoire et le snapshot. "
    "Une observation sans information tarifaire exploitable ne doit pas être "
    "utilisée pour mesurer une évolution de prix."
)

st.markdown(
    """
    Pour étudier les variations tarifaires entre deux observations,
    l'application privilégie les **annonces comparables**, c'est-à-dire
    les annonces présentes dans les deux observations et disposant d'un
    prix dans les deux snapshots.

    Cette approche limite les effets de changement de composition du marché.
    """
)

st.divider()

# ============================================================
# Disponibilité
# ============================================================

st.header("Disponibilité")

st.markdown(
    """
    Les données de calendrier Inside Airbnb indiquent si une date future
    est déclarée comme **disponible** ou **indisponible** pour une annonce.

    L'application reconstruit notamment la disponibilité à :

    - **30 jours** ;
    - **60 jours** ;
    - **90 jours** ;
    - **365 jours**.

    Deux lectures sont distinguées :

    **Disponibilité du marché**

    Elle correspond à la proportion de journées disponibles parmi toutes
    les journées représentées dans le calendrier.

    **Disponibilité médiane des annonces**

    Elle décrit la disponibilité de l'annonce médiane et évite qu'un petit
    nombre d'annonces très disponibles influence excessivement la lecture
    du marché.
    """
)

st.warning(
    "Une journée marquée comme indisponible ne signifie pas nécessairement "
    "qu'elle a été réservée. Elle peut également avoir été bloquée par "
    "l'hôte ou être indisponible pour une autre raison."
)

st.divider()

# ============================================================
# Saisonnalité
# ============================================================

st.header("Saisonnalité du calendrier")

st.markdown(
    """
    La saisonnalité est calculée à partir du calendrier futur visible
    depuis chaque snapshot.

    Certains mois situés au début ou à la fin de la fenêtre de calendrier
    peuvent n'être que **partiellement représentés**.

    L'application expose donc plusieurs indicateurs de couverture :

    - journées représentées ;
    - couverture du calendrier ;
    - part des annonces disposant d'un mois complet ;
    - identification des mois entièrement couverts.

    Les comparaisons saisonnières doivent privilégier les mois bénéficiant
    d'une couverture complète ou quasi complète.
    """
)

st.divider()

# ============================================================
# Quartiers
# ============================================================

st.header("Géographie")

st.markdown(
    """
    L'analyse géographique s'appuie sur le champ **NEIGHBOURHOOD**
    fourni dans les données Inside Airbnb et sur un référentiel
    géographique dédié.

    Le niveau géographique dépend du territoire étudié. Il peut
    correspondre notamment à un **arrondissement**, une **commune**,
    un **quartier** ou un autre découpage disponible dans la source.

    Pour chaque zone, l'application mesure notamment :

    - le nombre d'annonces ;
    - le nombre d'hôtes ;
    - la structure des logements ;
    - les prix disponibles ;
    - la disponibilité ;
    - la part du marché ;
    - les mouvements d'annonces entre observations.

    La cartographie s'appuie sur le référentiel
    **REF_GEOGRAPHIC_AREAS**, qui associe les zones analytiques
    à leurs géométries lorsqu'un référentiel compatible est disponible.

    Les limites représentées correspondent donc au référentiel
    géographique chargé pour le territoire concerné. Leur niveau
    administratif ou analytique peut varier d'une destination à l'autre.
    """
)

st.divider()

# ============================================================
# Hôtes
# ============================================================

st.header("Hôtes et concentration")

st.markdown(
    """
    Un hôte est identifié à partir de son identifiant dans les données
    Inside Airbnb.

    Les hôtes sont notamment distingués entre :

    - **mono-annonce** : une seule annonce observée ;
    - **multi-annonces** : plusieurs annonces observées.

    La concentration du marché est également mesurée à travers la part
    des annonces contrôlées par les **1 %, 5 % et 10 % des hôtes**
    disposant des portefeuilles les plus importants.

    L'application présente également un **indice HHI
    (Herfindahl-Hirschman Index)** construit à partir de la répartition
    des annonces entre les hôtes.
    """
)

st.info(
    "Ces indicateurs décrivent la concentration de l'offre observée. "
    "Ils ne permettent pas, à eux seuls, d'identifier la nature juridique "
    "ou professionnelle d'un hôte."
)

st.divider()

# ============================================================
# Reviews
# ============================================================

st.header("Avis")

st.markdown(
    """
    Les données historiques d'avis permettent de reconstruire le nombre
    d'avis connus à chaque date d'observation.

    L'application distingue les compteurs natifs présents dans les données
    Inside Airbnb des métriques **reconstruites à partir de l'historique
    des avis**.

    Les fenêtres de 30, 90 et 365 jours correspondent au nombre d'avis
    reconstruits sur les périodes précédant chaque snapshot.
    """
)

st.warning(
    "Le nombre d'avis ne correspond pas directement au nombre de séjours. "
    "Tous les voyageurs ne publient pas nécessairement un avis."
)

st.divider()

# ============================================================
# Limites
# ============================================================

st.header("Limites d'interprétation")

st.markdown(
    """
    Les résultats doivent être interprétés en tenant compte de plusieurs
    limites :

    - les données proviennent d'extractions périodiques et non d'un flux
      transactionnel continu ;
    - une annonce absente d'un snapshot n'est pas nécessairement supprimée ;
    - la couverture de certaines variables peut varier entre les snapshots ;
    - la disponibilité déclarée ne constitue pas une mesure directe
      d'occupation ;
    - les avis ne constituent pas un décompte exhaustif des séjours ;
    - les éventuelles estimations d'occupation ou de revenus issues
      d'Inside Airbnb restent des **estimations** et non des transactions
      commerciales observées.
    """
)

st.divider()

# ============================================================
# Qualité des données
# ============================================================

st.header("Qualité et reproductibilité")

st.markdown(
    """
    La couche analytique est construite avec **dbt** et fait l'objet de
    contrôles automatisés portant notamment sur :

    - les clés et la granularité des modèles ;
    - les valeurs nulles ;
    - les relations entre les différentes populations ;
    - les réconciliations entre snapshots ;
    - les agrégations utilisées par les marts.

    Le build dbt complet du POC comporte :

    **25 modèles · 464 tests · 489 éléments exécutés**

    **488 succès · 1 avertissement connu · 0 erreur**
    """
)

st.info(
    "L'avertissement connu concerne le contrôle de cohérence entre "
    "les annonces présentes dans les calendriers et la population "
    "listings correspondante. Ce contrôle reste volontairement non "
    "bloquant afin de conserver explicitement les écarts observés "
    "dans les données sources."
)

st.divider()

# ============================================================
# Stack
# ============================================================

st.header("Stack technique")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Entrepôt", "Snowflake")

with col2:
    st.metric("Transformation", "dbt")

with col3:
    st.metric("Application", "Streamlit")

with col4:
    st.metric("Source", "Inside Airbnb")

st.caption(
    "Inside Airbnb Analytics · POC analytique historique multi-territoires"
)
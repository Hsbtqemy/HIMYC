# Backlog — demandes à lancer plus tard

Ce fichier recense les idées / demandes discutées (brainstorming) pour les implémenter ultérieurement.

**Lors du nettoyage des doc**, utiliser aussi **DOC_NETTOYAGE.md** : ce rituel sert à affiner les items du backlog, à marquer ce qu’on souhaite changer et ce qu’on veut vérifier.

---

## 1. Onglet Corpus — cases à cocher pour la sélection

**Demande :** Pouvoir sélectionner les épisodes via des **cases à cocher** (au lieu ou en complément de la sélection par clic / Shift+Ctrl).

**Pistes :**
- Ajouter une colonne checkbox dans la table (ou une case « tout sélectionner » + cases par ligne).
- Décider : remplacer la sélection actuelle ou la compléter (ex. case « tout » + cases par épisode).
- Exposer les **actions de masse** sur la sélection (lancer pipeline, export, etc.) de façon cohérente.

**Fichiers concernés (à vérifier) :**  
`src/howimetyourcorpus/app/ui_mainwindow.py` (onglet Corpus), `models_qt.py` (EpisodesTableModel).

---

## 2. Onglet Inspecteur — redimensionnement et export

### 2.1 Redimensionner les box

**Demande :** Pouvoir **redimensionner** les zones (transcription, sous-titres, alignement, etc.) comme on souhaite.

**Piste :** Utiliser des **QSplitter** entre les zones avec poignées déplaçables ; optionnel : sauvegarder les proportions (settings).

**Fichiers concernés (à vérifier) :**  
`src/howimetyourcorpus/app/ui_mainwindow.py` — construction de l’onglet Inspecteur.

### 2.2 Exporter les textes segmentés depuis l’Inspecteur

**Demande :** Pouvoir **exporter les textes segmentés** depuis l’onglet Inspecteur (sans passer par l’onglet Corpus / Export).

**Pistes :**
- Format d’export : TXT (un segment par ligne), CSV/TSV (segment + timecodes + langue), SRT-like, etc.
- Périmètre : tout l’épisode affiché ou une sélection future dans l’Inspecteur.
- Un bouton « Exporter les segments » avec choix de format (boîte de dialogue ou menu).

**Fichiers concernés (à vérifier) :**  
`src/howimetyourcorpus/app/ui_mainwindow.py` (Inspecteur), éventuellement `core/export_utils.py` pour réutiliser des helpers.

---

## 3. Alignement sans timecodes

**Contexte :** Aujourd’hui, l’alignement **segment (transcript) ↔ cue EN** se fait par **similarité textuelle** (pas de timecodes). L’alignement **cue EN ↔ cue cible (FR, IT, etc.)** se fait par **recouvrement temporel** (`start_ms` / `end_ms` du SRT). Si on n’a **pas de timecodes** (fichiers “une phrase par ligne” ou SRT sans timings), la partie EN↔cible ne fonctionne plus.

**Pistes à mettre en œuvre :**

1. **Alignement par ordre**  
   Supposer que les deux fichiers sont parallèles (cue 1 EN ↔ cue 1 FR, cue 2 EN ↔ cue 2 FR, …) et créer des paires par indice. Option : activer ce mode si les cues n’ont pas de `start_ms` / `end_ms` (ou si tous à 0).

2. **Alignement EN↔cible par similarité textuelle**  
   Réutiliser la même logique que segment↔EN : comparer le texte de chaque cue EN au texte des cues cible (similarité lexicale / rapidfuzz). Utile quand les timecodes sont absents ou peu fiables.

3. **Format “sans timecodes”**  
   Accepter un format d’import type “une phrase par ligne” (sans timecodes) ; ne faire que segment↔cue EN (et éventuellement EN↔cible par ordre ou par similarité selon la piste choisie).

**Fichiers concernés (à vérifier) :**  
`src/howimetyourcorpus/core/align/aligner.py` (`align_cues_by_time` → fallback), `core/storage/db.py` / parsers SRT (gestion de cues sans `start_ms`/`end_ms`).

---

## 4. Version Mac — programme avec une icône

**Demande :** Proposer une **version Mac** du programme, livrée avec une **icône d’application** (bundle .app avec icône dans le Dock / Finder).

**Pistes :**
- Build PyInstaller (ou équivalent) ciblant macOS (`.app` avec icône personnalisée).
- Créer ou intégrer une icône (icns) pour l’application (Dock, Finder, barre de menu).
- Documenter ou automatiser le build Mac (script ou CI) en cohérence avec les scripts Windows existants dans `scripts/windows/`.

**Fichiers concernés (à vérifier) :**  
`HowIMetYourCorpus.spec` (PyInstaller), éventuellement `.github/workflows/release.yml` pour ajouter un artefact Mac, et nouveau répertoire `scripts/macos/` si besoin.

---

## 5. Workflow — visibilité, enchaînement, retour après action

**Contexte :** Le workflow (Découvrir → Télécharger → Normaliser → Segmenter → SRT → Aligner → Export) n’est pas encore figé ; en parallèle, améliorer la lisibilité et le guidage.

**Pistes :**

- **Visibilité de l’état** — Indicateur global ou checklist du type « épisodes téléchargés / normalisés / segmentés / avec SRT / alignés » pour voir où on en est sans ouvrir chaque onglet.
- **Enchaînement** — Bouton « Tout faire pour la sélection » (télécharger → normaliser → segmenter, sans SRT/alignement qui dépendent de fichiers externes) ; ou assistant « prochaine étape logique » selon l’état (ex. « Ces épisodes sont normalisés mais pas segmentés »).
- **Sélection vs périmètre** — Clarifier partout : « cette action porte sur la sélection cochée » vs « tout le corpus » vs « l’épisode courant » (label, tooltip).
- **Retour après action** — Message explicite en fin d’action (« 3 épisodes normalisés ») ; optionnel : bascule automatique vers l’onglet pertinent (ex. Inspecteur après normalisation, Alignement après alignement).
- **Erreurs et reprise** — Résumé en fin de job (succès / échecs par épisode ou par étape) pour savoir quoi corriger ou relancer.
- **Modification puis re-propagation** — Si on modifie le CLEAN (édition manuelle future) ou le SRT : proposer ou lancer re-segmentation / re-alignement / mise à jour index selon les dépendances.
- **Ordre et dépendances** — Désactiver ou expliquer les prérequis (ex. « Normalisez d’abord la sélection ») ; afficher quand une action est « épisode courant » vs « sélection » vs « tout le projet ».

**Fichiers concernés (à vérifier) :**  
`ui_mainwindow.py` (onglets Corpus, Inspecteur, Sous-titres, Alignement), `workers.py`, éventuellement un module « workflow » ou helpers d’état.

---

## 6. Workflow — batch par saison, filtre saison

**Contexte :** Hésitation entre « normaliser tout le corpus puis étapes suivantes » et « faire un batch complet d’une saison » (télécharger → normaliser → segmenter → SRT → aligner une saison, puis passer à la suivante).

**Pistes :**

- **Filtre / sélection par saison** — Dans l’onglet Corpus : moyen de sélectionner rapidement « toute la saison N » (ex. bouton « Sélectionner saison 1 », ou filtre par colonne Saison puis « Tout cocher »). Les cases à cocher permettent déjà le batch ; il s’agit de faciliter le ciblage « une saison ».
- **Documenter le workflow** — Dans le README ou une doc dédiée : décrire un ou deux scénarios recommandés (ex. « batch saison par saison » vs « tout normaliser puis batch saison pour le reste ») pour que le choix soit explicite.

**Fichiers concernés (à vérifier) :**  
`ui_mainwindow.py` (onglet Corpus, liste épisodes), `models_qt.py`, README ou `DOC_*.md`.

### 6.1 Workflow — commencer par les SRT

**Contexte :** Aujourd’hui le workflow par défaut part des **transcriptions** (Découvrir → Télécharger → Normaliser → Segmenter → Importer SRT → Aligner). Certains utilisateurs ont déjà des **fichiers SRT** (opensubtitles, DVD, autre source) et veulent construire un corpus à partir des SRT sans passer par le scraping ni la transcription.

**Demande :** Pouvoir avoir un **workflow qui commence par les SRT** : créer ou ouvrir un projet, définir la liste des épisodes (sans « Découvrir » ni « Télécharger »), importer les SRT comme première étape, puis aligner (EN↔cible) et utiliser le Concordancier sur les cues. Pas obligatoirement de transcript (raw/clean) ni de segments ; les cues SRT servent de base pour la recherche et l’alignement multilingue.

**Pistes :**

- **Création de projet « SRT only »** — Lors de la création ou l’initialisation du projet : option ou mode « Je n’ai pas de transcriptions, je pars des SRT » (pas de series_url obligatoire, pas d’étape Découvrir/Télécharger). La liste des épisodes peut être créée à la main (ajouter S01E01, S01E02, …) ou importée depuis un fichier (ex. liste d’episode_id).
- **Importer SRT en premier** — Les épisodes existent (référence S01E01, …) sans raw/clean ; l’utilisateur importe directement les fichiers SRT (une ou plusieurs langues) par épisode. Les cues sont stockées comme aujourd’hui (subtitle_cues, cues_fts). Pas d’étape « Segment » (transcript) ; optionnel : générer un « pseudo-transcript » à partir des cues EN (concaténation des textes) pour garder une cohérence avec l’Inspecteur ou l’indexation.
- **Alignement cue ↔ cue** — Aligner directement les cues EN ↔ cues cible (par timecodes si présents, sinon par ordre ou similarité), sans étape segment↔cue EN. Le Concordancier peut interroger les cues (query_kwic_cues) sans index sur les segments.
- **Indexation optionnelle** — Pour la recherche plein texte : soit indexer uniquement les cues (cues_fts déjà en place), soit générer un document « clean » par épisode à partir des cues et l’indexer (documents_fts) pour un usage KWIC sur le texte concaténé.

**Points à clarifier :**  
Faut-il un « type de projet » (transcript-first vs SRT-first) ou suffit-il de permettre une liste d’épisodes sans raw/clean et de désactiver / masquer les boutons Télécharger / Normaliser / Segmenter quand il n’y a pas de transcript ? Gestion des statuts (episode sans raw : statut « SRT only » ou équivalent).

**Ajouter les transcriptions après (SRT first → transcript later) :**  
Oui : si on commence uniquement avec les SRT, on doit pouvoir **rajouter les transcriptions ensuite** (par épisode ou en lot). Un même épisode peut avoir d’abord des pistes SRT (alignement cue↔cue, concordancier sur cues), puis plus tard raw/clean (téléchargement, import manuel ou collage) ; on peut alors lancer Normaliser → Segmenter → alignement segment↔cue EN. Le projet n’est pas figé « SRT only » : les boutons Télécharger / Normaliser / Segmenter restent utilisables dès qu’un épisode a du raw (ou on prévoit un moyen d’ajouter du raw sans « Découvrir », ex. importer un fichier texte par épisode). À documenter dans le backlog : workflow « SRT first, transcriptions ajoutées plus tard » comme scénario supporté.

#### Import SRT en masse

**Contexte :** Aujourd’hui l’import SRT est **un fichier à la fois** : on choisit l’épisode dans l’onglet Sous-titres, on clique « Importer SRT/VTT… », on sélectionne un fichier et la langue. Pour des dizaines d’épisodes ou plusieurs langues, c’est fastidieux.

**Demande :** Pouvoir **importer en masse** des fichiers SRT/VTT : sélectionner un dossier (ou plusieurs fichiers), associer chaque fichier à un épisode et une langue (automatiquement si possible, sinon par mapping), puis lancer l’import pour tout le lot.

**Pistes :**

- **Choix d’un dossier** — Bouton « Importer SRT en masse » (onglet Sous-titres ou Corpus) : dialogue « Choisir un dossier » ; l’app scanne les `*.srt` / `*.vtt` récursivement ou à la racine du dossier.
- **Convention de nommage** — Détecter automatiquement (episode_id, langue) à partir du nom de fichier. Exemples : `S01E01_en.srt`, `s01e01_fr.srt`, `Show - 1x01 - Title.en.srt`. Une ou plusieurs regex / patterns configurables (ex. `(S\d+E\d+)_(\w{2})\.srt` → episode_id, lang). Si le nom ne matche pas, proposer une liste (fichier → épisode ? langue ?) que l’utilisateur peut corriger.
- **Structure par sous-dossiers** — Option : le dossier choisi a une structure du type `S01E01/en.srt`, `S01E01/fr.srt`, ou `S01E01/s01e01_en.srt`. Le nom du sous-dossier ou du fichier donne l’épisode ; l’extension ou le nom donne la langue. Scanner et construire la liste (episode_id, lang, path).
- **Table de mapping** — Dialogue listant tous les fichiers trouvés avec colonnes « Fichier », « Épisode » (combo ou auto-rempli si détecté), « Langue » (combo). L’utilisateur valide ou corrige puis lance l’import. Pour les épisodes : filtrer sur la liste des épisodes déjà connus du projet (series_index) ou permettre d’ajouter un episode_id « à la volée » si workflow SRT-first.
- **Exécution** — Construire une liste de `ImportSubtitlesStep(episode_id, lang, path)` et lancer `_run_job(steps)` comme pour les autres batch (progress bar, annulation, résumé en fin).

**Fichiers concernés (à vérifier) :**  
`ui_mainwindow.py` (onglet Sous-titres : nouveau bouton + dialogue d’import en masse), `core/pipeline/tasks.py` (réutiliser `ImportSubtitlesStep` tel quel), éventuellement `project_store.py` ou un helper pour parser le nom de fichier → (episode_id, lang).

---

**Fichiers concernés (à vérifier) — §6.1 global :**  
`ui_mainwindow.py` (onglet Projet, Corpus, Sous-titres, Alignement), `project_store.py` (création projet, liste épisodes sans raw), `core/storage/db.py` (statuts, indexation cues), `core/pipeline/tasks.py` (alignement sans segment).

---

### 6.2 Télécharger des sous-titres depuis OpenSubtitles (ou similaire)

**Contexte :** Aujourd’hui les SRT sont **importés** depuis des fichiers locaux (ouverture d’un fichier, ou import en masse depuis un dossier). L’utilisateur doit avoir déjà téléchargé les sous-titres (ex. depuis opensubtitles.com à la main). On pourrait proposer de **télécharger directement** des sous-titres depuis une source en ligne (ex. [OpenSubtitles](https://www.opensubtitles.com/)).

**Demande :** Pouvoir **télécharger des sous-titres** depuis OpenSubtitles (ou un service similaire) : par épisode ou en batch, choix de la langue, sauvegarde dans le layout projet (episodes/<id>/subs/<lang>.srt) puis import en DB comme aujourd’hui.

**Pistes techniques :**

- **API OpenSubtitles** — REST API (`api.opensubtitles.com`), authentification par **Api-Key** (inscription gratuite, clé dans le dashboard). Recherche par titre de série/épisode, IMDb/TMDB ID, langue ; endpoint de **download** pour récupérer le fichier SRT. Rate limits à respecter (ex. 1 req/s sur login). Headers : `Api-Key`, `User-Agent`.
- **Adapteur « opensubtitles »** — Même pattern que l’adapteur subslikescript : module dans `core/adapters/` (ex. `opensubtitles.py`) avec recherche par série + saison/épisode (ou par identifiant externe), téléchargement du fichier, retour du contenu SRT. Pas de parsing HTML : appels API REST (httpx). Stockage de l’Api-Key : config projet (fichier local) ou préférences utilisateur, jamais en dur.
- **UI** — Dans l’onglet Sous-titres (ou Corpus) : bouton « Télécharger sous-titres depuis OpenSubtitles… » (ou « Source : OpenSubtitles »). Dialogue : choix de la langue, épisode(s) (sélection ou tout), optionnellement identifiant série (IMDb/TMDB) si le projet n’a pas d’URL. Puis appel API (recherche + download) et enregistrement comme un import (même chemin subs, même étape d’indexation cues).
- **Mapping série → OpenSubtitles** — Pour une série, OpenSubtitles identifie par titre ou par ID (IMDb, TMDB). Il faudrait soit que le projet connaisse un identifiant externe (ex. IMDb ID de la série), soit recherche par nom (ambiguïtés possibles). Documenter dans le backlog : champ optionnel `series_imdb_id` / `series_tmdb_id` dans la config ou dans l’index.

**Points à clarifier :**  
Conditions d’utilisation de l’API OpenSubtitles (quota gratuit, usage « research »). Alternative : sous-titres.org ou autre source avec API ou scraping (légalité, ToS). Gestion des comptes utilisateur (chacun sa clé API) vs clé partagée dans l’app.

**Pros :** Workflow « je crée un projet SRT only → j’ajoute les épisodes → je télécharge les SRT depuis OpenSubtitles » sans quitter l’app. Complète l’import en masse (fichiers locaux) par un téléchargement en ligne.

**Cons :** Dépendance à une API tierce, clé API à configurer, rate limits, évolution possible de l’API.

**Fichiers concernés (à vérifier) :**  
Nouveau `core/adapters/opensubtitles.py` (ou équivalent), `core/utils/http.py` (ou requêtes dédiées avec Api-Key), `ui_mainwindow.py` (onglet Sous-titres / Corpus : bouton + dialogue), config projet (clé API, optionnellement IMDb/TMDB ID), `core/pipeline/tasks.py` (étape « DownloadSubtitlesStep » ou réutilisation import après téléchargement en mémoire).

---

## 7. Profil de normalisation — modifiable / personnalisable

**Contexte :** Aujourd’hui on ne peut que **choisir** un profil parmi ceux définis dans le code (`default_en_v1`, `conservative_v1`, `aggressive_v1`). Impossible de créer ou modifier un profil depuis l’app.

**Pistes :**

- **Écran ou dialogue « Profils de normalisation »** — Liste des profils + « Nouveau » / « Modifier » ; pour chaque profil : nom + options (fusion des césures oui/non, `max_merge_examples_in_debug`, etc.) ; stockage dans la config du projet ou un fichier dédié (ex. `profiles.json` dans le projet).
- **Profil custom par projet (fichier)** — Un fichier par projet (ex. `normalize_profile.toml` ou une section dans `config.toml`) qui décrit un seul profil « custom » (mêmes paramètres qu’aujourd’hui). L’app charge ce profil s’il existe et l’utilise ; modification = éditer le fichier à la main, sans UI dédiée.
- **Extension des paramètres** — À terme, exposer d’autres réglages du profil (ex. règles de fusion, seuils) si le moteur de normalisation le permet.

**Fichiers concernés (à vérifier) :**  
`core/normalize/profiles.py`, `core/normalize/rules.py`, `ui_mainwindow.py` (onglet Projet), `project_store.py`, `config.toml` / chargement config.

### 7.1 Normalisation multi-sources / profils multiples (brainstorming)

**Contexte :** Les problèmes de normalisation ne sont pas les mêmes selon la **source** (site web) dont vient le raw : un autre site = autre structure HTML, autre bruit, autres règles utiles. Par ailleurs on peut avoir **plusieurs sites** pour une même série (ex. saison 1 sur le site A, saison 2 ou trous comblés sur le site B). Il faut pouvoir adapter la normalisation (batch + réglage par épisode) et, à terme, associer des profils différents selon la source ou le lot.

**Pistes :**
- **Plusieurs profils** dans le projet (voir §7) : pas un seul profil global, mais plusieurs (ex. `subslikescript`, `autre_site`, `custom_1`) qu’on peut créer/éditer et **choisir au moment de normaliser** (batch ou par épisode dans l’Inspecteur).
- **Choix du profil à la normalisation** : dans le Corpus (batch) et dans l’Inspecteur (cet épisode), liste déroulante « Profil : … » avant de lancer Normaliser. Optionnel : mémoriser un « profil préféré » par épisode ou par source une fois qu’on a un `source_id` par épisode.
- **Lien source ↔ profil** : quand plusieurs sources seront supportées (§7.2), on pourra proposer par défaut le profil associé à la source de l’épisode ; sinon choix explicite à chaque normalisation.

**Référence :** §7 (profil modifiable), §7.2 (plusieurs sources).

**Comment ça va se faire (pistes techniques) :**

1. **Choix du profil au moment de normaliser (sans nouveau stockage)**  
   Garder les profils prédéfinis dans `profiles.py`. Dans le Corpus (batch) : avant « Normaliser sélection », afficher une liste déroulante « Profil pour ce batch » (pré-remplie avec `config.normalize_profile`). Dans l’Inspecteur (par épisode) : liste « Profil pour cet épisode » + bouton « Normaliser cet épisode ». Les steps utilisent le profil choisi. Pas de nouveau fichier : `get_profile(profile_id)` reste sur les profils codés en dur.

2. **Profils personnalisés stockés dans le projet**  
   Fichier dans le projet (ex. `profiles.json` ou section dans `config.toml`) qui décrit des profils en plus des prédéfinis (mêmes champs : `merge_subtitle_breaks`, `max_merge_examples_in_debug`). Au chargement du projet, fusionner profils du code + profils du fichier. `get_profile(profile_id)` (ou équivalent prenant le projet en paramètre) consulte d’abord le fichier projet, puis le dictionnaire codé en dur. Les listes « Profil pour ce batch » / « Profil pour cet épisode » affichent tous les profils (prédéfinis + personnalisés).

3. **Édition des profils dans l’UI**  
   Écran ou dialogue « Profils de normalisation » : liste des profils (prédéfinis en lecture seule ou clonables, personnalisés éditables), « Nouveau » / « Modifier ». Pour chaque profil : nom (id) + options (fusion des césures, max exemples debug, etc.). Sauvegarde dans le fichier projet. Même logique qu’en 2 pour le chargement et pour `get_profile`.

---

## 7.2 Plusieurs sources (sites web) dans un même projet

**État actuel :** **Non.** Aujourd’hui un projet a **un seul** `source_id` et **une seule** `series_url`. « Découvrir épisodes » utilise cet adapteur et cette URL, et **remplace** tout l’index (series_index.json). Au téléchargement, tous les épisodes sont traités avec le **même** adapteur (`config.source_id`). On ne peut pas mélanger des épisodes venant de subslikescript et d’un autre site dans le même projet sans changer la config (et en changeant, la prochaine découverte écrase l’index).

**Demande :** Pouvoir faire intervenir **plusieurs sites** dans un même projet (ex. récupérer la saison 1 sur le site A, combler des manques ou la saison 2 sur le site B), avec la bonne logique de fetch/parse par source et, à terme, un profil de normalisation adapté par source (§7.1).

**Pistes (à préciser) :**
- **Source par épisode** : stocker un `source_id` (ou `adapter_id`) par épisode (dans l’index ou en base). Au fetch, utiliser l’adapteur indiqué pour cet épisode.
- **Découverte multi-sources** : pouvoir lancer « Découvrir » avec une autre source + une autre series_url, et **fusionner** les épisodes dans l’index (sans écraser), en marquant d’où vient chaque épisode (source_id). Gestion des doublons (même episode_id venant de deux sources : garder un, ou proposer de choisir).
- **Config projet** : soit une liste de (source_id, series_url) au lieu d’un seul, soit garder un « défaut » projet + association source par épisode après découverte.

**Fichiers concernés (à vérifier) :**  
`core/models.py` (EpisodeRef, ProjectConfig), `project_store.py` (series_index, format JSON), `core/pipeline/tasks.py` (FetchSeriesIndexStep, FetchEpisodeStep — adapter selon l’épisode), `ui_mainwindow.py` (onglet Projet, découverte).

---

## 8. Assignation et propagation des noms de personnages (brainstorming constitution du projet)

**Résumé (à implémenter) :**

1. **Définir une liste de personnages** — Par projet : noms canoniques (ou identifiants) des personnages, avec **noms possibles par langue** (ex. Marshall en EN/FR, ou forme localisée différente selon la langue).
2. **Assigner des noms à des segments** — Sur **un** des fichiers récupérés (SRT officiel, retranscription, ou fichier langue étrangère), **attribuer** un personnage à des segments : soit en normalisant des étiquettes déjà présentes (TED: → Ted), soit en étiquetant manuellement / semi-auto quand il n’y a pas d’étiquette. Au final, des segments (ou répliques) sont « étiquetés » par un personnage canonique.
3. **Propager via le concordancier (alignement)** — S’appuyer sur **l’alignement** (segment ↔ cue EN ↔ cue FR, etc.) : si un segment ou une cue a été assigné à un personnage, **propager** ce nom vers les **positions alignées** dans les autres fichiers. Le « bon endroit » dans l’autre fichier = la cue ou le segment lié par l’alignement. En FR (ou autre langue), utiliser le nom du personnage pour cette langue s’il est défini.
4. **Personnage = noms possibles selon la langue** — Un même personnage peut avoir un nom (ou une forme) par langue ; la table de personnages porte cette info, et la propagation écrit la bonne forme selon le fichier cible.

**Contrainte :** Utilisable sur **d’autres séries** : pas de liste figée. Configuration **par projet** (ex. `character_names.toml` ou section `config.toml`). UI et doc neutres (« Personnages », « Noms canoniques »).

**UI : onglet dédié** — Prévoir un **onglet à part** (ex. « Personnages » ou « Assignation ») où l’on : (1) constitue la liste des personnages (noms canoniques + noms par langue, alias éventuels) ; (2) assigne les segments — en choisissant une source (transcription, SRT officiel, ou fichier langue étrangère), en affichant les segments/cues de cette source, et en attribuant un personnage à chaque segment (ou par lot). La propagation (bouton « Propager vers les autres fichiers » ou équivalent) peut vivre dans le même onglet, après assignation. Un onglet dédié évite de surcharger Corpus, Inspecteur ou Alignement et rend le workflow assignation → propagation lisible.

**Constat — existe-t-il un outil qui le fait directement ?**  
- **Non**, pas d’outil standard qui applique en une passe une liste de noms canoniques sur « transcription + SRT multi-langues » d’un même épisode ou projet.  
- **Proches** : Final Draft / Arc Studio (renommage personnage dans un seul script) ; outils de NER / identification de locuteurs (détection, pas normalisation ciblée) ; Subtitle Edit (recherche/remplacement manuel par fichier).  
- Donc soit on intègre la fonctionnalité dans l’app, soit on s’appuie sur un **script externe** ou des **remplacements batch** avec une table de mapping partagée.

**Pistes à mettre en œuvre :**

- **Assignation (construire la table)** — Fichier ou écran projet « Personnages » : pour chaque nom canonique (ex. Ted, Barney, Marshall, Lily, Robin), lister les alias / variantes à lui associer (TED, Ted -, Marshall:, Marshall -, etc., et éventuellement équivalents FR). Stockage par projet (ex. `character_names.toml` ou section dans `config.toml`). Option : détection des candidats (patterns récurrents en début de réplique) puis validation manuelle.
- **Table de mapping (alias → nom canonique) + noms par langue** — Résultat de l’assignation : table utilisée pour l’assignation et la propagation ; chaque personnage peut avoir un nom (ou une forme) par langue pour l’affichage / l’écriture dans les fichiers cibles.
- **Propagation pilotée par l’alignement (concordancier)** — Utiliser les **liens d’alignement** (segment ↔ cue EN ↔ cue FR) pour propager le personnage assigné d’un segment/cue vers les **positions alignées** dans les autres fichiers (transcription, SRT EN, SRT FR, etc.). Le « bon endroit » = la position liée par l’alignement, pas un simple rechercher-remplacer global.
- **Étape « Propager noms »** — Après assignation sur au moins un fichier source : pour chaque lien d’alignement, écrire le nom du personnage (forme selon la langue du fichier cible) au bon endroit dans chaque fichier cible. Dépendances : alignement déjà calculé (segment ↔ cues) ; après normalisation et import SRT.
- **Périmètre** — Par épisode, par sélection d’épisodes, ou tout le projet.
- **Alternative hors app** — Script (ex. Python) qui lit la table de mapping + la structure du projet (episodes/<id>/raw.txt, clean.txt, subs/<lang>.srt) et applique les remplacements ; l’app n’intègre pas la feature mais le workflow reste reproductible.

**Fichiers concernés (à vérifier) :**  
`core/normalize/` (règles ou nouveau module « character_names »), `project_store.py` (chemins raw/clean/subs), pipeline (nouvelle étape ou script), config projet, éventuellement `core/subtitles/parsers.py` si on touche au texte des cues.

---

## 9. Arborescence ou filtre par saison (Saison → Épisodes)

**Contexte :** Une série peut compter beaucoup d’épisodes (ex. plusieurs saisons × 20+ épisodes). Aujourd’hui l’onglet Corpus affiche une **liste plate** (QTableView) : tous les épisodes à la suite, avec colonnes ID, Saison, Épisode, Titre, Statut, et cases à cocher. Pour travailler **par saison** (batch « toute la saison 1 », puis « toute la saison 2 »), il faut soit tout cocher à la main, soit filtrer mentalement par la colonne Saison. Les données ont déjà une structure **saison / épisode** (`EpisodeRef.season`, `episode`), et le stockage disque est `episodes/<episode_id>/` (ex. S01E01) ; il n’y a pas aujourd’hui de niveau « Saison » dans l’UI. Un **système d’arborescence** (ou un équivalent) permettrait de gérer les saisons de façon plus lisible et de faciliter la sélection par saison.

**Demande :** Pouvoir **organiser / filtrer les épisodes par saison** dans l’onglet Corpus, afin de : (1) voir d’un coup la structure Saison → Épisodes ; (2) sélectionner rapidement toute une saison (cases à cocher ou équivalent) ; (3) plier / déplier les saisons pour réduire le bruit à l’écran. Utile pour le workflow « batch par saison » et pour la lisibilité quand le corpus est gros.

**Deux options possibles :**

### Option A — Arborescence (QTreeView : Saison → Épisodes)

- **Principe :** Remplacer (ou compléter) la table plate par une **arborescence** à deux niveaux : nœud « Saison 1 », « Saison 2 », etc., et sous chaque nœud les épisodes de cette saison. Cases à cocher possibles sur les deux niveaux : cocher « Saison 1 » = cocher tous les épisodes de la saison 1.
- **Pros :** Structure très lisible ; plier / déplier les saisons ; sélection « toute la saison » naturelle (cocher le nœud saison). Aligné avec la logique métier (série = saisons = épisodes).
- **Cons :** Refonte plus lourde de l’onglet Corpus (passage de QTableView à QTreeView ou modèle hiérarchique) ; gestion des lignes « Saison » (pas d’actions directes comme « télécharger » sur un nœud saison, seulement sur les épisodes) ; tri / colonnes un peu différents d’une table plate.
- **Fichiers concernés :** `ui_mainwindow.py` (onglet Corpus), `models_qt.py` (modèle hiérarchique ou proxy pour arbre, au lieu d’un simple EpisodesTableModel plat).

### Option B — Table plate + filtre par saison + bouton « Sélectionner la saison »

- **Principe :** Garder la **table plate** actuelle. Ajouter un **filtre** (ex. combo « Toutes les saisons » / « Saison 1 » / « Saison 2 ») qui restreint les lignes affichées aux épisodes de la saison choisie. Ajouter un bouton (ex. « Sélectionner toute la saison visible » ou « Cocher la saison N ») qui coche tous les épisodes de la saison courante (ou de la saison sélectionnée dans le filtre).
- **Pros :** Moins de refonte : on garde EpisodesTableModel et QTableView ; ajout d’un filtre + un bouton. Comportement des cases à cocher et des actions (télécharger, normaliser, etc.) inchangé. Rapide à mettre en œuvre.
- **Cons :** Moins « visuel » qu’un arbre : on ne voit pas la hiérarchie Saison → Épisodes en un coup d’œil ; il faut choisir une saison dans le filtre pour réduire la liste. Pas de plier / déplier.

**Recommandation (à trancher) :** Option B pour un premier pas (filtre + « Cocher la saison ») ; Option A si on souhaite une UI plus structurée et qu’on accepte la refonte de l’onglet Corpus.

**Stockage / données :** Aucun changement nécessaire côté disque ou modèle de données : `EpisodeRef` a déjà `season` et `episode` ; il s’agit uniquement d’**affichage et de sélection** dans l’UI.

**Fichiers concernés (à vérifier) :**  
`ui_mainwindow.py` (onglet Corpus), `models_qt.py` (EpisodesTableModel ; si Option A, ajout d’un modèle hiérarchique ou QTreeView).

---

## 10. Visualiseuse raw (et clean) dans l’onglet Corpus — brainstorming

**Contexte :** Aujourd’hui l’onglet Corpus affiche la **liste des épisodes** (table avec ID, Saison, Épisode, Titre, Statut, cases à cocher) et les **actions** (Télécharger, Normaliser, Indexer, etc.). Pour voir le contenu d’un épisode (raw ou clean), il faut aller dans l’**Inspecteur** et choisir l’épisode dans la liste déroulante. La normalisation (raw → clean) est pilotée par un **profil** (ex. `default_en_v1`) ; les paramètres ne sont pas modifiables dans l’UI, et on ne voit pas facilement « ce qui ne va pas » dans le raw avant / après normalisation.

**Idée (brainstorming, pas d’engagement) :** Ajouter dans l’onglet Corpus une **visualiseuse** : en sélectionnant un épisode (ou en cliquant dessus), afficher le **raw** (et éventuellement le **clean** côte à côte ou en onglets) dans une zone dédiée (ex. QPlainTextEdit ou panneau sous la table). Objectifs : (1) **repérer les problèmes** propres à chaque raw (formatage bizarre, caractères parasites, structure variable selon la source) ; (2) **ajuster les paramètres de normalisation** en fonction de ce qu’on voit (idéalement sans quitter l’onglet Corpus).

**Points à discuter :**

- **Où placer la visualiseuse ?** Sous la table dans le même onglet, ou panneau latéral (splitter), ou fenêtre modale « Aperçu raw/clean » au clic sur une ligne ?
- **Raw seul ou raw + clean ?** Afficher les deux (côte à côte ou onglets) permet de voir l’effet du profil immédiatement ; raw seul suffit pour « diagnostiquer » avant de normaliser.
- **Paramètres de normalisation modifiables ici ?** Si on va vers un **profil modifiable** (voir §7), la visualiseuse pourrait être le lieu où on règle les options et on relance un prévisualisation (clean simulé) sans écraser le fichier. Sinon, la visualiseuse reste en **lecture seule** (juste afficher raw/clean déjà sur disque).
- **Périmètre :** Un épisode à la fois (sélection) ou comparaison rapide entre plusieurs épisodes (plus lourd en UI) ?
- **Lien avec l’Inspecteur :** L’Inspecteur affiche déjà raw + clean pour l’épisode choisi, avec segments/cues. La visualiseuse Corpus serait plutôt un **aperçu rapide** centré sur la qualité du texte (raw/clean) pour décider des paramètres de normalisation, sans charger segments/sous-titres. Éviter la duplication de logique (charger raw/clean) : factoriser dans le store ou un helper.

**Pros :** Workflow « je vois le raw → je vois ce qui pose problème → j’ajuste la normalisation » sans aller-retour Inspecteur / config. Utile pour des corpus hétérogènes (plusieurs sources ou épisodes avec des formats différents).

**Cons :** Encombrement de l’onglet Corpus (déjà dense) ; risque de doublon avec l’Inspecteur si on affiche raw+clean dans les deux ; dépendance avec le backlog « profil de normalisation modifiable » (§7) pour que l’ajustement soit vraiment utile.

**Référence :** À croiser avec §7 (profil de normalisation modifiable) et avec l’existant Inspecteur (raw/clean déjà affichés par épisode).

**Alternative ou complément — répartition des rôles :** Une autre vision est de **séparer clairement** les rôles :
- **Onglet Corpus** = **gestionnaire du corpus** : tenir à jour le travail en masse — liste des épisodes, sélection, découverte, téléchargement, normalisation en batch, export. Pas d’aperçu raw/clean ici : uniquement la table, les statuts et les actions de flux (télécharger tout, normaliser sélection, etc.).
- **Onglet Inspecteur** = **atelier de travail** sur un épisode : là où on **normalise** (voir raw, ajuster paramètres ou profil, produire/voir clean), **segmente**, **vérifie** (segments, notes), et **indexe en DB** pour cet épisode. Toute la partie « contenu » (raw, clean, segments, éventuellement réglages de normalisation) et les actions « par épisode » (Segmenter, Indexer DB pour l’épisode courant) vivent dans l’Inspecteur.

Dans ce modèle, pas de visualiseuse dans le Corpus (évite l’encombrement) ; la visualiseuse / le réglage de normalisation et l’indexation « pour cet épisode » seraient dans l’Inspecteur. Le Corpus reste léger et focalisé sur « quoi est à jour, quoi sélectionner, quoi lancer en batch ». À discuter : déplacer le bouton « Indexer DB » vers l’Inspecteur (indexer l’épisode affiché) ou garder les deux (batch dans Corpus + option dans Inspecteur).

### 10.1 Corpus = gestionnaire des docs (comptabilisation SRT, etc.)

**Contexte :** Aujourd’hui l’onglet Corpus affiche une colonne **Statut** par épisode (NEW, FETCHED, NORMALIZED, INDEXED, ERROR) qui reflète surtout le **transcript** (raw → clean → indexé). Les **SRT** (pistes par langue) et l’**alignement** ne sont pas visibles dans cette table : il faut aller dans Sous-titres ou Alignement pour voir quels épisodes ont des SRT ou un run d’alignement.

**Demande :** Faire de l’onglet Corpus un **gestionnaire plus large des documents** : afficher (et éventuellement comptabiliser) non seulement l’état du transcript, mais aussi la **présence des SRT** par langue et, optionnellement, l’état d’alignement. Ainsi on voit d’un coup d’œil « cet épisode a raw, clean, SRT EN, SRT FR, aligné » sans changer d’onglet.

**Pistes :**

- **Colonnes supplémentaires** — Ajouter des colonnes (ou une colonne agrégée) du type : « SRT » (ex. « EN, FR » ou « 2 langues »), « Aligné » (oui/non ou run_id). Données : pour chaque épisode, interroger le store ou la DB (pistes SRT par épisode, runs d’alignement). Le modèle de la table (EpisodesTableModel) serait alimenté par le store + la DB (get_tracks_for_episode, get_align_runs_for_episode).
- **Statut enrichi** — Au lieu d’une seule colonne Statut (transcript), afficher un **résumé document** : ex. « raw, clean, EN, FR, aligné » ou des icônes / badges (✓ raw, ✓ clean, ✓ EN, ✓ FR, ✓ align). Limite : la table peut devenir large ; prévoir un mode « résumé » (une colonne « Docs » avec tooltip détaillé) ou colonnes repliables.
- **Comptage global** — En en-tête de l’onglet ou sous la table : « 12 épisodes avec raw, 10 avec clean, 8 avec SRT EN, 7 avec SRT FR, 6 alignés » (ou par saison). Utile pour le batch : « il me manque des SRT FR sur la saison 2 ».
- **Cohérence avec import SRT en masse (§6.1)** — Après un import SRT en masse, le rafraîchissement de la table Corpus doit refléter les nouvelles pistes (colonnes SRT ou statut enrichi). Même logique après alignement en batch.

**Points à clarifier :**  
Éviter une table trop large (nombre de langues variable) : soit colonnes fixes « SRT » (liste des langues en une cellule), soit colonnes dynamiques par langue connue du projet. Performance : charger les infos SRT/align pour tous les épisodes peut coûter des requêtes ; prévoir un chargement groupé ou en cache.

**Fichiers concernés (à vérifier) :**  
`ui_mainwindow.py` (onglet Corpus, table épisodes), `models_qt.py` (EpisodesTableModel : colonnes supplémentaires, données store + DB), `project_store.py` (liste pistes SRT par épisode si pas déjà exposé), `core/storage/db.py` (get_tracks_for_episode, get_align_runs_for_episode).

**Référence :** §6.1 (workflow SRT, import en masse), §10 (Corpus = gestionnaire).

---

## Réalisé

- **Exemple utilisable (EN + FR, court)** — projet démo dans `example/` avec transcript, SRT EN/FR, README et corpus.db pré-initialisé. Voir `example/README.md` et section « Projet exemple » du `README.md` principal.
- **§1 — Onglet Corpus — cases à cocher** — colonne de cases + « Tout cocher » / « Tout décocher » ; « Télécharger sélection » et « Normaliser sélection » utilisent les cases (avec repli sur la sélection par clic). Intégré à l’arbre (§9).
- **§2.1 — Onglet Inspecteur — redimensionnement** — QSplitter horizontal (liste segments | zone RAW/CLEAN) et vertical (RAW | CLEAN) ; sauvegarde/restauration des proportions (QSettings).
- **§2.2 — Onglet Inspecteur — export segments** — bouton « Exporter les segments » (TXT, CSV, TSV) depuis l’épisode affiché.
- **§3 — Alignement sans timecodes (par ordre)** — si les cues EN ou target n’ont pas de timecodes utilisables (`start_ms`/`end_ms` tous à 0), l’alignement EN↔target utilise `align_cues_by_order` (cue i ↔ cue i). Voir `aligner.py` : `cues_have_timecodes`, `align_cues_by_order` ; fallback automatique dans `AlignEpisodeStep`.
- **§4 — Version Mac — .app avec icône** — spec PyInstaller produit un bundle `.app` sur macOS (COLLECT + APP) avec icône ; `resources/icons/icon_512.png` + `make_icns.sh` → `icon.icns` ; `scripts/macos/build_app.sh` pour build local ; CI Release (tag v*) build .exe et .app et attache les deux à la release. Voir `scripts/macos/README.md`.
- **§6 — Filtre saison + batch par saison** — filtre « Saison » (combo) + bouton « Cocher la saison » ; workflow batch par saison documenté dans README (option A/B).
- **§6.1 — Workflow SRT only** — case « Projet SRT uniquement » à la création ; URL série vide = SRT only ; bouton « Ajouter épisodes (SRT only) » (liste d’episode_id) ; actions Télécharger/Normaliser/Segmenter adaptées quand pas de transcript.
- **§6.1 — Import SRT en masse** — bouton « Importer SRT en masse… » (onglet Sous-titres) ; dialogue avec scan dossier, détection (episode_id, langue) par nom de fichier, table de mapping (Fichier, Épisode, Langue) ; exécution via `ImportSubtitlesStep` en batch (progress, annulation). Voir `SubtitleBatchImportDialog`, `_parse_subtitle_filename`.
- **§7 — Profil de normalisation modifiable** — profils personnalisés dans le projet (`profiles.json`) ; dialogue « Gérer les profils de normalisation » (ProfilesDialog) : créer, modifier, supprimer ; chargement avec profils prédéfinis ; choix du profil au batch (Corpus) et par épisode (Inspecteur). Optionnel : `episode_preferred_profiles.json`, `source_profile_defaults.json` (project_store).
- **§9 — Arborescence (Option A)** — Onglet Corpus : QTreeView avec EpisodesTreeModel (Saison → Épisodes), filtre par saison, « Cocher la saison », cases à cocher par épisode. Fichiers : `ui_mainwindow.py`, `models_qt.py` (EpisodesTreeModel, EpisodesTreeFilterProxyModel).
- **§10.1 — Corpus = gestionnaire des docs** — Colonnes SRT et Aligné dans l'arbre épisodes, alimentées par `get_tracks_for_episode` et `get_align_runs_for_episode` ; comptage global « X avec SRT, Y aligné(s) » sous la table. Fichiers : `models_qt.py`, `ui_mainwindow.py`, `project_store.py` / `db.py`.
- **§5 — Workflow visibilité et prérequis** — Checklist « Découverts | Téléchargés | Normalisés | Segmentés | SRT | Alignés » (corpus_status_label) ; résumé fin de job « X réussie(s), Y échec(s) » (barre de statut + onglet Logs) avec episode_id en échec ; boutons « Normaliser sélection/tout » désactivés si aucun épisode téléchargé.
- **§7.2 — Multi-sources** — Découverte initiale tague chaque ref avec `config.source_id` ; `FetchEpisodeStep` utilise `ref.source_id` pour choisir l'adapteur ; « Découvrir (fusionner) » sans écraser l'index (FetchAndMergeSeriesIndexStep).
- **§3 (complément) — Option alignement par similarité** — Case « Forcer alignement par similarité » (onglet Alignement) ; `AlignEpisodeStep(use_similarity_for_cues=True)` force l'appariement EN↔cible par similarité textuelle au lieu des timecodes.
- **M4 — Sous-module KWIC** — `storage/db_kwic.py` : KwicHit, `query_kwic`, `query_kwic_segments`, `query_kwic_cues` ; CorpusDB délègue à ces fonctions pour alléger db.py et permettre des tests unitaires ciblés.
- **M1 — Découpage ui_mainwindow** — Tous les onglets extraits dans `app/tabs/` (Projet, Corpus, Inspecteur, Sous-titres, Alignement, Concordance, Personnages, Logs) ; dialogues dans `app/dialogs/` ; MainWindow allégée, signaux/slots préservés.
- **§6.2 — Télécharger SRT depuis OpenSubtitles** — Client `core/opensubtitles/` (search par imdb_id + season/episode, download) ; step `DownloadOpenSubtitlesStep` ; dialogue « Télécharger depuis OpenSubtitles… » (onglet Sous-titres) ; clé API et series_imdb_id stockés dans config.toml (load_config_extra / save_config_extra).
- **§7.1 — Profils par source** — Priorité profil (préféré épisode > défaut source > batch) déjà en place (episode_preferred_profiles, source_profile_defaults) ; complété par tooltips Corpus/Inspecteur et libellé dialogue Profils (lien source→profil).
- **§8 — Personnages (assignation + propagation)** — Onglet Personnages (liste personnages, assignation segment/cue→personnage) ; propagation via `store.propagate_character_names(db, episode_id, run_id)` : mise à jour segments.speaker_explicit, cues text_clean (préfixe « Nom: »), réécriture des fichiers SRT ; `db.update_segment_speaker`, `db.update_cue_text_clean` ; `cues_to_srt` dans parsers.
- **§10 — Aperçu épisode depuis Corpus** — Alternative retenue (pas de visualiseuse dans Corpus) : double-clic sur un épisode dans l’arbre Corpus ouvre l’onglet Inspecteur sur cet épisode (raw/clean, segments). Tooltip sur l’arbre ; callback `on_open_inspector` (même impl que Concordance).

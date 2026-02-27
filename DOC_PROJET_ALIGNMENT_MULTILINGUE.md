# Projet Cible: Alignement Multilingue de Documents + Concordancier

## 1. Vision

Construire une application desktop orientée **corpus multilingue** (hors transcript/SRT), capable de:

1. Importer des documents `TXT`, `DOCX`, et `TEI XML`.
2. Segmenter et normaliser les textes par langue.
3. Aligner les unités textuelles d'une langue source vers une ou plusieurs langues cibles.
4. Explorer les résultats via un concordancier monolingue et parallèle.

Objectif produit: couvrir les besoins classiques de type Alinea/ParaConc/AntConc, avec une base moderne et extensible.

## 2. Cas d'usage principal

1. L'utilisateur importe un lot de documents dans plusieurs langues.
2. Il définit une langue source (pivot) et des langues cibles.
3. L'application aligne les segments source/cible (avec score + audit).
4. L'utilisateur interroge un terme et obtient:
   - les occurrences dans la langue choisie (KWIC),
   - les correspondances alignées dans les autres langues.

## 3. Positionnement par rapport à HIMYC

### 3.1 Composants réutilisables

1. Moteur de stockage SQLite + FTS/KWIC:  
   [db.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/storage/db.py),  
   [db_kwic.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/storage/db_kwic.py)
2. Gestion des runs d'alignement et des liens:  
   [db_align.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/storage/db_align.py)
3. Orchestration des étapes (pipeline):  
   [runner.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/pipeline/runner.py)

### 3.2 Composants à refondre

1. Modèle métier centré épisodes/transcripts/SRT.
2. Ingestion orientée web/adapters de scraping.
3. UI orientée onglets Corpus/Sous-titres/Inspecteur actuels.

## 4. Architecture cible (proposée)

## 4.1 Ingestion

1. Importeurs:
   - `TXT`: encodage robuste, découpage brut.
   - `DOCX`: extraction paragraphes/runs.
   - `TEI XML`: parsing structuré (`div`, `p`, `s`, `seg`, `w`, etc. selon profil TEI retenu).
2. Sortie interne: format canonique unique de segments.

## 4.2 Modèle de données canonique

Tables (ou équivalent) à prévoir:

1. `documents`: `doc_id`, `lang`, `title`, `source_path`, métadonnées.
2. `units`: `unit_id`, `doc_id`, `n`, `text_raw`, `text_norm`, offsets, métadonnées TEI.
3. `align_runs`: config run (langue source/cibles, méthode, paramètres).
4. `align_links`: `source_unit_id`, `target_unit_id`, `score`, `status`, `meta`.
5. `fts_units` (FTS5): index plein-texte sur `text_norm`.

## 4.3 Alignement

1. Alignement source -> cible par stratégie configurable:
   - ordre/position,
   - similarité textuelle,
   - hybride (indices structurels + similarité),
   - extensions futures (embeddings, alignement lexical).
2. Production de liens auditables (accept/reject, correction manuelle).

## 4.4 Concordancier

1. KWIC monolingue:
   - recherche FTS, filtres par langue/document/sous-corpus.
2. Concordance parallèle:
   - affichage des unités alignées dans langues cibles.
3. Exports:
   - CSV/TSV/JSONL/HTML.

## 5. TEI dès le départ: recommandation

Oui, TEI dès la V1 est pertinent si:

1. On conserve les identifiants TEI (`xml:id`) et ancres structurelles dans les métadonnées.
2. On définit un **profil TEI supporté** (pour limiter la variabilité).
3. On garde une représentation interne unifiée pour ne pas complexifier le reste du pipeline.

Principe: importer TEI en interne comme des `units` génériques, sans imposer la structure TEI à tous les modules.

## 6. Roadmap conseillée

## Phase 1 - MVP fonctionnel

1. Import `TXT` et `DOCX`.
2. Segmentation basique par paragraphe/phrase.
3. Alignement source->cible simple (ordre + similarité).
4. KWIC monolingue + vue parallèle minimale.

## Phase 2 - Qualité corpus

1. Import TEI (profil défini).
2. Outils de validation/diagnostic des imports.
3. Édition manuelle des liens d'alignement.
4. Filtres avancés sur métadonnées.

## Phase 3 - Fonctions type AntConc/ParaConc

1. Wordlist, n-grams, clusters, collocations.
2. Statistiques (fréquences, dispersion, comparaison de sous-corpus).
3. Requêtes avancées (regex/wildcards robustes, éventuellement lemme/POS si NLP ajouté).

## 7. Risques clés

1. Hétérogénéité TEI: nécessite un profil explicite.
2. Qualité d'alignement variable selon langues/domaines.
3. Performance sur gros corpus sans stratégie batch/indexation stricte.

## 8. Décision recommandée

1. Réutiliser le **core technique** de HIMYC (DB/FTS/pipeline/runs).
2. Créer un **nouveau domaine métier** (documents/unités) et une **nouvelle UI** dédiée.
3. Intégrer TEI dès le départ via un importeur profilé + mapping vers modèle canonique.

## 9. UI/UX recommandée (grand public + usage avancé)

### 9.1 Principes directeurs

1. **Progressive disclosure**: interface simple au départ, puissance accessible ensuite.
2. **Deux niveaux d'usage**:
   - mode guidé (utilisateur lambda),
   - mode expert (chercheur, linguistique de corpus).
3. **Traçabilité**: chaque run d'import, segmentation, alignement doit être visible, rejouable, exportable.
4. **Tolérance aux erreurs**: messages concrets et actions proposées (corriger, ignorer, relancer).
5. **Performances perçues**: feedback immédiat (progression, états, logs lisibles).

### 9.2 Architecture UX cible

Organisation conseillée en 5 espaces:

1. **Accueil / Projet**
   - créer/ouvrir projet,
   - choisir langues et langue pivot,
   - charger un preset.
2. **Import**
   - glisser-déposer `TXT`, `DOCX`, `TEI`,
   - contrôle qualité (encodage, structure, erreurs TEI, doublons).
3. **Alignement**
   - config run (source, cibles, méthode),
   - vue de validation des liens (accepter/rejeter/éditer),
   - métriques de qualité.
4. **Concordancier**
   - KWIC monolingue,
   - concordance parallèle sur unités alignées,
   - filtres par langue/document/métadonnées.
5. **Exports**
   - résultats (CSV/TSV/JSONL/HTML),
   - rapport run + paramètres pour reproductibilité.

### 9.3 Mode guidé vs mode expert

Mode guidé:

1. Wizard en étapes: `Importer -> Segmenter -> Aligner -> Rechercher`.
2. Paramètres “recommandés” par défaut.
3. Validation assistée: alertes simples, termes non techniques.

Mode expert:

1. Panneau de paramètres complet (méthodes d'alignement, seuils, filtres regex, options TEI).
2. Actions batch et rejouabilité des runs.
3. Raccourcis clavier, colonnes configurables, export des logs techniques.

### 9.4 Éléments UX indispensables

1. **Jeux de données exemple** intégrés pour prise en main rapide.
2. **Historique des runs** (qui, quand, paramètres, statut, durée).
3. **Undo/redo** dans les corrections manuelles.
4. **Sauvegarde automatique** des préférences projet.
5. **Command palette** (recherche d'actions) pour utilisateurs avancés.
6. **Aide contextuelle** par écran (micro-doc + exemples).

## 10. Évaluation des options technologiques UI

### 10.1 Critères de comparaison

1. Facilité pour utilisateur non technique.
2. Puissance pour usage avancé.
3. Gestion locale de gros corpus (offline).
4. Packaging/distribution desktop.
5. Coût de maintenance long terme.

### 10.2 Comparatif synthétique

| Option | Points forts | Points faibles | Fit global |
|---|---|---|---|
| Web app pure (navigateur) | Très accessible, déploiement simple | Offline/local files plus contraints, sécurité/permissions plus complexes | Moyen |
| Electron (desktop web) | Écosystème énorme, outillage mature | Binaire lourd, consommation RAM élevée | Bon |
| **Tauri (desktop web)** | Léger, bon packaging desktop, bon accès local, UX web moderne | Écosystème plus jeune qu'Electron, couche Rust à gérer | **Très bon** |
| Qt/PySide (desktop natif) | Solide pour apps desktop data-heavy, proche de l'existant HIMYC | UX moderne plus coûteuse à concevoir, distribution/UI web moins flexible | Bon |
| Tkinter | Très simple | UX limitée pour produit moderne complexe | Faible |

### 10.3 Recommandation

Pour ce projet, la meilleure option équilibre “lambda + expert” est:

1. **Tauri + frontend web moderne** (React/Vue/Svelte) pour l'UX.
2. **Moteur métier local** réutilisant le core Python (pipeline, DB, alignement) via API locale (ex: FastAPI en sidecar) ou bindings.
3. **SQLite local** + mode offline par défaut.

Cette stratégie permet:

1. UI moderne et pédagogique pour grand public.
2. Écrans riches et configurables pour profils avancés.
3. Distribution desktop légère (Windows/macOS/Linux) sans dépendre d'un serveur distant.

## 11. Décision UX/tech finale proposée

1. Construire un MVP en **desktop local-first**.
2. Utiliser une UI à deux vitesses (Guidé / Expert).
3. Prioriser Tauri si l'équipe accepte une petite couche Rust; sinon Qt/PySide reste une alternative viable à court terme.
4. Garder le moteur d'alignement/concordance découplé de l'UI pour conserver la portabilité (desktop aujourd'hui, web demain).

## 12. Éléments à reprendre / exporter vers l'autre projet

Cette section liste précisément ce qui peut être extrait de HIMYC pour accélérer le nouveau projet.

### 12.1 Modules code à reprendre en priorité

1. **Moteur DB + migrations + FTS**
   - [db.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/storage/db.py)
   - [db_kwic.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/storage/db_kwic.py)
   - [schema.sql](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/storage/schema.sql)
   - dossier migrations: `/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/storage/migrations`
2. **Alignement**
   - [aligner.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/align/aligner.py)
   - [similarity.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/align/similarity.py)
   - [run_metadata.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/align/run_metadata.py)
   - [db_align.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/storage/db_align.py)
3. **Pipeline**
   - [runner.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/pipeline/runner.py)
   - [steps.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/pipeline/steps.py)
   - [context.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/pipeline/context.py)
4. **Exports**
   - [export_utils.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/export_utils.py)
5. **Utilitaires transverses**
   - [text.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/utils/text.py)
   - [logging.py](/Users/hsmy/Dev/HIMYC-1/src/howimetyourcorpus/core/utils/logging.py)

### 12.2 Modules à ne pas reprendre tels quels

1. Couche UI actuelle `app/*` (très liée à l'usage transcript/SRT).
2. Adapters web de scraping série/épisodes:
   - `core/adapters/*` (subslikescript/tvmaze).
3. Domaine spécifique sous-titres/transcripts:
   - `core/subtitles/*`,
   - partie “episode/season” des modèles et workflows.

### 12.3 Artefacts non-code à exporter

1. **Tests de base de données et alignement** comme templates:
   - `tests/test_db_*`,
   - `tests/test_align*`,
   - `tests/test_integration_pipeline.py`.
2. **Jeux de fixtures** utiles pour tests unitaires et régression:
   - `/Users/hsmy/Dev/HIMYC-1/tests/fixtures`.
3. **Scripts de build/packaging** à adapter:
   - `/Users/hsmy/Dev/HIMYC-1/scripts`.
4. **Conventions de projet** (structure, nommage, changelog, docs techniques).

### 12.4 Contrats à redéfinir avant extraction

Avant de copier les modules, définir les contrats du nouveau domaine:

1. `DocumentRef` (id, langue, source, métadonnées).
2. `Unit` (id, document_id, ordre, texte brut/normalisé, ancres TEI).
3. `AlignRunConfig` (pivot, cibles, stratégie, seuils).
4. `AlignLink` (source_unit_id, target_unit_id, score, statut, méta).
5. `KwicHit` (langue, contexte gauche/match/droite, références d'alignement).

Objectif: remplacer les dépendances `EpisodeRef`, `SxxExx`, `cue_id`, etc. par des identifiants documentaires génériques.

### 12.5 Plan d'export recommandé (ordre d'exécution)

1. **Lot A - Extraction core technique**
   - copier `storage/db*`, `align/*`, `pipeline/runner+steps+context`, `export_utils` dans un package dédié.
2. **Lot B - Découplage métier**
   - supprimer les références épisode/sous-titres,
   - introduire les nouveaux modèles `document/unit`.
3. **Lot C - Schéma DB cible**
   - créer `documents`, `units`, `align_runs`, `align_links`, FTS sur `units`.
   - garder la logique de migration versionnée.
4. **Lot D - Ingestion**
   - ajouter importeurs `TXT/DOCX/TEI` vers le modèle canonique.
5. **Lot E - UI**
   - brancher le core sur la nouvelle UI (Tauri/Qt).

### 12.6 Livrables exportables (checklist)

1. Package Python `core_engine` (sans UI).
2. Schéma SQL + migrations versionnées.
3. API interne stable:
   - `import_documents()`,
   - `segment_documents()`,
   - `run_alignment()`,
   - `query_kwic()`,
   - `query_parallel_concordance()`.
4. Pack tests minimum:
   - tests DB,
   - tests alignement,
   - tests pipeline end-to-end.
5. Documentation développeur:
   - architecture,
   - contrat de données,
   - guide d'extension (nouveau format, nouvelle stratégie d'alignement).

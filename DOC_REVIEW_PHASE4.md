# Revue de code — Phase 4 (HowIMetYourCorpus)  
**Alignement transcript (segments) ↔ cues EN ↔ cues FR/IT**

*Date : février 2025 — 1ʳᵉ révision (correctifs appliqués)*

---

## 1. Contexte

La Phase 4 ajoute l’alignement des segments (phrases du transcript) avec les cues sous-titres EN (par similarité textuelle), puis des cues EN avec les cues cibles FR/IT (par recouvrement temporel). Les runs d’alignement et les liens sont stockés en base et sur disque (audit) ; l’UI permet de lancer un run, consulter les liens et exporter en CSV/JSONL. Ce document résume la revue du code Phase 4 et liste les corrections ou évolutions à prévoir.

---

## 2. Ce qui va bien

- **Similarité** : `text_similarity` avec rapidfuzz (optionnel) ou fallback Jaccard sur tokens ; gestion des chaînes vides.
- **Alignement** : `align_segments_to_cues` (segment↔cues EN par similarité, concaténations 1..K cues) et `align_cues_by_time` (cues EN↔cues target par overlap temporel) ; `AlignLink` avec `to_dict` pour la DB.
- **Stockage** : migration 004 (align_runs, align_links), `create_align_run`, `upsert_align_links`, `query_alignment_for_episode` (filtres run_id, status, min_confidence), `set_align_status`, `get_align_runs_for_episode` ; `save_align_audit` (align/<run_id>.jsonl + report, run_id sécurisé pour Windows).
- **Pipeline** : `AlignEpisodeStep` charge segments (sentence) et cues EN, lance pivot_links puis target_links par langue cible, génère run_id horodaté, enregistre run + liens + audit.
- **UI** : onglet Alignement (épisode, run, boutons « Lancer alignement » et « Exporter aligné »), table des liens (`AlignLinksTableModel`), rafraîchissement dans `_on_job_finished`.
- **Export** : CSV et JSONL des liens (link_id, segment_id, cue_id, cue_id_target, lang, role, confidence, status) ; JSONL inclut `meta` si présent.
- **Tests** : `test_align.py` (similarité, align_segments_to_cues, align_cues_by_time, AlignLink.to_dict), `test_db_kwic.py` (create_align_run, upsert_align_links, query_alignment_for_episode, set_align_status).

---

## 3. Actions à traiter

### 3.1 Priorité moyenne

#### A. Validation des liens depuis l’UI

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py` (et éventuellement `models_qt.py`)

**Constat :** La base expose `set_align_status(link_id, status)` (accepted/rejected) et les tests l’utilisent, mais **aucune action dans l’UI** ne permet de changer le statut d’un lien. L’utilisateur voit la colonne « Statut » sans pouvoir valider ou rejeter un lien.

**À faire :** Ajouter un moyen de modifier le statut depuis l’UI (ex. menu contextuel ou boutons « Accepter » / « Rejeter » sur la ligne sélectionnée), en appelant `db.set_align_status(link_id, "accepted")` ou `"rejected"`, puis en rafraîchissant la table (ou le modèle).

---

#### B. Rafraîchissement après « Lancer alignement »

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py`  
**Méthode :** `_run_align_episode` (ligne ~716)

**Problème :** Comme en Phase 3, on appelle `_refresh_align_runs()` juste après `_run_job([AlignEpisodeStep(...)])`. Le job étant asynchrone, le rafraîchissement s’exécute avant la fin du run ; le nouveau run n’apparaît qu’après `_on_job_finished`, qui appelle déjà `_refresh_align_runs()`.

**À faire :** Supprimer l’appel à `_refresh_align_runs()` dans `_run_align_episode` pour éviter la redondance et la confusion.

---

#### C. Variable `used_cue_indices` non utilisée

**Fichier :** `src/howimetyourcorpus/core/align/aligner.py`  
**Fonction :** `align_segments_to_cues`

**Constat :** `used_cue_indices` est mis à jour lorsqu’un segment est aligné à une cue, mais n’est jamais utilisé pour empêcher qu’une même cue soit réutilisée pour un autre segment. Plusieurs segments peuvent donc pointer vers la même cue (une ligne de sous-titre peut couvrir plusieurs phrases).

**À faire :** Soit documenter explicitement ce choix (une cue peut être liée à plusieurs segments), soit utiliser `used_cue_indices` pour exclure les cues déjà assignées et imposer une bijection partielle (selon le besoin métier).

---

### 3.2 Priorité basse

#### D. Lien segment↔N cues : seul le premier cue_id stocké

**Fichier :** `src/howimetyourcorpus/core/align/aligner.py`  
**Fonction :** `align_segments_to_cues`

**Constat :** Quand un segment s’aligne à une concaténation de N cues (best_n > 1), on enregistre uniquement `cue_id` de la première cue ; `meta["n_cues"]` indique le nombre. Pour un usage avancé (ex. export avec plage de cues), il pourrait être utile de stocker la plage (ex. cue_id_start, cue_id_end ou liste de cue_ids dans meta).

**À faire :** Optionnel : enrichir `AlignLink` ou `meta` avec la plage / la liste des cue_ids quand best_n > 1.

---

#### E. Dépendance optionnelle rapidfuzz

**Fichier :** `src/howimetyourcorpus/core/align/similarity.py`  
**Fichier :** `pyproject.toml`

**Constat :** rapidfuzz n’est pas déclaré dans les dépendances du projet ; le code fonctionne sans (fallback Jaccard). La qualité d’alignement est meilleure avec rapidfuzz.

**À faire :** Documenter dans le README ou le RECAP que l’installation de `rapidfuzz` est optionnelle mais recommandée pour la Phase 4 ; éventuellement l’ajouter en dépendance optionnelle (extra) dans `pyproject.toml`.

---

#### F. Export alignement : colonne meta

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py`  
**Méthode :** `_export_alignment`

**Constat :** L’export CSV ne contient pas la colonne `meta` ; l’export JSONL inclut tout le `row` (donc `meta`). Pour un export CSV complet, on pourrait ajouter une colonne `meta` (JSON sérialisé) ou les champs utiles extraits de meta (ex. n_cues, overlap_ms).

**À faire :** Optionnel : ajouter une colonne meta (ou champs dérivés) à l’export CSV, ou documenter que le détail est dans le JSONL.

---

## 4. Bilan des correctifs appliqués

| Réf   | Sujet | Statut |
|-------|--------|--------|
| § 3.1 A | Validation des liens depuis l’UI (Accepter / Rejeter) | ✅ Menu contextuel sur la table des liens ; `set_align_status` puis `_align_fill_links`. |
| § 3.1 B | Rafraîchissement après « Lancer alignement » | ✅ Appel à `_refresh_align_runs()` supprimé dans `_run_align_episode` (déjà fait par `_on_job_finished`). |
| § 3.1 C | Variable `used_cue_indices` | ✅ Documenté dans la docstring : une cue peut être liée à plusieurs segments ; `used_cue_indices` réservé pour évolution. |
| § 3.2 D | Plage cue_ids (optionnel) | ⏸ Non fait (optionnel). |
| § 3.2 E | Dépendance rapidfuzz | ✅ Doc README et RECAP ; extra `[align]` dans `pyproject.toml` avec `rapidfuzz>=3.0`. |
| § 3.2 F | Export CSV colonne meta | ✅ Colonne `meta` (JSON sérialisé) ajoutée à l’export CSV. |

---

## 5. Synthèse pour le dev (référence)

| Priorité | Réf   | Sujet |
|----------|-------|--------|
| Moyenne  | § 3.1 A | Permettre de valider/rejeter un lien depuis l’UI (set_align_status). ✅ |
| Moyenne  | § 3.1 B | Supprimer l’appel redondant à _refresh_align_runs dans _run_align_episode. ✅ |
| Moyenne  | § 3.2 C | Documenter ou utiliser used_cue_indices dans align_segments_to_cues. ✅ |
| Basse    | § 3.3 D–F | Plage de cue_ids (optionnel), doc rapidfuzz ✅, export CSV meta ✅. |

---

## 6. Fichiers Phase 4 concernés

| Fichier | Rôle Phase 4 |
|---------|----------------|
| `core/align/__init__.py` | Export text_similarity, AlignLink, align_segments_to_cues, align_cues_by_time. |
| `core/align/similarity.py` | text_similarity (rapidfuzz ou Jaccard). |
| `core/align/aligner.py` | AlignLink, align_segments_to_cues, align_cues_by_time. |
| `core/storage/project_store.py` | align_dir, save_align_audit. |
| `core/storage/db.py` | create_align_run, upsert_align_links, set_align_status, get_align_runs_for_episode, query_alignment_for_episode. |
| `core/storage/migrations/004_align.sql` | Tables align_runs, align_links. |
| `core/pipeline/tasks.py` | AlignEpisodeStep. |
| `app/ui_mainwindow.py` | Onglet Alignement, menu contextuel Accepter/Rejeter, _refresh_align_runs, _align_fill_links, _run_align_episode, _export_alignment (CSV avec meta). |
| `app/models_qt.py` | AlignLinksTableModel. |
| `tests/test_align.py` | Tests similarité et alignement. |
| `tests/test_db_kwic.py` | test_align_run_and_links. |

---

*Document généré à partir de la revue de code Phase 4 du projet HowIMetYourCorpus. Correctifs § 3.1 A–C, § 3.2 E–F appliqués.*

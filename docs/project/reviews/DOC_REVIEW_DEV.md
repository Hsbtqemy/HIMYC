# Revue de code — HowIMetYourCorpus  
**Document à transmettre au développeur**

*Date : février 2025 — 6ᵉ révision*

---

## 1. Contexte

Application desktop Windows (PySide6) pour construire, normaliser, indexer et explorer des transcriptions (source web type subslikescript). Ce document résume la revue de code du MVP et liste les corrections / évolutions à prévoir.

**État des lieux (6ᵉ passe) :** Reprise de la review Phase 3 : vérification dans le code que tous les correctifs des sections 3.1 à 3.3 sont bien appliqués. La section 4.2 documente la 6ᵉ vérification. La section 3 est conservée comme référence historique.

---

## 2. Ce qui va bien

- **Architecture** : séparation nette `core/` (logique) et `app/` (UI, workers). Pipeline par étapes (Step/StepResult), idempotence (skip si déjà fait).
- **Modèles** : dataclasses typées (`ProjectConfig`, `EpisodeRef`, `SeriesIndex`, etc.) et enum `EpisodeStatus`.
- **Extensibilité** : `SourceAdapter` + `AdapterRegistry` pour ajouter des sources sans toucher au reste.
- **Tests** : adapter, normalisation et DB/KWIC couverts avec fixtures.
- **Doc projet** : README et RECAP à jour.

---

## 3. Actions à traiter

### 3.1 Priorité haute

#### A. Fuite de handlers de log

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py`  
**Méthode :** `_setup_logging_for_project`

**Problème :** Le handler de fichier est ajouté au logger `howimetyourcorpus`, mais la suppression est faite sur le logger **racine**. Les anciens `FileHandler` ne sont jamais retirés → à chaque ouverture de projet, un nouveau handler s’accumule (fuite).

**À faire :** Cibler le même logger pour add/remove. Exemple :

```python
corpus_logger = logging.getLogger("howimetyourcorpus")
if self._log_handler:
    corpus_logger.removeHandler(self._log_handler)
# ... créer file_handler ...
corpus_logger.addHandler(file_handler)
self._log_handler = file_handler
```

---

#### B. Utilisation d’une API privée

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py` (lignes 177–178)  
**Fichier concerné :** `src/howimetyourcorpus/core/storage/project_store.py`

**Problème :** L’UI importe et utilise `_read_toml` depuis `project_store`. Les noms préfixés par `_` sont considérés privés et peuvent changer sans préavis.

**À faire :** Exposer une API publique, par exemple :
- `ProjectStore.load_config(path: Path) -> dict` dans `project_store.py`, ou
- une fonction `read_project_config(path: Path) -> dict` dans le même module.

Puis dans `ui_mainwindow.py`, appeler cette API au lieu de `_read_toml`.

---

#### C. Signal d’erreur du job jamais affiché

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py`  
**Contexte :** `_run_job` connecte `progress`, `log`, `finished`, `cancelled` mais **pas** `error`.

**Problème :** `JobRunner` émet `error(step_name, exception)` en cas d’échec d’une étape, mais aucun slot n’est connecté. L’utilisateur voit le job se terminer (barre à 100 %, bouton Annuler désactivé) sans message d’erreur explicite.

**À faire :** Connecter le signal `error` à un slot qui affiche l’erreur (ex. `QMessageBox.critical` ou ajout dans l’onglet Logs), par exemple :

```python
self._job_runner.error.connect(self._on_job_error)
# ...
def _on_job_error(self, step_name: str, exc: object):
    QMessageBox.critical(self, "Erreur", f"{step_name}: {exc}")
```

---

### 3.2 Priorité moyenne

#### D. FTS5 non utilisé pour la recherche KWIC

**Fichier :** `src/howimetyourcorpus/core/storage/db.py`  
**Méthode :** `query_kwic`

**Problème :** Le schéma crée une table FTS5 `documents_fts` (et les triggers la maintiennent), mais `query_kwic` charge tout le texte depuis `documents` et fait une recherche par regex en Python. Pour un gros corpus, les perfs se dégraderont.

**À faire :** Utiliser FTS5 pour filtrer les documents (ex. `SELECT ... FROM documents_fts WHERE documents_fts MATCH ?`), puis construire left/match/right en Python sur les résultats, pour garder de bonnes perfs à l’échelle.

---

#### E. Dépendance à un détail d’implémentation du store

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py`  
**Méthode :** `_inspect_load_episode` (lignes 377–378)

**Problème :** Utilisation de `self._store._episode_dir(eid)` pour construire le chemin de `transform_meta.json`. L’UI ne devrait pas dépendre d’une méthode privée ni du layout interne du store.

**À faire :** Ajouter dans `ProjectStore` une méthode publique, par exemple :
- `get_episode_transform_meta_path(episode_id: str) -> Path`, ou
- `load_episode_transform_meta(episode_id: str) -> dict | None`

Puis utiliser cette méthode dans l’UI.

---

#### F. Index d’onglets en dur

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py`

**Problème :** Les index d’onglets sont codés en dur (ex. `self.tabs.widget(4)` pour les logs, `self.tabs.setCurrentIndex(2)` pour l’inspecteur). Un réordonnancement ou ajout d’onglets casse le comportement.

**À faire :** Introduire des constantes ou un mapping nom d’onglet → index (ou retrouver l’onglet par objet/widget) et utiliser ces références au lieu des entiers magiques.

---

#### G. Champs Projet non rafraîchis à l’ouverture

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py`  
**Méthode :** `_load_existing_project` (lignes 193–195)

**Problème :** Lors de l’ouverture d’un projet existant, seuls `proj_root_edit`, `series_url_edit` et `normalize_profile_combo` sont mis à jour. Les champs **Rate limit** (`rate_limit_spin`) et **Source** (`source_id_combo`) conservent leur valeur précédente (ou défaut). L’affichage du formulaire Projet ne reflète donc pas entièrement la config chargée.

**À faire :** Après avoir chargé la config, mettre à jour tous les champs de l’onglet Projet, par exemple :
- `self.rate_limit_spin.setValue(int(config.rate_limit_s))`
- `self.source_id_combo.setCurrentText(config.source_id)` (ou `setCurrentIndex` si l’id n’est pas dans la liste)

---

### 3.3 Priorité basse

#### G. Handler de log qui avale les exceptions

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py`  
**Classe :** `TextEditHandler.emit`

**Problème :** `except Exception: pass` masque toute erreur (widget détruit, etc.) et complique le débogage.

**À faire :** Au minimum logger l’exception (`logger.exception(...)`). Éviter un `pass` silencieux sur `Exception`.

---

#### H. Import et petits nettoyages

- **`db.py`** : déplacer `import datetime` (utilisé dans `set_episode_status`) en tête de fichier.
- **`subslikescript.py`** : regrouper les imports (stdlib, tiers, projet) en tête pour la lisibilité.
- **`project_store._write_toml`** : pour l’instant la config ne contient que des scalaires ; si on étend avec des types complexes, prévoir une sérialisation TOML correcte (ou une lib type `tomli-w` pour l’écriture).

---

#### I. Imports inutilisés (UI)

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py`

**Problème :** Imports déclarés mais non utilisés : `datetime`, `QTableWidget`, `QTableWidgetItem`, `QGroupBox`, `QAction`. Ils alourdissent le fichier et peuvent induire en erreur.

**À faire :** Supprimer ces imports.

---

#### J. Variable morte

**Fichier :** `src/howimetyourcorpus/core/normalize/profiles.py`  
**Ligne :** 52 (`span_start = i`)

**Problème :** `span_start` est assigné mais jamais utilisé.

**À faire :** Supprimer la ligne ou l’utiliser (ex. pour du debug ou des stats).

---

#### K. Type hint du handler de log

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py`  
**Attribut :** `self._log_handler`

**Problème :** Le type est déclaré `TextEditHandler | None`, alors qu’après ouverture d’un projet on y assigne un `logging.FileHandler`. Le type devrait refléter les deux cas.

**À faire :** Par exemple : `logging.Handler | None` ou `TextEditHandler | logging.FileHandler | None`.

---

#### L. Workers / thread

**Fichier :** `src/howimetyourcorpus/app/workers.py`

**Constat :** Après `_on_worker_finished`, `wait(3000)` est utilisé. Si le thread ne se termine pas dans ce délai, il reste actif sans message. Optionnel : réduire le timeout et logger un avertissement en cas de dépassement.

---

## 4. Bilan de la 4ᵉ révision

Tous les points des revues précédentes ont été corrigés. Aucun nouveau point bloquant n’a été identifié.

| Réf   | Sujet | Statut |
|-------|--------|--------|
| § 3.1 A | Handlers de log (fuite, logger ciblé) | ✅ Corrigé |
| § 3.1 B | API publique `load_project_config` au lieu de `_read_toml` | ✅ Corrigé |
| § 3.1 C | Signal `error` connecté à `_on_job_error` | ✅ Corrigé |
| § 3.2 D | FTS5 utilisé dans `query_kwic` | ✅ Corrigé |
| § 3.2 E | `load_episode_transform_meta` au lieu de `_episode_dir` | ✅ Corrigé |
| § 3.2 F | Constantes `TAB_*` pour les index d’onglets | ✅ Corrigé |
| § 3.2 G | `rate_limit_spin` et `source_id_combo` rafraîchis à l’ouverture | ✅ Corrigé |
| § 3.3 G | Exceptions loguées dans `TextEditHandler.emit` | ✅ Corrigé |
| § 3.3 H | Import `datetime` en tête de `db.py` | ✅ Corrigé |
| § 3.3 I | Imports inutilisés supprimés | ✅ Corrigé |
| § 3.3 J | Variable morte `span_start` supprimée | ✅ Corrigé |
| § 3.3 K | Type `_log_handler` → `logging.Handler \| None` | ✅ Corrigé |
| § 3.3 L | Avertissement si thread ne se termine pas (workers) | ✅ Corrigé |

**Imports subslikescript :** ordre stdlib / tiers / projet déjà correct.

---

### 4.1 Vérification 5ᵉ révision (relecture post-correctifs)

**Vérification effectuée :** relecture des fichiers modifiés et du flux principal.

| Élément | Statut |
|--------|--------|
| `_setup_logging_for_project` | ✅ Utilise `corpus_logger = logging.getLogger("howimetyourcorpus")` pour add/remove. |
| `load_project_config` | ✅ Utilisé dans `_load_existing_project` ; `_read_toml` n’est plus importé par l’UI. |
| Signal `error` | ✅ Connecté à `_on_job_error` ; `QMessageBox.critical` affiché. |
| `query_kwic` | ✅ Filtre via `documents_fts MATCH ?`, puis construction KWIC en Python ; `_fts5_match_query` pour l’échappement. |
| `load_episode_transform_meta` | ✅ Utilisé dans `_inspect_load_episode` ; plus d’usage de `_episode_dir` côté UI. |
| Constantes `TAB_*` | ✅ Définies et utilisées (`TAB_PROJET`, `TAB_LOGS`, `TAB_INSPECTEUR`, etc.). |
| Champs à l’ouverture | ✅ `rate_limit_spin.setValue` et `source_id_combo.setCurrentText` dans `_load_existing_project`. |
| `TextEditHandler.emit` | ✅ `logger.exception("TextEditHandler.emit")` au lieu de `pass`. |
| `db.py` | ✅ `import datetime` en tête ; `set_episode_status` sans import local. |
| Imports UI | ✅ `datetime`, `QTableWidget`, `QTableWidgetItem`, `QGroupBox`, `QAction` supprimés. |
| `profiles.py` | ✅ Ligne `span_start = i` supprimée. |
| `_log_handler` | ✅ Type `logging.Handler | None`. |
| `workers.py` | ✅ `if not self._thread.wait(3000): logger.warning(...)`. |
| `subslikescript.py` | ✅ Imports regroupés (stdlib, tiers, projet), puis `_make_soup`. |

**Conclusion :** Aucun point bloquant. Le code est cohérent avec les correctifs décrits.

**Points optionnels (priorité très basse, pour une évolution ultérieure) :**

- **`query_kwic`** : Si la fonction est un jour appelée avec un terme vide (en dehors de l’UI), `_fts5_match_query("")` produit `'""'` et FTS5 peut réagir de façon imprévisible. L’UI filtre déjà avec `if not term: return`. Pour plus de robustesse, on peut ajouter en tête de `query_kwic` : `if not term or not term.strip(): return []`. ✅ *Déjà en place dans le code.*
- **`subslikescript._make_soup`** : Le `except Exception:` (fallback lxml → html.parser) n’est pas loggé. Acceptable pour un fallback silencieux ; optionnel : logger en debug. ✅ *Corrigé en 6ᵉ révision : `logger.debug(...)` dans le fallback.*

---

### 4.2 Vérification 6ᵉ révision (reprise review Phase 3)

**Vérification effectuée :** relecture du code pour confirmer que tous les correctifs listés en § 3 sont bien présents.

| Élément | Statut |
|--------|--------|
| § 3.1 A – Handlers de log (logger `howimetyourcorpus` pour add/remove) | ✅ Présent dans `_setup_logging_for_project` |
| § 3.1 B – `load_project_config` au lieu de `_read_toml` | ✅ UI utilise `load_project_config` ; pas d’import `_read_toml` dans l’app |
| § 3.1 C – Signal `error` → `_on_job_error` | ✅ Connecté ; `QMessageBox.critical` affiché |
| § 3.2 D – FTS5 dans `query_kwic` | ✅ `documents_fts MATCH ?` + `_fts5_match_query` ; garde-fou `if not term or not term.strip(): return []` présent |
| § 3.2 E – `load_episode_transform_meta` au lieu de `_episode_dir` | ✅ `_inspect_load_episode` utilise `self._store.load_episode_transform_meta(eid)` |
| § 3.2 F – Constantes `TAB_*` | ✅ Définies et utilisées (`TAB_PROJET`, `TAB_LOGS`, etc.) |
| § 3.2 G – Champs Projet à l’ouverture | ✅ `rate_limit_spin.setValue`, `source_id_combo.setCurrentText` dans `_load_existing_project` |
| § 3.3 G – TextEditHandler.emit | ✅ `logger.exception("TextEditHandler.emit")` au lieu de `pass` |
| § 3.3 H – Import `datetime` en tête de `db.py` | ✅ Présent en tête de fichier |
| § 3.3 I – Imports inutilisés (UI) | ✅ Aucun import inutile (datetime, QTableWidget, etc.) dans la liste actuelle |
| § 3.3 J – Variable morte `span_start` | ✅ Supprimée dans `profiles.py` |
| § 3.3 K – Type `_log_handler` | ✅ `logging.Handler \| None` |
| § 3.3 L – Workers timeout | ✅ `if not self._thread.wait(3000): logger.warning(...)` dans `workers.py` |
| Optionnel `_make_soup` | ✅ `logger.debug` dans le fallback lxml → html.parser |

**Conclusion :** Tous les correctifs de la review Phase 3 sont appliqués. Un seul ajout lors de la 6ᵉ passe : log debug dans `subslikescript._make_soup` pour le fallback.

---

## 5. Synthèse pour le dev (référence historique)

Les points ci‑dessous ont été traités (voir § 4). Tableau conservé pour référence.

| Priorité | Réf   | Sujet |
|----------|-------|--------|
| Haute    | § 3.1 A | Gestion des handlers de log (éviter la fuite, cibler le logger `howimetyourcorpus`). |
| Haute    | § 3.1 B | API publique `load_project_config` au lieu de `_read_toml`. |
| Haute    | § 3.1 C | Signal `error` du JobRunner connecté pour afficher les erreurs. |
| Moyenne  | § 3.2 D | FTS5 utilisé dans `query_kwic`. |
| Moyenne  | § 3.2 E | `load_episode_transform_meta` au lieu de `_episode_dir`. |
| Moyenne  | § 3.2 F | Constantes `TAB_*` pour les onglets. |
| Moyenne  | § 3.2 G | Rafraîchir rate_limit_spin et source_id_combo à l’ouverture. |
| Basse    | § 3.3 G–L | TextEditHandler, imports, variable morte, type hint, workers. |

---

## 6. Fichiers modifiés (référence)

| Fichier | Modifications effectuées |
|---------|--------------------------|
| `src/howimetyourcorpus/app/ui_mainwindow.py` | Handlers de log, `load_project_config`, signal error, constantes TAB_*, champs à l’ouverture, TextEditHandler, imports, type hint |
| `src/howimetyourcorpus/core/storage/project_store.py` | `load_project_config`, `load_episode_transform_meta` / `get_episode_transform_meta_path` |
| `src/howimetyourcorpus/core/storage/db.py` | FTS5 dans `query_kwic`, import datetime en tête |
| `src/howimetyourcorpus/core/normalize/profiles.py` | Suppression de `span_start` |
| `src/howimetyourcorpus/app/workers.py` | Avertissement si thread ne se termine pas dans le délai |
| `src/howimetyourcorpus/core/adapters/subslikescript.py` | (6ᵉ révision) `logger.debug` dans le fallback `_make_soup` (lxml → html.parser) |

---

*Document généré à partir de la revue de code du projet HowIMetYourCorpus (6ᵉ révision).*

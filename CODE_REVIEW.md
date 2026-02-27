# Revue de code — HowIMetYourCorpus (HIMYC)

**Date** : 2026-02-27  
**Périmètre** : Code source `src/howimetyourcorpus`, tests `tests/`, selon la méthodologie `.cursor/rules/analyse-himyc.mdc`.

---

## 1. Synthèse

L’architecture est **claire et en couches** (UI → core → storage), avec une bonne séparation des responsabilités. Les **décorateurs** `@require_project` / `@require_db` / `@require_project_and_db` évitent la duplication des gardes. La **maintenabilité** est bonne (typage, découpage par onglets/contrôleurs). Quelques axes d’amélioration : factorisation de l’extraction d’`episode_id`, typage strict (`callable` → `Callable`), messages d’erreur plus contextualisés, et tests ciblés sur les zones à risque.

---

## 2. Points forts

### 2.1 Architecture et responsabilités

- **MainWindow** délègue correctement à `MainWindowProjectController`, `MainWindowJobsController`, `MainWindowTabsController` ; chaque contrôleur a un rôle précis.
- **Pipeline** : `PipelineRunner` + `steps` + `PipelineContext` ; pas de logique métier dans l’UI.
- **Storage** : `CorpusDB` avec `connection()` / `transaction()`, méthodes batch (`upsert_episodes_batch`), PRAGMA SQLite (WAL, cache, mmap) — Phase 6 bien intégrée.
- **Onglet Corpus** : découpage net entre `corpus_ui.py`, `corpus_view.py`, `corpus_context.py`, `corpus_workflow.py`, etc.

### 2.2 Déduplication et gardes

- **`ui_utils.py`** : `require_project`, `require_db`, `require_project_and_db` utilisés de façon homogène dans les onglets (Projet, Corpus, Inspecteur, Préparer, Alignement, Concordance, Personnages, Sous-titres).
- **Messages centralisés** : `show_info`, `show_warning`, `show_error`, `confirm_action` pour un style de dialogue cohérent.

### 2.3 UX / feedback

- Jobs asynchrones avec **QProgressDialog** (Phase 7 HP3), barre de progression onglet Corpus, annulation propre.
- Résumé de fin de job (succès/échecs, liste d’épisodes en échec), écriture dans l’onglet Logs.
- **Préparer** : `prompt_save_if_dirty()` à la sortie d’onglet et à la fermeture de la fenêtre.

### 2.4 Tests

- **34 fichiers** de tests (pipeline, DB, normalisation, segment, alignement, UI guards, dialogs, preparer, workers, etc.).
- Tests des **gardes UI** (`test_ui_guards.py`) avec monkeypatch sur `QMessageBox.warning` pour vérifier « Ouvrez un projet d'abord. ».

---

## 3. Améliorations recommandées

### 3.1 Factorisation — extraction `episode_id` depuis un message

**Problème** : La règle `analyse-himyc.mdc` signale un doublon : l’extraction d’un ID d’épisode (pattern `S01E01`) depuis un message d’erreur n’est faite que dans `MainWindowJobsController.build_job_summary_message` via `re.search(r"S\d+E\d+", message, re.IGNORECASE)`. Si d’autres endroits ont besoin du même pattern (logs, export, etc.), il y a risque de duplication.

**Recommandation** : Introduire une fonction réutilisable, par exemple dans `core.utils.text` ou `app.ui_utils` :

```python
def extract_episode_id_from_message(message: str) -> str | None:
    """Extrait l'ID épisode (ex. S01E01) depuis un message d'erreur ou de log."""
    match = re.search(r"S\d+E\d+", message, re.IGNORECASE)
    return match.group(0).upper() if match else None
```

Puis dans `mainwindow_jobs.py` : utiliser cette fonction au lieu du `re.search` inline.

**Impact** : Maintenabilité, unicité du format (ex. `.upper()`), réutilisation pour logs/rapports.

---

### 3.2 Typage — `callable` dans `aligner.py`

**Fichier** : `src/howimetyourcorpus/core/align/aligner.py`  
**Ligne** : `on_progress: callable | None = None`

**Problème** : Pour les annotations de type, il vaut mieux utiliser `typing.Callable` pour les signatures précises et la compatibilité avec les vérificateurs statiques.

**Recommandation** :

```python
from typing import Callable
# ...
on_progress: Callable[[int, int], None] | None = None  # (current, total) si c'est le contrat
```

Adapter la signature exacte au contrat du callback (paramètres et retour).

---

### 3.3 Gestion d’erreurs — messages plus contextualisés

**Constat** : Plusieurs `except Exception as e` affichent uniquement `str(e)` dans une `QMessageBox.critical`, sans indiquer l’action en cours ni une piste de résolution (comme recommandé dans la règle projet).

**Exemples** :
- `tab_corpus.py` (export) : `QMessageBox.critical(self, "Erreur", str(e))`
- `tab_concordance.py` (export KWIC, graphique) : idem
- `tab_sous_titres.py` (export SRT, sauvegarde) : idem
- `preparer_actions.py`, `preparer_persistence.py`, `preparer_context.py` : titre "Préparer" mais message générique

**Recommandation** : Pour les chemins critiques (export, sauvegarde, chargement), utiliser un message du type :

- « [Action] a échoué : {message}. Vérifiez les droits du fichier / que le projet est ouvert / … »  
et logger l’exception complète (`logger.exception(...)`), ce qui est déjà souvent le cas.

---

### 3.4 Refresh global après un job

**Fichier** : `mainwindow_jobs.py` — `refresh_tabs_after_job` appelle une liste fixe de rafraîchissements (episodes, inspecteur, preparer, subs, align, concordance, personnages).

**Constat** : Comportement correct pour garantir la cohérence. La règle projet suggère un « refresh ciblé » (seulement l’onglet visible) pour la performance.

**Recommandation** : Conserver le refresh global pour l’instant (cohérence des données). Si des lenteurs sont observées avec beaucoup d’épisodes, envisager soit un refresh différé (QTimer court), soit un refresh ciblé + refresh des autres onglets au premier affichage. Documenter le choix dans le code.

---

### 3.5 Duplication de logique « titre de message selon contexte »

**Fichier** : `ui_utils.py`  
Les décorateurs `require_project`, `require_db`, `require_project_and_db` répètent la même logique pour choisir le **titre** du message (« Corpus », « Sous-titres », « Préparer », etc.) à partir de `class_name` et `method_name`.

**Recommandation** : Extraire une fonction privée, par exemple `_message_title_for_context(class_name: str, method_name: str) -> str`, et l’appeler depuis les trois décorateurs. Réduit la duplication et facilite l’ajout de nouveaux contextes.

---

### 3.6 Longueur / complexité de certaines méthodes

- **`mainwindow_jobs.build_job_summary_message`** : ~20 lignes, lisible ; après factorisation de `extract_episode_id_from_message`, restera claire.
- **`tab_corpus.py`** : beaucoup de méthodes ; le découpage en `corpus_workflow`, `corpus_view`, etc. est déjà bien avancé. À surveiller : toute nouvelle grosse méthode devrait être placée dans le module approprié (workflow, view, context).
- **`pipeline/tasks.py`** : fichiers longs (plusieurs steps) ; acceptable pour un fichier de « registre » d’étapes. Si le fichier grossit encore, envisager un découpage par domaine (fetch, normalize, segment, subtitles, align).

---

### 3.7 Docstrings et type hints

- **core/models.py** : Dataclasses bien documentées (attributs + rôle).
- **core/align/aligner.py** : Bonne docstring pour `align_segments_to_cues` (paramètres, monotonic, etc.). À compléter par le typage `Callable` ci-dessus.
- **storage/db.py** : Méthodes publiques documentées ; `_conn()` et context managers clairs.
- **Recommandation** : Vérifier que les nouvelles fonctions publiques des onglets (export, actions métier) ont une docstring courte (une ligne) ou des type hints complets, selon la complexité.

---

### 3.8 Tests

- **Couverture** : Beaucoup de cas couverts (pipeline, DB, normalisation, alignement, UI guards, preparer, workers). Les tests UI utilisent `QT_QPA_PLATFORM=offscreen` où c’est pertinent.
- **Recommandation** :  
  - Ajouter un test unitaire pour `extract_episode_id_from_message` une fois la fonction introduite.  
  - Pour les exports (Corpus, Concordance, Sous-titres, Alignement), des tests d’intégration ou des tests unitaires sur les fonctions d’export (sans UI) renforceraient la non-régression.

---

## 4. Checklist rapide par thème

| Thème | État | Commentaire |
|-------|------|-------------|
| **SRP / découpage** | ✅ Bon | Contrôleurs, pipeline, storage bien séparés. |
| **Doublons** | ✅ Traité | extract_episode_id_from_message + _message_title_for_context (2026-02-27). |
| **UI cohérence** | ✅ Bon | Tooltips, QFormLayout / layouts, splitters. |
| **UX / feedback** | ✅ Bon | Progression, annulation, résumé de job, prompt sauvegarde Préparer. |
| **Erreurs** | ✅ Amélioré | Messages contextualisés (export corpus, SRT, KWIC, sauvegarde SRT) — 2026-02-27. |
| **Performance** | ✅ Bon | Batch DB, WAL, workers async ; refresh global après job assumé. |
| **Typage** | ✅ Corrigé | `callable` → `Callable` dans aligner.py. |
| **Tests** | ✅ Bon | + `test_utils_text.py` pour extract_episode_id_from_message. |

---

## 5. Actions proposées (par priorité)

1. **Priorité haute**  
   - Corriger le type `on_progress` dans `aligner.py` (`Callable` depuis `typing`). ✅ Appliqué.

2. **Priorité moyenne**  
   - Introduire `extract_episode_id_from_message` et l'utiliser dans `mainwindow_jobs.py`. ✅ Appliqué (core/utils/text.py).
   - Extraire `_message_title_for_context` dans `ui_utils.py` pour les décorateurs. ✅ Appliqué.

3. **Priorité basse**  
   - Enrichir les messages d’erreur (export, sauvegarde, chargement) avec contexte et suggestion.  
   - Ajouter tests pour la fonction d’extraction d’episode_id et, si possible, pour les exports.

---

## 6. Conclusion

Le projet est **solide** : architecture claire, bon usage des décorateurs et du pipeline, UI réactive et bien découpée. Les améliorations suggérées sont surtout de l’ordre du **nettoyage** (factorisation, typage, messages d’erreur) et du **renfort des tests**, sans changement d’architecture. La revue est alignée avec `STATUT_PHASES.md` et la règle `analyse-himyc.mdc`.

# Audit Fonctionnel — Vue Expert Transverse (2026-03-17)

## 1) Perimetre
- Cible: nouvelle vue `Expert` (onglet transverse) introduite dans `MainWindow`.
- Hors perimetre: refonte UX globale, corrections d autres onglets non lies.

## 2) Methode (preuves obligatoires)
- Capture code (refs de lignes et branchements): `evidence/branchage_refs.txt`, `evidence/tab_expert_controls_and_wiring_refs.txt`, `evidence/tab_expert_method_refs.txt`.
- Mesure runtime (snapshot reel): `evidence/expert_runtime_snapshot.txt`, `evidence/expert_runtime_metrics.json`, `evidence/expert_runtime_snapshot_mismatch.txt`, `evidence/expert_runtime_mismatch_metrics.json`.
- Mesure qualite/tests: `evidence/pytest_test_ui_expert_tab.log`, `evidence/pytest_expert_integration.log`, `evidence/pytest_global.log`.
- Inventaire et classification: `evidence/tab_expert_branching_matrix.json`, `evidence/tab_expert_branching_matrix.csv`, `evidence/tab_expert_branching_metrics.json`.

## 3) Verdict global
- Elements audites: **11**.
- Branches effectifs: **11**.
- Branches partiels: **0**.
- Non branches: **0**.
- Source: `evidence/tab_expert_branching_metrics.json`.

## 4) Inventaire fonctionnel (present vs vraiment branche)

| Element | Presence UI | Branchement reel | Preuve |
|---|---|---|---|
| `refresh_btn` (QPushButton) | Oui | Oui, signal `clicked` -> `refresh()` | `evidence/tab_expert_controls_and_wiring_refs.txt` (lignes 48-49) |
| `summary_edit` (QPlainTextEdit) | Oui | Oui, rendu par `setPlainText(...)` | `evidence/tab_expert_controls_and_wiring_refs.txt` (lignes 53-54, 277) |
| Montage onglet Expert | Oui | Oui, instance + ajout QTabWidget | `evidence/branchage_refs.txt` (`mainwindow_tabs.py:163-177`, `ui_mainwindow.py:105`) |
| Refresh a l activation onglet | Oui | Oui | `evidence/branchage_refs.txt` (`ui_mainwindow.py:329-330`) |
| Refresh post-job | Oui | Oui | `evidence/branchage_refs.txt` (`mainwindow_jobs.py:109`) + `evidence/pytest_expert_integration.log` |
| Refresh post-ouverture projet | Oui | Oui | `evidence/branchage_refs.txt` (`mainwindow_project.py:128`) |
| Refresh apres MAJ langues | Oui | Oui | `evidence/project_language_combo_refresh_excerpt.txt` (lignes 40-41) |
| Flag `Project loaded` | Oui | Oui (derive store+db) | `evidence/tab_expert_method_refs.txt` (ligne 219) + `evidence/expert_runtime_metrics.json` |
| Flag `Context consistent` | Oui | Oui (derive des episodes vus) | `evidence/tab_expert_method_refs.txt` (ligne 210) + `evidence/expert_runtime_mismatch_metrics.json` |
| Etat Alignement (segment filter etc.) | Oui | Oui | `evidence/tab_expert_method_refs.txt` + `evidence/expert_runtime_metrics.json` |
| Etat Propagation + Undo/Redo | Oui | Oui | `evidence/tab_expert_read_write_scan.txt` + `evidence/expert_runtime_snapshot_metrics.json` |

Conclusion controle/branchage: **aucun element present non branche detecte**.

## 5) Comportement observe (runtime)
- Cas nominal: snapshot genere, contexte coherent, episode `S01E01`, segment filter `utterance`, Undo `0`.
  - Preuves: `evidence/expert_runtime_snapshot.txt`, `evidence/expert_runtime_metrics.json`.
- Cas divergent: `Inspecteur=S01E01` vs `Preparer=S99E99` -> `Context consistent: no`.
  - Preuves: `evidence/expert_runtime_snapshot_mismatch.txt`, `evidence/expert_runtime_mismatch_metrics.json`.

## 6) Resultats tests
- Cible vue Expert: **3/3 pass**.
  - `evidence/pytest_test_ui_expert_tab.log`
- Integration inter-onglets: **6/6 pass**.
  - `evidence/pytest_expert_integration.log`
- Suite complete: **312/312 pass**.
  - `evidence/pytest_global.log`

## 7) Ecarts / risques classes (P0/P1/P2)

### P0 (corriger immediatement)
- **Aucun P0 detecte** sur la vue Expert.
- Preuve indirecte de stabilite: `evidence/pytest_global.log` + matrice sans non-branche.

### P1 (completer pour fiabiliser l interpretation)
1. Semantique `Project loaded` potentiellement optimiste.
- Observation: calcule via `bool(store and db)` sans verifier etat fonctionnel du projet ou acces reussi.
- Preuve: `evidence/tab_expert_method_refs.txt` (ligne 219).
- Impact: risque de faux positif d etat.

2. `Context consistent` mesure la coherence, pas la completude.
- Observation: coherence basee sur set des episodes non vides (<=1), donc "yes" possible avec vues partiellement vides.
- Preuve: `evidence/tab_expert_method_refs.txt` (ligne 210) + snapshots runtime.
- Impact: signal utile mais ambigu si certaines vues ne sont pas chargees.

### P2 (polish)
1. Auto-refresh temps reel pendant edition dans d autres onglets (quand Expert reste ouvert).
- Observation: refresh present sur activation onglet, jobs, ouverture projet, MAJ langues; pas d abonnement evenementiel universel.
- Preuve: `evidence/branchage_refs.txt`, `evidence/project_language_combo_refresh_excerpt.txt`.

2. Ajout d une legende explicite (coherence vs completude) dans la vue.
- Observation: actuellement indicateur unique `Context consistent`.
- Preuve: `evidence/expert_runtime_snapshot.txt`.

## 8) Decision d audit
- La vue Expert est **fonctionnelle et effectivement branchee**.
- Pas d element "present mais non branche" detecte.
- Sortie recommandee: accepter la vue en etat, puis traiter les 2 items P1 en priorite de cycle stabilisation.

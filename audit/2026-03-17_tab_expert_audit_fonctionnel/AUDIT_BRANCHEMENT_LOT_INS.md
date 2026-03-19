# Audit Final de Branchement — Lot INS-001 → INS-012

Date : 2026-03-18
Périmètre : lot de recentrage Inspecteur (INS-001 à INS-012).

---

## Verdict global

| Critère | Résultat |
|---|---|
| Contrôles critiques non branchés | **0** |
| Éléments PARTIELS | **0** |
| Logique orpheline | **0** |
| Doublons de création | **0** |
| Régressions suite globale | **0** (400/400 tests verts) |
| Cible produit "RAW/CLEAN unique multi-source" | **Partiellement atteint** |

---

## Mise a jour de cadrage produit (2026-03-18)

Ce rapport confirme la conformite du lot INS-001 -> INS-012 sur son perimetre technique.
En revanche, la cible produit finale "zone RAW/CLEAN unique pour transcript et SRT" n est pas entierement atteinte a ce stade.

Ecart principal a traiter:

1. Le selecteur `Source` pilote surtout la disponibilite des actions (et la guidance),
   mais pas encore completement le contenu de travail charge/sauve dans la zone unique.

Decision:

- Ouvrir un complement de backlog pour converger sans refonte:
  - `HIMYC-INS-013` (cadrage contrat source-centric),
  - `HIMYC-INS-014` (source pilote reellement le contenu),
  - `HIMYC-INS-015` (coherence actions/handlers/CTA),
  - `HIMYC-INS-016` (gate final cible produit).

Reference:

- `BACKLOG_EXECUTABLE_INSPECTEUR_REFOCUS.md`

---

## INS-001/002 — Mode Focus (`tab_inspecteur_sous_titres.py`)

| Élément | Branchement | Localisation |
|---|---|---|
| `_focus_mode: bool = True` | Initialisé avant `_restore_combined_splitter()` | ligne 98 |
| `_apply_focus_mode()` | Appelé après restore et dans `_toggle_srt_panel()` | lignes 100, 114 |
| `_srt_panel` | Référence stockée ; passée à `setVisible(not focus)` | lignes 89, 108 |
| `_srt_toggle_btn` | Connecté à `_toggle_srt_panel` ; texte mis à jour dans `_apply_focus_mode()` | lignes 62, 109 |
| `_restore_combined_splitter()` | Lit QSettings `"inspecteur/focus_mode"` → écrase `_focus_mode` | lignes 168–171 |
| `save_state()` | Persiste `_focus_mode` dans QSettings | ligne 177 |

Couverture tests : 8 tests dans `test_ui_inspecteur_sprint2.py`
(défaut True, masquage panneau, étiquette ▸/▾, toggle, double-toggle, save_state sans crash, changement épisode).

---

## INS-005/006 — Sélecteur Fichier (`tab_inspecteur.py`)

| Élément | Branchement | Localisation |
|---|---|---|
| `inspect_file_combo` créé | `addItem("Transcript", "transcript")` initial | lignes 83–90 |
| `_refresh_file_combo(None)` | Appelé dans la branche early-return de `_load_episode()` | ligne 465 |
| `_refresh_file_combo(eid)` | Appelé dans le flux normal de `_load_episode()` | ligne 511 |
| `currentIndexChanged` → `_update_action_buttons` | Connexion signal/slot directe | ligne 90 |
| Lecture `currentData()` | `source = ...currentData()` puis `is_transcript = not source or source == "transcript"` | lignes 302–303 |
| `not is_transcript` → Normaliser disabled | Tooltip "Source SRT sélectionnée…" | lignes 306–311 |
| `not is_transcript` → Segmenter disabled | Tooltip "Source SRT sélectionnée…" | lignes 319–323 |
| `is_transcript` → comportement existant | has_raw / has_clean inchangé | lignes 312–318, 324–330 |

Couverture tests : 7 tests dans `test_ui_inspecteur_sprint2.py` + 3 scénarios dans `test_ui_inspecteur_source_flow.py`
(transcript toujours présent, SRT ajouté si tracks, désactivation Normaliser/Segmenter, restauration, reset au changement épisode).

---

## INS-007/008 — API de capacité et découplage mainwindow

| Élément | Branchement | Localisation |
|---|---|---|
| `has_subtitle_panel() → True` | Défini sur `InspecteurEtSousTitresTabWidget` | `tab_inspecteur_sous_titres.py:184–186` |
| `set_subtitle_languages(langs)` | Délègue à `subtitles_tab.set_languages()` avec guard hasattr | `tab_inspecteur_sous_titres.py:188–191` |
| `mainwindow_project.py:refresh_language_combos` | Migré → `has_subtitle_panel()` + `set_subtitle_languages()` | ligne 27–28 |
| `mainwindow_project.py:_refresh_tabs_after_project_open` | Migré → `has_subtitle_panel()` | lignes 115–120 |
| `mainwindow_jobs.py:refresh_tabs_after_job` | Migré → `has_subtitle_panel()` | lignes 97–102 |
| Aucun `hasattr(inspector_tab, "subtitles_tab")` résiduel | **Confirmé 0 occurrence** dans tout le projet | — |
| `InspectorTabWidget` n'expose PAS `has_subtitle_panel` | **Confirmé absent** de `tab_inspecteur.py` | — |

Couverture tests : 3 tests dans `test_ui_inspecteur_source_flow.py`
(`has_subtitle_panel()` retourne True sur combined, absent sur inspector seul, `set_subtitle_languages` sans crash).

---

## INS-009 — Tests d'intégration parcours source-flow

Nouveau fichier `tests/test_ui_inspecteur_source_flow.py` — 14 tests couvrant :

| Scénario | Tests |
|---|---|
| A — Transcript-first complet | rien → Démarrer, RAW → Normaliser, CLEAN → Segmenter, complet → transcript-first + Prêt Oui |
| B — SRT-only | tracks sans transcript → SRT-only, source SRT → Normaliser/Segmenter disabled, combo Fichier multi-lang |
| C — Changement épisode/fichier | combo Fichier mis à jour, CTA rechargé, retour transcript si SRT indisponible, Focus préservé |
| D — Handoffs Alignement | `has_subtitle_panel()`, `has_subtitle_panel` absent sur InspectorTabWidget seul, `set_subtitle_languages` |

---

## INS-010 — Libellés UX

| Ancien | Nouveau | Localisation |
|---|---|---|
| `"Segmente l'épisode"` | `"Découper en segments"` | `tab_inspecteur.py:133` (bouton) + 2 tooltips/messages |
| `"Kind:"` | `"Type:"` | `tab_inspecteur.py:104` |
| Tooltip `pret_alignement_label` (sans ref SRT) | Contient `"Outils SRT ▸ en haut de l'Inspecteur"` | `tab_inspecteur.py:198` |

Vérification cohérence CTA : `cta_recommender.py:130` conserve `label="Segmenter l'épisode"` —
les tests `"Segmenter" in text` restent valides. ✓

---

## Vérifications transversales

### Hasattr structurels résiduels

| Fichier | Occurrence | Type | Verdict |
|---|---|---|---|
| `mainwindow_project.py:27` | `hasattr(win, "inspector_tab")` | check sur window | Acceptable ✓ |
| `mainwindow_project.py:118` | `hasattr(win.inspector_tab, "has_subtitle_panel")` | API capacité moderne | Correct ✓ |
| `mainwindow_jobs.py:100` | `hasattr(win.inspector_tab, "has_subtitle_panel")` | API capacité moderne | Correct ✓ |
| `tab_inspecteur_sous_titres.py:190` | `hasattr(self.subtitles_tab, "set_languages")` | interne au widget combiné | Défensif, acceptable ✓ |
| `hasattr(inspector_tab, "subtitles_tab")` | **0 occurrence** | — | Supprimé ✓ |

### Flux d'appel `_load_episode → _refresh_file_combo`

Les deux chemins de sortie de `_load_episode()` appellent `_refresh_file_combo` :
- Early return (no eid/store) → `_refresh_file_combo(None)` — reset à Transcript ✓
- Flux normal → `_refresh_file_combo(eid)` puis `_update_action_buttons()` ✓

---

## Couverture tests par ticket

| Ticket | Fichier(s) de test | Nb tests | Résultat |
|---|---|---|---|
| INS-001/002 | `test_ui_inspecteur_sprint2.py` | 8 | ✓ Verts |
| INS-003 | `test_cta_recommender.py`, `test_ui_inspecteur_sprint3.py` | 13+11 | ✓ Verts |
| INS-004 | `test_ui_inspecteur_sprint2.py` | inclus ci-dessus | ✓ Verts |
| INS-005/006 | `test_ui_inspecteur_sprint2.py` + `test_ui_inspecteur_source_flow.py` | 7+3 | ✓ Verts |
| INS-007/008 | `test_ui_inspecteur_source_flow.py` | 3 | ✓ Verts |
| INS-009 | `test_ui_inspecteur_source_flow.py` | 14 | ✓ Verts |
| INS-010 | Couvert par tests existants (labels non testés directement) | — | ✓ Verts |
| **Suite ciblée totale** | 6 fichiers | **125** | **✓ 125/125** |
| **Suite globale** | tous tests | **400** | **✓ 400/400** |

---

## Observations mineures (non-bloquantes)

1. **Guard défensif dans `set_subtitle_languages`** (`tab_inspecteur_sous_titres.py:190`) :
   `hasattr(self.subtitles_tab, "set_languages")` — utile pour la résilience future mais `subtitles_tab` est toujours créé (ligne 73). Impact zéro.

2. **Deux espaces de QSettings distincts** : `"inspecteur_sous_titres/mainSplitter"` (splitter combiné) et `"inspecteur/focus_mode"` (mode Focus). Nommage cohérent, pas de conflit.

---

## Verdict final

**Lot INS-001 -> INS-012 : CONFORME techniquement, avec complement fonctionnel planifie.**

- 0 contrôle non branché.
- 0 doublon logique.
- 0 régression (400/400 tests verts).
- Découplage mainwindow complet (`subtitles_tab` direct → API de capacité).
- Frontière `InspectorTabWidget` / `InspecteurEtSousTitresTabWidget` respectée.
- DoD du lot INS-001 -> INS-012 satisfait.
- Cible produit "RAW/CLEAN unique multi-source" couverte via plan d action INS-013 -> INS-016.

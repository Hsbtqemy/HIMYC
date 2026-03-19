# Backlog Executable - Recentrage Onglet Inspecteur

Date: 2026-03-18
Mise a jour: 2026-03-18 (cloture lot — 406/406 tests verts)
Contexte: suite a l audit UX/fonctionnel du 2026-03-18.
Objectif: desurcharger l Inspecteur et converger vers un modele "Episode + Fichier + vue de travail unique", sans reprise complete.

## Statut global : LIVRE

Suite ciblee finale :
`pytest -q` → **406/406 passes**

---

## Principes de livraison

- Pas de migration DB.
- Pas de refonte du pipeline de normalisation/segmentation/alignement.
- Priorite aux changements d orchestration UI et de couplage.
- Compatibilite transitoire obligatoire pour limiter le risque de regression.

## Plan d action valide (Lot 0 -> Lot 4) — CLOS

### Lot 0 - Cadrage fonctionnel ✅

- Objectif: figer le contrat produit "Source = contexte de travail".
- Resultat:
  - `Source=Transcript` → edition transcript (RAW/CLEAN + segmentation). ✅
  - `Source=SRT` → edition SRT dans la meme zone de travail. ✅
- Tickets:
  - HIMYC-INS-013 ✅

### Lot 1 - Recentrer le chargement par source ✅

- Objectif: le selecteur Source pilote le contenu charge/sauve, pas seulement les boutons.
- Tickets:
  - HIMYC-INS-014 ✅

### Lot 2 - Recentrer les actions et la guidance ✅

- Objectif: aucune contradiction entre boutons, handlers metier et CTA.
- Tickets:
  - HIMYC-INS-015 ✅

### Lot 3 - Garder SRT en outil avance ✅

- Objectif: vue par defaut epuree, outils SRT accessibles a la demande.
- Tickets:
  - HIMYC-INS-001 ✅
  - HIMYC-INS-002 ✅
  - HIMYC-INS-010 ✅

### Lot 4 - Durcissement qualite et gate final ✅

- Objectif: verrouiller la non-regression et cloturer avec preuves.
- Tickets:
  - HIMYC-INS-004 ✅
  - HIMYC-INS-009 ✅
  - HIMYC-INS-012 ✅
  - HIMYC-INS-016 ✅

---

## Ticket backlog

### HIMYC-INS-013 - Cadrer le contrat produit "Source pilote le contexte" ✅ LIVRE

Priorite: P0

Travaux:
- [x] Documenter le comportement cible transcript vs SRT dans l Inspecteur.
- [x] Valider la semantique du selecteur Source avec produit/UX.
- [x] Aligner les tooltips et labels avec le contrat (pas d ambiguite fonctionnelle).

AC:
- [x] Le comportement attendu de la zone RAW/CLEAN est explicite et versionne.
      → `DECISION_SOURCE_CONTEXTE_TRAVAIL.md`
- [x] Aucun texte UI ne promet une fonctionnalite non implementee.
      → Tooltip `inspect_file_combo` reecrit.

---

### HIMYC-INS-001 - Introduire un mode Focus dans l onglet Inspecteur ✅ LIVRE

Priorite: P0

Travaux:
- [x] Ajouter un mode d affichage "Focus transcript" par defaut.
- [x] Masquer le panneau Sous-titres au chargement (affichage reactivable).
- [x] Persister l etat (focus/complet) dans `QSettings`.

AC:
- [x] A l ouverture de l onglet Inspecteur, l utilisateur voit d abord la zone RAW/CLEAN.
- [x] Les outils SRT restent accessibles sans changer d onglet.
- [x] Aucune regression de chargement episode.

Validation: `pytest -q tests/test_ui_inspecteur_sprint2.py` → vert ✅

---

### HIMYC-INS-002 - Ajouter une commande explicite "Ouvrir outils SRT" ✅ LIVRE

Priorite: P0

Travaux:
- [x] Ajouter un bouton explicite pour afficher/masquer la zone SRT ("Outils SRT ▸/▾").
- [x] Clarifier le libelle (pas de comparaison RAW/CLEAN vs SRT implicite).
- [x] Garder le comportement existant import/normalisation piste.

AC:
- [x] Le chemin utilisateur vers les operations SRT est explicite et volontaire.
- [x] Aucun controle SRT critique ne disparait.

---

### HIMYC-INS-003 - Aligner microcopy et hints avec le nouveau flux ✅ LIVRE

Priorite: P0

Travaux:
- [x] Mettre a jour les textes CTA pour eviter la confusion "Inspecteur vs Sous-titres".
- [x] Mettre a jour les messages d avertissement Alignement references aux etapes prealables.
- [x] Mettre a jour tooltip onglet Inspecteur.

AC:
- [x] Les textes de guidance refletent le flux reel sans contradiction.
- [x] Les parcours `transcript-first` et `srt-only` restent explicites.

Validation: `pytest -q tests/test_cta_recommender.py tests/test_ui_inspecteur_sprint3.py` → vert ✅

---

### HIMYC-INS-004 - Verrouiller la non-regression UX P0 par tests UI ✅ LIVRE

Priorite: P0

Travaux:
- [x] Ajouter des tests de visibilite mode Focus/complet.
- [x] Ajouter un test de persistence `QSettings`.
- [x] Ajouter un test "ouverture outils SRT puis retour focus" sans perte de contexte episode.

AC:
- [x] Les tests couvrent le comportement par defaut et les transitions.
- [x] Pas de crash lors de changements rapides d episode.

Validation: `pytest -q tests/test_ui_inspecteur_sprint2.py tests/test_ui_inspecteur_sprint3.py` → vert ✅

---

### HIMYC-INS-005 - Introduire le selecteur "Source" dans Inspecteur ✅ LIVRE

Priorite: P1
Note: libelle final "Source :" (pas "Fichier :") — decision INS-013.

Travaux:
- [x] Ajouter un combo "Source" dans Inspecteur (`transcript`, `srt_<lang>`).
- [x] Reutiliser la logique d availability des sources basee sur les pistes episode.
- [x] Synchroniser episode + source sans casser la navigation existante.
- [x] Deduplication des entrees SRT par langue.

AC:
- [x] L utilisateur choisit explicitement la source a traiter.
- [x] Les options SRT indisponibles sont desactivees si piste absente.
- [x] Le changement episode conserve un choix source coherent (reset a Transcript si SRT indisponible).

---

### HIMYC-INS-014 - Source pilote reellement le contenu RAW/CLEAN ✅ LIVRE

Priorite: P1

Travaux:
- [x] Brancher le changement de Source sur le chargement du contenu de travail.
      → `_on_source_changed()` + `_load_source_content()` dans `tab_inspecteur.py`
- [x] Unifier la zone de travail pour transcript et SRT (sans nouveau schema DB).
      → SRT charge via `store.load_episode_subtitle_content(eid, lang)` dans `raw_edit`
- [x] Comportement coherent au switch : Transcript restaure RAW+CLEAN, SRT vide clean_edit.

AC:
- [x] Changer Source modifie le contenu charge dans la zone d edition.
- [x] Pas de perte de donnees lors du switch Transcript <-> SRT.
- [x] Le panneau SRT n est plus necessaire pour les modifications textuelles courantes.

Validation: tests scenarios E (4 tests) dans `test_ui_inspecteur_source_flow.py` → vert ✅

---

### HIMYC-INS-006 - Rendre les actions contextuelles selon la source ✅ LIVRE

Priorite: P1

Travaux:
- [x] Transcript: conserver Normaliser + Segmenter + Export segments.
- [x] SRT: desactiver Segmenter transcript et Normaliser avec tooltips explicites.
- [x] CTA source-aware : override si source SRT recommande une action desactivee.

AC:
- [x] Aucun bouton ne propose une action invalide pour la source courante.
- [x] Les raisons de desactivation restent explicites.

---

### HIMYC-INS-015 - Durcir coherence actions/handlers/CTA par source ✅ LIVRE

Priorite: P1

Travaux:
- [x] Ajouter des gardes metier dans `_run_normalize` et `_run_segment` selon la source active.
- [x] CTA override cote UI si source SRT active et recommandation porte sur action transcript-only.
- [x] Ajouter tests explicites sur les cas source SRT active (scenarios E et F).

AC:
- [x] Pas de contradiction entre CTA, boutons et handlers.
- [x] Meme en appel programmatique, les actions invalides sont bloquees proprement.

Validation: `pytest -q tests/test_ui_inspecteur_source_flow.py` → 20/20 vert ✅

---

### HIMYC-INS-007 - Introduire un adaptateur de capacite `subtitles_tab` ✅ LIVRE

Priorite: P1

Travaux:
- [x] Encapsuler l acces `inspector_tab.subtitles_tab` derriere une API stable.
      → `has_subtitle_panel()` + `set_subtitle_languages()` sur `InspecteurEtSousTitresTabWidget`
- [x] Fournir un fallback de compatibilite pour rafraichissement langues et jobs.
- [x] 0 occurrence de `hasattr(inspector_tab, "subtitles_tab")` dans mainwindow.

AC:
- [x] Les workflows projet/jobs fonctionnent sans dependre d un widget visible.
- [x] Aucun `AttributeError` en execution.

---

### HIMYC-INS-008 - Extraire les points de couplage vers une interface explicite ✅ LIVRE

Priorite: P1

Travaux:
- [x] Remplacer les checks structurels par des checks de capacite.
      → `mainwindow_project.py` + `mainwindow_jobs.py` migres vers `has_subtitle_panel()`
- [x] Cycle ouverture projet -> refresh tabs -> jobs stable.

---

### HIMYC-INS-009 - Couvrir les parcours utilisateur clefs en tests d integration ✅ LIVRE

Priorite: P1

Travaux:
- [x] Scenario transcript-first complet (4 tests).
- [x] Scenario srt-only complet (3 tests).
- [x] Scenario changement episode/fichier avec brouillon (4 tests).
- [x] Handoffs vers Alignement : `has_subtitle_panel()` / `set_subtitle_languages()` (3 tests).
- [x] INS-014 : source pilote contenu (4 tests).
- [x] INS-015 : guards metier (2 tests).

Fichier : `tests/test_ui_inspecteur_source_flow.py` — **20 tests verts** ✅

---

### HIMYC-INS-010 - Nettoyage UX final de l Inspecteur ✅ LIVRE

Priorite: P2

Travaux:
- [x] Libelles : "Segmente l'episode" → "Decouvrir en segments", "Kind:" → "Type:".
- [x] Tooltip `pret_alignement_label` aligne sur "Outils SRT ▸".
- [x] Coherence groupes `Consulter`, `Produire`, `Avance` verifiee.

---

### HIMYC-INS-011 - Documentation de migration ✅ LIVRE

Priorite: P2

Livrables :
- [x] `MIGRATION_INSPECTEUR_RECENTRAGE.md` — changelog complet lot INS-001→012.
- [x] `DECISION_SOURCE_CONTEXTE_TRAVAIL.md` — contrat produit Source=contexte.
- [x] `PLAN_SPRINTS_DETAILLE.md` — mis a jour avec etat reel 2026-03-18.
- [x] APIs de compatibilite et horizon de deprecation documentes.

---

### HIMYC-INS-012 - Gate final et cloture lot ✅ LIVRE

Priorite: P2

AC:
- [x] Suite ciblee verte : 125/125 (lot INS-001→012).
- [x] Suite globale : 400/400 apres lot INS-001→012.
- [x] Aucun incident bloquant ouvert.

---

### HIMYC-INS-016 - Gate complementaire cible produit "Source unique" ✅ LIVRE

Priorite: P2

AC:
- [x] Parcours transcript-first couvert par tests (scenarios A + E).
- [x] Parcours srt-only couvert par tests (scenarios B + E/F).
- [x] Zone de travail unique multi-source operationnelle.
- [x] Suite globale : **406/406** passes (6 tests additionels INS-014/015).

---

## Definition of Done globale ✅

- [x] Le mode par defaut de l Inspecteur est non surcharge (Focus mode actif).
- [x] L utilisateur choisit episode + source avant action.
- [x] Le choix de source pilote reellement le contenu charge.
- [x] Les actions proposees sont valides pour la source active.
- [x] Les parcours transcript-first et srt-only sont lisibles et testables.
- [x] Aucun changement de schema DB ni de pipeline d alignement.

## Risques residuels clos

1. ~~Risque de couplage cache dans d autres tests UI.~~ → 406/406 verts, aucun couplage cache.
2. ~~Risque de confusion temporaire pendant coexistence mode legacy/focus.~~ → Focus mode par defaut, transition transparente.
3. ~~Risque de creep scope.~~ → Politique anti-refonte respectee, pas de modification DB/pipeline.

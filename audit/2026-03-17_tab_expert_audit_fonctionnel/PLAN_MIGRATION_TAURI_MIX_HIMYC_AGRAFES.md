# Plan Migration - Tauri Mix HIMYC + AGRAFES (Squelette)

Date: 2026-03-18
Branche: `feature/tauri-mix-himyc-agrafes`
Perimetre: definir une trajectoire de migration pragmatique vers une UI Tauri (style AGRAFES) avec logique metier HIMYC.
Backlog executable associe: `BACKLOG_EXECUTABLE_TAURI_MIX_HIMYC_AGRAFES.md`

---

## 1) Objectif

Construire une version Tauri qui:
- gere la constitution de corpus transcript + SRT (multi-langues) par episode,
- preserve les dependances de sources (`transcript`, `srt_en`, `srt_fr`, etc.),
- supporte les gros corpus (jobs, reprise, suivi d avancement),
- evite une refonte "big bang" de toute la logique metier.

---

## 2) Contraintes non negociables

- Pas de perte fonctionnelle metier critique (normalisation, segmentation, alignement).
- Pas de changement schema DB non maitrise en phase initiale.
- Compatibilite de donnees avec projets HIMYC existants.
- Migration progressive avec checkpoints Go/No-Go.

### Baseline AGRAFES amont (obligatoire)

- Reference AGRAFES a utiliser: `origin/main@03a8790` (sync realise le 2026-03-18).
- Delta cle depuis l ancienne base locale (`9f58b01..03a8790`):
  - robustesse vue parallele (overflow + scroll colonne alignee + KWIC pivot lisible),
  - panneau meta (extrait hydrate avec contexte complet, sans flash inutile),
  - UX copie (copie par groupe aligne + copie citation multi-langue).
- Decision: la migration Tauri mix doit partir de cette baseline pour eviter de porter
  une version AGRAFES deja obsolete.
- Regle de gouvernance: apres figement, toute mise a jour AGRAFES au-dela de `03a8790`
  passe par un ticket dedie de bump baseline (pas de sync implicite en cours de sprint).

---

## 3) Architecture cible (proposition)

### 3.1 Frontend
- Shell Tauri inspire AGRAFES (navigation modes + sous-vues).
- Reprise prioritaire des composants UI AGRAFES de la baseline `03a8790` avant adaptation HIMYC.
- Stack frontend a figer en ADR (cible par defaut: TypeScript vanilla comme AGRAFES, sauf decision contraire explicite).
- Module `Constituer` (import corpus + orchestration sources episode).
- Module `Inspecter` (zone de travail unique par source selectionnee).
- Module `Aligner` (handoff explicite transcript-first / srt-only).

### 3.2 Backend
- Option A (recommandee court terme): reutiliser services HIMYC Python existants via sidecar/API locale.
- Option B (long terme): reimplementation progressive en Rust/TS si ROI confirme.

### 3.3 Modele de donnees
- Episode = agregat de sources.
- Source key canonique: `transcript`, `srt_<lang>`.
- Etats par source: `raw`, `normalized`, `segmented`, `ready_for_alignment`.
- Piste a exploiter: reutiliser le modele AGRAFES `doc_id + doc_relations` comme socle.
- Contrainte HIMYC: imposer `episode_key` + `source_key` sur chaque doc pour lever les ambiguities.
- Convention UX: `pivot/target` reserve a l Alignement; Inspecter reste en contexte `Episode + Source`.

---

## 4) Phasage executable

### Phase 0 - Discovery & contrat (3-5 jours)
Objectif:
- figer contrat fonctionnel source-centric.

Livrables:
- ADR architecture mix (frontend Tauri + backend HIMYC services),
- mapping des fonctionnalites HIMYC -> vues Tauri cibles,
- liste ecarts critiques et ordre de migration.
- decision emplacement shell (`/Users/hsmy/Dev/HIMYC/tauri-shell-himyc` en monorepo ou repo separe) — **repo Tauri public :** https://github.com/Hsbtqemy/HIMYC_Tauri.git,
- decision stack frontend (vanilla TS ou framework),
- strategie packaging sidecar Python pour pilote (lancement manuel vs orchestre).
- decision sur le mapping hybride `doc_id/doc_relations` -> `episode_key/source_key`.

DoD:
- decision ecrite sur backend (Option A/B),
- check-list de parite MVP validee,
- decisions repo/stack/packaging signees en ADR avant MX-002,
- mapping de donnees cible valide (ou rejete explicitement) avant MX-004.

---

### Phase 0 bis - Alignement amont AGRAFES (1-2 jours)
Objectif:
- verrouiller la baseline AGRAFES recente avant les travaux d integration HIMYC.

Livrables:
- reference commit AGRAFES documentee (`03a8790`),
- cartographie des apports amont reutilises tels quels vs adaptes,
- backlog d integration des deltas amont dans le shell Tauri HIMYC.

DoD:
- aucune ambiguite sur la version AGRAFES source,
- tickets d integration amont priorises avant bootstrap avance.

---

### Phase 1 - Bootstrap technique Tauri (4-6 jours)
Objectif:
- disposer d un shell Tauri operationnel dans HIMYC.

Livrables:
- app Tauri demarrable (dev/build),
- navigation modes initiale (`Constituer`, `Inspecter`, `Aligner` placeholders),
- connexion backend de base (healthcheck + config projet).

DoD:
- lancement local stable macOS,
- logs runtime exploitables,
- test smoke de navigation.

---

### Phase 2 - Constituer corpus multi-source (5-8 jours)
Objectif:
- porter import/download corpus et modeliser dependances par episode.

Livrables:
- ecran episodes + sources associees,
- import transcript/SRT multi-langues,
- jobs batch (queue, statut, reprise simple).

DoD:
- scenario complet "nouveau projet -> episodes -> sources importees",
- persistence et reprise apres redemarrage.

---

### Phase 3 - Inspecter source-centric (6-10 jours)
Objectif:
- zone de travail unique pilotee par `Episode + Source`.

Livrables:
- selecteur episode/source,
- edition contenu selon source active dans une vue unique,
- actions contextuelles coherentes (pas d actions invalides).

DoD:
- transcript-first: raw -> clean -> segments,
- srt-only: source SRT editable + handoff alignement,
- aucune contradiction CTA/boutons/handlers.

---

### Phase 4 - Aligner + parite fonctionnelle (6-10 jours)
Objectif:
- retablir parite alignement/exploitation.

Livrables:
- alignement transcript-first,
- alignement srt-only,
- messages d erreurs et guidance unifies.

DoD:
- scenarios nominal + erreurs courantes valides,
- export/resultats alignement verifies.

---

### Phase 5 - Gros corpus & industrialisation (5-8 jours)
Objectif:
- fiabiliser charge, perf et exploitation long run.

Livrables:
- batch volumineux (pagination, virtualisation si besoin),
- observabilite jobs (logs, metriques de progression),
- reprise robuste (interruption/restart).

DoD:
- benchmark corpus volumineux valide,
- absence de freeze UI sur operations longues.

---

## 5) Backlog initial (epics)

- MX-013: Verrouillage baseline AGRAFES amont (commit, deltas, strategie de reprise).
- MX-001: ADR architecture (backend, repo shell, stack frontend, packaging sidecar).
- MX-002: Bootstrap app Tauri dans HIMYC.
- MX-014: Port adapte des deltas AGRAFES `03a8790` (parallel/meta/copy UX).
- MX-003: Bridge backend vers services HIMYC existants.
- MX-016: Spike mapping `doc_id/doc_relations` vers `episode_key/source_key`.
- MX-004: Modele donnees source-centric.
- MX-005: Vue Constituer (episodes + import).
- MX-006: Orchestration jobs batch (gros corpus v1).
- MX-007: Vue Inspecter source-centric (zone unique).
- MX-008: Gardes metier et coherence CTA.
- MX-009: Handoff vers Aligner.
- MX-010: Parite messages et erreurs alignement.
- MX-015: Campagne non-regression Python + bridge pendant migration.
- MX-011: Hardening gros corpus.
- MX-012: Gate final pilote.
- MX-017: Recette visuelle interactive parite AGRAFES x HIMYC-TAURI.
- MX-018: Point d entree unifie HIMYC -> HIMYC-TAURI.

---

## 6) Risques majeurs + mitigation

1. Double stack (Tauri + backend Python) complexifie packaging.
- Mitigation: commencer par mode dev local + package interne avant distribution large.

2. Parite fonctionnelle inachevee.
- Mitigation: gates par phase avec scenarios metiers obligatoires.

3. Dette de couplage legacy HIMYC UI.
- Mitigation: extraire services metier stables avant portage complet des vues.

4. Performance sur gros corpus.
- Mitigation: profiling des requetes et rendering incremental des listes.

5. Derive entre AGRAFES amont et fork HIMYC pendant la migration.
- Mitigation: verrouiller commit de reference + ticket dedie de port amont (MX-013/MX-014).

6. Mauvaise decision tardive sur stack frontend ou packaging sidecar.
- Mitigation: rendre ces 2 decisions obligatoires dans l ADR MX-001 avant MX-002.

7. Ambiguite entre modeles AGRAFES (doc-centric) et HIMYC (episode/source-centric).
- Mitigation: ticket de spike dedie (MX-016) avec criteres d acceptation avant MX-004.

8. Confusion de lancement entre app PyQt HIMYC et pilote Tauri (repo separe).
- Mitigation: recette visuelle ciblee + entree de lancement unifiee (MX-017/MX-018).

---

## 7) Checkpoints Go/No-Go

- Gate A (fin Phase 0 + 0 bis, MX-013 + MX-001): baseline AGRAFES + ADR architecture valides.
- Gate B (fin Phase 2, MX-002 + MX-014 + MX-003 + MX-016 + MX-004..MX-006): shell Tauri + bridge + constitution multi-source operationnels.
- Gate C (fin Phase 3, MX-007..MX-009): Inspecter source-centric + handoff alignement valides.
- Gate D (fin Phase 5, MX-010 + MX-015 + MX-011 + MX-012): hardening, non-regression et pilote valides.
- Gate E (post-pilote, MX-017 + MX-018): parite visuelle confirmee + lancement unifie.

---

## 8) Criteres de succes

- L utilisateur travaille avec un flux unique episode + source.
- Les dependances de sources par episode sont explicites et robustes.
- Le mapping `doc_id/doc_relations` est encapsule proprement vers `episode_key/source_key`.
- Les parcours transcript-first et srt-only sont tous deux first-class.
- La charge gros corpus est supportee sans degradation bloquante.

---

## 9) Prochaine action immediate

1. Ouvrir et executer MX-013 (baseline AGRAFES `03a8790` + note de delta).
2. Executer MX-001 pour figer repo shell, stack frontend et packaging sidecar pilote.
3. Ouvrir MX-002 et MX-014 une fois Gate A valide, puis lancer MX-016 avant MX-004.
4. Apres Gate D, executer MX-017 puis MX-018 pour fermer l ambiguite d usage.

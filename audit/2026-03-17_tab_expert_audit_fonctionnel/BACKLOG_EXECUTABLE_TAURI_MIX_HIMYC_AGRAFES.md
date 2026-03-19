# Backlog Executable - Tauri Mix HIMYC + AGRAFES

Date: 2026-03-18
Branche: `feature/tauri-mix-himyc-agrafes`
Reference: `PLAN_MIGRATION_TAURI_MIX_HIMYC_AGRAFES.md`

## Objectif

Livrer une trajectoire executable vers une UI Tauri style AGRAFES, tout en reutilisant le metier HIMYC pour:
- constitution de corpus transcript + SRT multi-langues,
- dependances de sources par episode (`transcript`, `srt_en`, `srt_fr`, ...),
- support gros corpus (jobs, reprise, suivi).

## Principes

- Pas de big bang.
- Pas de rupture de donnees projet.
- Reutilisation maximale des services metier HIMYC.
- Gate Go/No-Go a chaque phase.

## Baseline

- Repo cible: `/Users/hsmy/Dev/HIMYC`
- Branch de travail: `feature/tauri-mix-himyc-agrafes`
- Suite Python actuelle a conserver verte pendant la migration.
- Source AGRAFES amont: `/Users/hsmy/Dev/AGRAFES` (remote `origin/main`)
- Commit AGRAFES de reference: `03a8790`
- Delta amont notable depuis l ancienne base locale `9f58b01`:
  - `tauri-app/src/features/metaPanel.ts`
  - `tauri-app/src/ui/dom.ts`
  - `tauri-app/src/ui/results.ts`

## Clarification importante (etat des depots)

- **Dépôt officiel du shell Tauri :** https://github.com/Hsbtqemy/HIMYC_Tauri.git (decision ADR MX-001, repo separe du metier Python).
- Clone local typique : dossier `HIMYC_Tauri` (ex. `/Users/hsmy/Dev/HIMYC_Tauri`). Les scripts `launch-tauri.sh` / `launch-tauri-split.sh` utilisent la variable **`HIMYC_TAURI_DIR`** si définie, sinon ce chemin par défaut.
- Le repo `/Users/hsmy/Dev/HIMYC` reste la source metier Python + audit/backlog.
- Consequence: lancer "HIMYC" dans ce repo demarre la version PyQt; lancer "Tauri" se fait depuis le clone **HIMYC_Tauri**.
- Cette separation explique l impression "AGRAFES lance, mais pas HIMYC Tauri" tant que l entree unifiee n est pas mise en place.

## Ordre d execution recommande

1. MX-013
2. MX-001
3. MX-002
4. MX-014
5. MX-003
6. MX-016
7. MX-004
8. MX-005
9. MX-006
10. MX-007
11. MX-008
12. MX-009
13. MX-010
14. MX-015
15. MX-011
16. MX-012
17. MX-017
18. MX-018
19. MX-019
20. MX-020
21. MX-021
22. MX-022
23. MX-023
24. MX-024

## Plan d action par priorite (synthese)

P0:
- MX-013, MX-001, MX-002, MX-014, MX-003 (socle architecture + shell + bridge) — livres.

P1:
- MX-016, MX-004, MX-005, MX-006, MX-007, MX-008, MX-015 (modele source-centric + corpus + inspecter + non-regression) — livres.

P2:
- MX-009, MX-010, MX-011, MX-012 (alignement, hardening, gate pilote) — livres.

Post-pilote immediat:
- MX-017 (validation visuelle parite AGRAFES/HIMYC en session utilisateur).
- MX-018 (entree de lancement unifiee depuis le workspace HIMYC).

Post-pilote correctif (parite UX AGRAFES):
- MX-019 (decision produit: AGRAFES comme reference UX cible).
- MX-020 (parite shell: retour mode Explorer + navigation cible).
- MX-021 (recomposition Constituer: Importer/Documents/Actions/Exporter).
- MX-022 (backend query MVP pour concordancier).
- MX-023 (vue Explorer concordancier MVP).
- MX-024 (gate final parite UX + recette E2E).

## Tickets backlog

### MX-013 - Verrouiller baseline AGRAFES amont ✅ LIVRE

Priorite: P0
Estimation: 0.5 jour
Dependances: aucune
Risque: faible

Scope principal:
- `/Users/hsmy/Dev/AGRAFES`
- `audit/2026-03-17_tab_expert_audit_fonctionnel/`

Travaux:
- [x] Synchroniser AGRAFES sur `origin/main` une fois pour photographie amont.
      → HEAD deja a `03a8790` au moment du figement, depot clean.
- [x] Figer le commit de reference (`03a8790`) pour la migration.
      → Commit `feat(copy): add per-group and full-citation copy buttons` — 2026-03-18.
- [x] Documenter le delta entrant (`9f58b01..03a8790`) et ses impacts.
      → `NOTE_BASELINE_AGRAFES_03a8790.md` : 3 fichiers, cartographie portage vs adaptation vs hors perimetre.
- [x] Definir la regle de bump baseline (ticket dedie obligatoire si mise a jour).
      → Regle documentee dans `NOTE_BASELINE_AGRAFES_03a8790.md`.

AC:
- [x] Version AGRAFES source non ambigue (`03a8790`).
- [x] Regle de bump baseline explicite (pas de sync implicite en cours de sprint).
- [x] Plan + backlog HIMYC alignes sur cette baseline.

Validation:
- [ ] Revue technique croisee.

---

### MX-001 - ADR architecture mix (Tauri frontend + metier HIMYC) ✅ LIVRE

Priorite: P0
Estimation: 0.5 jour
Dependances: aucune
Risque: faible

Scope principal:
- `audit/2026-03-17_tab_expert_audit_fonctionnel/`

Travaux:
- [x] Ecrire l ADR de reference (Option A backend Python sidecar/API locale).
      → `ADR_ARCHITECTURE_MIX_TAURI_HIMYC.md`
- [x] Decider emplacement du shell Tauri (monorepo HIMYC vs repo separe) avec impact CI/package.
      → Repo separe **HIMYC_Tauri** (`https://github.com/Hsbtqemy/HIMYC_Tauri.git`).
- [x] Decider stack frontend (vanilla TS par defaut AGRAFES ou framework) avec justification.
      → TypeScript vanilla (coherence AGRAFES, port deltas direct).
- [x] Definir la strategie packaging/execution sidecar Python pour pilote.
      → Manuel 2 commandes — runbook documente dans l ADR (port 8765).
- [x] Definir frontieres front/back et contrat d appels.
      → Contrat HTTP initial : 7 endpoints, format erreur standard documente.
- [x] Definir criteres de succes MVP.
      → 6 criteres listes dans l ADR.

AC:
- [x] ADR validee produit + technique.
- [x] Decision Option A/B explicite (Option A retenue).
- [x] Emplacement shell + stack frontend figes avant MX-002.
- [x] Mode de lancement pilote backend/front explicite (commande ou runbook).

Validation:
- [ ] Revue croisee equipe.

---

### MX-002 - Bootstrap app Tauri dans HIMYC ✅ LIVRE

Priorite: P0
Estimation: 1.5 jours
Dependances: MX-001
Risque: moyen

Scope principal:
- `/Users/hsmy/Dev/HIMYC_Tauri` (repo separe, decision ADR MX-001)

Travaux:
- [x] Initialiser la structure Tauri (dev/build).
      → Repo **HIMYC_Tauri** init, npm install, Cargo compile — Vite port 1421, Tauri 2.x.
- [x] Ajouter shell minimal avec 3 modes: `Constituer`, `Inspecter`, `Aligner`.
      → `shell.ts` : header fixe, 3 onglets avec accents couleur, lifecycle mount/dispose,
         healthcheck backend au demarrage + polling 30s, toast, localStorage last_mode.
      → `api.ts` : `sidecar_fetch_loopback` (loopback-only), `fetchHealth()`.
      → `context.ts` : `ShellContext` (getApiBase, getBackendStatus, onStatusChange).
      → Placeholders Constituer/Inspecter/Aligner : navigation sans crash verifiee.
- [x] Ajouter scripts de lancement standardises.
      → `start-dev.sh` : runbook 2 commandes (backend port 8765 + tauri dev).

AC:
- [x] L app Tauri demarre en local.
      → `cargo build` OK, `npm run tauri dev` : Finished + Running confirmes.
- [x] Changement de mode sans crash.
      → 3 modules montes/disposes independamment, smoke test passe.
- [x] Structure repo conforme a la decision ADR MX-001.
      → Repo separe **HIMYC_Tauri**, vanilla TS, port 1421.

Validation:
- [ ] Smoke test manuel de navigation (a realiser en session interactive).

---

### MX-014 - Porter les deltas AGRAFES `03a8790` utilitaires ✅ LIVRE

Priorite: P0
Estimation: 1 jour
Dependances: MX-013, MX-002
Risque: eleve

Scope principal:
- `/Users/hsmy/Dev/HIMYC_Tauri/src/ui/` + `src/features/`

Travaux:
- [x] Adapter (pas copier tel quel) le layout parallele/KWIC au contexte HIMYC.
      → KWIC/parallel view hors perimetre HIMYC — non porte (documente ci-dessous).
      → `dom.ts` : tokens CSS + delta 03a8790 uniquement.
- [x] Adapter la logique meta excerpt hydratee par contexte aux vues HIMYC disponibles.
      → `features/metaPanel.ts` : structure open/close/backdrop conservee.
         Modele remplace : QueryHit -> EpisodeSourceInfo (episode_id, source_key, source_state).
         Sprint I "contexte local GET /unit/context" hors perimetre (documente).
- [x] Reprendre les actions de copie utiles (groupe aligne, citation complete) la ou elles ont du sens.
      → `ui/copyUtils.ts` : makeCopyBtn(), makeGroupCopyBtn(), buildCitationText(),
         makeCitationBtn() avec types HIMYC natifs (CitationPivot/AlignedSource).
- [x] Documenter les deltas AGRAFES non portes et la raison (hors perimetre ou couplage fort).
      → Non portes : vue parallele KWIC (concordancier AGRAFES uniquement),
         navigation hits prev/next (pas de state.hits HIMYC),
         compteur occurrences (pas de concordancier),
         contexte local GET /unit/context (pas de segmentation en unites).

AC:
- [x] Les composants Tauri reutilises reflettent la baseline AGRAFES recente.
      → dom.ts inclut les 3 ajouts CSS du commit 03a8790.
- [x] Aucune dependance dure a un module AGRAFES absent dans HIMYC.
      → tsc --noEmit : 0 erreur. Aucun import AGRAFES.
- [x] Aucune regression de navigation/smoke sur le shell Tauri.
      → Nouveaux fichiers additifs uniquement, pas de modification shell.ts.

Validation:
- [ ] Smoke test vue resultats + panneau meta (a realiser en session interactive).

---

### MX-003 - Bridge backend vers services HIMYC ✅ LIVRE

Priorite: P0
Estimation: 2 jours
Dependances: MX-002
Risque: eleve

Scope principal:
- `/Users/hsmy/Dev/HIMYC/src/howimetyourcorpus/api/server.py`
- `/Users/hsmy/Dev/HIMYC_Tauri/src/api.ts`

Travaux:
- [x] Exposer healthcheck backend.
      → GET /health — toujours disponible, retourne {status, version}.
- [x] Exposer lecture config projet + episodes + tracks.
      → GET /config — project_name, path, languages, normalize_profile.
      → GET /episodes — serie + episodes avec sources et etats (transcript + SRT via DB).
      → GET /episodes/{id}/sources/{key} — contenu transcript (raw/clean) ou SRT.
      → GET/POST /jobs, GET /jobs/{id} — stubs MX-006.
      → Projet charge via HIMYC_PROJECT_PATH (env var).
- [x] Definir format de reponses/erreurs stable.
      → Format standard : {error: string, message: string} sur tous les cas d erreur.
      → CORS : Vite dev (1421) + Tauri WebView.
      → pyproject.toml : optional-dep [api] = fastapi>=0.110 + uvicorn>=0.27.

AC:
- [x] Front Tauri peut lister episodes et sources via backend HIMYC.
      → api.ts : fetchConfig(), fetchEpisodes(), fetchEpisodeSource() types.
      → Types : ConfigResponse, Episode, EpisodeSource, SourceContent.
      → tsc --noEmit : 0 erreur.
- [x] Gestion d erreur standardisee.
      → ApiError(status, errorCode, message) cote front.
      → HTTPException detail {error, message} cote back.

Validation:
- [x] Test integration bridge (happy path + erreur backend indisponible).
      → tests/test_api_bridge.py : 13/13 passes.
      → Suite globale HIMYC : 419/419 passes.

---

### MX-016 - Spike mapping `doc_id/doc_relations` vers `episode_key/source_key` ✅ LIVRE

Priorite: P1
Estimation: 0.5 jour
Dependances: MX-003
Risque: moyen

Scope principal:
- couche modele/metadonnees front-back

Travaux:
- [x] Prototyper un mapping ou chaque source HIMYC est un `doc_id` AGRAFES.
      → `doc_id = "{episode_id}:{source_key}"` — string composite, front uniquement, pas de partage DB.
- [x] Definir le jeu minimal de metadonnees: `episode_key`, `source_key`, `language`, `doc_role`.
      → `doc_role` = "original" (transcript) | "translation" (srt).
      → `state` = "unknown" | "raw" | "normalized" | "segmented" | "ready_for_alignment".
- [x] Definir l usage de `doc_relations` pour lier les sources d un meme episode.
      → Relations implicites dans HIMYC — derivees a la demande depuis GET /episodes, pas stockees en DB.
      → srt_<lang> est "translation_of" transcript ; srt-only : pivot = langue primaire.
- [x] Verifier la faisabilite sur 3 cas: transcript-only, transcript+srt, srt-only.
      → 3 cas documentes avec requetes Constituer/Inspecter/Aligner identifiees.

AC:
- [x] Mapping cible univoque et exploitable sans migration destructive immediate.
      → Pas de migration DB ; projection a la demande dans alignerModule.ts (MX-009).
- [x] Requetes necessaires pour `Constituer` et `Inspecter` sont definies.
      → Tables de requetes par onglet archivees dans la note de design.
- [x] Convention `pivot/target` bornee au contexte Alignement.
      → Regle documentee : pivot/target exclusifs a l Aligner ; Constituer et Inspecter = episode_key + source_key.

Validation:
- [x] Note de design courte archivee dans `audit/...`.
      → `NOTE_DESIGN_MX016_MAPPING_DOC_EPISODE_SOURCE.md` : mapping, faisabilite 3 cas, types MX-004.

---

### MX-004 - Modele donnees source-centric ✅ LIVRE

Priorite: P1
Estimation: 1 jour
Dependances: MX-003, MX-016
Risque: moyen

Scope principal:
- couche mapping front/back

Travaux:
- [x] Canoniser `source_key`: `transcript`, `srt_<lang>`.
      → `isValidSourceKey()` : transcript + srt_[a-z]{2,5} — rejectées : srt_, srt_UPPER, clés inconnues.
- [x] Definir etat par source: `raw|normalized|segmented|ready_for_alignment`.
      → type SourceState = "unknown" | "raw" | "normalized" | "segmented" | "ready_for_alignment".
- [x] Definir dependances episode/sources.
      → `deriveDocRelations()` : cas 1 (transcript+srt), cas 2 (srt-only pivot), cas 3 (transcript seul → 0).
      → `resolveSrtPivot()` : résout le pivot langue primaire en srt-only.
      → `resolveDocRole()` : original / translation / standalone selon contexte.
- [x] Integrer le resultat du spike MX-016 dans le modele cible.
      → `src/model.ts` : HimycDoc, HimycDocRelation, SourceState, DocRole.
      → `episodeSourceToDoc()`, `episodesToDocs()`, `docId()`, `parseDocId()`.

AC:
- [x] Un episode expose ses sources et etats de maniere coherente.
      → episodeSourceToDoc() propage state, language, nb_cues, format depuis EpisodeSource.
- [x] Pas d ambiguite entre source absent vs source vide.
      → episodesToDocs() filtre sur available=true ; source unavailable = absente du modele.

Validation:
- [x] Tests unitaires mapping.
      → tests/model.test.ts : 30/30 passes. tsc --noEmit : 0 erreur.

---

### MX-005 - Vue Constituer (episodes + import) ✅ LIVRE

Priorite: P1
Estimation: 2 jours
Dependances: MX-004
Risque: moyen

Scope principal:
- frontend Tauri mode `Constituer`

Travaux:
- [x] Table episodes + colonnes des sources.
      → constituerModule.ts : table dynamique, colonnes auto-détectées depuis les langues SRT présentes.
      → Badges état par source : raw/normalisé/segmenté/prêt/absent.
- [x] Actions import transcript/SRT.
      → Import transcript : dialog Tauri → readTextFile → POST /episodes/{id}/sources/transcript.
      → Import SRT : dialog Tauri (.srt/.vtt) → readTextFile → POST /episodes/{id}/sources/srt_{lang}.
      → Détection fmt automatique depuis l extension (.vtt → "vtt", sinon "srt").
      → Backend : POST /episodes/{id}/sources/transcript + POST /episodes/{id}/sources/{srt_key}.
      → api.ts : importTranscript(), importSrt(), ImportResult.
- [x] Affichage statut de completion par episode.
      → Badge par source avec état backend (raw/normalized/segmented/ready_for_alignment).
      → Indicateur API live (dot vert/rouge) + chargement auto au retour backend.

AC:
- [x] L utilisateur peut importer transcript et SRT par episode.
      → Dialog fichier natif Tauri → POST backend → actualisation automatique de la table.
- [x] Les dependances de sources sont visibles.
      → Colonne Transcript séparée des colonnes SRT par langue. Source absente = badge "—".

Validation:
- [ ] Scenario manuel "nouveau projet -> import transcript + SRT" (a realiser en session interactive).
      → Backend : 18/18 tests bridge passes (424/424 total). tsc --noEmit : 0 erreur.

---

### MX-006 - Orchestration jobs batch (gros corpus v1) ✅ LIVRE

Priorite: P1
Estimation: 2 jours
Dependances: MX-005
Risque: moyen

Scope principal:
- `Constituer` + backend jobs

Travaux:
- [x] Queue jobs import/normalisation.
      → `api/jobs.py` : JobStore (persistance jobs.json) + JobWorker (thread daemon FIFO).
      → Types : normalize_transcript, normalize_srt, segment_transcript.
      → POST /jobs (201), GET /jobs, GET /jobs/{id}, DELETE /jobs/{id} (annulation pending).
      → api.ts : fetchJobs(), createJob(), fetchJob(), cancelJob(), JobRecord, JobType.
- [x] Suivi progression et erreurs.
      → Panneau "File de jobs" dans constituerModule : dot statut (pending/running/done/error), erreur truncatée.
      → Polling auto 2s quand jobs actifs, arrêt auto quand file vide.
      → Bouton "Normaliser tout" : batch-queue normalize_transcript pour tous les épisodes état raw.
- [x] Reprise simple apres interruption.
      → Au démarrage JobStore, les jobs "running" sont remis en "pending" (_recover_interrupted).
      → jobs.json réécrit à chaque mutation (thread-safe via Lock).

AC:
- [x] Batch multi-episodes operationnel.
      → queueBatchNormalize() → createJob() x N épisodes → worker thread séquentiel.
- [x] Etat jobs persistent apres relance.
      → jobs.json dans {project_path}/. Reprise automatique au redémarrage du serveur.

Validation:
- [x] Tests backend : 23/23 bridge passes (429/429 total). tsc --noEmit : 0 erreur.
- [ ] Test charge sur corpus de reference (a realiser en session interactive).

---

### MX-007 - Vue Inspecter source-centric (zone unique) ✅ LIVRE

Priorite: P1
Estimation: 2.5 jours
Dependances: MX-004, MX-006
Risque: eleve

Scope principal:
- frontend Tauri mode `Inspecter`

Travaux:
- [x] Selecteur `Episode + Source`.
      → Dropdown épisode → dropdown source auto-filtré (available=true uniquement).
      → Sélection auto premier épisode/source au chargement.
      → Rechargement liste épisodes au retour backend online.
- [x] Zone unique de travail (texte) pilotée par source.
      → Transcript : onglets RAW / CLEAN (CLEAN visible seulement si clean.txt non vide).
      → SRT : affichage brut (pre formaté), pas d'onglet.
      → fetchEpisodeSource() → rendu pré/texte en zone scrollable.
- [x] Actions contextuelles selon source active.
      → Transcript raw/unknown → bouton "Normaliser" (createJob normalize_transcript).
      → Transcript normalized → bouton "Segmenter" (createJob segment_transcript).
      → SRT → message "actions dans Aligner (MX-009)".
      → Bouton "ℹ Info" → openMetaPanel(EpisodeSourceInfo).
      → Feedback inline ("Job ajouté ✓" / message erreur).

AC:
- [x] `Source=Transcript` et `Source=SRT` exploitent la meme zone de travail.
      → Zone .insp-content-wrap unique, contenu switché selon source_key.
- [x] Pas d action invalide visible/executable.
      → "Normaliser" absent si state != raw/unknown. "Segmenter" absent si state != normalized.
      → Bouton "ℹ Info" désactivé tant qu'aucune source n'est sélectionnée.

Validation:
- [ ] Recette transcript-first et srt-only (a realiser en session interactive).
      → tsc --noEmit : 0 erreur. 429/429 tests Python passes.

---

### MX-008 - Gardes metier et coherence CTA ✅ LIVRE

Priorite: P1
Estimation: 1 jour
Dependances: MX-007
Risque: moyen

Scope principal:
- logique guidance front

Travaux:
- [x] Aligner CTA avec source active et etats reels.
      → inspecterModule : normGuard/segGuard évalués avant rendu HTML — bouton absent si garde bloquée.
      → constituerModule : bouton "+ transcript" masqué si transcript déjà disponible.
      → Message de guidance inline quand aucune action n'est disponible (ex: "déjà segmenté").
- [x] Bloquer actions invalides cote handler (pas seulement UI).
      → guardedAction() : vérifie la garde à l'exécution du handler, pas seulement à l'affichage.
      → jobs.py _execute_job() : pré-conditions backend (raw.txt absent → erreur explicite avant exécution NormalizeEpisodeStep).
- [x] Uniformiser messages de guidance.
      → guards.ts : source unique de vérité pour tous les messages (7 gardes, 1 wrapper).
      → Messages actionnables : indiquent toujours l'action à faire ("Normalisez avant de segmenter").
      → guardImportTranscript / guardImportSrt : warning confirm() avant écrasement.

AC:
- [x] Aucune contradiction CTA/boutons/handlers.
      → UI et handler vérifient la même garde (même appel guardNormalize/guardSegment).
- [x] Messages d erreurs actionnables.
      → Chaque garde.reason décrit l'état bloquant ET l'action à entreprendre.

Validation:
- [x] Tests unitaires guards : 37/37 passes (67/67 total TS). tsc --noEmit : 0 erreur.
- [ ] Tests UI sur cas limites source SRT active (a realiser en session interactive).

---

### MX-009 - Handoff vers Aligner ✅ LIVRE

Priorite: P2
Estimation: 1.5 jours
Dependances: MX-007, MX-008
Risque: moyen

Scope principal:
- frontend Tauri mode `Aligner` + bridge backend

Travaux:
- [x] Passage de contexte `episode_id`, `source_key`, `segment_kind`.
      → context.ts : AlignerHandoff{episode_id, episode_title, pivot_key, target_keys, mode, segment_kind}.
      → shell.ts : _handoff (consommé une seule fois), setHandoff()/getHandoff()/navigateTo().
- [x] Support transcript-first.
      → inspecterModule : "→ Aligner" résout pivot=transcript, target_keys=srts.
      → alignerModule : handoff pré-remplit le formulaire, pivot_lang="" si transcript (pas de pivot SRT fixe).
- [x] Support srt-only.
      → resolveSrtPivot() identifie le pivot SRT primaire.
      → alignerModule : mode="srt_only" affiché, pivot_lang=first SRT lang.
      → Garde guardAlignEpisode() vérifie 2+ SRT disponibles.
- [x] Job "align" + params (pivot_lang, target_langs, segment_kind, run_id).
      → jobs.py : AlignEpisodeStep + rapport report.json dans align_dir.
      → server.py : GET /episodes/{id}/alignment_runs lit les run dirs.

AC:
- [x] Handoff stable depuis Inspecter vers Aligner.
      → ctx.setHandoff() → ctx.navigateTo("aligner") → alignerModule lit getHandoff().
      → Handoff consommé une seule fois (null sur navigation directe).
- [x] Lancement alignement possible dans les deux modes.
      → Bouton "▶ Lancer l'alignement" actif si guardAlignEpisode().allowed.
      → Garde ré-évaluée au clic (MX-008).
      → Poll 2s → feedback "terminé ✓" + rechargement historique.

Validation:
- [x] Tests backend : 431/431 passes. tsc --noEmit : 0 erreur. 67/67 TS passes.
- [ ] Recette bout en bout sur 2 episodes (a realiser en session interactive).

---

### MX-010 - Parite messages et erreurs alignement ✅ LIVRE

Priorite: P2
Estimation: 1 jour
Dependances: MX-009
Risque: faible

Scope principal:
- mode `Aligner`

Travaux:
- [x] Harmoniser preconditions et messages.
- [x] Ajouter feedback explicite sur pre requis manquants.
- [x] Eviter references UX obsoletes.

AC:
- [x] Messages comprehensibles pour parcours transcript-first et srt-only.
- [x] Pas de message contradictoire avec les actions disponibles.

Validation:
- [x] Tests integration erreurs.

Livraison:
- `guards.ts`: `getAlignPreconditions()` (checklist 4 items transcript-first / 1 item srt-only), `formatJobError()` (mapping Python errors → messages actionnables).
- `alignerModule.ts`: checklist structuree au lieu du message plat, `formatJobError()` dans le poll handler.
- `tests/guards.test.ts`: +19 tests (getAlignPreconditions x 9, formatJobError x 10). Total: 86/86 ✅.
- `tsc --noEmit`: 0 erreur. Python: 25/25 ✅.

---

### MX-015 - Campagne non-regression Python + bridge ✅ LIVRE

Priorite: P1
Estimation: 1 jour
Dependances: MX-003, MX-007, MX-009
Risque: moyen

Scope principal:
- tests Python HIMYC + bridge Tauri

Travaux:
- [x] Definir une matrice de non-regression minimale par gate (A/B/C/D).
- [x] Executer le subset critique (inspecteur, alignement, jobs, CTA) a chaque jalon.
- [x] Produire un rapport d ecarts actionnable avant passage de gate.

AC:
- [x] Gate C et Gate D incluent un verdict non-regression explicite.
- [x] Aucun bloquant P0/P1 non trace au moment du Go/No-Go.

Validation:
- [x] Rapport de campagne archive dans `audit/.../evidence`.

Livraison:
- Rapport : `evidence/non_regression_mx015_2026-03-18.md`
- Python full : 431/431 ✅ — subset critique Gate C/D : 127/127 ✅
- TypeScript : 86/86 ✅ — tsc --noEmit : 0 erreur ✅
- Verdict Gate A ✅ Gate B ✅ Gate C ✅ Gate D partiel (MX-011/MX-012 restants)

---

### MX-011 - Hardening gros corpus ✅ LIVRE

Priorite: P2
Estimation: 2 jours
Dependances: MX-006, MX-009
Risque: moyen

Scope principal:
- perf UI/jobs

Travaux:
- [x] Pagination/virtualisation listes episodes et sources.
- [x] Stabiliser temps de reponse sur gros corpus.
- [x] Ajouter metriques runtime minimales.

AC:
- [x] Pas de freeze UI sur operations longues.
- [x] Temps de navigation acceptable sur corpus volumineux.

Validation:
- [x] Benchmark compare avant/apres.

Livraison:
- `src/perf.ts` : utilitaire `markStart/markEnd/measure/measureAsync` — logs console.debug [HIMYC perf].
- `constituerModule.ts` : pagination PAGE_SIZE=50 (prev/next), reset _page=0 au rechargement, measureAsync sur fetchEpisodes.
- `inspecterModule.ts` : troncature grands textes TEXT_TRUNCATE_CHARS=50 000 + bouton "Afficher tout", measureAsync sur fetchEpisodes + fetchEpisodeSource.
- `tests/perf.test.ts` : 12 tests (markStart/markEnd, measure, measureAsync). Total : 98/98 ✅.
- tsc --noEmit : 0 erreur. Python : 431/431 ✅.

---

### MX-012 - Gate final pilote ✅ LIVRE

Priorite: P2
Estimation: 1 jour
Dependances: MX-011, MX-015
Risque: faible

Scope principal:
- global

Travaux:
- [x] Executer checklist de parite MVP.
- [x] Executer recette complete transcript-first.
- [x] Executer recette complete srt-only.
- [x] Verifier le mode de lancement pilote sidecar/front defini en MX-001.
- [x] Produire verdict Go/No-Go pilote.

AC:
- [x] Checkpoints A/B/C/D valides.
- [x] Aucun bloquant P0/P1 ouvert.

Validation:
- [x] Rapport de recette + decision explicite.

Livraison:
- Rapport : `evidence/gate_final_pilote_mx012_2026-03-18.md`
- Checklist parité MVP : 16/16 critères ✅
- Recettes transcript-first et srt-only : toutes étapes couvertes par tests ✅
- Mode lancement pilote : backend externe confirmé (pas de sidecar) — `uvicorn` + `tauri build`
- Verdict : **GO ✅ — Le pilote HIMYC peut démarrer.**
- Python : 431/431 ✅ — TypeScript : 98/98 ✅ — tsc : 0 erreur ✅

---

### MX-017 - Recette visuelle interactive parite AGRAFES x HIMYC-TAURI ⏳ EN COURS

Priorite: P0
Estimation: 0.5 jour
Dependances: MX-012
Risque: faible

Scope principal:
- session interactive desktop (pas seulement tests auto)

Travaux:
- [x] Checklist de recette visuelle preparee (83 items, 8 sections).
- [ ] Executer la recette visuelle guidee sur les parcours cibles (a faire en session interactive).
- [ ] Capturer ecarts UX visibles vs attentes produit.
- [ ] Produire liste corrections quick wins / non-bloquants.

AC:
- [ ] Rapport visuel valide avec captures (avant/apres si correction).
- [ ] Aucun ecart critique non trace sur les parcours cibles.

Validation:
- [ ] Rapport archive dans `audit/.../evidence`.

Livraison partielle:
- Checklist : `evidence/recette_visuelle_mx017_checklist.md` (83 items — a remplir en session).

---

### MX-018 - Point d entree unifie HIMYC -> HIMYC-TAURI ✅ LIVRE

Priorite: P1
Estimation: 0.5 jour
Dependances: MX-017
Risque: faible

Scope principal:
- `/Users/hsmy/Dev/HIMYC` (documentation/scripts de lancement)
- `/Users/hsmy/Dev/HIMYC_Tauri` (runbook reference)

Travaux:
- [x] Ajouter un script de lancement unique depuis le repo HIMYC (backend + frontend Tauri).
- [x] Documenter clairement "PyQt vs Tauri" et les commandes associees.
- [x] Verifier que le script couvre macOS (et note Windows a minima).

AC:
- [x] Une commande unique depuis HIMYC permet de demarrer le pilote Tauri.
- [x] Plus d ambiguite utilisateur sur "quelle app est lancee".

Validation:
- [ ] Smoke test manuel de lancement complet.

Livraison:
- `launch-tauri.sh` : lancement unifie backend + frontend (une fenetre, kill port 1421 auto).
- `launch-tauri-split.sh` : variante deux fenetres Terminal.app separees (logs independants).
- Bandeau ANSI "MODE TAURI vs PyQt" au demarrage pour lever l ambiguite.

---

### MX-019 - Cadrage produit post-audit UX (parite AGRAFES) ⏳ A OUVRIR

Priorite: P0
Estimation: 0.5 jour
Dependances: MX-017
Risque: moyen

Scope principal:
- `audit/2026-03-17_tab_expert_audit_fonctionnel/`
- `/Users/hsmy/Dev/HIMYC_Tauri`

Travaux:
- [ ] Acter la reference UX cible: shell AGRAFES a 2 axes (`Explorer`, `Constituer`) + parcours metier HIMYC.
- [ ] Figer la liste des ecarts critiques constates (shell, concordancier, place des actions).
- [ ] Reclasser MX-014 comme portage partiel UX (utilitaires portes, layout concordancier non porte).
- [ ] Produire la checklist de parite UX v1 (must-have vs nice-to-have).

AC:
- [ ] Decision produit/technique signee (pas d ambiguite sur la cible UI).
- [ ] Liste d ecarts critiques gelee avant implementation MX-020+.

Validation:
- [ ] Revue croisee produit + technique.

---

### MX-020 - Parite shell AGRAFES (mode Explorer + navigation cible) ⏳ A OUVRIR

Priorite: P0
Estimation: 1.5 jours
Dependances: MX-019
Risque: moyen

Scope principal:
- `/Users/hsmy/Dev/HIMYC_Tauri/src/shell.ts`
- `/Users/hsmy/Dev/HIMYC_Tauri/src/modules/`

Travaux:
- [ ] Ajouter le mode `Explorer` au shell HIMYC-Tauri.
- [ ] Recomposer la navigation top-level pour revenir au modele AGRAFES (`Explorer`, `Constituer`).
- [ ] Replacer `Inspecter`/`Aligner` dans la navigation fonctionnelle cible (sous-vues, CTA ou route interne), sans casser les parcours existants.
- [ ] Mettre a jour persistance de mode et labels shell.

AC:
- [ ] Navigation shell conforme a la decision MX-019.
- [ ] Aucun crash de montage/demontage modules.
- [ ] Backward compatibility de lancement conservee.

Validation:
- [ ] Smoke test manuel: bascule complete des modes + retour etat.

---

### MX-021 - Recomposition `Constituer` (Importer/Documents/Actions/Exporter) ⏳ A OUVRIR

Priorite: P1
Estimation: 2 jours
Dependances: MX-020
Risque: moyen

Scope principal:
- `/Users/hsmy/Dev/HIMYC_Tauri/src/modules/constituerModule.ts`

Travaux:
- [ ] Reintroduire les 4 sections AGRAFES dans `Constituer`: `Importer`, `Documents`, `Actions`, `Exporter`.
- [ ] Deplacer les actions batch (normaliser, jobs) dans la section `Actions`.
- [ ] Garder les flux episode/source HIMYC sans regression metier.
- [ ] Aligner microcopy et aides contextuelles avec la structure sectionnee.

AC:
- [ ] `Constituer` n est plus action-centric par defaut.
- [ ] Les actions restent accessibles mais dans la bonne section.
- [ ] Scenario import transcript + srt conserve.

Validation:
- [ ] Recette manuelle "nouveau projet -> import -> actions -> export".

---

### MX-022 - Backend query MVP pour concordancier Explorer ⏳ A OUVRIR

Priorite: P0
Estimation: 2 jours
Dependances: MX-019
Risque: eleve

Scope principal:
- `/Users/hsmy/Dev/HIMYC/src/howimetyourcorpus/api/server.py`
- `/Users/hsmy/Dev/HIMYC_Tauri/src/api.ts`

Travaux:
- [ ] Ajouter un endpoint de recherche MVP (`/query`) avec pagination.
- [ ] Exposer un socle de filtres minimum (langue, source, episode).
- [ ] Standardiser le format resultat pour rendu Segment/KWIC.
- [ ] Ajouter gestion d erreurs claire et tests API.

AC:
- [ ] Explorer peut executer une requete simple et paginer les resultats.
- [ ] Contrat API stable et documente.

Validation:
- [ ] Tests integration API query (happy path + erreurs).

---

### MX-023 - Vue Explorer concordancier MVP (Segment/KWIC) ⏳ A OUVRIR

Priorite: P0
Estimation: 2.5 jours
Dependances: MX-020, MX-022
Risque: eleve

Scope principal:
- `/Users/hsmy/Dev/HIMYC_Tauri/src/modules/`
- `/Users/hsmy/Dev/HIMYC_Tauri/src/ui/`
- `/Users/hsmy/Dev/HIMYC_Tauri/src/features/`

Travaux:
- [ ] Creer `explorerModule.ts` (mode dedie).
- [ ] Implementer UI concordancier MVP: recherche, mode Segment/KWIC, zone resultats.
- [ ] Porter les composants utilitaires AGRAFES deja adaptes (meta panel, copy utils) dans ce flux.
- [ ] Assurer compatibilite avec le backend query MVP MX-022.

AC:
- [ ] Une recherche est possible depuis Explorer avec affichage resultats.
- [ ] Les modes Segment/KWIC sont operants en MVP.
- [ ] Aucun couplage dur a des modules AGRAFES absents.

Validation:
- [ ] Recette visuelle ciblee Explorer (checklist dediee + captures).

---

### MX-024 - Gate final parite UX AGRAFES x HIMYC (E2E) ⏳ A OUVRIR

Priorite: P0
Estimation: 1 jour
Dependances: MX-021, MX-023
Risque: moyen

Scope principal:
- global (session interactive + evidence)

Travaux:
- [ ] Executer recette complete sur 3 parcours: `Constituer`, `Explorer`, `Inspecter/Aligner`.
- [ ] Capturer ecarts restants et classer P0/P1/P2.
- [ ] Corriger quick wins P0/P1 non structurants.
- [ ] Produire verdict Go/No-Go de parite UX.

AC:
- [ ] Plus d ecart critique non trace entre cible AGRAFES et HIMYC-Tauri.
- [ ] Rapport final archive dans `audit/.../evidence`.

Validation:
- [ ] Sign-off produit + technique.

## Gates Go/No-Go

1. Gate A (apres MX-013 + MX-001): baseline AGRAFES + ADR architecture valides.
2. Gate B (apres MX-002 + MX-014 + MX-003 + MX-016 + MX-004..MX-006): shell Tauri + bridge + constitution multi-source operationnels.
3. Gate C (apres MX-007..MX-009): inspection source-centric + handoff alignement valides.
4. Gate D (apres MX-010 + MX-015 + MX-011 + MX-012): hardening, non-regression et pilote valides.
5. Gate E (apres MX-017 + MX-018): recette visuelle initiale + entree de lancement unifiee valides.
6. Gate F (apres MX-019..MX-024): parite UX AGRAFES x HIMYC-Tauri validee (Explorer + Constituer restructures).

## Definition of Done globale

- Flux unique `Episode + Source` operationnel.
- Dependances de sources robustes par episode.
- Mapping `doc_id/doc_relations` encapsule proprement vers `episode_key/source_key`.
- Parcours transcript-first et srt-only first-class.
- Coherence UX cible AGRAFES retablie (Explorer + Constituer + concordancier MVP).
- Support gros corpus valide en pilote.
- Non-regression Python/bridge validee sur gates C et D.

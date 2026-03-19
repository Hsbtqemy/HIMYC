# Note de Baseline AGRAFES — MX-013

Date: 2026-03-18
Statut: **VALIDEE**
Commit de reference: `03a8790`

---

## Etat du depot AGRAFES au figement

- Depot: `/Users/hsmy/Dev/AGRAFES`
- Branche: `main`
- HEAD au figement: `03a8790` (clean, aucune modification locale)
- Message: `feat(copy): add per-group and full-citation copy buttons`
- Date commit: 2026-03-18 11:56:56 +0100

---

## Delta entrant documente (`9f58b01..03a8790`)

### Commit precedent de reference locale: `9f58b01`

Message: `fix(concordancier): vue parallele, doublons alignement, selecteur multi-docs (Sprint N)`
Amplitude: 19 fichiers, 526 insertions, 132 suppressions

### Delta `9f58b01..03a8790`

3 fichiers modifies, 231 insertions, 2 suppressions:

| Fichier | Nature des apports |
|---|---|
| `tauri-app/src/features/metaPanel.ts` | Extrait hydrate avec contexte complet, navigation prev/next, compteur occurrences, position §N/total, anti-flash |
| `tauri-app/src/ui/dom.ts` | CSS pour groupes alignes (`.meta-aligned-group`), boutons copie micro (`.meta-copy-micro`, `.parallel-group-copy-btn`) |
| `tauri-app/src/ui/results.ts` | `makeGroupCopyBtn()`, `buildCitationText()`, integration copie par groupe et citation multi-langue complete |

---

## Cartographie portage HIMYC (MX-014)

### Composants reutilisables tels quels ou avec adaptation legere

- **`dom.ts` CSS** : variables de couleurs, styles layout, animations — reutilisables directement dans le shell Tauri HIMYC.
- **`results.ts` utilitaires copie** : `makeCopyBtn()`, `makeGroupCopyBtn()`, `buildCitationText()` — logique generique, adaptable sans dependance AGRAFES specifique.

### Composants a adapter (pas un port direct)

- **`metaPanel.ts`** : logique fortement couplee au modele AGRAFES (`doc_id`, `unit_id`, `QueryHit`, concordancier). A adapter vers le contexte HIMYC `episode_id + source_key`. La structure navigate prev/next et le panneau de contexte sont des patterns reutilisables, mais le schema de donnees doit etre remplace.
- **`results.ts` rendu cartes** : les cartes resultats KWIC/concordance sont hors perimetre HIMYC pour les vues Constituer/Inspecter. Seules les fonctions utilitaires (copy) sont candidates au port direct.

### Composants hors perimetre HIMYC (non portes)

- Vue parallele KWIC et scroll colonne alignee : specifique concordancier AGRAFES. Non applicable dans les vues Inspecter/Constituer/Aligner de HIMYC.
- `PARALLEL_COLLAPSE_N` / `VIRT_DOM_CAP` : parametres KWIC, hors perimetre.

---

## Regle de gouvernance baseline

**Toute mise a jour AGRAFES au-dela de `03a8790` passe par un ticket dedie de bump baseline.**

- Pas de `git pull` implicite en cours de sprint sur le depot AGRAFES.
- Pour bumper la baseline : ouvrir un ticket `MX-0XX - Bump baseline AGRAFES <nouveau_commit>`, documenter le nouveau delta, valider les impacts sur MX-014 avant merge.
- Cette regle s applique a toute l equipe pour la duree de la migration `feature/tauri-mix-himyc-agrafes`.

---

## Alignement plan + backlog

- `PLAN_MIGRATION_TAURI_MIX_HIMYC_AGRAFES.md` : reference `03a8790` — conforme.
- `BACKLOG_EXECUTABLE_TAURI_MIX_HIMYC_AGRAFES.md` : reference `03a8790` — conforme.
- Prochaine action : MX-001 (ADR architecture) peut etre ouverte.

# ADR — Architecture Mix Tauri HIMYC × AGRAFES (MX-001)

Date: 2026-03-18
Statut: **VALIDEE**
Auteur: MX-001

---

## Contexte

HIMYC est actuellement une application desktop PySide6/Python. L objectif est de migrer vers une UI
Tauri (style AGRAFES) en reutilisant la logique metier Python existante, sans big bang fonctionnel.

Trois decisions structurantes conditionnent le bootstrap Tauri (MX-002) et la suite du backlog.

---

## Decision 1 — Backend : Option A (Python sidecar/API locale)

**Choix retenu : Option A — reutiliser les services HIMYC Python existants via API locale.**

### Justification

- La logique metier HIMYC (normalisation, segmentation, alignement, gestion corpus) est mature et testee
  (406+ tests verts). Une reimplementation serait un risque majeur sans ROI a court terme.
- L exposition via une API locale (FastAPI ou equivalent) decouple le frontend Tauri du backend Python
  sans modifier les services existants.
- Option B (reimplementation Rust/TS) reste ouverte comme horizon long terme si ROI confirme apres pilote.

### Contraintes

- Le backend Python doit exposer un contrat d API stable (endpoints versionnes).
- Les appels Tauri vers le backend passent exclusivement par ce contrat (pas d import direct Python).
- Toute modification du contrat d API est tracee dans un ticket dedie.

---

## Decision 2 — Emplacement du shell Tauri : Repo separe

**Choix retenu : repo Git independant, distinct de `/Users/hsmy/Dev/HIMYC`.**

### Justification

- Flexibilite de versionnage independante du cycle Python HIMYC.
- Evite de surcharger le repo HIMYC avec une stack JS/Rust/Tauri.
- Coherence avec la structure AGRAFES (repo autonome).

### Contraintes et gouvernance

- Le repo Tauri reference HIMYC comme service backend (via URL API locale), pas comme dependance de code.
- La branche de travail initiale est `feature/tauri-mix-himyc-agrafes` dans le repo Tauri.
- La suite Python HIMYC reste la reference de non-regression — elle doit rester verte en permanence
  (MX-015).
- Toute synchronisation inter-repos (ex. mise a jour du contrat API) est coordonnee par ticket.

### Nom du repo cible

**Dépôt public GitHub :** `https://github.com/Hsbtqemy/HIMYC_Tauri.git`  
Nom du dossier après `git clone` : typiquement **`HIMYC_Tauri`** (anciens clones locaux peuvent encore s’appeler `himyc-tauri`). Le package Rust interne peut conserver le nom `himyc-tauri` dans `Cargo.toml` sans impact sur le remote.

---

## Decision 3 — Stack frontend : TypeScript vanilla

**Choix retenu : TypeScript vanilla, sans framework UI.**

### Justification

- Coherence directe avec AGRAFES (`03a8790`) : port des deltas (`metaPanel.ts`, `dom.ts`, `results.ts`)
  sans couche de translation framework.
- Bundle minimal, pas de dependance framework a maintenir.
- Les vues HIMYC (Constituer, Inspecter, Aligner) sont des surfaces relativement simples : un framework
  n apporte pas de ROI suffisant a ce stade.
- Si la complexite des vues augmente significativement, un framework peut etre introduit par ADR
  complementaire.

### Contraintes

- Utiliser le meme systeme de modules que AGRAFES (ESM natif + esbuild ou equivalent).
- Copier les conventions de nommage et de structure de `tauri-app/src/` AGRAFES pour limiter la
  friction de port des composants.

---

## Decision 4 — Strategie lancement pilote (sidecar Python)

**Choix retenu : lancement manuel en 2 commandes distinctes.**

### Runbook pilote

```
# Terminal 1 — Backend HIMYC
cd /Users/hsmy/Dev/HIMYC
uvicorn howimetyourcorpus.api.server:app --port 8765 --reload

# Terminal 2 — Frontend Tauri
cd /chemin/vers/HIMYC_Tauri   # clone de https://github.com/Hsbtqemy/HIMYC_Tauri.git
npm run tauri dev
```

### Justification

- Mode dev : la separation des terminaux facilite le debug (logs independants, rechargement independant).
- Pas de couplage de process a ce stade — sidecar Tauri integre est une option phase post-pilote.
- Un `Makefile` ou script `start-dev.sh` peut etre ajoute ulterieurement (sans etre requis pour Gate A).

### Port et configuration

- Port backend par defaut : `8765` (evite les conflits avec les ports standards).
- URL base API frontend : `http://localhost:8765` (configurable via variable d environnement).
- Un healthcheck `GET /health` est le premier endpoint expose (MX-003).

---

## Frontieres front/back et contrat d appels

### Principe

Le frontend Tauri ne connait que le contrat HTTP de l API locale. Il n a aucune connaissance du schema
interne DB HIMYC ni des modules Python.

### Contrat initial (a implementer dans MX-003)

| Endpoint | Methode | Description |
|---|---|---|
| `/health` | GET | Healthcheck — renvoie `{"status": "ok", "version": "..."}` |
| `/config` | GET | Configuration projet courant (chemin, nom) |
| `/episodes` | GET | Liste des episodes avec sources et etats par source |
| `/episodes/{id}/sources/{source_key}` | GET | Contenu d une source (`transcript`, `srt_<lang>`) |
| `/jobs` | GET/POST | File de jobs (normalisation, segmentation, alignement) |
| `/jobs/{id}` | GET | Statut d un job |

### Format erreur standard

```json
{
  "error": "NOT_FOUND",
  "message": "Episode S01E01 introuvable",
  "detail": {}
}
```

---

## Criteres de succes MVP

1. L utilisateur peut ouvrir un projet HIMYC existant depuis l UI Tauri.
2. L utilisateur peut parcourir les episodes et leurs sources (transcript, SRT multi-langues).
3. L utilisateur peut importer un transcript ou un SRT via la vue Constituer.
4. La vue Inspecter affiche le contenu de la source selectionnee (transcript ou SRT) et bloque les
   actions invalides.
5. Le handoff vers Aligner est possible depuis Inspecter (transcript-first et srt-only).
6. La suite Python HIMYC reste 100% verte pendant toute la migration.

---

## Decisions hors scope de cet ADR

- Schema DB : aucun changement en phase initiale (contrainte non-negociable).
- Option B backend (Rust/TS) : decision differee apres pilote.
- Sidecar Tauri integre : decision differee apres pilote.
- Framework UI : decision differee si complexite vues le justifie.

---

## Gate A — Criteres de validation

- [x] Decision Option A/B backend explicite et documentee.
- [x] Emplacement shell fige (repo separe **HIMYC_Tauri** — `https://github.com/Hsbtqemy/HIMYC_Tauri.git`).
- [x] Stack frontend figee (vanilla TypeScript).
- [x] Mode lancement pilote documente (runbook 2 commandes).
- [x] Contrat API initial defini (endpoints, format erreur).
- [x] Criteres de succes MVP listes.
- [ ] Revue croisee equipe.

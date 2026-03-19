# MX-019 — Cadrage produit UX post-audit

Date: 2026-03-19
Statut: **SIGNÉ**
Dépendances: MX-017 ✅

---

## Décision

L'interface HIMYC-Tauri adopte la structure AGRAFES comme armature UX,
enrichie des fonctionnalités HIMYC spécifiques.

---

## Architecture cible signée

```
HUB (point d'entrée)
├── Concordancier   KWIC · recherche · filtres langue/personnage/épisode
├── Constituer      (voir sections ci-dessous)
└── Exporter        formats corpus · SRT final avec noms personnages
```

### Sections de Constituer

```
Constituer
├── Importer    = Projet + Import fusionnés
│               config série (nom, source_id, URL, profil, langues)
│               fetch subslikescript · TVMaze · OpenSubtitles API
│               import SRT local (unitaire + batch auto-détection)
│
├── Documents   table épisodes + sources + états
│               gestion gros corpus (virtualisation, filtres, pagination)
│               point d'entrée vers Inspecter (sous-vue)
│
├── Actions     pipeline batch : Discover → Fetch → Normalize → Segment → Index → Align
│               jobs panel (actuel HIMYC Tauri)
│               point d'entrée vers Aligner (sous-vue)
│
├── Personnages définition personnages (canonical + noms par langue + alias)
│               auto-import depuis segments
│               assignation segment/cue → personnage
│               propagation via liens alignement · réécriture SRT
│
└── Exporter    (accessible aussi depuis le hub)
```

### Inspecter et Aligner

- **Pas d'entrée top-level** dans la navigation principale.
- Inspecter = sous-vue ouverte depuis Documents (clic sur un épisode/source).
- Aligner = sous-vue ouverte depuis Actions (CTA "→ Aligner" ou depuis Documents).

---

## Ce que couvre le HIMYC Tauri actuel

Le Tauri livré (MX-001→MX-018) correspond à la section **Actions** de Constituer,
plus Inspecter et Aligner en onglets top-level (à repositionner).

Aucune régression fonctionnelle — tout est conservé, repositionné dans la hiérarchie.

---

## Priorités d'implémentation post-MX-019

| Priorité | Ticket | Travail |
|----------|--------|---------|
| P0 | MX-020 | Restructuration shell : hub + navigation Constituer sections |
| P0 | MX-021 | Section Documents : virtualisation gros corpus + entrée Inspecter |
| P0 | MX-022 | Backend `/query` pour Concordancier |
| P0 | MX-023 | Vue Concordancier MVP (KWIC + recherche + filtres) |
| P1 | MX-021b | Section Importer : config projet + sources fetch + import SRT |
| P1 | MX-021c | Section Personnages : UI/UX from scratch |
| P2 | MX-024 | Gate final E2E + recette 3 parcours |

---

## Points non tranchés (à décider en cours d'implémentation)

- Design précis de la section Personnages (densité vs simplicité).
- Niveau d'exposition de la config projet dans Importer (wizard vs formulaire direct).
- Comportement du hub au premier lancement (pas de projet → guide vers Importer ?).

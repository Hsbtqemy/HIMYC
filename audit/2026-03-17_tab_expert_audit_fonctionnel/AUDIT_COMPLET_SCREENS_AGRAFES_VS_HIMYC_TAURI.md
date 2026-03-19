# Audit Complet Screens - AGRAFES vs HIMYC-TAURI

Date: 2026-03-19
Perimetre: comparaison ecran par ecran (visuel + cablage) entre AGRAFES et HIMYC-TAURI.
Objectif produit: rapprocher HIMYC au plus pres de l experience AGRAFES sans refonte big bang.

---

## 1) Resume executif

Verdict global:
- La structure de navigation HIMYC-TAURI est maintenant plus proche d AGRAFES qu au debut (Hub + Concordancier + Constituer + Exporter + sous-vues).
- Mais la parite reste partielle: surtout sur Concordancier (outillage AGRAFES avance) et Actions/Exporter (profondeur fonctionnelle AGRAFES non reproduite).
- Le gap principal n est plus le "layout brut", mais la profondeur de cablage metier et l outillage UX avances (facets, aligned/parallel complet, history/export menu riche, audit alignement avance).

Evaluation globale (etat actuel):
- Parite visuelle: 60/100
- Parite cablage: 48/100
- Parite produit exploitable (parcours coeur): 65/100

Conclusion:
- La convergence est realiste sans tout reprendre.
- Il faut prioriser Concordancier + Actions avances + Exporter avance.

---

## 2) Methode d audit

Approche:
1. Inventaire des points d entree ecrans AGRAFES (shell, tauri-app, tauri-prep).
2. Inventaire des ecrans HIMYC-TAURI et de leur routing effectif.
3. Comparaison ecran par ecran:
   - parite visuelle (composition, composants, ergonomie),
   - parite cablage (API, handlers, gardes, jobs, etats),
   - niveau de risque de divergence.
4. Proposition d un plan de convergence progressif, borne par gates.

Regle:
- Pas de jugement "all or nothing".
- Priorite a l impact utilisateur et a la non regression.

---

## 3) Evidence technique inspectee

### 3.1 AGRAFES (references majeures)

- Shell:
  - `AGRAFES/tauri-shell/src/shell.ts` (modes, header, home, publish wizard).
  - `AGRAFES/tauri-shell/src/modules/explorerModule.ts`
  - `AGRAFES/tauri-shell/src/modules/constituerModule.ts`
- Concordancier:
  - `AGRAFES/tauri-app/src/ui/buildUI.ts`
  - `AGRAFES/tauri-app/src/ui/results.ts`
  - `AGRAFES/tauri-app/src/features/query.ts`
  - `AGRAFES/tauri-app/src/lib/sidecarClient.ts`
- Constituer:
  - `AGRAFES/tauri-prep/src/app.ts`
  - `AGRAFES/tauri-prep/src/screens/ImportScreen.ts`
  - `AGRAFES/tauri-prep/src/screens/MetadataScreen.ts`
  - `AGRAFES/tauri-prep/src/screens/ActionsScreen.ts`
  - `AGRAFES/tauri-prep/src/screens/ExportsScreen.ts`
  - `AGRAFES/tauri-prep/src/ui/tokens.css`

### 3.2 HIMYC-TAURI (references majeures)

- Shell:
  - `himyc-tauri/src/shell.ts`
  - `himyc-tauri/src/modules/hubModule.ts`
- Concordancier:
  - `himyc-tauri/src/modules/concordancierModule.ts`
- Constituer / sous-vues:
  - `himyc-tauri/src/modules/constituerModule.ts`
  - `himyc-tauri/src/modules/inspecterModule.ts`
  - `himyc-tauri/src/modules/alignerModule.ts`
  - `himyc-tauri/src/modules/exporterModule.ts`
- UI transverses:
  - `himyc-tauri/src/ui/dom.ts`
  - `himyc-tauri/src/features/metaPanel.ts`
  - `himyc-tauri/src/ui/copyUtils.ts`
- API:
  - `himyc-tauri/src/api.ts`
  - `HIMYC/src/howimetyourcorpus/api/server.py`

---

## 4) Inventaire des screens AGRAFES (modele de reference)

### 4.1 Shell AGRAFES

Screens et flux:
- Home (cards Explorer / Constituer / Publier + demo flow).
- Explorer (concordancier complet).
- Constituer (app prep complete).
- Publier (assistant 5 etapes).

Elements UX structurants:
- Header riche: tabs, presets, shortcuts, about, db badge.
- Deep-link + onboarding + demo prefill.
- Wizard publication avec progression, options, run async, recap.

### 4.2 Explorer AGRAFES (Concordancier)

Structure:
- Topbar + toolbar complete.
- Modes Segment/KWIC.
- Toggle aligned + parallel.
- Drawer filtres + doc selector + chips.
- Builder de requete FTS + aide.
- Historique + menu export multi-format.
- Resultats enrichis (groupes, parallel cards, copie fine, citation multi-langue).
- Panneau meta lateral.

Cablage:
- `query` + `query/facets`, pagination offset, virtualisation partielle.
- Export hits multi-formats.
- State management riche (sort, expanded aligned, filters, history).

### 4.3 Constituer AGRAFES (Prep)

Navigation:
- Sidebar sections: Importer / Documents / Actions / Exporter.
- Actions subtree: Curation / Segmentation / Alignement.

Screens:
- ImportScreen (batch import, options, queue, index).
- MetadataScreen (documents, edition meta, relations docs).
- ActionsScreen (curation/segmentation/alignement avances, audit, collisions, quality, exceptions persistantes, workflows).
- ExportsScreen (pipeline export V2 + advanced exports + QA/reporting).

---

## 5) Inventaire des screens HIMYC-TAURI (etat actuel)

### 5.1 Shell HIMYC-TAURI

Structure actuelle:
- Hub (tiles Concordancier / Constituer / Exporter).
- Tabs top-level: Concordancier / Constituer / Exporter.
- Sous-vues non tabbees: Inspecter / Aligner avec bouton retour + breadcrumb.

Constat:
- Base de navigation saine et coherente.
- Plus proche d AGRAFES que la version initiale.

### 5.2 Concordancier HIMYC-TAURI

Present:
- Search bar, filtres simples (scope/kind/lang/episode/speaker), table KWIC, pagination client-side, export CSV.
- Backend `/query` disponible.

Manquant vs AGRAFES:
- Topbar/toolbar complete AGRAFES.
- Toggle aligned/parallele et rendering groupe avance.
- History panel, export menu complet, builder de requete, chips/doc selector.
- Facets backend et analytics riches.

### 5.3 Constituer HIMYC-TAURI

Present:
- Sidebar sections + subtree Actions.
- Actions hub + curation/segmentation/alignement simplifies.
- Jobs + batch actions.
- Handoffs vers inspecter/aligner.

Partiel / placeholders:
- Certaines sections indiquent encore "En developpement" (importer/documents/personnages/exporter selon zones).
- Niveau d outillage avance inferieur au prep AGRAFES complet.

### 5.4 Sous-vues metier HIMYC

- Inspecter:
  - bon modele source-centric (Episode + Source, raw/clean transcript, srt, gardes, handoff aligner).
- Aligner:
  - flux fonctionnel pour transcript-first et srt-only, runs history, lancement job align.
- Exporter:
  - vue simple (corpus/segments, formats basiques).

---

## 6) Matrice de parite ecran par ecran

Notation:
- Visuel: 0 a 5
- Cablage: 0 a 5
- Statut: Vert (>=4), Orange (2-3), Rouge (0-1)

| Screen reference AGRAFES | Equivalent HIMYC | Visuel | Cablage | Statut | Commentaire |
|---|---:|---:|---:|---|---|
| Shell header/nav + home | shell + hub | 3 | 3 | Orange | Proche structurellement, mais AGRAFES a plus d outillage shell (presets, shortcuts, about, db UX). |
| Home cards + demo/onboarding | hub tile + onboarding minimal | 3 | 2 | Orange | Hub present, mais logique demo/onboarding profonde absente. |
| Explorer topbar+toolbar complete | concordancierModule | 2 | 2 | Orange/Rouge | MVP fonctionnel mais pas la richesse AGRAFES. |
| Explorer results advanced (aligned/parallel/meta/copy) | concordancier + meta/copy partiels | 2 | 1 | Rouge | Grosse difference de rendering et de state query. |
| Explorer history/export menus/builder/help | partiel | 1 | 1 | Rouge | Majoritairement non present. |
| Constituer shell sections | constituer sections | 4 | 3 | Orange | Bonne direction visuelle, cablage partiel. |
| Importer screen | importer section HIMYC | 3 | 3 | Orange | Features utiles presentes, mais moins complet/structure que AGRAFES ImportScreen. |
| Documents/metadata screen | documents section HIMYC | 3 | 2 | Orange | Moins riche que MetadataScreen AGRAFES (edition meta/relations). |
| Actions curation | curation simplifiee | 3 | 2 | Orange | Utilisable mais pas la profondeur review/exceptions/historique AGRAFES. |
| Actions segmentation | segmentation simplifiee | 3 | 2 | Orange | Flux principal present, outillage expert absent. |
| Actions alignement audit | alignement simplifie | 2 | 2 | Orange/Rouge | Audit/collisions/retarget/batch actions AGRAFES non reproduits. |
| Exporter avance V2 | exporter simple | 2 | 2 | Orange/Rouge | Forte simplification. |
| Publier wizard 5 etapes | absent | 0 | 0 | Rouge | Screen AGRAFES non porte. |

---

## 7) Ecarts critiques a traiter en priorite

### Ecart C1 - Concordancier incomplet

Impact:
- L utilisateur retrouve un ecran "search", mais pas l experience AGRAFES attendue.

Racine:
- Contrat `/query` et state UI moins riches.
- UI resultats non equivalente (aligned/parallele/facets/history/export).

Priorite: P0

### Ecart C2 - Actions avancees non equivalentes

Impact:
- Les parcours experts (review, audit, collisions, quality) ne sont pas au niveau AGRAFES.

Racine:
- Portage progressif non fini de l ecran Actions (AGRAFES tres dense).

Priorite: P1

### Ecart C3 - Exporter trop simplifie

Impact:
- Perte des usages QA/reporting et des formats/policies AGRAFES.

Priorite: P1

### Ecart C4 - Shell utilities AGRAFES manquants

Impact:
- Impression de produit moins "fini" et moins guidant.

Priorite: P2

---

## 8) Risques de convergence

R1 - Risque de faux positif visuel:
- Rendre les ecrans "ressemblants" sans cablage equivalent.
- Mitigation: AC obligatoires visuel + API + jobs par screen.

R2 - Risque de regression metier HIMYC:
- Reprendre AGRAFES sans respecter episode/source-centric HIMYC.
- Mitigation: conserver contrat HIMYC comme source de verite, adapter UI AGRAFES.

R3 - Risque de dette de test:
- Peu de tests UI front sur HIMYC-TAURI.
- Mitigation: ajouter smoke UI et snapshots ecran par ecran.

R4 - Risque de big bang:
- Vouloir porter tout ActionsScreen en une fois.
- Mitigation: decoupage par sous-vues et paliers de livraison.

---

## 9) Plan de convergence recommande (sans tout reprendre)

## Phase A - Concordancier parity v1 (P0, 4-6 jours)

Objectif:
- Rendre HIMYC Concordancier tres proche d AGRAFES sur l experience coeur.

Travaux:
- Etendre API query (facets, pagination serveur, options aligned).
- Refaire toolbar Concordancier proche AGRAFES (modes, toggles, filter drawer, history/export).
- Reprendre rendering results AGRAFES (groupes aligned + parallel + copy citation).

AC:
- Recette visuelle "Explorer AGRAFES vs HIMYC" >= 85% conforme.
- Cablage query/facets stable en scenario nominal + erreur.

## Phase B - Constituer parity v1 (P0/P1, 4-6 jours)

Objectif:
- Fermer les zones "en developpement" critiques.

Travaux:
- Completer Importer et Documents.
- Aligner UX nav/sidebar/sections avec AGRAFES prep.
- Garder handoffs inspecter/aligner et etats source-centric.

AC:
- Parcours complet import -> actions -> inspecter/aligner sans friction.

## Phase C - Actions avancees cibles (P1, 6-10 jours)

Objectif:
- Porter les usages experts a valeur forte.

Ordre:
1. Curation review + exceptions persistantes.
2. Audit alignement + actions unitaires.
3. Collisions + quality.
4. Exports de revue.

AC:
- Parcours expert valides sur corpus test.

## Phase D - Exporter avance + shell utilities (P1/P2, 3-5 jours)

Objectif:
- Completer le niveau "produit fini".

Travaux:
- Exporter V2 (formats + QA/reporting).
- Ajouter presets/shortcuts/about shell.
- Decision explicite sur publication wizard AGRAFES (porter ou non).

---

## 10) Mapping backlog executable

Alignement avec backlog en cours:
- MX-019: cadrage cible UX (deja coherent avec cet audit).
- MX-020: parite shell.
- MX-021: recomposition Constituer.
- MX-022: backend query MVP.
- MX-023: vue Explorer concordancier MVP.
- MX-024: gate parite UX E2E.

Complements recommandes a ouvrir apres MX-024:
- MX-025: Concordancier parity v2 (history/export/builder/facets avances).
- MX-026: Actions avancees (audit/collisions/exceptions).
- MX-027: Exporter parity v2 + QA/reporting.
- MX-028: Shell utilities parity (presets/shortcuts/about + decision publish wizard).

---

## 11) Definition of Done de parite "tres proche AGRAFES"

DoD proposee:
- 1) Concordancier:
  - toolbar complete, modes Segment/KWIC, filtres avances, history/export, meta panel, rendering aligned/parallele.
- 2) Constituer:
  - sections Importer/Documents/Actions/Exporter toutes branchees sans placeholder critique.
- 3) Actions:
  - au moins les parcours experts prioritaires couverts (review, audit, collisions, quality).
- 4) Exporter:
  - exports cibles et feedbacks equivalentes.
- 5) UX shell:
  - navigation, coherence visuelle, utilitaires shell principaux.
- 6) Tests:
  - smoke UI ecran par ecran + non-regression API.
- 7) Gate:
  - recette visuelle comparee AGRAFES/HIMYC validee sans ecart critique non trace.

---

## 12) Conclusion

HIMYC-TAURI est sur une bonne trajectoire, mais la parite "tres proche AGRAFES" n est pas encore atteinte.
Le point dur principal est le Concordancier (UX + cablage) puis la profondeur des ecrans Actions/Exporter.
La convergence est faisable sans tout reprendre si l execution suit un plan progressif centre sur les ecrans a fort impact.

---

## 13) Annexe A - preuves detaillees par screen (line refs)

### 13.1 Shell

| Sujet | AGRAFES | HIMYC-TAURI | Ecart |
|---|---|---|---|
| Modes shell | `tauri-shell/src/shell.ts:897` | `src/shell.ts:25-28` | AGRAFES: `home/explorer/constituer/publish`; HIMYC: `hub/concordancier/constituer/exporter + subviews`. |
| Header tabs | `tauri-shell/src/shell.ts:1733-1737` | `src/shell.ts:333-344` | Alignement partiel, mais AGRAFES ajoute presets/shortcuts/about. |
| Home cards | `tauri-shell/src/shell.ts:2799-2845` | `src/modules/hubModule.ts:175-200` | Hub present, mais flow demo AGRAFES absent. |
| Publish wizard | `tauri-shell/src/shell.ts:2366+` | absent | Gap critique si in-scope produit. |

### 13.2 Concordancier

| Sujet | AGRAFES | HIMYC-TAURI | Ecart |
|---|---|---|---|
| UI construction | `tauri-app/src/ui/buildUI.ts:20+` | `src/modules/concordancierModule.ts:365+` | HIMYC est MVP, AGRAFES est complet. |
| Modes Segment/KWIC | `buildUI.ts:49-54` | `concordancierModule.ts:391-404` | Present des 2 cotes. |
| Aligned/Parallel | `buildUI.ts:56-68`, `ui/results.ts:187+` | absent en pratique | Gap majeur de restitution multi-langues. |
| History/export menu | `buildUI.ts:157-176`, `488-540` | CSV simple `concordancierModule.ts:345-358` | Gap fort UX + formats. |
| Query facets | `tauri-app/src/lib/sidecarClient.ts:961-975`, `features/query.ts:121+` | absent dans contrat actuel | Gap cablage/analytics. |
| Meta/copy avance | `ui/results.ts:57-129`, `253-295` | partiel (`metaPanel`/`copyUtils`) | Partiel non integre au meme niveau de flux. |

### 13.3 Constituer

| Sujet | AGRAFES | HIMYC-TAURI | Ecart |
|---|---|---|---|
| Shell sections | `tauri-prep/src/app.ts:209-255` | `src/modules/constituerModule.ts:2473-2490` | Bonne convergence visuelle. |
| Actions subtree | `app.ts:225-249` | `constituerModule.ts:2477-2486` | Bonne convergence de structure. |
| Importer screen | `screens/ImportScreen.ts:49+` | `constituerModule.ts:1648+` | HIMYC plus compact, moins d outillage batch fin. |
| Documents screen | `screens/MetadataScreen.ts:97+` | `constituerModule.ts:1544+` | HIMYC n atteint pas la profondeur metadata/relations AGRAFES. |
| Actions screen | `screens/ActionsScreen.ts:243+` | `constituerModule.ts:2528+` | Gap tres important de richesse metier. |
| Exporter screen | `screens/ExportsScreen.ts:68+` | `constituerModule.ts:2105+` + `exporterModule.ts:118+` | HIMYC export plus simple. |

### 13.4 API / Cablage backend

| Sujet | AGRAFES | HIMYC | Ecart |
|---|---|---|---|
| Contrat query | sidecar query + facets + aligned (`tauri-app/lib/sidecarClient.ts:923+`) | `/query` MVP (`api/server.py:521+`) | Gap sur facets/aligned/options. |
| Jobs metier | sidecar riche (curate/segment/align/audit/quality/export) | jobs typage cible HIMYC (`api.ts:217+`) | Couverture partielle cote HIMYC. |
| Characters/assignments | present AGRAFES-style metadata workflows | present HIMYC (`server.py:592+`) | Base en place, UI a consolider. |
| Export | AGRAFES ExportsScreen V2 + QA/reporting | `/export` simple (`server.py:755+`) | Gap fonctionnel. |

---

## 14) Annexe B - indicateurs quantitatifs

Complexite code UI comparee (ordre de grandeur):
- AGRAFES:
  - `tauri-shell/src/shell.ts`: ~2961 lignes
  - `tauri-app/src/ui/buildUI.ts`: ~621 lignes
  - `tauri-prep/src/screens/ActionsScreen.ts`: ~7415 lignes
- HIMYC-TAURI:
  - `src/shell.ts`: ~429 lignes
  - `src/modules/concordancierModule.ts`: ~503 lignes
  - `src/modules/constituerModule.ts`: ~2954 lignes

Interpretation:
- Le delta de surface sur Actions/Concordancier explique la perception "pas encore AGRAFES-like".
- Le gap principal est de profondeur fonctionnelle, pas seulement de style CSS.

---

## 15) Annexe C - charge recommandee (sans big bang)

Charge indicative (jours ouvres):
- Lot L1 Concordancier parity v1: 4 a 6 j
- Lot L2 Constituer parity v1 (importer/documents): 4 a 6 j
- Lot L3 Actions avancees prioritaires: 6 a 10 j
- Lot L4 Exporter parity v2 + shell utilities: 3 a 5 j
- Lot L5 Recette visuelle + hardening + ajustements: 2 a 3 j

Total cible:
- 19 a 30 jours selon niveau de parite vise et profondeur Actions retenue.

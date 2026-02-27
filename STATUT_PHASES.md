# Statut des phases — HIMYC

**Dernière mise à jour** : 2026-02-27  
**Objectif** : un seul fichier de référence pour les phases **livrées**, **en cours**, **planifiées** et **non engagées**.

---

## 1. Phases livrées (produit)

Les phases 1 à 7 + HP + MP sont **terminées**. Synthèse dans [RESUME_EXECUTIF.md](RESUME_EXECUTIF.md) et détail dans [RECAP.md](RECAP.md).

| Bloc | Contenu |
|------|--------|
| Phase 1–5 | MVP, segments, sous-titres, alignement, concordancier parallèle |
| Phase 6 | DB (optimisation, index, batch), packaging PyInstaller |
| Phase 7 | Refactoring onglets UI (décorateurs, messages) |
| HP / MP | Barre progression, stats permanentes alignement, filtrage logs, navigation segments, actions bulk |

---

## 2. Onglet Préparer

**Référence** : [PLAN_IMPLEMENTATION_ONGLET_PREPARER.md](PLAN_IMPLEMENTATION_ONGLET_PREPARER.md)

- **Statut** : implémentation **terminée** pour P0 + Phase 1 + Phase 2 + Phase 3.1/3.3 + refacto P3 du widget.
- **Phase 3.2 (statut par ligne)** : **option d’affichage en place** (menu **Affichage → Statut par ligne (onglet Préparer)** ; colonne « Statut » affichée si activé, préférence persistée en QSettings). La persistance du statut par ligne en base (migration segments/cues) reste **optionnelle / non engagée**.

---

## 3. En cours / recommandé (après Phases 6–7)

Les points listés comme « ⏳ En cours / Recommandé » dans [CHANGELOG_PHASE6-7.md](CHANGELOG_PHASE6-7.md) (décorateurs restants, import batch SRT, stats permanentes, filtrage logs, barre progression, actions bulk) **ont été réalisés** et sont reflétés dans [RESUME_EXECUTIF.md](RESUME_EXECUTIF.md).

### Phase en cours (engagée)

**À partir du 2026-02-26** : les chantiers suivants sont considérés comme **engagés** (à traiter en priorité). Détail et pistes dans [DOC_BACKLOG.md](DOC_BACKLOG.md).

| # | Chantier | Backlog | Priorité suggérée | État |
|---|----------|---------|-------------------|------|
| 1 | **Onglet Corpus — cases à cocher** | §1 | Haute | ✅ Fait (déjà en place ; tooltips + ligne d'aide 2026-02-26) |
| 2 | **Import SRT en masse** | §6.1 (Import SRT en masse) | Haute | ✅ Fait (récursif, sous-dossiers, 1x01, combo éditable 2026-02-26) |
| 3 | **Workflow — visibilité / enchaînement** | §5 | Moyenne | ✅ Fait (prochaine étape, tooltips périmètre 2026-02-26) |

- **Suite livrée** : §2 Inspecteur ✅ (redimensionnement + sauvegarde à la sortie d’onglet, export SRT-like, tooltip — 2026-02-26). §3 Alignement sans timecodes ✅ (ordre d’abord si les deux pistes sans timecodes, puis similarité en secours — 2026-02-26). §6 Filtre saison ✅ (Cocher / Décocher la saison, tooltips et aide batch par saison, README — 2026-02-26). §4 Mac ✅ (build .app, scripts/macos/, CI ; README). Option **Affichage → Statut par ligne (Préparer)** ✅ (2026-02-27). §7.1 piste 1 (profil pour le batch) ✅. §6.2 OpenSubtitles ✅. §7 (ProfilesDialog, profiles.json) ✅. §7.2 (multi-sources, fusion index) ✅. SRT-first (projet SRT uniquement, ajout épisodes à la main) ✅. §15.5 Inspecteur outils de normalisation (GroupBox + Gérer les profils…) ✅. §11 normalisation SRT à l'import ✅. §8 personnages alias (colonne + Suggérer par alias) ✅.
- **Non engagé pour l’instant** : autres idées backlog (voir DOC_BACKLOG). Détail : [DOC_BACKLOG.md](DOC_BACKLOG.md).

---

## 4. Travail « engagé » au sens workflow (validation)

[CHECKLIST_WORKFLOW_E2E.md](CHECKLIST_WORKFLOW_E2E.md) (2026-02-24) décrit les **scénarios à valider** :

- **Scénario A** : Transcript → Préparer → Alignement → Personnages
- **Scénario B** : Sous-titres only
- **Scénario C** : Continuité multi-langues

Ce n’est **pas une phase de dev**, mais une **checklist de validation** du workflow déjà en place (critères de sortie, vérifs inter-onglets).

---

## Résumé

| Catégorie | État |
|-----------|------|
| Phases 1–7 + HP + MP | ✅ Livrées |
| Onglet Préparer (P0, 1, 2, 3.1, 3.3, refacto P3) | ✅ Livré |
| Préparer Phase 3.2 | ✅ Option affichage (menu Affichage) ; persistance DB optionnelle |
| Backlog §1–§6 + §6.1 | ✅ Fait (Corpus, Inspecteur, Alignement sans timecodes, Mac, Workflow, Filtre saison, Import SRT en masse) |
| **Prochaines cibles** | Voir DOC_BACKLOG : §1–§15.5, §11, §8 déjà Fait. Suite = validation E2E, puis Phase 3.2 / doc |
| Validation workflow | Checklist E2E (CHECKLIST_WORKFLOW_E2E.md) |

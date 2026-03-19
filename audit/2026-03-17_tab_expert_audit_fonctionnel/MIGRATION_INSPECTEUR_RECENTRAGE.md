# Migration — Recentrage Inspecteur (lot INS-001 → INS-012)

Date : 2026-03-18
Auteur : automatisé via Claude Code
Périmètre : `InspectorTabWidget`, `InspecteurEtSousTitresTabWidget`, mainwindow_project/jobs

---

## Ce qui change pour les usages

### Mode Focus transcript (INS-001/002)

**Avant** : l'onglet Inspecteur affichait toujours deux panneaux côte à côte (Transcript + SRT).

**Après** : seul le panneau Transcript est visible par défaut. Le panneau SRT est accessible via
le bouton **Outils SRT ▸** en haut de l'onglet. L'état est persisté dans QSettings
(`"inspecteur/focus_mode"`).

*Impact utilisateur* : ouverture plus nette, moins de surcharge visuelle. Aucune fonctionnalité
SRT supprimée.

---

### Sélecteur Fichier (INS-005/006)

**Avant** : l'Inspecteur opérait toujours sur la source Transcript.

**Après** : un combo **Fichier** (Transcript / SRT — `<lang>`) est visible dans la barre d'épisode.
Les options SRT sont peuplées depuis `db.get_tracks_for_episode()` au chargement de chaque épisode.

*Règle INS-006* : quand une source SRT est sélectionnée, Normaliser et Découper en segments sont
désactivés (avec tooltip explicite). Les autres actions restent inchangées.

---

### Libellés mis à jour (INS-003/010)

| Ancien libellé | Nouveau libellé | Localisation |
|---|---|---|
| `Segmente l'épisode` | `Découper en segments` | bouton `inspect_segment_btn` |
| `Kind:` | `Type:` | label vue Segments |
| Références « onglet Sous-titres » | « bouton Outils SRT ▸ » | CTA details, messages alignement |

---

### APIs de capacité (INS-007/008)

Deux méthodes ajoutées sur `InspecteurEtSousTitresTabWidget` :

```python
def has_subtitle_panel(self) -> bool: ...
def set_subtitle_languages(self, langs: list[str]) -> None: ...
```

Les mainwindow (`mainwindow_project.py`, `mainwindow_jobs.py`) utilisent désormais ces méthodes
au lieu de `hasattr(inspector_tab, "subtitles_tab")` pour détecter le panneau combiné.

#### Horizon de dépréciation

L'accès direct `inspector_tab.subtitles_tab` continue de fonctionner (attribut présent) mais
est considéré **legacy** à partir de cette version. Toute logique métier doit passer par les
méthodes de capacité. Suppression prévue dans le lot suivant si aucune dépendance externe
n'est identifiée.

---

## Ce qui ne change pas

- Schéma DB : aucune migration.
- Pipeline normalisation/segmentation/alignement : inchangé.
- Attributs publics de `InspectorTabWidget` : tous conservés (aucune régression d'interface).
- Suite de tests Sprint 1–3 : 125/125 verts.

---

## Pour un nouveau dev (flux cible en 10 minutes)

### Flux transcript-first

```
Projet ouvert → Inspecteur → sélectionner épisode
→ Fichier: Transcript (défaut)
→ CTA indique l'étape suivante (Normaliser / Découper / SRT / Aligner)
→ Actions Produire filtrées selon disponibilité RAW/CLEAN
```

### Flux SRT-only

```
Projet ouvert → Inspecteur → sélectionner épisode
→ Outils SRT ▸ → importer piste(s)
→ Fichier: SRT — EN (ou autre)
→ CTA indique "SRT-only" ou "transcript-first" selon état
→ Onglet Alignement → Lancer
```

### Flux développeur — ajout d'une vérification capacité

```python
# Avant (couplage structurel)
if hasattr(win.inspector_tab, "subtitles_tab"):
    win.inspector_tab.subtitles_tab.set_languages(langs)

# Après (API de capacité)
if hasattr(win.inspector_tab, "has_subtitle_panel") and win.inspector_tab.has_subtitle_panel():
    win.inspector_tab.set_subtitle_languages(langs)
```

---

## Points de dépréciation explicites

| Élément | Statut | Action requise |
|---|---|---|
| `inspector_tab.subtitles_tab` (accès direct) | Legacy | Migrer vers `set_subtitle_languages()` / `has_subtitle_panel()` |
| `hasattr(inspector_tab, "subtitles_tab")` dans mainwindow | Supprimé | Remplacé par `has_subtitle_panel()` dans ce lot |

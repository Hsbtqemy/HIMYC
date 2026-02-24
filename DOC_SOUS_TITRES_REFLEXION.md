# Réflexion : traitement des sous-titres dans HIMYC

**Date** : 2026-02-23  
**Contexte** : Problèmes signalés sur la « segmentation des sous-titres » et souhaits d’amélioration (reprises, transformation, robustesse).

---

## 1. Ce qui existe aujourd’hui

### 1.1 Deux sens de « segmentation » dans l’app

| Terme | Où | Quoi |
|-------|-----|-----|
| **Segmentation du transcript** | Inspecteur, Corpus (Bloc 2) | Découpage du texte CLEAN en **phrases** et **tours de parole** (segments). Fichier `segments.jsonl`, table `segments` en DB. Utilisé pour l’alignement segment ↔ cue EN. |
| **Traitement des sous-titres (SRT)** | Onglet Inspecteur (Sous-titres), import SRT | Parsing SRT/VTT → **cues** (une réplique par bloc numéroté, avec timecodes, `text_raw`, `text_clean`). Pas de « segmentation » au sens découpage : les cues sont déjà des unités. |

Donc aujourd’hui il n’y a **pas** de segmentation au sens « découper / fusionner les lignes SRT » : on importe le SRT tel quel (parsing strict), puis on peut **normaliser** le texte des cues (appliquer un profil → `text_clean`).

### 1.2 Chaîne actuelle

1. **Import SRT** : fichier → `parse_srt` / `parse_vtt` → liste de `Cue` (n, start_ms, end_ms, text_raw) → sauvegarde store + DB (`subtitle_cues`).
2. **Normalisation** : appliquer un profil de normalisation à une piste → mise à jour `text_clean` en DB (et éventuellement réécriture du fichier SRT côté store).
3. **Alignement** : segments (transcript) ↔ cues EN (pivot) ↔ cues FR/IT (cible). Les cues ne sont pas « segmentées » ; on les associe par timecodes ou similarité.

### 1.3 Points de friction possibles

- **Pivot EN obligatoire** : l’alignement suppose une piste « pivot » (par défaut EN). Message d’erreur rendu plus clair (langue pivot, pas « EN obligatoire »).
- **Segmentation du transcript** : si « Segmente l’épisode » n’est pas faite ou échoue, pas de segments → pas d’alignement. Les sous-titres seuls ne créent pas de segments.
- **Reprise / cohérence** : après modification d’une piste SRT (édition manuelle, re-normalisation), les runs d’alignement existants peuvent devenir incohérents (liens vers d’anciennes cues). Pas de invalidation automatique des runs.
- **Import batch SRT** : dans l’onglet Corpus, l’import batch détecte les fichiers et crée les épisodes mais n’importe pas encore les pistes en DB (TODO documenté).

---

## 2. Pistes d’amélioration (à discuter)

### 2.1 Reprises et cohérence

- **Invalider les runs d’alignement** quand une piste SRT de l’épisode est modifiée ou supprimée (ou proposer « Recréer les runs ? »).
- **Reprise après erreur** : si l’import SRT ou la normalisation échoue sur un épisode, permettre de relancer uniquement cet épisode (comme pour le Corpus avec « Reprendre les échecs »).

### 2.2 Transformation des sous-titres

- **Fusion / découpage de cues** : aujourd’hui non prévu. Si besoin (ex. fusionner deux lignes SRT en une), il faudrait soit un mode édition avancé (fusionner deux cues, recalculer timecodes), soit un prétraitement externe avant import.
- **Normalisation par lot** : appliquer un profil à toutes les pistes d’un épisode (ou tous les épisodes) en une action, avec progression.
- **Détection de langue** : les SRT ne portent pas de métadonnée langue ; l’utilisateur choisit à l’import. Une détection automatique (sur le premier bloc de texte) pourrait être proposée en option.

### 2.3 Workflow « SRT only »

- **Projet sans transcript** : certains projets n’ont que des SRT (pas de transcript). Aujourd’hui l’alignement segment↔cue exige des segments (transcript segmenté). Pour du « SRT only », il faudrait soit :
  - un mode « alignement cue EN ↔ cue FR » sans segment (déjà partiellement là : `align_cues_by_time` / `align_cues_by_similarity`), soit
  - considérer chaque cue comme un « segment » virtuel pour exposer un flux concordancier cohérent.
- **Pivot configurable** : permettre de choisir la langue pivot (ex. FR si pas d’EN) dans l’onglet Projet ou Alignement, au lieu de fixer EN en dur.

### 2.4 UX et feedback

- **Validation avant alignement** : rappeler les prérequis (transcript segmenté, piste pivot importée) dans l’onglet Alignement avec des indicateurs clairs (ex. « Segments : 42 », « Piste EN : oui »).
- **Segmentation des sous-titres (wording)** : si par « segmentation des sous-titres » tu entends autre chose (ex. découpage intelligent des lignes, ou au contraire regroupement), on peut préciser le besoin et l’intégrer ici.

---

## 3. Prochaines étapes suggérées

1. **Valider les corrections** : conservation de l’épisode courant au refresh, message pivot clarifié.
2. **Préciser le besoin** « segmentation des sous-titres » : quel comportement exact manque (reprise, fusion de lignes, normalisation en lot, autre) ?
3. **Prioriser** : invalidation des runs après modification SRT, import batch complet, pivot configurable, autre.

Ce document peut être mis à jour au fil de la discussion.

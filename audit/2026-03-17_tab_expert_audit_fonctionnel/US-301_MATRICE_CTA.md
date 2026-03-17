# US-301 — Matrice CTA « Prochaine action recommandée »

Statut : **GELEE** (Sprint 2 — 2026-03-17)
Source de vérité pour US-302. Toute modification exige un change request avant reprise de Sprint 3.

---

## Entrées (colonnes d'état)

| Champ | Type | Source |
|-------|------|--------|
| `has_raw` | bool | `store.has_episode_raw(eid)` |
| `has_clean` | bool | `store.has_episode_clean(eid)` |
| `has_segments` | bool | `db.get_segments_for_episode(eid)` non vide |
| `has_tracks` | bool | `db.get_tracks_for_episode(eid)` non vide |
| `has_alignment_run` | bool | `db.get_align_runs_for_episode(eid)` non vide |
| `use_similarity` | bool | `tab.align_by_similarity_cb.isChecked()` |

---

## Matrice de décision (priorité décroissante)

| # | has_run | use_sim | has_clean | has_seg | has_tracks | has_raw | Mode | action_id | Label CTA |
|---|---------|---------|-----------|---------|-----------|---------|------|-----------|-----------|
| 1 | **Oui** | * | * | * | * | * | aligned | `consult_alignment` | Consulter ou exporter l'alignement |
| 2 | Non | **Oui** | * | * | **Oui** | * | similarity | `run_alignment_similarity` | Lancer l'alignement par similarité |
| 3 | Non | Non | **Oui** | **Oui** | **Oui** | * | transcript-first | `run_alignment_transcript_first` | Lancer l'alignement transcript-first |
| 4 | Non | Non | **Oui** | **Oui** | Non | * | incomplete | `import_srt` | Importer des SRT |
| 5a | Non | Non | **Oui** | Non | **Oui** | * | srt-only | `segment_or_srt_only` | Segmenter ou lancer SRT-only |
| 5b | Non | Non | **Oui** | Non | Non | * | incomplete | `segment_episode` | Segmenter l'épisode |
| 6 | Non | Non | Non | Non | **Oui** | * | srt-only | `run_alignment_srt_only` | Lancer l'alignement SRT-only |
| 7 | Non | Non | Non | Non | Non | **Oui** | incomplete | `normalize_episode` | Normaliser le transcript |
| 8 | Non | Non | Non | Non | Non | Non | incomplete | `start` | Démarrer (télécharger ou importer SRT) |

`*` = valeur indifférente.

---

## Couverture des cas limites (requis par DoR US-302)

### Cas `transcript = N/A`

| Scénario | has_clean | has_seg | has_tracks | Règle appliquée |
|----------|-----------|---------|-----------|-----------------|
| SRT-only pur | Non | Non | Oui | #6 → `run_alignment_srt_only` |
| Similarité sans transcript | Non | Non | Oui + use_sim | #2 → `run_alignment_similarity` |
| Rien du tout | Non | Non | Non | #8 → `start` |

### Cas `similarité forcée`

| Scénario | has_tracks | use_sim | Règle |
|----------|-----------|---------|-------|
| Tracks + similarity | Oui | Oui | #2 → `run_alignment_similarity` (priorité sur transcript-first) |
| Tracks + similarity + has_run | Oui | Oui | #1 → `consult_alignment` (run déjà existant prioritaire) |
| Pas de tracks + similarity | Non | Oui | #7 ou #8 (similarity ignorée sans tracks) |

---

## Implémentation de référence

Module : `src/howimetyourcorpus/app/tabs/cta_recommender.py`
Entrypoint : `recommend(state: EpisodeState) -> CtaRecommendation`

---

## Validation requise avant Sprint 3

- [ ] Revue produit : matrice cohérente avec les usages réels (UX review US-204)
- [ ] Cas limites `srt-only` et `similarité forcée` couverts par au moins 1 test chacun
- [ ] Critères de test US-302 définis (1 test par `action_id`)

Date de gel : 2026-03-17

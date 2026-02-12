# HowIMetYourCorpus — Récapitulatif MVP + Phases 2–5

Document de synthèse du projet (Phase 1 MVP, Phase 2 segments, Phase 3 sous-titres, Phase 4 alignement, Phase 5 concordancier parallèle et rapports). À garder à côté du dossier pour retrouver rapidement structure, commandes et critères.

---

## En bref

- **Nom :** HowIMetYourCorpus  
- **Type :** Application desktop Windows (Python 3.11+, PySide6)  
- **Objectif :** Construire, normaliser, indexer et explorer des transcriptions (source web subslikescript), sans logique métier en dur (générique + preset HIMYM en config).
- **Phase 4 (alignement) :** dépendance optionnelle `rapidfuzz` recommandée pour la similarité textuelle (`pip install rapidfuzz` ou `pip install -e ".[align]"`). Sinon : fallback Jaccard.

---

## Commandes utiles

| Action | Commande |
|--------|----------|
| Installer (venv + deps) | `scripts\windows\install.bat` |
| Lancer l’app (sans console) | `scripts\windows\run.bat` |
| Lancer avec console | `.venv\Scripts\activate` puis `set PYTHONPATH=src` et `python -m howimetyourcorpus.app.main` |
| Lancer les tests | `set PYTHONPATH=src` puis `python -m pytest tests\ -v` |

---

## Structure du projet

```
HowIMetYourCorpus/
├── pyproject.toml
├── requirements.txt
├── preset_himym.toml
├── README.md
├── RECAP.md                    ← ce fichier
├── src/howimetyourcorpus/
│   ├── app/
│   │   ├── main.py             # Point d’entrée
│   │   ├── ui_mainwindow.py    # 5 onglets (Projet, Corpus, Inspecteur, Concordance, Logs)
│   │   ├── workers.py          # JobRunner (pipeline en arrière-plan)
│   │   └── models_qt.py        # Modèles table épisodes / KWIC
│   └── core/
│       ├── models.py           # ProjectConfig, SeriesIndex, EpisodeRef, TransformStats, etc.
│       ├── adapters/
│       │   ├── base.py         # SourceAdapter, AdapterRegistry
│       │   └── subslikescript.py
│       ├── normalize/
│       │   ├── profiles.py     # NormalizationProfile.apply()
│       │   └── rules.py
│       ├── pipeline/
│       │   ├── steps.py        # Step, StepResult
│       │   ├── tasks.py        # FetchSeriesIndex, FetchEpisode, Normalize, BuildDbIndex, SegmentEpisodeStep, RebuildSegmentsIndexStep, ImportSubtitlesStep, AlignEpisodeStep
│       │   └── runner.py       # PipelineRunner
│       ├── segment/            # Phase 2
│       │   ├── segmenters.py   # Segment, segmenter_sentences, segmenter_utterances
│       │   └── legacy.py       # Utterance, Phrase, exports compat
│       ├── subtitles/          # Phase 3
│       │   └── parsers.py      # Cue, parse_srt, parse_vtt, parse_subtitle_file
│       ├── align/              # Phase 4
│       │   ├── similarity.py   # text_similarity (rapidfuzz ou Jaccard)
│       │   └── aligner.py      # AlignLink, align_segments_to_cues, align_cues_by_time
│       ├── storage/
│       │   ├── project_store.py # Layout projet, RAW/CLEAN, subs, align
│       │   ├── db.py           # SQLite + FTS5 + KWIC + segments + cues + align + Phase 5 stats/parallel
│       │   ├── schema.sql      # + schema_version
│       │   └── migrations/     # 002_segments.sql, 003_subtitles.sql, 004_align.sql
│       └── utils/              # logging, text, http
├── tests/
│   ├── fixtures/               # subslikescript_*.html, sample.srt, sample.vtt
│   ├── test_adapter_subslikescript.py
│   ├── test_normalize_profiles.py
│   ├── test_db_kwic.py
│   ├── test_segment.py        # Phase 2
│   ├── test_subtitles.py      # Phase 3
│   ├── test_align.py          # Phase 4
│   └── test_export_phase5.py  # Phase 5
├── HowIMetYourCorpus.spec    # Phase 6 PyInstaller (datas schema + migrations)
└── scripts/windows/
    ├── install.bat
    └── run.bat
```

---

## Workflow utilisateur (UI)

1. **Projet** — Choisir dossier (nouveau ou existant) → source, URL série, rate limit, profil → « Valider & initialiser ».
2. **Corpus** — Découvrir épisodes → Télécharger (sélection / tout) → Normaliser → Indexer DB. Progression + Annuler.
3. **Inspecteur** — Choisir épisode → voir RAW vs CLEAN, stats, exemples de fusions. Vue « Segments » : liste phrases/tours + surlignage ; bouton « Segmente l’épisode ».
4. **Sous-titres** — Choisir épisode + langue, « Importer SRT/VTT... » ; liste des pistes (lang, format, nb cues).
5. **Alignement** — Choisir épisode + run (ou « Lancer alignement ») ; table des liens ; Accepter/Rejeter ; export aligné CSV/JSONL ; **Phase 5** : export concordancier parallèle (CSV/TSV/JSONL), rapport HTML, stats.
6. **Concordance** — Saisir terme, scope (Épisodes / Segments / Cues), kind, langue (si Cues), filtres → KWIC ; export CSV/TSV/JSON/JSONL ; double-clic → Inspecteur.
7. **Logs** — Logs en direct + « Ouvrir fichier log ».

---

## Layout d’un projet (sur disque)

```
projects/<project_name>/
├── config.toml
├── series_index.json
├── runs/
│   └── app.log
├── episodes/
│   └── <episode_id>/
│       ├── page.html
│       ├── raw.txt
│       ├── clean.txt
│       ├── parse_meta.json
│       ├── transform_meta.json
│       ├── segments.jsonl     # Phase 2 (audit segments)
│       ├── subs/               # Phase 3
│       │   ├── <lang>.srt ou .vtt
│       │   └── <lang>_cues.jsonl
│       └── align/              # Phase 4
│           ├── <run_id>.jsonl
│           └── <run_id>_report.json
└── corpus.db
```

---

## Principes respectés

- **Core sans UI** : toute la logique dans `core/` ; l’UI dans `app/` appelle le pipeline et les stores.
- **RAW jamais écrasé** : CLEAN et index dérivés ; reprise possible.
- **Steps idempotents** : skip si fichier/DB déjà présent (sauf `force=True`).
- **Rate limit** : délai entre requêtes (config dans `config.toml`).
- **Extensibilité** : adapters + registre ; profils de normalisation ; pas de HIMYM en dur.

---

## Tests (46 au total)

- **Adapter subslikescript** : discover (fixture), parse_episode, erreur si transcript trop court.
- **Normalisation** : fusion césure, double saut conservé, didascalie, ligne type « TED: », profils.
- **DB / KWIC** : init, index, `query_kwic` → left / match / right ; segments, cues ; **Phase 4** : `align_runs`, `align_links`, `query_alignment_for_episode`, `set_align_status` ; **Phase 5** : `get_align_stats_for_run`, `get_parallel_concordance`.
- **Alignement (Phase 4)** : similarité texte, `align_segments_to_cues`, `align_cues_by_time`, `AlignLink.to_dict`.
- **Export Phase 5** : `export_parallel_concordance_csv/tsv/jsonl`, `export_align_report_html`.

---

## Phases suivantes (hors MVP)

- **Phase 2** : Segmentation phrases / utterances, exports JSONL/CSV. ✅ *Fait : `core/segment.py` (utterances, phrases), export corpus segmenté JSONL + CSV (utterances / phrases) dans l’UI.*
- **Phase 3** : Import sous-titres SRT/VTT (fichiers locaux). ✅ *Fait.*
- **Phase 4** : Alignement transcript ↔ sous-titres officiels, UI validation. ✅ *Fait : `core/align/` (similarity, aligner), tables `align_runs`/`align_links`, onglet Alignement, export CSV/JSONL, audit par run.*
- **Phase 5** : Exports concordancier parallèle, stats, rapports (Quarto optionnel). ✅ *Fait : `get_align_stats_for_run`, `get_parallel_concordance`, export CSV/TSV/JSONL concordancier parallèle, rapport HTML (stats + échantillon), boutons Stats / Rapport HTML / Exporter concordancier parallèle dans l’onglet Alignement.*
- **Phase 6** : Packaging Windows (PyInstaller, mise à jour optionnelle). ✅ *Fait : HowIMetYourCorpus.spec (datas schema.sql + migrations), build_exe.bat et release.yml utilisent le spec ; menu Aide → À propos (version), Aide → Vérifier les mises à jour (ouvre GitHub releases).*

---

*Récap généré pour HowIMetYourCorpus MVP — à ouvrir avec le dossier projet.*

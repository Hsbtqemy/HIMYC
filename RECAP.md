# HowIMetYourCorpus — Récapitulatif MVP

Document de synthèse du projet (Phase 1 MVP). À garder à côté du dossier pour retrouver rapidement structure, commandes et critères.

---

## En bref

- **Nom :** HowIMetYourCorpus  
- **Type :** Application desktop Windows (Python 3.11+, PySide6)  
- **Objectif :** Construire, normaliser, indexer et explorer des transcriptions (source web subslikescript), sans logique métier en dur (générique + preset HIMYM en config).

---

## Commandes utiles

| Action | Commande |
|--------|----------|
| Installer (venv + deps) | `scripts\windows\install.bat` |
| Lancer l’app (sans console) | `scripts\windows\run.bat` |
| Lancer avec console | `.venv\Scripts\activate` puis `set PYTHONPATH=src` et `python -m corpusstudio.app.main` |
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
├── src/corpusstudio/
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
│       │   ├── tasks.py        # FetchSeriesIndex, FetchEpisode, Normalize, BuildDbIndex
│       │   └── runner.py       # PipelineRunner
│       ├── storage/
│       │   ├── project_store.py # Layout projet, RAW/CLEAN
│       │   ├── db.py           # SQLite + FTS5 + KWIC
│       │   └── schema.sql
│       └── utils/              # logging, text, http
├── tests/
│   ├── fixtures/               # subslikescript_series.html, subslikescript_episode.html
│   ├── test_adapter_subslikescript.py
│   ├── test_normalize_profiles.py
│   └── test_db_kwic.py
└── scripts/windows/
    ├── install.bat
    └── run.bat
```

---

## Workflow utilisateur (UI)

1. **Projet** — Choisir dossier (nouveau ou existant) → source, URL série, rate limit, profil → « Valider & initialiser ».
2. **Corpus** — Découvrir épisodes → Télécharger (sélection / tout) → Normaliser → Indexer DB. Progression + Annuler.
3. **Inspecteur** — Choisir épisode → voir RAW vs CLEAN, stats, exemples de fusions.
4. **Concordance** — Saisir terme, filtres saison/épisode → résultats KWIC ; double-clic → Inspecteur sur l’épisode.
5. **Logs** — Logs en direct + « Ouvrir fichier log ».

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
│       └── transform_meta.json
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

## Tests (14 au total)

- **Adapter subslikescript** : discover (fixture), parse_episode, erreur si transcript trop court.
- **Normalisation** : fusion césure, double saut conservé, didascalie, ligne type « TED: », profils.
- **DB / KWIC** : init, index, `query_kwic` → left / match / right.

---

## Phases suivantes (hors MVP)

- **Phase 2** : Segmentation phrases / utterances, exports JSONL/CSV.
- **Phase 3** : Import sous-titres SRT/VTT (fichiers locaux).
- **Phase 4** : Alignement transcript ↔ sous-titres officiels, UI validation.
- **Phase 5** : Exports concordancier parallèle, stats, rapports (Quarto optionnel).
- **Phase 6** : Packaging Windows (PyInstaller, mise à jour optionnelle).

---

*Récap généré pour HowIMetYourCorpus MVP — à ouvrir avec le dossier projet.*

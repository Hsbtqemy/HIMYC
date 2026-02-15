# Baseline UI Perf - Lot 0

Date de mesure: 2026-02-14  
Script: `scripts/benchmark_ui_baseline.py`  
Sortie brute: `artifacts/ui_baseline/baseline_ui_perf.json`

## Objectif

Figer une baseline reproductible avant les prochains lots (KWIC async/logs/personnages/controller),
avec des KPI mesurables et comparables apres chaque patch.

## Commande reproduite

```bash
python scripts/benchmark_ui_baseline.py
```

## Environnement

- Python: `3.13.9`
- Plateforme: `macOS-26.2-arm64-arm-64bit-Mach-O`
- Machine: `arm64`

## Dataset synthetique utilise

- Episodes: `96`
- Lignes texte / episode: `180`
- Segments (sentence): `17280`
- Cues (sous-titres): `11520`
- Fichier logs pour tail: `80000` lignes
- Setup DB + index initial: `1109.17 ms`

## KPI (resultats initiaux)

| KPI | p50 (ms) | p95 (ms) | Mean (ms) | Seuil cible |
|---|---:|---:|---:|---|
| KWIC episodes (1 page) | 1.00 | 1.07 | 1.01 | pas de freeze UI |
| KWIC episodes (2 pages) | 2.35 | 3.76 | 2.62 | pagination stable |
| KWIC segments (1 page) | 12.77 | 14.26 | 13.00 | pas de freeze UI |
| KWIC cues (1 page) | 3.91 | 4.14 | 3.93 | pas de freeze UI |
| Open project -> export KWIC | 2.33 | 3.53 | 2.54 | tendance a la baisse |
| Filtre logs 5k | 34.22 | 38.44 | 35.08 | p95 < 200 ms |
| Filtre logs 10k | 68.78 | 69.77 | 68.74 | p95 < 200 ms |
| Render logs 10k | 68.45 | 69.79 | 68.71 | p95 < 200 ms |
| Tail logs (500 lignes) | 0.09 | 0.10 | 0.09 | quasi instantane |

## Notes d'interpretation

1. Cette baseline est volontairement "backend + logique UI pure" (pas de rendu Qt frame par frame).
2. Elle sert de reference comparative stable entre commits, pas de "truth absolute" UX.
3. Les KPI logs sont deja sous le seuil perceptif cible (`p95 < 200 ms`) sur ce jeu de donnees.
4. Le scenario "open project -> export KWIC" est mesure sur projet deja indexe (ouverture + requete + export).

## Prochaines etapes Lot 0

1. Rejouer ce script apres chaque lot P0/P1 impactant KWIC ou logs.
2. Ajouter un run Windows de baseline pour valider les contraintes cible plateforme.
3. Archiver un JSON par date (ou par commit) pour graphe d'evolution.

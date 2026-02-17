# Adapter TVMaze - Documentation

## 📋 Vue d'ensemble

L'adapter **TVMaze** permet de découvrir automatiquement la liste complète des épisodes d'une série TV **par simple recherche de nom**, sans avoir besoin de transcripts web.

## 🎯 Cas d'usage

### Workflow idéal
1. **Créer la structure** : Rechercher "Breaking Bad" sur TVMaze → récupère S01E01 à S05E16
2. **Remplir avec du contenu** au choix :
   - **Transcripts** : Télécharger depuis subslikescript
   - **Sous-titres** : Importer vos fichiers .srt
   - **Les deux** : Transcripts + SRT pour alignement

### Avantages
- ✅ **Pas besoin d'URL** : juste le nom de la série
- ✅ **Métadonnées complètes** : titres d'épisodes, saisons, dates
- ✅ **API gratuite** : TVMaze API publique sans clé requise
- ✅ **Recherche flexible** : tolère les fautes de frappe (fuzzy search)
- ✅ **Compatible** : fonctionne avec transcripts ET/OU sous-titres

## 🚀 Utilisation

### Via l'interface graphique

1. **Onglet Projet** → Source : sélectionner `tvmaze`
2. Le champ change automatiquement en **"Nom de la série"**
3. Entrer le nom : `Breaking Bad`, `The Wire`, `Friends`, etc.
4. **Onglet Corpus** → Cliquer sur **"🔍 Découvrir épisodes"**
5. Résultat : liste complète avec S01E01, S01E02, ..., titres inclus

### Via Python (programmatique)

```python
from howimetyourcorpus.core.adapters.tvmaze import TvmazeAdapter

adapter = TvmazeAdapter()
index = adapter.discover_series("Breaking Bad")

print(f"Série: {index.series_title}")
print(f"Nombre d'épisodes: {len(index.episodes)}")

for ep in index.episodes[:5]:
    print(f"{ep.episode_id} - {ep.title}")
```

**Résultat** :
```
Série: Breaking Bad
Nombre d'épisodes: 62
S01E01 - Pilot
S01E02 - Cat's in the Bag...
S01E03 - ...And the Bag's in the River
S01E04 - Cancer Man
S01E05 - Gray Matter
```

## 📊 Exemples testés

| Série | Épisodes | Saisons | Status |
|-------|----------|---------|--------|
| Breaking Bad | 62 | 5 | ✅ |
| The Wire | 60 | 5 | ✅ |
| Friends | 236 | 10 | ✅ (potentiel) |
| Game of Thrones | 73 | 8 | ✅ (potentiel) |

## 🔧 API Technique

### Endpoints utilisés

1. **Recherche série** : `GET https://api.tvmaze.com/singlesearch/shows?q={nom}`
   - Retourne les infos de la série (ID, nom, etc.)
   - Fuzziness = 1 (tolère les petites fautes)

2. **Liste épisodes** : `GET https://api.tvmaze.com/shows/{id}/episodes`
   - Retourne tous les épisodes avec métadonnées
   - Format : JSON avec season, number, name, url

### Rate limiting
- **Limite** : 20 requêtes / 10 secondes
- **Implémentation** : délai automatique de 0.5s entre requêtes
- **Gestion 429** : retry automatique avec backoff exponentiel

### Cache
- Les requêtes JSON sont mises en cache (7 jours par défaut)
- Fichiers `.json` dans `project_root/.cache/`
- Évite les appels répétés pour la même série

## ⚠️ Limitations connues

### Ce que TVMaze NE fournit PAS
- ❌ **Pas de transcripts textuels** : TVMaze ne contient pas les dialogues
- ❌ **Pas de sous-titres** : seulement les métadonnées d'épisodes
- ❌ **Pas de téléchargement** : `fetch_episode_html()` et `parse_episode()` lèvent `NotImplementedError`

### Solution
TVMaze est un **adapter de découverte uniquement**. Après avoir créé la structure :
- Utilisez **subslikescript** pour télécharger les transcripts
- Ou importez vos **fichiers .srt** manuellement

## 🔄 Comparaison avec subslikescript

| Caractéristique | TVMaze | subslikescript |
|-----------------|--------|----------------|
| **Découverte** | ✅ Recherche par nom | ✅ URL directe |
| **Transcripts** | ❌ Non disponible | ✅ Téléchargement HTML |
| **Métadonnées** | ✅ Titres, dates | ⚠️ Basique |
| **API** | ✅ JSON REST | ⚠️ Scraping HTML |
| **Stabilité** | ✅ Très stable | ⚠️ Dépend du HTML |
| **Rate limit** | 20 req/10s | Variable |

## 💡 Workflow recommandé

### Scénario 1 : Transcripts + SRT
```
1. TVMaze → Découvrir "Breaking Bad" (structure)
2. subslikescript → Télécharger transcripts
3. Import SRT → Ajouter sous-titres
4. Alignement → Lier transcripts ↔ SRT
```

### Scénario 2 : SRT uniquement
```
1. TVMaze → Découvrir "The Wire" (structure)
2. Import batch SRT → Ajouter tous les .srt
3. Normaliser → Segmenter → Indexer
```

### Scénario 3 : Transcripts uniquement
```
1. TVMaze → Découvrir "Friends" (structure)
2. subslikescript → Télécharger transcripts
3. Normaliser → Segmenter → Indexer
```

## 🛠️ Fichiers modifiés

### Nouveaux fichiers
- `src/howimetyourcorpus/core/adapters/tvmaze.py` : adapter complet
- `ADAPTER_TVMAZE.md` : cette documentation

### Fichiers modifiés
- `src/howimetyourcorpus/core/adapters/__init__.py` : enregistrement adapter
- `src/howimetyourcorpus/core/utils/http.py` : ajout fonction `get_json()`
- `src/howimetyourcorpus/app/tabs/tab_projet.py` : UI dynamique selon source

## 📝 Notes techniques

### Architecture
```python
class TvmazeAdapter:
    id = "tvmaze"
    
    def discover_series(series_name: str) -> SeriesIndex:
        # 1. Recherche via /singlesearch/shows
        # 2. Récupération épisodes via /shows/{id}/episodes
        # 3. Construction SeriesIndex avec EpisodeRef
        
    def fetch_episode_html() -> NotImplementedError
    def parse_episode() -> NotImplementedError
```

### Gestion d'erreurs
- Série introuvable → `ValueError` avec message explicite
- API indisponible → retry automatique (3 tentatives)
- Timeout → configurable (30s par défaut)
- Épisodes sans numéro → ignorés silencieusement (log debug)

## 🎓 Exemple complet

```python
from pathlib import Path
from howimetyourcorpus.core.adapters.tvmaze import TvmazeAdapter
from howimetyourcorpus.core.storage.project_store import ProjectStore

# 1. Découverte via TVMaze
adapter = TvmazeAdapter()
index = adapter.discover_series("Breaking Bad")

# 2. Sauvegarde dans un projet
store = ProjectStore(Path("./my_project"))
store.save_series_index(index)

# 3. Affichage
print(f"✅ {index.series_title} : {len(index.episodes)} épisodes")
for ep in index.episodes[:3]:
    print(f"   {ep.episode_id} - {ep.title}")
```

## 🚀 Prochaines améliorations possibles

1. **Support IMDb/TheTVDB** : lookup alternatif par ID
2. **Filtrage saisons** : découvrir uniquement S01-S03
3. **Cache intelligent** : détection mises à jour séries
4. **Métadonnées enrichies** : cast, genre, résumé
5. **Recherche avancée** : année, pays, langue

---

**Version** : 1.0  
**Date** : 2026-02-17  
**Auteur** : HowIMetYourCorpus Team

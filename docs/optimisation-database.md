# 🗄️ Optimisation Base de Données — Diagnostic et Solutions

**Date** : 2026-02-16  
**Phase** : Phase 6  
**Objectif** : Améliorer les performances de la base de données SQLite (requêtes, index, connexions)

---

## 📊 1. Diagnostic

### 🔴 Problème Critique : Surcharge de Connexions

**Observation** :
```python
# db.py — Pattern actuel (PROBLÈME)
def query_kwic(self, term: str, ...) -> list[KwicHit]:
    conn = self._conn()  # ❌ Nouvelle connexion
    try:
        return _query_kwic(conn, ...)
    finally:
        conn.close()  # ❌ Fermeture immédiate
```

**Impact** :
- **60+ méthodes** ouvrent/ferment des connexions individuellement
- Une recherche KWIC + affichage segments = **5-10 connexions**
- Refresh UI (arbre corpus) = **20-50 connexions** selon le nombre d'épisodes

**Calcul de surcharge** :
- Ouverture connexion SQLite : ~2-5ms
- Refresh UI avec 50 épisodes : **100-250ms** juste pour les connexions !

---

### 🟡 Index Manquants ou Sous-Optimisés

#### Requêtes fréquentes non indexées :

1. **Filtrage par statut d'épisode** :
```sql
SELECT * FROM episodes WHERE status = ?  -- Pas d'index sur status
```

2. **Recherche segments par speaker** :
```sql
SELECT DISTINCT speaker_explicit FROM segments WHERE ...  -- Lent
```

3. **Comptage cues par langue** :
```sql
SELECT COUNT(*) FROM subtitle_cues WHERE lang = ?  -- Pas d'index dédié
```

#### Index existants (002_segments.sql) :
✅ `idx_segments_episode_kind_n` sur `(episode_id, kind, n)`  
✅ `idx_subtitle_tracks_episode` sur `(episode_id)`  
✅ `idx_subtitle_cues_episode_lang` sur `(episode_id, lang)`  
✅ `idx_align_links_run` sur `(align_run_id)`

---

### 🟡 Transactions Non-Optimales

**Problème** : Insertions multiples sans transaction explicite

```python
# db_segments.py — CORRECT ✅
def upsert_segments(conn, episode_id, kind, segments):
    with conn:  # Transaction automatique
        conn.execute("DELETE FROM segments WHERE ...")
        for seg in segments:  # 1 transaction pour tous
            conn.execute("INSERT INTO segments ...")
```

Mais dans `db.py`, les appels successifs ouvrent/ferment :
```python
# ❌ Pattern problématique
for ep in episodes:
    db.upsert_episode(ep)  # Connexion 1, 2, 3...
```

---

## 🚀 2. Solutions Proposées

### Solution 1 : Context Manager pour Connexions

**Objectif** : Réutiliser une connexion pour plusieurs opérations

```python
@contextmanager
def connection(self) -> sqlite3.Connection:
    """Context manager pour réutiliser une connexion."""
    conn = self._conn()
    try:
        yield conn
    finally:
        conn.close()

# Utilisation :
with db.connection() as conn:
    db_segments.upsert_segments(conn, ep_id, "sentence", segs)
    db_segments.upsert_segments(conn, ep_id, "utterance", utts)
    # 1 seule connexion pour 2+ opérations !
```

**Avantage** : 
- Rétrocompatible avec l'API existante
- Optionnel (on peut garder les méthodes simples)
- Réduit la surcharge de **90%** pour les opérations batch

---

### Solution 2 : Méthodes Batch

```python
def upsert_episodes_batch(self, refs: list[EpisodeRef], status: str = "new") -> None:
    """Insère plusieurs épisodes en une seule transaction."""
    conn = self._conn()
    try:
        with conn:
            for ref in refs:
                conn.execute(
                    """INSERT INTO episodes (...)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(episode_id) DO UPDATE SET ...""",
                    (ref.episode_id, ref.season, ref.episode, ref.title, ref.url, status),
                )
    finally:
        conn.close()
```

---

### Solution 3 : Index Additionnels

**Migration `005_optimize_indexes.sql`** :

```sql
-- Index sur status pour filtrage rapide
CREATE INDEX IF NOT EXISTS idx_episodes_status ON episodes(status);

-- Index composite season+episode pour recherche rapide
CREATE INDEX IF NOT EXISTS idx_episodes_season_episode ON episodes(season, episode);

-- Index sur speaker_explicit pour recherche locuteurs
CREATE INDEX IF NOT EXISTS idx_segments_speaker ON segments(speaker_explicit) 
  WHERE speaker_explicit IS NOT NULL;

-- Index sur lang pour comptage rapide des sous-titres
CREATE INDEX IF NOT EXISTS idx_subtitle_cues_lang ON subtitle_cues(lang);

-- Index composite pour requêtes d'alignement fréquentes
CREATE INDEX IF NOT EXISTS idx_align_links_episode_status ON align_links(episode_id, status);

UPDATE schema_version SET version = 5;
```

**Impact attendu** :
- Filtrage par statut : **10-50x plus rapide** (scan → index)
- Recherche locuteurs : **5-20x plus rapide**
- Comptage sous-titres : **instantané**

---

### Solution 4 : Optimisations SQLite

**Pragma au démarrage** :

```python
def _conn(self) -> sqlite3.Connection:
    conn = sqlite3.connect(self.db_path)
    # Optimisations de performance
    conn.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
    conn.execute("PRAGMA synchronous = NORMAL")  # Balance sécurité/perf
    conn.execute("PRAGMA cache_size = -64000")  # Cache 64MB
    conn.execute("PRAGMA temp_store = MEMORY")  # Temp tables en RAM
    conn.execute("PRAGMA mmap_size = 268435456")  # Memory-mapped I/O 256MB
    return conn
```

**Justification** :
- **WAL mode** : Lectures concurrentes + écritures non-bloquantes
- **cache_size** : Réduit les I/O disque (important pour FTS5)
- **mmap_size** : Accélère les grosses requêtes KWIC

---

## 📈 3. Gains de Performance Attendus

### Benchmark Estimé

| Opération | Avant | Après | Gain |
|-----------|-------|-------|------|
| Refresh UI (50 épisodes) | ~200ms | ~20ms | **10x** |
| Recherche KWIC (1000 hits) | ~150ms | ~80ms | **2x** |
| Import 10 épisodes | ~500ms | ~100ms | **5x** |
| Filtrage par statut | ~50ms | ~2ms | **25x** |
| Comptage segments/cues | ~30ms | ~3ms | **10x** |

**Gain global estimé** : **5-10x sur opérations UI courantes**

---

## ✅ 4. Plan d'Implémentation

1. ✅ **Documenter** le diagnostic (ce fichier)
2. ⏳ **Créer migration** `005_optimize_indexes.sql`
3. ⏳ **Ajouter PRAGMA** dans `_conn()`
4. ⏳ **Implémenter `connection()` context manager**
5. ⏳ **Ajouter méthodes batch** (`upsert_episodes_batch`, etc.)
6. ⏳ **Tester performances** avec benchmark script
7. ⏳ **Documenter changements** dans `CHANGELOG_DB_PHASE6.md`

---

## 🔍 5. Tests de Validation

### Test 1 : Vérifier les index

```sql
-- Vérifier qu'un index est utilisé
EXPLAIN QUERY PLAN 
SELECT * FROM episodes WHERE status = 'indexed';
-- Doit afficher : SEARCH episodes USING INDEX idx_episodes_status
```

### Test 2 : Benchmark connexions

```python
import time

# Avant (pattern actuel)
start = time.perf_counter()
for i in range(100):
    conn = db._conn()
    conn.execute("SELECT 1")
    conn.close()
elapsed_before = time.perf_counter() - start

# Après (context manager)
start = time.perf_counter()
with db.connection() as conn:
    for i in range(100):
        conn.execute("SELECT 1")
elapsed_after = time.perf_counter() - start

print(f"Avant : {elapsed_before:.3f}s")
print(f"Après : {elapsed_after:.3f}s")
print(f"Gain  : {elapsed_before / elapsed_after:.1f}x")
```

---

## 📚 Références

- [SQLite Performance Tuning](https://www.sqlite.org/pragma.html#pragma_optimize)
- [FTS5 Best Practices](https://www.sqlite.org/fts5.html)
- [Write-Ahead Logging](https://www.sqlite.org/wal.html)

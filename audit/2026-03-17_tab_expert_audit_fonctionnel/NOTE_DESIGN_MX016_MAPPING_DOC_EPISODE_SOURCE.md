# Note de Design — MX-016 : Mapping doc_id/doc_relations → episode_key/source_key

Date: 2026-03-18
Statut: **VALIDE**
Depends: MX-003 (bridge), informe MX-004 (modele donnees)

---

## Contexte

AGRAFES est doc-centrique : chaque corpus = un `document` (doc_id INTEGER),
les relations inter-documents sont explicites (`doc_relations`),
les alignements sont des liens au niveau unites (`alignment_links`).

HIMYC est episode/source-centrique : un episode possede des sources
(`transcript`, `srt_<lang>`), liees implicitement par leur `episode_id`.

Ce spike valide le mapping entre les deux modeles sans migration destructive.

---

## Modele AGRAFES (reference)

```
documents          : doc_id (INT PK), title, language, doc_role, resource_type
units              : unit_id (INT PK), doc_id (FK), external_id (INT §N), text_raw, text_norm
doc_relations      : doc_id → target_doc_id via relation_type ('translation_of' | 'excerpt_of')
alignment_links    : pivot_unit_id ↔ target_unit_id via external_id §N partagé
```

`doc_role` valeurs : `"original"` | `"translation"` | `"excerpt"` | `"standalone"` | `"unknown"`

---

## Mapping HIMYC → AGRAFES (projection conceptuelle)

### doc_id

| HIMYC                            | Projection doc_id (string composite) |
|----------------------------------|---------------------------------------|
| episode S01E01, source transcript | `"S01E01:transcript"`                |
| episode S01E01, source srt_en     | `"S01E01:srt_en"`                    |
| episode S01E01, source srt_fr     | `"S01E01:srt_fr"`                    |

> **Decision** : Le `doc_id` dans le frontend Tauri est une chaine composite
> `"{episode_id}:{source_key}"`, pas un entier. Pas de partage de DB avec AGRAFES.

### Metadonnees minimales par source (MX-004)

```
episode_key   : string    — ex: "S01E01"
source_key    : string    — ex: "transcript" | "srt_en" | "srt_fr"
language      : string    — ex: "en", "fr" (depuis source_key ou config)
doc_role      : string    — "original" (transcript) | "translation" (srt)
title         : string    — "{series_title} — {episode_id}"
state         : string    — "raw" | "normalized" | "segmented" | "ready_for_alignment"
```

### doc_relations (implicites dans HIMYC)

HIMYC n a pas de table `doc_relations`. Les relations sont deduites de la structure :

- Toutes les sources d un meme episode sont implicitatement liees par `episode_id`.
- `srt_<lang>` est "translation_of" `transcript` si transcript existe.
- Si srt-only : les SRT multi-langues sont liees entre elles (pivot = langue primaire).

La projection explicite pour l Aligner :

```json
{
  "doc_id": "S01E01:srt_en",
  "relation_type": "translation_of",
  "target_doc_id": "S01E01:transcript"
}
```

Calculee a la demande — pas stockee dans corpus.db.

### Convention pivot/target

| Contexte    | pivot                  | target                |
|-------------|------------------------|-----------------------|
| Constituer  | non applicable         | non applicable        |
| Inspecter   | non applicable         | non applicable        |
| Aligner     | transcript (ou srt pivot lang) | srt_<lang>  |

> **Regle** : `pivot` et `target` sont des concepts exclusifs a l Aligner.
> Constituer et Inspecter travaillent toujours en contexte `episode_key + source_key`.

---

## Faisabilite — 3 cas

### Cas 1 : transcript-only

```
Docs      : 1 — S01E01:transcript (role="original", lang="en")
Relations : 0
Units     : segments transcript (apres segmentation)
Aligner   : N/A (pas de cible SRT disponible)
```

Requetes Constituer : `GET /episodes` → source transcript available=true.
Requetes Inspecter  : `GET /episodes/S01E01/sources/transcript`.

### Cas 2 : transcript + srt_en

```
Docs      : 2 — S01E01:transcript (role="original") + S01E01:srt_en (role="translation")
Relations : 1 — srt_en "translation_of" transcript
Units     : segments transcript + cues SRT
Aligner   : pivot=transcript, target=srt_en
alignment_links : transcript §N ↔ srt_en cue_n (via external_id partagé)
```

Requetes Constituer : `GET /episodes` → sources: [{transcript}, {srt_en}].
Requetes Inspecter  : `GET /episodes/S01E01/sources/srt_en`.
Requetes Aligner    : `GET /episodes/S01E01/alignment_runs` (API MX-009).

### Cas 3 : srt-only (pas de transcript)

```
Docs      : N — S01E01:srt_en (role="original"), S01E01:srt_fr (role="translation")
Relations : 1 — srt_fr "translation_of" srt_en (pivot=langue primaire)
Units     : cues SRT par langue
Aligner   : pivot=srt_en, target=srt_fr
```

Requetes Constituer : `GET /episodes` → source transcript available=false, sources SRT listes.
Requetes Inspecter  : `GET /episodes/S01E01/sources/srt_en` ou `srt_fr`.
Requetes Aligner    : meme interface, pivot/target configures dynamiquement.

---

## Decision : pas de migration DB, projection a la demande

Le modele AGRAFES `doc/unit/doc_relations` n est PAS injecte dans `corpus.db`.

Raisons :
1. Migration DB = contrainte non-negociable du backlog.
2. `corpus.db` est le referentiel HIMYC existant — stable et teste.
3. Les relations inter-sources sont derivables depuis l API `/episodes`.
4. Seul l Aligner a besoin de la projection `pivot/target` — elle sera calculee
   dans le module `alignerModule.ts` en MX-009, pas en DB.

---

## Impact sur MX-004 (modele donnees front-back)

MX-004 doit implementer :

```typescript
// Types canoniques (front)
interface HimycDoc {
  doc_id: string;          // "{episode_id}:{source_key}"
  episode_key: string;
  source_key: string;
  language: string;
  doc_role: "original" | "translation" | "standalone";
  title: string;
  state: SourceState;
}

type SourceState = "unknown" | "raw" | "normalized" | "segmented" | "ready_for_alignment";

interface HimycDocRelation {
  doc_id: string;
  relation_type: "translation_of";
  target_doc_id: string;
}

// Derivee depuis EpisodesResponse (MX-003)
function episodeSourceToDoc(episode: Episode, source: EpisodeSource): HimycDoc
function deriveDocRelations(episode: Episode): HimycDocRelation[]
```

---

## Requetes identifiees pour Constituer et Inspecter

### Constituer

| Besoin                              | Requete                             |
|-------------------------------------|-------------------------------------|
| Lister episodes + sources           | `GET /episodes`                     |
| Etat de completion par source       | `episode.sources[].state`           |
| Import transcript                   | `POST /episodes/{id}/sources/transcript` (MX-005) |
| Import SRT                          | `POST /episodes/{id}/sources/srt_{lang}` (MX-005) |

### Inspecter

| Besoin                              | Requete                             |
|-------------------------------------|-------------------------------------|
| Sources disponibles pour un episode | `GET /episodes` → episode.sources   |
| Contenu source active               | `GET /episodes/{id}/sources/{key}`  |
| Actions disponibles (transcript)    | derive de source.state              |
| Actions disponibles (SRT)           | derive de source.state + doc_role   |

---

## Conclusion

Le mapping est **univoque et exploitable** sans migration destructive :

- `doc_id` = `"{episode_id}:{source_key}"` (string composite, front uniquement)
- `doc_role` = "original" (transcript) | "translation" (srt)
- `doc_relations` = derivees a la demande depuis `/episodes`
- `pivot/target` = Aligner uniquement
- Les APIs MX-003 couvrent tous les besoins Constituer + Inspecter
- MX-004 instanciera les types ci-dessus et les fonctions de derivation

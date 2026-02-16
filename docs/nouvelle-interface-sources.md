# ✨ Nouvelle Interface : Sources Équilibrées (Transcripts ⚖️ Sous-titres)

## 🎉 Ce qui a changé

L'interface de l'onglet **Corpus** a été entièrement repensée pour mettre **Transcripts** et **Sous-titres** au même niveau. Les deux sources sont maintenant présentées de manière égale, permettant des workflows flexibles.

## 🎨 Nouvelle Interface - Bloc 1 : SOURCES

### Vue d'ensemble

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. SOURCES — Constitution du corpus                              │
│                                                                   │
│ [Tout cocher] [Tout décocher]                                    │
│                                                                   │
│ ┌─────────────────────────┬─────────────────────────────────────┐│
│ │ 📄 TRANSCRIPTS          │ 📺 SOUS-TITRES (SRT)               ││
│ │ Texte narratif web      │ Alignés sur la vidéo               ││
│ ├─────────────────────────┼─────────────────────────────────────┤│
│ │ Récupération            │ Import manuel                       ││
│ │ automatique web         │ depuis ordinateur                   ││
│ │                         │                                     ││
│ │ 🔍 Découvrir épisodes   │ ➕ Ajouter épisodes (liste)        ││
│ │ 🔀 Fusionner source     │ 📥 Importer SRT sélection          ││
│ │ ⬇️ Télécharger sél.     │ 📁 Import batch (dossier)          ││
│ │ ⬇️ Télécharger tout     │ ⚙️ Gérer sous-titres               ││
│ │                         │                                     ││
│ │ Status : 15/24 ✅       │ Status : 8/24 ⚠️ (16 manquants)   ││
│ └─────────────────────────┴─────────────────────────────────────┘│
│                                                                   │
│ 💡 Workflows flexibles : Transcripts seuls, Sous-titres seuls,  │
│    ou les deux ensemble. Commencez par la source de votre choix!│
└──────────────────────────────────────────────────────────────────┘
```

## 📋 Fonctionnalités par Colonne

### 📄 TRANSCRIPTS (Colonne Gauche)

**Description** : Texte narratif complet récupéré depuis des sites web spécialisés.

**Boutons** :
- **🔍 Découvrir épisodes** : Récupère automatiquement la liste depuis la source web configurée (onglet Projet)
- **🔀 Fusionner autre source** : Fusionne avec une autre source/URL sans écraser les épisodes existants
- **⬇️ Télécharger sélection** : Télécharge le texte narratif des épisodes cochés
- **⬇️ Télécharger tout** : Télécharge le texte narratif de tous les épisodes découverts

**Status** :
- ✅ Vert : Tous les épisodes ont un transcript téléchargé
- ⚠️ Orange : Certains épisodes n'ont pas de transcript

---

### 📺 SOUS-TITRES (Colonne Droite)

**Description** : Fichiers de sous-titres (.srt) alignés précisément sur la vidéo avec timestamps.

**Boutons** :
- **➕ Ajouter épisodes (liste)** : Créer manuellement la liste des épisodes (S01E01, S01E02...). Nécessaire si vous n'avez pas découvert via transcripts.
- **📥 Importer SRT sélection** : Importer les fichiers .srt pour les épisodes sélectionnés (redirige vers Inspecteur)
- **📁 Import batch (dossier)** : Importer automatiquement tous les .srt d'un dossier avec détection automatique des épisodes
- **⚙️ Gérer sous-titres** : Ouvre l'onglet Inspecteur pour gérer les pistes de sous-titres

**Status** :
- ✅ Vert : Tous les épisodes ont au moins une piste de sous-titres
- ⚠️ Orange : Certains épisodes n'ont pas de sous-titres

## 🚀 Workflows Supportés

### Workflow 1 : Transcripts d'Abord (Classique)

**Cas d'usage** : Vous travaillez avec des transcripts web uniquement.

**Étapes** :
1. **Transcripts** → Découvrir épisodes
2. **Transcripts** → Télécharger tout
3. **Normalisation** → Normaliser + Segmenter
4. **Concordance** → Explorer le corpus

---

### Workflow 2 : Sous-titres d'Abord (Nouveau ⭐)

**Cas d'usage** : Vous travaillez uniquement avec des fichiers .srt locaux.

**Étapes** :
1. **Sous-titres** → Ajouter épisodes (liste) : S01E01, S01E02, S01E03...
2. **Sous-titres** → Import batch (dossier) : Sélectionner le dossier contenant vos .srt
3. **Sous-titres** → Gérer sous-titres : Vérifier les pistes dans l'Inspecteur
4. **Normalisation** → Normaliser + Segmenter
5. **Concordance** → Explorer le corpus

**Exemple de dossier** :
```
/mes-sous-titres/
├── S01E01.srt
├── S01E02.srt
├── S01E03.srt
└── S02E01.srt
```

---

### Workflow 3 : Les Deux en Parallèle (Optimal)

**Cas d'usage** : Vous avez à la fois des transcripts web et des sous-titres locaux.

**Étapes** :
1. **Transcripts** → Découvrir épisodes + Télécharger tout
2. **Sous-titres** → Import batch (dossier)
3. **Normalisation** → Normaliser + Segmenter (les deux sources)
4. **Alignement** → Aligner transcripts ↔ sous-titres
5. **Concordance** → Explorer le corpus aligné

---

### Workflow 4 : Hybride (Flexibilité Maximale)

**Cas d'usage** : Certains épisodes ont des transcripts, d'autres ont des sous-titres.

**Étapes** :
1. **Transcripts** → Découvrir + Télécharger (ex: S01E01-S01E05)
2. **Sous-titres** → Importer SRT (ex: S01E06-S01E10)
3. **Normalisation** → Normaliser tout (gère les deux sources)
4. **Concordance** → Explorer le corpus mixte

## 🎯 Nouveautés

### 1. ➕ Ajouter Épisodes (Liste)

**Avant** : Bouton "Ajouter épisodes (SRT only)" isolé et confus  
**Après** : Bouton clair dans la colonne Sous-titres

**Utilisation** :
```
1. Cliquer sur "➕ Ajouter épisodes (liste)"
2. Saisir un episode_id par ligne :
   S01E01
   S01E02
   S01E03
3. OK
4. Les épisodes sont ajoutés à l'arbre
```

---

### 2. 📁 Import Batch (Dossier) ⭐

**Nouveauté majeure** : Importer automatiquement tous les .srt d'un dossier !

**Fonctionnalités** :
- Détection automatique des épisodes depuis les noms de fichiers
- Création automatique des épisodes dans l'index
- Recherche récursive dans les sous-dossiers
- Récapitulatif avant import

**Format attendu** : Les fichiers .srt doivent contenir `S01E01`, `S02E05`, etc. dans leur nom.

**Exemples valides** :
- `S01E01.srt` ✅
- `Friends - S01E01 - The One With The Pilot.srt` ✅
- `s02e05.french.srt` ✅
- `Breaking Bad S03E10.srt` ✅

**Exemples invalides** :
- `episode1.srt` ❌ (pas de format SxxExx)
- `01x01.srt` ❌ (format 01x01 non supporté, utiliser S01E01)

**Dialogue de récapitulatif** :
```
42 fichier(s) .srt détecté(s) :

• S01E01 ← Friends - S01E01.srt
• S01E02 ← Friends - S01E02.srt
• S01E03 ← Friends - S01E03.srt
... et 39 autres

Continuer l'import automatique ?
[Oui] [Non]
```

---

### 3. 📥 Importer SRT Sélection

**Fonctionnalité** : Import ciblé pour les épisodes sélectionnés.

**Utilisation** :
1. Cocher les épisodes souhaités dans l'arbre (ou sélectionner des lignes)
2. Cliquer sur "📥 Importer SRT sélection"
3. Le dialogue vous redirige vers l'onglet Inspecteur
4. Dans l'Inspecteur, gérer les pistes de sous-titres pour chaque épisode

---

### 4. ⚙️ Gérer Sous-titres

**Fonctionnalité** : Accès rapide à l'onglet Inspecteur.

**Utilisation** :
- Clic → Ouvre l'onglet Inspecteur avec le premier épisode
- Dans l'Inspecteur, vous pouvez :
  - Voir les pistes de sous-titres existantes
  - Ajouter de nouvelles pistes
  - Supprimer des pistes
  - Normaliser les sous-titres

---

### 5. Status en Temps Réel

**Nouveauté** : Chaque colonne affiche son propre status.

**Transcripts** :
- `Status : 15/24 téléchargés ⚠️ (9 manquants)` → Orange si manquants
- `Status : 24/24 téléchargés ✅` → Vert si complets

**Sous-titres** :
- `Status : 8/24 importés ⚠️ (16 manquants)` → Orange si manquants
- `Status : 24/24 importés ✅` → Vert si complets

## 💡 Conseils et Bonnes Pratiques

### Pour Projets Sous-titres Uniquement

✅ **Commencez par** : Sous-titres → Ajouter épisodes (liste)  
✅ **Puis** : Sous-titres → Import batch (dossier)  
✅ **Organisez vos fichiers** : Nommez vos .srt avec le format S01E01, S01E02...  
✅ **Ignorez** : La colonne Transcripts (pas nécessaire)

### Pour Projets Transcripts Uniquement

✅ **Commencez par** : Transcripts → Découvrir épisodes  
✅ **Puis** : Transcripts → Télécharger tout  
✅ **Ignorez** : La colonne Sous-titres (pas nécessaire)

### Pour Projets Hybrides

✅ **Utilisez les deux colonnes** en parallèle  
✅ **Alignez** ensuite dans l'onglet Alignement  
✅ **Exploitez** la concordance parallèle

### Organisation des Fichiers SRT

✅ **Bonne organisation** :
```
/mes-sous-titres/
├── Saison 1/
│   ├── S01E01.srt
│   ├── S01E02.srt
│   └── S01E03.srt
└── Saison 2/
    ├── S02E01.srt
    └── S02E02.srt
```

✅ **Aussi acceptable** :
```
/mes-sous-titres/
├── Friends.S01E01.French.srt
├── Friends.S01E02.French.srt
└── Friends.S01E03.French.srt
```

## 🎓 Exemples Complets

### Exemple 1 : Corpus de Sous-titres de Films

**Contexte** : Vous avez 50 fichiers .srt de films que vous voulez analyser.

**Étapes** :
1. Créer un nouveau projet HIMYC
2. **Sous-titres** → Ajouter épisodes : S01E01, S01E02, ... S01E50
3. **Sous-titres** → Import batch : Sélectionner le dossier contenant les 50 .srt
4. **Normalisation** → Normaliser tout (profil français si pertinent)
5. **Normalisation** → Segmenter tout
6. **Normalisation** → Indexer DB
7. **Concordance** → Recherche KWIC sur les 50 films

---

### Exemple 2 : Série TV Multilingue

**Contexte** : Série TV avec transcripts anglais + sous-titres français.

**Étapes** :
1. **Transcripts** → Découvrir épisodes (source anglaise)
2. **Transcripts** → Télécharger tout (texte anglais)
3. **Sous-titres** → Import batch : Dossier avec .srt français
4. **Normalisation** → Normaliser tout (profil anglais pour transcripts, français pour SRT)
5. **Alignement** → Aligner EN ↔ FR
6. **Concordance** → Concordance parallèle EN/FR

## 🚀 Évolutions Futures (Optionnel)

### Phase 2 : Import SRT Automatique Complet

**Objectif** : Import automatique direct dans la DB (pas de passage par Inspecteur).

**Fonctionnalités prévues** :
- Import batch → Ajout automatique des pistes dans la DB
- Détection automatique de la langue (depuis nom fichier : `.fr.srt`, `.en.srt`)
- Normalisation automatique après import

### Phase 3 : Détection Intelligente

**Objectif** : Détection automatique du workflow optimal.

**Fonctionnalités prévues** :
- Détection si projet = Transcripts, SRT, ou Hybride
- Suggestions contextuelles (ex: "Vous avez des transcripts mais pas de SRT, voulez-vous en importer ?")
- Workflow guidé au premier lancement

## 📖 Documentation Complémentaire

- `docs/refonte-sources-equilibrees.md` : Proposition de refonte complète (design)
- `README.md` : Guide général HIMYC
- `docs/profils-normalisation-phase3.md` : Profils de normalisation avancés

---

**Auteur** : Cursor AI Assistant  
**Date** : 2026-02-16  
**Status** : ✅ Implémenté  
**Version HIMYC** : Refonte Interface Sources Équilibrées

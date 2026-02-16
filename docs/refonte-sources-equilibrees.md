# 🔄 Refonte Interface : Sources Équilibrées (Transcripts ⚖️ Sous-titres)

## 📋 Problème Identifié

**Interface actuelle** :
- ❌ Transcripts = ressource principale (Bloc 1)
- ❌ Sous-titres = ajout secondaire (mention dans tooltip, bouton "SRT only")
- ❌ Workflow implicite : transcripts d'abord, sous-titres après
- ❌ Bouton "Ajouter épisodes (SRT only)" isolé et peu visible

**Conséquences** :
- Utilisateurs travaillant principalement avec sous-titres se sentent relégués
- Workflow sous-titres d'abord n'est pas évident
- Interface ne reflète pas l'égalité des deux sources

## ✨ Solution : Interface à Deux Colonnes Équilibrées

### Nouvelle Structure de l'Onglet Corpus

```
┌──────────────────────────────────────────────────────────────────────┐
│ CORPUS — Constitution du corpus                                      │
├──────────────────────────────────────────────────────────────────────┤
│ [Arbre épisodes + filtres saison]                                   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ ┌──────────────────────────────────────────────────────────────────┐│
││ 1. SOURCES — Constitution du corpus (choisir une ou deux sources)  ││
│└──────────────────────────────────────────────────────────────────┘│
│                                                                      │
│ ┌─────────────────────────────┬──────────────────────────────────┐ │
│ │ 📄 TRANSCRIPTS              │ 📺 SOUS-TITRES (SRT)            │ │
│ │ Texte narratif web          │ Alignés sur la vidéo            │ │
│ ├─────────────────────────────┼──────────────────────────────────┤ │
│ │ Configuration :             │ Configuration :                 │ │
│ │ • Source : [subslikescript▼]│ • Import : Manuel ou batch      │ │
│ │ • URL série : [________]    │ • Langues : Toutes              │ │
│ │                             │                                  │ │
│ │ Actions :                   │ Actions :                        │ │
│ │ □ Découvrir épisodes        │ □ Ajouter épisodes (liste)      │ │
│ │ □ Fusionner autre source    │ □ Importer SRT sélection        │ │
│ │ □ Télécharger sélection     │ □ Importer SRT tout             │ │
│ │ □ Télécharger tout          │ □ Import batch (dossier)        │ │
│ │                             │                                  │ │
│ │ Status : 0/0 téléchargés    │ Status : 0/0 importés           │ │
│ └─────────────────────────────┴──────────────────────────────────┘ │
│                                                                      │
│ ⚙️ Workflow flexible :                                               │
│ • Transcripts seuls → Normaliser → Segmenter                        │
│ • Sous-titres seuls → Normaliser → Aligner (avec vidéo/transcripts)│
│ • Les deux → Aligner transcripts ↔ sous-titres → Concordance       │
│                                                                      │
│ ┌──────────────────────────────────────────────────────────────────┐│
││ 2. NORMALISATION — Nettoyer et segmenter (les deux sources)        ││
│└──────────────────────────────────────────────────────────────────┘│
│ Profil : [default_fr_v1 ▼] [⚙️ Gérer profils]                       │
│ □ Normaliser sélection  □ Normaliser tout                           │
│ □ Segmenter sélection   □ Segmenter tout                            │
│ □ Indexer (KWIC)                                                     │
│                                                                      │
│ ┌──────────────────────────────────────────────────────────────────┐│
││ 3. EXPORT — Exporter le corpus                                     ││
│└──────────────────────────────────────────────────────────────────┘│
│ □ Exporter corpus (TXT, CSV, JSON, DOCX, JSONL...)                 │
│ □ Exporter sélection uniquement                                     │
│                                                                      │
│ [Barre de progression] [Annuler]                                    │
└──────────────────────────────────────────────────────────────────────┘
```

## 🎨 Mise en Œuvre Visuelle

### Deux Colonnes Égales avec GroupBox

**Colonne Gauche** : 
- Titre : "📄 TRANSCRIPTS"
- Icône claire, couleur neutre
- Actions spécifiques aux transcripts

**Colonne Droite** :
- Titre : "📺 SOUS-TITRES (SRT)"
- Icône claire, même poids visuel
- Actions spécifiques aux sous-titres

**Séparateur** : Ligne verticale légère ou splitter pour clarté

### Avantages de ce Design

✅ **Égalité visuelle** : Les deux sources ont le même poids (colonnes égales)
✅ **Clarté** : Chaque source a ses actions dédiées
✅ **Flexibilité** : Workflows multiples clairement visibles
✅ **Discoverabilité** : Nouveaux utilisateurs comprennent immédiatement les options
✅ **Pas de hiérarchie** : Aucune source n'est "première" ou "secondaire"

## 🔧 Modifications Techniques

### Fichiers à Modifier

#### 1. `tab_corpus.py` - Refonte Complète

**Avant** :
```python
# Bloc 1 — Import (constitution du corpus)
group_import = QGroupBox("1. Import — Constitution du corpus")
btn_row1 = QHBoxLayout()
# Tous les boutons transcripts + un bouton "SRT only" isolé
```

**Après** :
```python
# Bloc 1 — Sources (deux colonnes égales)
group_sources = QGroupBox("1. SOURCES — Constitution du corpus")
sources_layout = QHBoxLayout()

# Colonne gauche : Transcripts
transcripts_group = QGroupBox("📄 TRANSCRIPTS")
transcripts_group.setToolTip("Texte narratif récupéré depuis des sites web")
transcripts_layout = QVBoxLayout()
# Config
# Actions : Découvrir, Télécharger...
transcripts_group.setLayout(transcripts_layout)

# Colonne droite : Sous-titres
subtitles_group = QGroupBox("📺 SOUS-TITRES (SRT)")
subtitles_group.setToolTip("Fichiers de sous-titres alignés sur la vidéo")
subtitles_layout = QVBoxLayout()
# Config
# Actions : Ajouter épisodes, Importer SRT...
subtitles_group.setLayout(subtitles_layout)

sources_layout.addWidget(transcripts_group)
sources_layout.addWidget(subtitles_group)
group_sources.setLayout(sources_layout)
```

#### 2. Actions Spécifiques aux Sous-titres

**Nouveaux boutons** :
- "Ajouter épisodes" (était "SRT only", maintenant contextualisé)
- "Importer SRT sélection" (nouveau)
- "Importer SRT tout" (nouveau)
- "Import batch (dossier)" (nouveau, pour importer un dossier entier)

#### 3. Tooltips et Guides

**Transcripts** :
- "Découvrir épisodes : Récupère la liste depuis la source web"
- "Télécharger : Récupère le texte narratif complet"

**Sous-titres** :
- "Ajouter épisodes : Créer la liste manuellement (S01E01, S01E02...)"
- "Importer SRT : Importer fichiers .srt depuis votre ordinateur"
- "Import batch : Importer un dossier complet de sous-titres"

### Changements dans l'Onglet Inspecteur

**Avant** : Sous-titres dans un panneau secondaire  
**Après** : Sous-titres au même niveau que le transcript (splitter horizontal)

## 📊 Workflows Supportés

### Workflow 1 : Transcripts d'Abord (Actuel)
```
1. Sources → Transcripts → Découvrir + Télécharger
2. Normalisation → Normaliser + Segmenter
3. Sources → Sous-titres → Importer SRT (optionnel)
4. Alignement → Aligner transcripts ↔ sous-titres
5. Concordance → Explorer le corpus
```

### Workflow 2 : Sous-titres d'Abord (Nouveau)
```
1. Sources → Sous-titres → Ajouter épisodes + Importer SRT
2. Normalisation → Normaliser + Segmenter les sous-titres
3. Sources → Transcripts → Découvrir + Télécharger (optionnel)
4. Alignement → Aligner sous-titres ↔ transcripts
5. Concordance → Explorer le corpus
```

### Workflow 3 : Les Deux en Parallèle (Optimal)
```
1. Sources → 
   - Transcripts → Découvrir + Télécharger
   - Sous-titres → Ajouter épisodes + Importer SRT
2. Normalisation → Normaliser + Segmenter (les deux)
3. Alignement → Aligner transcripts ↔ sous-titres
4. Concordance → Explorer le corpus bilingue/multimodal
```

### Workflow 4 : Sous-titres Seuls (Cas d'usage spécifique)
```
1. Sources → Sous-titres → Ajouter épisodes + Importer SRT
2. Normalisation → Normaliser + Segmenter
3. Concordance → Explorer les sous-titres (sans transcripts)
```

## 🎯 Indicateurs Visuels de Progression

Dans chaque colonne (Transcripts / Sous-titres), afficher :

```
Status : 15/24 téléchargés ✅
         9 manquants ⚠️
```

**Codes couleur** :
- ✅ Vert : Ressource disponible
- ⚠️ Orange : Ressource manquante
- ⏳ Bleu : En cours de téléchargement/import

## 💡 Améliorations UX Supplémentaires

### 1. Mode de Démarrage Intelligent

Au premier lancement, dialogue :
```
┌─────────────────────────────────────────┐
│ Quel type de corpus souhaitez-vous     │
│ créer ?                                 │
│                                         │
│ ○ Transcripts uniquement                │
│   (texte narratif web)                  │
│                                         │
│ ○ Sous-titres uniquement                │
│   (fichiers .srt)                       │
│                                         │
│ ● Les deux (recommandé)                 │
│   (alignement transcripts ↔ sous-titres)│
│                                         │
│         [Continuer]  [Aide]             │
└─────────────────────────────────────────┘
```

### 2. Onglet "Projet" Simplifié

**Section "Type de corpus"** :
```
Type de corpus :
□ Transcripts web (nécessite : Source + URL série)
□ Sous-titres SRT (nécessite : Fichiers .srt locaux)
```

### 3. Aide Contextuelle

Bouton "?" dans chaque colonne ouvrant un mini-guide :

**Transcripts** :
```
📄 TRANSCRIPTS

Les transcripts sont du texte narratif complet
récupéré depuis des sites web spécialisés.

Avantages :
✓ Texte complet (descriptions, contexte)
✓ Récupération automatique
✓ Bon pour analyse linguistique

Inconvénients :
✗ Pas aligné sur la vidéo
✗ Dépendant de la source web
```

**Sous-titres** :
```
📺 SOUS-TITRES (SRT)

Les sous-titres sont des fichiers .srt alignés
précisément sur la vidéo (timestamps).

Avantages :
✓ Alignement précis (timecodes)
✓ Correspond exactement à l'audio
✓ Bon pour synchronisation vidéo

Inconvénients :
✗ Import manuel nécessaire
✗ Texte plus court (contraintes affichage)
```

## 📝 Messages et Labels

### Changements de Terminologie

**Avant** → **Après** :
- "Import" → "SOURCES"
- "Télécharger transcripts" → "Télécharger" (contexte clair)
- "SRT only" → "Ajouter épisodes" (dans colonne Sous-titres)
- "Importer SRT (onglet Sous-titres)" → "Importer SRT" (dans colonne)

### Tooltips Clarifiés

**Transcripts** :
- "Découvrir épisodes : Récupère automatiquement la liste des épisodes depuis la source web configurée"
- "Télécharger : Récupère le texte narratif complet pour les épisodes sélectionnés"

**Sous-titres** :
- "Ajouter épisodes : Créer manuellement la liste des épisodes (ex: S01E01, S01E02...). Nécessaire avant d'importer les SRT"
- "Importer SRT : Importer les fichiers .srt depuis votre ordinateur pour les épisodes sélectionnés"
- "Import batch : Importer automatiquement tous les .srt d'un dossier (détection automatique épisodes)"

## 🧪 Tests Suggérés

### Test 1 : Workflow Sous-titres d'Abord
1. Créer nouveau projet
2. Ignorer section Transcripts
3. Sous-titres → Ajouter 3 épisodes (S01E01, S01E02, S01E03)
4. Importer 3 fichiers .srt
5. Normaliser
6. Vérifier que tout fonctionne sans transcripts

### Test 2 : Workflow Transcripts d'Abord
1. Créer nouveau projet
2. Transcripts → Découvrir + Télécharger
3. Ignorer section Sous-titres
4. Normaliser
5. Vérifier que tout fonctionne sans sous-titres

### Test 3 : Workflow Hybride
1. Créer nouveau projet
2. Transcripts → Découvrir + Télécharger 5 épisodes
3. Sous-titres → Importer SRT pour 3 épisodes seulement
4. Vérifier que chaque épisode gère indépendamment ses sources

## 📊 Comparaison Avant/Après

| Aspect | Avant | Après |
|--------|-------|-------|
| **Position transcripts** | Bloc principal | Colonne gauche (50%) |
| **Position sous-titres** | Mention secondaire | Colonne droite (50%) |
| **Visibilité SRT** | Bouton isolé "SRT only" | Groupe dédié avec icône |
| **Actions sous-titres** | 1 bouton caché | 4 boutons dédiés |
| **Workflow implicite** | Transcripts → SRT | Flexible (les deux égaux) |
| **Clarté** | Confuse | Claire et structurée |

## 🎉 Bénéfices Utilisateurs

### Pour Chercheurs en Sous-titres
✅ Interface claire dès le départ  
✅ Workflow évident (Ajouter → Importer → Normaliser)  
✅ Pas d'impression de "contourner" l'interface

### Pour Chercheurs en Transcripts
✅ Workflow inchangé  
✅ Plus de clarté sur les options disponibles

### Pour Chercheurs Hybrides
✅ Vision d'ensemble des deux sources  
✅ Gestion parallèle évidente  
✅ Alignement facilité

## 🚀 Implémentation Progressive

### Phase 1 : Interface Visuelle (Prioritaire)
- Refonte onglet Corpus (2 colonnes)
- Nouveaux boutons sous-titres
- Tooltips clarifiés

### Phase 2 : Fonctionnalités Sous-titres
- Import batch SRT (dossier entier)
- Détection automatique épisodes depuis noms fichiers
- Status sous-titres par épisode

### Phase 3 : Aide et Documentation
- Dialogue type de corpus au démarrage
- Guides contextuels (?)
- Exemples de workflows dans docs

---

**Auteur** : Cursor AI Assistant  
**Date** : 2026-02-16  
**Type** : Proposition de Refonte UX  
**Status** : ⏳ À Valider par l'Utilisateur

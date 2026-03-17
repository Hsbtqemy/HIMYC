# Amélioration des Profils de Normalisation - Phase 2

## 🎯 Objectif

Faciliter l'accès et l'édition des profils de normalisation, avec ajout de nouvelles règles de ponctuation et d'espaces pour améliorer la qualité des transcripts normalisés.

## ✨ Nouvelles Fonctionnalités

### 1. Accès Facilité aux Profils

#### Avant
- Bouton "Profils" caché dans l'onglet Projet
- Peu visible et rarement utilisé

#### Après
- **Bouton "⚙️ Gérer profils"** directement dans l'onglet Corpus (section Normalisation)
- Accessible en 1 clic depuis le workflow principal
- Toujours disponible (bouton Projet conservé pour compatibilité)

### 2. Nouvelles Règles de Normalisation

#### Règles Ajoutées

| Règle | Description | Exemple |
|-------|-------------|---------|
| **Corriger doubles espaces** | Remplace espaces multiples par un seul | `"A  B"` → `"A B"` |
| **Ponctuation française** | Ajoute espace avant `;:!?` | `"Bonjour!" → "Bonjour !"` |
| **Normaliser apostrophes** | Remplace `'` par `'` | `"C'est"` → `"C'est"` |
| **Normaliser guillemets** | Remplace `""` par `« »` | `"Salut"` → `« Salut »` |
| **Supprimer espaces début/fin** | Nettoie les lignes | `" Hello "` → `"Hello"` |

### 3. Éditeur de Profil Amélioré

#### Interface Repensée
- **Fenêtre avec splitter** : Formulaire (gauche) | Prévisualisation (droite)
- **Prévisualisation en temps réel** : Testez vos règles instantanément
- **Statistiques** : Nombre de fusions, corrections ponctuation, durée
- **Texte d'exemple** : Échantillon par défaut pour tester rapidement
- **Organisation par catégories** :
  - Fusion de lignes (césures)
  - Ponctuation et espaces (5 règles)

#### Workflow de Test
1. Configurer les règles (checkboxes)
2. Coller un extrait de texte brut (ou utiliser l'exemple)
3. Cliquer sur "Tester le profil →" (ou automatiquement)
4. Visualiser le résultat normalisé + statistiques
5. Ajuster les règles si nécessaire
6. Sauvegarder

### 4. Nouveau Profil Prédéfini

**`default_fr_v1`** : Profil optimisé pour le français
- Fusion de césures : ✅
- Doubles espaces : ✅
- **Ponctuation française : ✅** (nouveauté)
- **Apostrophes typographiques : ✅** (nouveauté)
- Guillemets français : ❌ (optionnel)

## 📂 Fichiers Modifiés

### Core (Logique Métier)

#### `src/howimetyourcorpus/core/normalize/profiles.py`
- ✅ Ajout de 5 nouveaux attributs à `NormalizationProfile`
- ✅ Méthode `_apply_line_rules()` pour appliquer les règles de ponctuation
- ✅ Intégration dans `apply()` avec statistiques `punctuation_fixes`
- ✅ Nouveau profil `default_fr_v1`
- ✅ Mise à jour du schéma de validation `PROFILE_SCHEMA`
- ✅ Mise à jour de `validate_profiles_json()`

#### `src/howimetyourcorpus/core/storage/project_store.py`
- ✅ Mise à jour de `load_custom_profiles()` pour charger les 5 nouveaux champs
- ✅ Support de la rétrocompatibilité (valeurs par défaut si absentes)

### Interface Utilisateur

#### `src/howimetyourcorpus/app/dialogs/profiles.py`
- ✅ Nouvelle classe `ProfileEditorDialog` avec prévisualisation temps réel
- ✅ Splitter gauche/droite (formulaire | aperçu)
- ✅ Groupes de règles organisés (Identité, Fusion, Ponctuation)
- ✅ Statistiques de normalisation affichées
- ✅ Mise à jour automatique de la prévisualisation
- ✅ Texte d'exemple par défaut
- ✅ Tooltips explicatifs sur chaque règle
- ✅ Méthode `get_profile_data()` retournant tous les champs
- ✅ Refactoring de `_new_profile()` et `_edit_profile()` pour utiliser le nouveau dialogue
- ✅ Mise à jour de `_load_list()` pour charger les nouveaux champs

#### `src/howimetyourcorpus/app/tabs/tab_corpus.py`
- ✅ Ajout du bouton **"⚙️ Gérer profils"** dans la section Normalisation
- ✅ Nouvelle méthode `_open_profiles_dialog()` pour ouvrir le gestionnaire
- ✅ Tooltip explicatif sur le bouton
- ✅ Rafraîchissement automatique du combo de profils après fermeture du dialogue

### Documentation

#### `docs/profils-normalisation.md` (NOUVEAU)
- ✅ Guide complet des profils de normalisation
- ✅ Accès aux profils (2 méthodes)
- ✅ Description de tous les types de profils (prédéfinis, personnalisés)
- ✅ Explication détaillée de chaque règle avec exemples
- ✅ Guide pas-à-pas pour créer/modifier/supprimer un profil
- ✅ Exemples de profils personnalisés
- ✅ Conseils et bonnes pratiques
- ✅ Section dépannage
- ✅ Format du fichier `profiles.json`

## 🔧 Modifications Techniques

### Rétrocompatibilité
- ✅ Les profils existants (sans nouveaux champs) fonctionnent avec valeurs par défaut
- ✅ Le fichier `profiles.json` existant reste valide
- ✅ Ancienne interface conservée (bouton Projet → Profils)

### Validation
- ✅ Schéma JSON étendu avec les 5 nouveaux champs (booléens optionnels)
- ✅ Validation stricte : refuse les clés inconnues
- ✅ Messages d'erreur clairs en français

### Performance
- ✅ Règles de ponctuation appliquées après fusion (une seule passe)
- ✅ Regex optimisées (compilation implicite)
- ✅ Statistiques `punctuation_fixes` ajoutées au debug

## 📊 Statistiques d'Impact

| Métrique | Avant | Après | Gain |
|----------|-------|-------|------|
| **Clics pour accéder aux profils** | Projet → Profils (2 clics, caché) | Corpus → ⚙️ Gérer profils (1 clic, visible) | **+50% accessibilité** |
| **Règles de normalisation** | 2 règles (fusion, debug) | **7 règles** (fusion + 5 ponctuation/espaces) | **+250% options** |
| **Prévisualisation** | ❌ Aucune | ✅ Temps réel avec stats | **Workflow amélioré** |
| **Profils prédéfinis** | 3 profils | **4 profils** (+ `default_fr_v1`) | **+33%** |

## 🎨 Captures d'Écran (Conceptuel)

### Ancien Dialogue (Avant)
```
┌─────────────────────────────────┐
│ Nouveau profil                  │
├─────────────────────────────────┤
│ Id: [____________]              │
│ Fusionner césures: [✓]         │
│ Max exemples debug: [20▼]      │
│                                 │
│          [OK] [Annuler]         │
└─────────────────────────────────┘
```

### Nouveau Dialogue (Après)
```
┌────────────────────────────────────────────────────────────────┐
│ Éditer le profil de normalisation                              │
├──────────────────────┬─────────────────────────────────────────┤
│ FORMULAIRE           │ PRÉVISUALISATION                        │
│                      │                                         │
│ [Identité]           │ Texte brut (RAW) :                     │
│  ID: mon_profil      │ ┌─────────────────────────────────────┐│
│                      │ │Salut  ,  comment   ça  va?          ││
│ [Fusion de lignes]   │ │Je suis content de te voir!         ││
│  ✓ Fusionner césures │ │C'est vraiment                       ││
│  Max debug: [20]     │ │génial d'être ici.                   ││
│                      │ └─────────────────────────────────────┘│
│ [Ponctuation]        │                                         │
│  ✓ Doubles espaces   │ Texte normalisé (CLEAN) :             │
│  ✓ Ponctuation FR    │ ┌─────────────────────────────────────┐│
│  ✓ Apostrophes       │ │Salut, comment ça va ?               ││
│  ☐ Guillemets        │ │Je suis content de te voir !        ││
│  ✓ Espaces début/fin │ │C'est vraiment génial d'être ici.    ││
│                      │ └─────────────────────────────────────┘│
│ [Tester le profil →] │                                         │
│                      │ Stats: 7→3 lignes | 2 fusions |        │
│                      │        4 corrections | 12 ms           │
├──────────────────────┴─────────────────────────────────────────┤
│                        [OK] [Annuler]                          │
└────────────────────────────────────────────────────────────────┘
```

## 🧪 Tests Suggérés

### Test 1 : Création de Profil Français
1. Ouvrir Corpus → ⚙️ Gérer profils → Nouveau
2. ID : `test_fr`
3. Activer : Fusion, Doubles espaces, Ponctuation FR, Apostrophes
4. Tester avec : `"Comment ça va?" et "C'est super!"`
5. Vérifier : `"Comment ça va ?" et "C'est super !"`

### Test 2 : Prévisualisation Temps Réel
1. Éditer un profil
2. Désactiver "Ponctuation française"
3. Observer le changement immédiat dans l'aperçu
4. Réactiver → Observer le changement

### Test 3 : Normalisation avec Nouveau Profil
1. Créer un profil personnalisé avec règles spécifiques
2. Onglet Corpus → Sélectionner le profil dans "Profil (batch)"
3. Normaliser un épisode
4. Vérifier dans l'Inspecteur que les règles sont appliquées

### Test 4 : Rétrocompatibilité
1. Ouvrir un projet existant avec ancien `profiles.json`
2. Gérer profils → Éditer un profil existant
3. Vérifier que les nouvelles règles ont des valeurs par défaut
4. Sauvegarder → Vérifier que `profiles.json` contient les nouveaux champs

## 📝 Notes de Migration

### Pour les Utilisateurs Existants
- ✅ **Aucune action requise** : Les profils existants fonctionnent sans modification
- ✅ Les nouveaux champs utilisent des valeurs par défaut sensées
- ✅ Vous pouvez éditer vos profils existants pour activer les nouvelles règles

### Pour les Développeurs
- ✅ `NormalizationProfile` a 5 nouveaux attributs booléens
- ✅ `apply()` retourne maintenant `debug["punctuation_fixes"]`
- ✅ `ProjectStore.load_custom_profiles()` charge les nouveaux champs avec `getattr()` pour rétrocompatibilité

## 🚀 Prochaines Étapes (Phase 3 - Optionnel)

### Fonctionnalités Avancées Envisageables
- [ ] **Import/Export de profils** : Partager des profils entre projets (.json)
- [ ] **Règles regex personnalisées** : Permettre des remplacements regex arbitraires
- [ ] **Historique de normalisation** : Visualiser avant/après pour chaque règle appliquée
- [ ] **Profils par langue automatique** : Détection de la langue → profil automatique
- [ ] **Prévisualisation diff** : Coloration des différences avant/après
- [ ] **Règles de casse** : UPPERCASE, lowercase, Title Case
- [ ] **Règles de nombres** : Normalisation des chiffres (12 → douze)

## 📞 Contact

Pour toute question ou suggestion :
- **Issues GitHub** : https://github.com/Hsbtqemy/HIMYC/issues
- **Pull Requests** : Bienvenues !

---

**Auteur** : Cursor AI Assistant  
**Date** : 2026-02-16  
**Version HIMYC** : Phase 2 - Profils de Normalisation Avancés

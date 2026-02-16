# Guide des Profils de Normalisation

## 📋 Vue d'ensemble

Les **profils de normalisation** permettent de contrôler finement comment les transcripts bruts (RAW) sont transformés en textes nettoyés (CLEAN). Chaque profil définit un ensemble de règles appliquées automatiquement lors de la normalisation.

## 🚀 Accès aux Profils

### Méthode 1 : Via l'Onglet Corpus (Recommandé)
1. Ouvrez l'onglet **Corpus**
2. Dans la section **"2. Normalisation / segmentation"**
3. Cliquez sur le bouton **⚙️ Gérer profils** (à côté de la liste déroulante "Profil (batch)")

### Méthode 2 : Via l'Onglet Projet
1. Ouvrez l'onglet **Projet**
2. Cliquez sur le bouton **Profils** dans la section Configuration

## 📂 Types de Profils

### Profils Prédéfinis (Lecture Seule)
Ces profils sont fournis avec HIMYC et ne peuvent pas être modifiés :

- **`default_en_v1`** : Profil par défaut pour l'anglais
  - Fusion des césures sous-titres
  - Correction des doubles espaces
  - Pas de règles de ponctuation française

- **`default_fr_v1`** : Profil par défaut pour le français
  - Fusion des césures sous-titres
  - Correction des doubles espaces
  - **Ponctuation française activée** (espaces avant `;:!?`)
  - **Normalisation apostrophes** (' → ')

- **`conservative_v1`** : Profil conservateur
  - Fusion activée avec peu d'exemples debug (10)
  - Corrections minimales

- **`aggressive_v1`** : Profil agressif
  - Fusion activée avec beaucoup d'exemples debug (30)
  - Corrections standards

### Profils Personnalisés (Éditables)
Vous pouvez créer vos propres profils adaptés à vos besoins spécifiques.

## ✨ Règles Disponibles

### 🔀 Fusion de Lignes (Césures Sous-Titres)

#### **Fusionner césures**
- **Description** : Fusionne les lignes coupées en milieu de phrase (typique des sous-titres)
- **Exemple** :
  ```
  AVANT (RAW) :
  Je suis content
  de te voir aujourd'hui.
  
  APRÈS (CLEAN) :
  Je suis content de te voir aujourd'hui.
  ```
- **Recommandé** : Toujours activé pour les transcripts de sous-titres

#### **Max exemples debug**
- **Description** : Nombre d'exemples de fusion conservés dans les logs de débogage
- **Valeur** : 0-100 (défaut: 20)

---

### 📝 Ponctuation et Espaces

#### **Corriger doubles espaces**
- **Description** : Remplace les espaces multiples consécutifs par un seul espace
- **Exemple** :
  ```
  AVANT : "Salut  ,  comment   ça  va ?"
  APRÈS : "Salut , comment ça va ?"
  ```
- **Recommandé** : Toujours activé

#### **Ponctuation française**
- **Description** : Ajoute un espace insécable avant `;:!?` (règle typographique française)
- **Exemple** :
  ```
  AVANT : "Comment ça va? Très bien!"
  APRÈS : "Comment ça va ? Très bien !"
  ```
- **Recommandé** : Activé pour les transcripts en français, désactivé pour l'anglais

#### **Normaliser apostrophes (' → ')**
- **Description** : Remplace les apostrophes droites par des apostrophes typographiques
- **Exemple** :
  ```
  AVANT : "C'est l'heure"
  APRÈS : "C'est l'heure"
  ```
- **Recommandé** : Activé pour une typographie soignée (français)

#### **Normaliser guillemets (" → « »)**
- **Description** : Remplace les guillemets droits par des guillemets français
- **Exemple** :
  ```
  AVANT : "Bonjour" dit-il
  APRÈS : « Bonjour » dit-il
  ```
- **Recommandé** : Activé pour les transcripts en français nécessitant une typographie stricte

#### **Supprimer espaces début/fin**
- **Description** : Supprime les espaces en début et fin de chaque ligne
- **Recommandé** : Toujours activé

## 🛠️ Créer un Profil Personnalisé

### Étape 1 : Ouvrir le Gestionnaire
1. Cliquez sur **⚙️ Gérer profils** (onglet Corpus)
2. Cliquez sur **Nouveau**

### Étape 2 : Configurer les Règles
1. **ID du profil** : Choisissez un nom unique (ex: `mon_profil_fr_strict`)
2. **Cochez les règles** souhaitées selon vos besoins
3. **Testez le profil** en temps réel :
   - Collez un extrait de texte dans le panneau "Texte brut (RAW)"
   - Cliquez sur **Tester le profil →**
   - Visualisez le résultat dans "Texte normalisé (CLEAN)"
   - Consultez les statistiques (fusions, corrections, durée)

### Étape 3 : Sauvegarder
1. Cliquez sur **OK** pour créer le profil
2. Le profil est immédiatement disponible dans les listes déroulantes

## 📋 Exemples de Profils Personnalisés

### Profil pour Transcripts Français Stricts
```
ID: francais_strict_v1
Règles activées :
✅ Fusionner césures
✅ Corriger doubles espaces
✅ Ponctuation française
✅ Normaliser apostrophes
✅ Normaliser guillemets
✅ Supprimer espaces début/fin
```

### Profil pour Transcripts Anglais Minimalistes
```
ID: english_minimal_v1
Règles activées :
✅ Fusionner césures
✅ Corriger doubles espaces
❌ Ponctuation française
❌ Normaliser apostrophes
❌ Normaliser guillemets
✅ Supprimer espaces début/fin
```

### Profil "Brut" (Aucune Transformation)
```
ID: raw_passthrough_v1
Règles activées :
❌ Fusionner césures
❌ Corriger doubles espaces
❌ Ponctuation française
❌ Normaliser apostrophes
❌ Normaliser guillemets
❌ Supprimer espaces début/fin
```
*Utile pour conserver le texte exact tel quel*

## 🔧 Modifier un Profil Existant

1. Ouvrez le gestionnaire de profils
2. Sélectionnez un profil **personnalisé** dans la liste
3. Cliquez sur **Modifier**
4. Ajustez les règles et testez en temps réel
5. Cliquez sur **OK** pour sauvegarder

**Note** : Les profils prédéfinis ne peuvent pas être modifiés. Créez plutôt un profil personnalisé basé sur un prédéfini.

## 🗑️ Supprimer un Profil

1. Sélectionnez le profil personnalisé à supprimer
2. Cliquez sur **Supprimer**
3. Confirmez la suppression

## 📖 Utilisation des Profils

### Normalisation par Lot (Corpus)
1. Onglet **Corpus** → Section "2. Normalisation / segmentation"
2. Sélectionnez un profil dans **"Profil (batch)"**
3. Cliquez sur **Normaliser sélection** ou **Normaliser tout**

**Priorité des profils** (du plus prioritaire au moins prioritaire) :
1. **Profil préféré de l'épisode** (défini dans l'Inspecteur)
2. **Profil par défaut de la source** (défini dans Profils → table source→profil)
3. **Profil batch** (sélectionné dans le combo "Profil (batch)")

### Normalisation Individuelle (Inspecteur)
1. Onglet **Inspecteur** → Sélectionnez un épisode
2. Choisissez un profil dans la liste déroulante
3. Cliquez sur **Normaliser** pour cet épisode uniquement

### Profil par Défaut par Source
Vous pouvez définir un profil par défaut pour chaque source de transcripts :

1. Ouvrez le gestionnaire de profils
2. En bas, section **"Profil par défaut par source"**
3. Cliquez sur **Ajouter lien source→profil**
4. Choisissez :
   - **Source** : `subslikescript`, etc.
   - **Profil** : Le profil à appliquer par défaut
5. Fermez le dialogue (sauvegarde automatique)

## 💡 Conseils et Bonnes Pratiques

### Pour les Transcripts en Français
✅ Utilisez `default_fr_v1` ou créez un profil avec :
- Ponctuation française activée
- Normalisation apostrophes activée
- Normalisation guillemets (optionnel, selon le besoin)

### Pour les Transcripts en Anglais
✅ Utilisez `default_en_v1` ou créez un profil avec :
- Ponctuation française **désactivée**
- Normalisation apostrophes **désactivée**

### Pour les Corpus Multilingues
✅ Créez un profil par langue (ex: `mon_projet_fr`, `mon_projet_en`)
✅ Utilisez la table **"Profil par défaut par source"** pour associer automatiquement

### Tester Avant de Normaliser en Masse
✅ Toujours tester un profil sur un échantillon (prévisualisation) avant de normaliser tout le corpus
✅ Normalisez d'abord un épisode dans l'Inspecteur pour vérifier le résultat

### Éviter les Conflits
⚠️ Ne créez pas deux profils avec le même ID
⚠️ Ne supprimez pas un profil utilisé comme "profil préféré" dans des épisodes

## 🔍 Dépannage

### Le bouton "Modifier" est grisé
➡️ Vous avez sélectionné un profil prédéfini. Seuls les profils personnalisés peuvent être modifiés.

### Mes règles ne s'appliquent pas
➡️ Vérifiez la **priorité des profils** (préféré épisode > défaut source > batch)
➡️ Re-normalisez l'épisode après avoir modifié le profil

### Erreur "Fichier profiles.json invalide"
➡️ Le fichier JSON des profils personnalisés est corrompu
➡️ Ouvrez `<projet>/profiles.json` et corrigez la syntaxe
➡️ Ou supprimez le fichier pour réinitialiser (perte des profils personnalisés)

### Les statistiques ne s'affichent pas
➡️ Assurez-vous d'avoir collé du texte dans la zone de prévisualisation
➡️ Cliquez sur "Tester le profil →" pour relancer

## 📁 Stockage des Profils

### Profils Prédéfinis
📂 Intégrés dans le code source de HIMYC (`core/normalize/profiles.py`)

### Profils Personnalisés
📂 Fichier `profiles.json` à la racine du projet
```
<mon_projet>/
├── config.toml
├── profiles.json  ← Profils personnalisés
├── corpus.db
└── ...
```

Format du fichier `profiles.json` :
```json
{
  "profiles": [
    {
      "id": "mon_profil_fr",
      "merge_subtitle_breaks": true,
      "max_merge_examples_in_debug": 20,
      "fix_double_spaces": true,
      "fix_french_punctuation": true,
      "normalize_apostrophes": true,
      "normalize_quotes": false,
      "strip_line_spaces": true
    }
  ]
}
```

## 🆘 Support

Pour toute question ou suggestion sur les profils de normalisation :
- Ouvrez une issue sur GitHub : https://github.com/Hsbtqemy/HIMYC/issues
- Consultez la documentation principale : `README.md`

---

**Version du guide** : 1.0 (Phase 2 - Règles de ponctuation et espaces)

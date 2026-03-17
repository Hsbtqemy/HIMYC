# Scénario : Onglet Préparer un fichier + Personnages série + Normalisation explicite

**Date** : 2026-02-23  
**Statut** : Discussion / spécification (aucune modification de code pour l’instant).

---

## 1. Profil de normalisation plus explicite

### Constat

Aujourd’hui les profils (JSON) contiennent déjà des options booléennes : `merge_subtitle_breaks`, `fix_double_spaces`, `fix_french_punctuation`, `normalize_apostrophes`, `normalize_quotes`, `strip_line_spaces`, `case_transform`, `custom_regex_rules`. Mais dans l’UI (Corpus, Inspecteur) on choisit surtout un **profil par nom** sans voir clairement **ce qui sera appliqué**.

### Objectif

- Le profil de normalisation doit être **explicite** : l’utilisateur voit et **choisit** les éléments concernés par la normalisation.
- Idéalement : une interface (dans l’onglet Préparer ou dans un dialogue dédié) où chaque règle est une **option cochable** avec une courte explication, par exemple :
  - Fusion des césures de sous-titres (lignes courtes fusionnées)
  - Espaces doubles → simple
  - Ponctuation française (espaces avant : ; ! ?)
  - Apostrophes typographiques
  - Guillemets typographiques
  - Espaces en début/fin de ligne
  - Casse (aucune / minuscules / majuscules / Titre / Phrase)
  - Règles regex personnalisées (liste éditable)
- On peut conserver des **présets** (ex. « SRT léger », « Transcript strict ») qui pré-cochent un sous-ensemble, tout en permettant de modifier les cases avant d’appliquer.
- **Où** : dans l’onglet « Préparer un fichier » au moment du nettoyage ; éventuellement aussi dans Corpus/Inspecteur pour cohérence.

---

## 2. Personnages : base série (recherche, corpus par personnage)

### Évolution proposée

L’onglet Personnages ne se limite plus à « assignation par épisode » : il devient une **base de personnages pour toute la série**, avec :

- **Liste des personnages** (déjà en place) : id, canonique, noms par langue, utilisée pour l’assignation et la propagation.
- **Recherche / sélection dans le corpus** : pouvoir interroger « toutes les prises de parole d’un personnage X sur toute la série » (ou par saison, par épisode). Cela suppose :
  - que les assignations et/ou `speaker_explicit` soient indexés (déjà en base : segments.speaker_explicit, character_assignments, cues avec préfixe « Nom : » après propagation) ;
  - une **vue ou un filtre** : choix d’un personnage → affichage des segments/cues où ce personnage parle (liste, export, ou lien vers le concordancier / l’Inspecteur avec filtre).
- **Recherche** : recherche texte parmi les répliques d’un personnage (ex. tous les segments où Marshall dit « … »).

### Implémentation possible

- Requêtes : par personnage (id ou nom canonique), récupérer les `segment_id` / `cue_id` concernés (depuis assignations + speaker_explicit + liens alignement si besoin).
- UI : dans l’onglet Personnages, une section « Corpus par personnage » : combo ou liste personnage → bouton « Voir toutes les prises de parole » → ouverture d’une liste / table (épisode, type segment/cue, extrait de texte, lien vers l’épisode) ou redirection vers le concordancier avec filtre speaker = ce personnage.
- Pas de changement du modèle de données fondamental : on s’appuie sur les tables existantes (segments, cues, character_assignments) et on ajoute des vues ou requêtes dédiées.

---

## 3. Timecodes des sous-titres

### Où ils sont aujourd’hui

- En base : `subtitle_cues` a `start_ms`, `end_ms` par cue. Ils ne sont **pas** dans le corps du texte ; le texte affiché/édité est `text_raw` / `text_clean`.
- À l’import SRT : les timecodes sont parsés et stockés dans la cue.
- À l’export SRT : on régénère les blocs `n`, `start_ms --> end_ms`, `text`.
- Alignement : `align_cues_by_time` utilise les timecodes pour apparier des cues de langues différentes ; si timecodes absents ou peu fiables, on bascule sur similarité ou ordre.

### Dans l’onglet « Préparer un fichier » (piste SRT)

- **Affichage** : pour chaque réplique (tour / cue), afficher en plus du texte les timecodes (ex. colonnes « Début », « Fin » ou une colonne « Timecode » en `HH:MM:SS,mmm --> HH:MM:SS,mmm`). Cela permet de vérifier la cohérence sans quitter l’édition.
- **Édition** : selon le niveau de fonctionnalité qu’on vise :
  - **Option minimale** : pas d’édition des timecodes dans le prep ; on édite le texte et les personnages, les timecodes restent ceux importés (sauf si on ré-importe un SRT modifié ailleurs).
  - **Option complète** : champs éditables pour `start_ms` / `end_ms` (ou timecode affiché en lecture seule), avec validation (début < fin, ordre des cues). Utile pour corriger des SRT mal timecodés.
- **Statut** : si on introduit un statut « édité/vérifié à la main » (voir §4), les timecodes peuvent être marqués comme « non modifiés depuis l’import » vs « modifiés manuellement » pour traçabilité.

---

## 4. Statut « édité / vérifié à la main » et maîtrise du statut

### Besoin

- Signaler qu’un contenu (segment, cue, ou fichier entier) a été **édité ou vérifié à la main**, pour distinguer du contenu brut ou uniquement normalisé automatiquement.
- Avoir **la main sur le statut** : l’utilisateur peut le changer (ex. « brut » → « vérifié », « vérifié » → « à revoir »).

### Proposition

- **Niveau d’granularité** : au choix selon la complexité :
  - **Par fichier / piste** : un statut par (épisode, type de source : transcript vs SRT EN/FR/IT), ex. `raw | normalized | verified`.
  - **Par segment / cue** : un champ `status` ou `verification_status` sur chaque segment et chaque cue (ex. `auto`, `edited`, `verified`). Plus fin mais plus lourd en UI et en persistance.
- **Valeurs possibles** (à affiner) : par ex. `raw`, `normalized`, `edited`, `verified`, `to_review`. Par défaut après import : `raw` ; après normalisation : `normalized` ; après édition manuelle : `edited` ou `verified`.
- **UI** : dans l’onglet Préparer (et éventuellement Inspecteur), un indicateur + un moyen de changer le statut (liste déroulante ou boutons). Si on part sur un statut par « fichier » (piste), un seul sélecteur en haut de la vue préparation ; si par segment/cue, une colonne « Statut » dans la table des tours.
- **Impact** : filtres possibles dans le concordancier ou les exports (ex. « n’afficher que les lignes vérifiées ») ; rapports (combien de segments encore en `raw` par épisode).

---

## 5. Points déjà tranchés

1. **Choix de la source à préparer** : il faut pouvoir **choisir** ce sur quoi on travaille en premier. Parfois le transcript est très mauvais → partir du **sous-titre** est plus simple ; parfois le transcript fait référence → partir du **transcript**. Donc l’onglet « Préparer un fichier » doit proposer explicitement : **Fichier = Transcript** ou **SRT EN** / **SRT FR** / **SRT IT**. Un seul fichier actif à la fois par épisode.

2. **Édition tour par tour** : à discuter encore (grille éditable vs vue lecture + édition ponctuelle). On peut trancher après un premier prototype.

3. **Synchronisation avec l’Inspecteur** : oui. Introduction d’un **statut** (édité/vérifié, etc.) et possibilité pour l’utilisateur de **changer le statut** comme il le souhaite (voir §4).

4. **Place de l’onglet** : **entre Inspecteur et Alignement** dans la barre d’onglets, pour marquer la séquence : préparer → aligner → propager / concordancier.

5. **Alignement** : quand la source a été préparée en **tours** (avec personnages, etc.), on lance l’alignement en choisissant **Segments : Tours** ; la propagation des personnages s’appuie sur le run comme aujourd’hui. Pas de changement de fond sur le moteur d’alignement.

---

## 6. Scénario utilisateur (parcours type)

### Contexte

- Projet HIMYC avec une série ; épisodes découverts, transcripts et/ou SRT importés.
- L’utilisateur veut aligner transcript ↔ SRT et avoir les personnages bien assignés pour la recherche et les exports.

### Parcours A : Transcript comme référence (« vérité »)

1. **Ouvrir l’onglet « Préparer un fichier »** (nouvel onglet entre Inspecteur et Alignement).
2. **Choisir l’épisode** (ex. S01E01) et **Fichier = Transcript**.
3. **Voir le contenu** : texte brut ou déjà segmenté en tours (selon état actuel). Si besoin, **recherche / remplacement** global (ex. remplacer des abréviations, uniformiser des noms).
4. **Profil de normalisation explicite** : clic sur « Nettoyer / Normaliser » → ouverture d’un panneau ou dialogue listant **toutes les options** (fusion césures, espaces doubles, apostrophes, guillemets, ponctuation française, casse, regex custom). L’utilisateur **coche** les règles à appliquer (ou choisit un préréglage puis ajuste). Aperçu ou diff si possible, puis **Appliquer**. Le statut du transcript pour cet épisode passe à `normalized` (ou `edited` si réglages manuels).
5. **Segmentation en tours** : lancer « Segmenter en tours de parole » (découpage par ligne + détection « Nom : »). La liste des tours s’affiche (Personnage | Texte), avec possibilité de **corriger** le nom du personnage (combo depuis la base personnages série) et le texte. Option : marquer le statut de l’épisode ou des tours en `edited` / `verified`.
6. **Enregistrer** : les segments (utterances) et `speaker_explicit` sont mis à jour en base ; l’Inspecteur reflète aussitôt les changements.
7. **Aller à l’onglet Alignement** : même épisode, **Segment = Tours de parole**, **Lancer alignement**. Le run créé lie les tours du transcript aux cues (pivot puis cibles).
8. **Personnages** : ouvrir l’onglet Personnages, choisir l’épisode et le run (tours), éventuellement compléter des assignations manquantes, puis **Propager** (avec choix des langues SRT à réécrire). Les noms apparaissent dans les SRT et dans le concordancier.
9. **Recherche série** : dans Personnages, choisir un personnage → « Voir toutes les prises de parole » → liste ou concordancier filtré sur ce personnage pour toute la série (ou par saison).

### Parcours B : SRT comme point de départ (transcript trop mauvais)

1. **Préparer un fichier** : épisode S01E01, **Fichier = SRT FR** (ou EN).
2. **Contenu** : liste des répliques (cues) avec **timecodes** visibles (Début / Fin ou timecode SRT). Option : **normalisation explicite** (même principe que pour le transcript : choix des règles à appliquer sur `text_clean`).
3. **Assignation personnages** : pour chaque réplique, choisir le personnage dans la liste (base série). Si les noms sont déjà en préfixe « Nom : » après import, les pré-remplir ; sinon saisie manuelle. **Enregistrer** : les cues sont mises à jour (text_clean avec préfixe, ou table d’assignation cue → personnage).
4. **Statut** : marquer la piste comme `edited` ou `verified` si tout a été vérifié.
5. **Alignement** : en amont il faut malgré tout des **segments** côté transcript pour les liens segment ↔ cue (ou alors on envisage un mode « alignement cue ↔ cue » seulement, sans transcript — à préciser). Si le transcript existe mais est mauvais, on peut :
   - soit le segmenter minimalement (phrases ou tours) et aligner quand même, en sachant que la « vérité » pour l’affichage sera plutôt la piste SRT préparée ;
   - soit considérer la piste SRT comme pivot et aligner les autres pistes SRT dessus (déjà partiellement possible).  
   La décision « alignement sans transcript » vs « transcript minimal » reste à trancher selon les cas d’usage.

### Parcours C : Personnages comme hub de recherche

1. **Onglet Personnages** : la liste des personnages de la série est à jour (création manuelle ou import depuis les segments).
2. **Sélectionner un personnage** (ex. « Marshall »).
3. **Action « Voir toutes les prises de parole »** (ou « Recherche dans le corpus ») : requête sur toute la série (segments avec speaker_explicit = Marshall + assignations segment/cue → Marshall). Résultat : liste (épisode, type, extrait, lien) ou **ouverture du concordancier** avec filtre speaker = Marshall.
4. **Recherche texte** (optionnel) : champ « Rechercher dans les répliques de ce personnage » → filtre supplémentaire sur le texte (LIKE ou FTS).

---

## 7. Résumé des briques à développer (sans ordre d’implémentation)

| Brique | Description courte |
|--------|--------------------|
| **Profil normalisation explicite** | UI (cases à cocher / options) pour choisir les règles de normalisation à appliquer, avec présets optionnels. |
| **Onglet « Préparer un fichier »** | Contexte épisode + choix du fichier (Transcript ou SRT). Zone contenu, recherche/remplacement, normalisation (profil explicite), segmentation tours, édition tours (personnage + texte), timecodes visibles (SRT), statut édité/vérifié. Enregistrement en base, lien vers Alignement. |
| **Personnages : base série** | Requêtes « toutes les prises de parole d’un personnage » (série / saison / épisode). UI : section « Corpus par personnage » avec liste ou lien vers concordancier filtré. |
| **Statut éditable** | Champ statut (raw / normalized / edited / verified / to_review) sur la source préparée (ou par segment/cue). UI pour afficher et **changer** ce statut. |
| **Timecodes en vue préparation** | Affichage (et optionnellement édition) des timecodes des cues dans l’onglet Préparer quand la source est une piste SRT. |

---

## 8. Suite

- On peut détailler une **première version minimale** (ex. onglet Préparer avec transcript uniquement, normalisation explicite, segmentation tours, assignation personnages, sans statut ni timecodes) puis ajouter SRT, statut, timecodes et « corpus par personnage » par itérations.
- Ou prioriser une brique précise (ex. profil explicite partout, ou Personnages série) avant de toucher à l’onglet Préparer.

Ce document sert de référence pour la discussion et pour décider par quoi commencer.

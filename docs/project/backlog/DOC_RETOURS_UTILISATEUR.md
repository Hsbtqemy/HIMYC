# Retours utilisateur — Synthèse et corrections (2026-02-23)

## 1. Pivot et comparaison transcript EN ↔ SRT FR

**Retour** : Le jeu de comparaison est surtout entre transcript EN et sous-titres FR ; le pivot ne devrait pas être obligatoire ; l’essentiel est le transcript nettoyé, normalisé et segmenté.

**Corrections** :
- Si aucune piste pour la langue pivot (défaut EN), l’alignement utilise automatiquement la **première langue cible** qui a des cues (ex. FR). Comparaison **transcript EN ↔ SRT FR** sans piste EN possible.
- Le run est créé avec `pivot_lang` = langue effectivement utilisée (ex. `fr`). Le concordancier parallèle et la table d’alignement affichent correctement le texte (segment + colonne FR).

---

## 2. Suppression des runs et réalignement

**Retour** : Impossible de supprimer les runs ; à la réalignement, les éléments après la ligne réalignée n’étaient pas réorganisés (segment 1 aligné avec segment 45, etc.).

**Corrections** :
- **Suppression** : Si aucun run n’est sélectionné dans la liste « Run », un message indique : « Aucun run sélectionné. Choisissez un run dans la liste déroulante « Run ». » Le bouton « Supprimer ce run » n’est actif que lorsqu’un run est sélectionné.
- **Ordre** : Contrainte **monotone** dans `align_segments_to_cues` : un segment ne peut s’aligner qu’à une cue d’index ≥ dernière cue déjà utilisée. Les liens restent ordonnés (plus de croisement du type segment 1 ↔ cue 45).

---

## 3. Affichage des segments dans l’onglet Alignement

**Retour** : La segmentation des phrases ne s’affichait pas tout le temps dans l’onglet Alignement.

**Clarification** :
- La table affiche les **liens** d’alignement ; les colonnes « Segment » et « Cue pivot » sont remplies à partir de la DB (segments + cues). Si la langue pivot effective est FR, la colonne Cue pivot affiche le texte des cues FR.
- Workflow : **Segmente l’épisode** (Inspecteur) → **Lancer alignement** (Alignement) → choisir le run créé. Si les segments viennent d’être recalculés, créer un **nouveau** run (ou supprimer l’ancien puis relancer) pour que les liens correspondent aux segments actuels.

---

## 4. Normalisation SRT et timecodes

**Retour** : Difficile de comprendre ce que fait la normalisation ; souhaiter garder le timecode comme donnée supplémentaire, pas dans le corps du texte.

**Clarification** :
- **Normaliser la piste** : applique le **même profil** que pour les transcripts (césures, espaces, apostrophes, guillemets, etc.) à chaque réplique (`text_raw` → `text_clean`). Le but est d’uniformiser le texte pour l’alignement et les exports.
- **Timecodes** : ils ne sont **jamais** dans le corps du texte. Ils restent en métadonnées (`start_ms`, `end_ms`) en base et à l’export SRT. Une évolution possible : afficher start/end en colonne(s) dédiée(s) dans l’éditeur de piste.

---

## 5. Personnages : extraction depuis SRT et propagation

**Retour** : On pensait pouvoir retirer les noms des personnages depuis les SRT ; ce qui sortait de l’import des personnages, c’étaient des bouts de phrases sans rapport. La propagation ne semblait pas fonctionner ; où sont les exports ; le nom du personnage n’apparaît pas après sur les textes.

**Clarification** :
- **Importer depuis les segments** : récupère uniquement les **noms de locuteurs** détectés dans le **transcript** segmenté (lignes du type « Marshall : », « Ted : »). Les SRT n’ont en général pas ce format (pas de préfixe "Name :" par réplique) ; il n’y a pas d’extraction automatique de noms depuis le texte des cues.
- **Assignation** : Pour les cues SRT, il faut **assigner à la main** : Personnages → Épisode → Source « Cues FR » (ou EN/IT) → Charger → assigner un personnage à chaque ligne → Enregistrer assignations.
- **Propagation** : Utilise les **liens d’alignement** (segment ↔ cue pivot ↔ cue cible) pour copier le personnage assigné (sur segment ou cue pivot) vers les cues alignées. Elle met à jour `text_clean` avec le préfixe « Name: » et **réécrit les fichiers SRT**. Prérequis : au moins un **run d’alignement** pour l’épisode.
- **Exports** : Le nom du personnage apparaît dans tout ce qui utilise `text_clean` : **export SRT** de la piste (Inspecteur), **concordancier parallèle** (export CSV/TSV/HTML, etc.) après propagation.

---

## 6. Reprise après erreur et micro-édition

**Retour** : Reprise après erreur compliquée ; on ne sait pas où aller ; est-ce qu’il faut tout réimporter / sauvegarder pour une micro-édition ?

**Clarification** :
- Pour une **micro-édition** (corriger une piste, une réplique) : éditer dans l’Inspecteur (piste SRT) puis **Enregistrer**. Pas besoin de tout réimporter. En revanche, les **runs d’alignement** existants ne sont pas invalidés automatiquement ; en cas de changement important sur les cues, supprimer les runs concernés et relancer l’alignement.
- Amélioration prévue : proposer d’invalider (ou recréer) les runs quand une piste de l’épisode est modifiée ou supprimée.

---

## 7. Prise de parole et personnages

**Retour** : La prise de parole semble une meilleure piste ; il faudrait pouvoir spécifier les personnages ; l’onglet Personnages n’est pas facile à prendre en main ; la propagation ne semble pas fonctionner ; où sont les exports ; le nom du personnage n’apparaît pas après.

**Résumé** :
- Workflow Personnages : 1) Définir la liste (Nouveau / Importer depuis les segments pour le transcript). 2) Par épisode : Charger (Segments ou Cues EN/FR/IT), assigner, Enregistrer assignations. 3) Propager (nécessite un run d’alignement pour cet épisode).
- Les exports (concordancier, SRT final) incluent le texte avec préfixe personnage **après** propagation. Si la propagation n’a pas été lancée ou a échoué (ex. pas de run), les noms n’apparaîtront pas.
- Pistes d’amélioration : UX de l’onglet Personnages (workflow guidé, aide contextuelle), vérification des conditions de propagation, colonne « personnage » explicite dans les exports.

---

Voir aussi **DOC_SOUS_TITRES_REFLEXION.md** pour les pistes d’amélioration (reprises, normalisation par lot, timecodes en colonne, etc.).

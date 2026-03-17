# Plan : Onglet Personnages et prises de parole

**Date** : 2026-02-23  
**Contexte** : Clarifier le rôle de l’onglet Personnages, les options d’évolution (source d’assignation, propagation, segment vs tour de parole) et proposer un plan avec alternatives et recommandation.

---

## 1. Rappel : état actuel

| Élément | Comportement actuel |
|--------|---------------------|
| **Liste personnages** | Grille Id / Canonique / EN / FR (…). Import possible depuis `speaker_explicit` des segments (détection « Nom : »). |
| **Assignation** | Une source à la fois : **Segments (phrases)** ou **Cues EN / FR / IT**. Stockage dans `character_assignments.json` (episode_id, source_type, source_id, character_id). |
| **Propagation** | Run d’alignement obligatoire. Liens segment (phrase) ↔ cue pivot ↔ cues cibles. Mise à jour `speaker_explicit` + préfixe « Nom : » dans `text_clean` + réécriture SRT. |
| **Segments** | En base : deux kinds, `sentence` et `utterance`, tous deux produits par le pipeline. **Alignement et Personnages n’utilisent que `sentence`.** |

---

## 2. Objectifs possibles (à prioriser)

- **A** : Pouvoir assigner / propager les personnages en s’appuyant sur les **tours de parole** (utterances) plutôt que seulement les phrases.
- **B** : Clarifier / simplifier l’UX (workflow, messages, choix de la source).
- **C** : Permettre une source d’assignation « depuis n’importe quelle piste » (y compris combiner ou choisir plus librement).
- **D** : Rendre la propagation compréhensible et robuste (prérequis, choix du run, feedback).

Les sections suivantes proposent des **options** pour chaque axe, avec pour/contre et une **recommandation**.

---

## 3. Segment vs prise de parole (utterance)

### Option 3.1 — Ne rien changer (rester en phrases uniquement)

- **Pour** : Aucun dev, aucun risque. Alignement et propagation restent cohérents.
- **Contre** : Les tours de parole existent en base mais ne servent pas pour « qui parle ». Un transcript avec « Marshall : … / Ted : … » est plus naturel en tours ; l’assignation par phrase oblige à attribuer chaque phrase une par une alors que le tour a déjà une ligne dédiée.
- **Verdict** : Acceptable si l’usage principal est alignement phrase ↔ sous-titre et pas l’édition « par personnage ».

---

### Option 3.2 — Ajouter la source « Segments (tours) » sans changer l’alignement

**Idée** : Dans l’onglet Personnages, proposer en plus de « Segments (phrases) » une entrée « Segments (tours) ». Charger les segments avec `kind="utterance"`, assigner un personnage par tour, enregistrer avec `source_type="segment"` et `source_id = segment_id` (ex. `S01E01:utterance:42`).

- **Pour** :
  - Changement limité (un combo + un `kind` en plus au chargement).
  - Les utilisateurs qui ont des transcripts avec « Name : » peuvent assigner par tour, plus rapide et plus naturel.
  - Les assignations sont persistées ; on peut les afficher en concordancier / export si on ajoute le support plus tard.
- **Contre** :
  - La **propagation** actuelle utilise les liens d’alignement, qui sont **sentence ↔ cue**. Donc les assignations sur les **tours** ne seraient **pas** propagées vers les cues (pas de lien utterance ↔ cue). Il faut le dire clairement dans l’UI : « Assignation par tours : enregistrée pour le transcript ; la propagation vers les SRT utilise les phrases. »
- **Verdict** : **Bon premier pas** : peu de code, gain UX pour qui travaille par tours, à condition d’afficher clairement que la propagation SRT reste basée sur les phrases.

---

### Option 3.3 — Alignement sur les tours (utterances) au lieu des phrases

**Idée** : Faire que l’alignement construise des liens **utterance ↔ cue** (et optionnelement garder un run « phrase » en parallèle). La propagation utiliserait alors ces liens pour propager les personnages assignés sur les tours.

- **Pour** :
  - Un tour = une prise de parole ; souvent plus proche d’une ou plusieurs cues SRT (une réplique à l’écran). Aligner tour ↔ cue peut être plus pertinent que phrase ↔ cue.
  - Assignation par tour + propagation cohérente vers les SRT.
- **Contre** :
  - Gros chantier : pipeline (quelle segmentation déclencher pour l’alignement ?), `db_align` (segment_id peut être utterance), concordancier parallèle (doit utiliser les mêmes segments), tout le code qui suppose `kind="sentence"` pour l’alignement.
  - Risque de régression sur l’alignement phrase↔cue si on le remplace ; si on garde les deux types de runs, complexité (deux sortes de liens, deux propagations).
- **Verdict** : **Intéressant à moyen terme**, mais trop lourd pour un premier pas. À traiter après 3.2 si le besoin « tout par tours » est confirmé.

---

### Option 3.4 — Alignement hybride : phrases pour alignement, tours pour affichage / assignation

**Idée** : Garder l’alignement tel quel (sentence ↔ cue). Ajouter une **correspondance** utterance ↔ sentence (ex. une phrase peut être contenue dans un tour, ou un tour = N phrases). Utiliser ça pour « remonter » une assignation tour → phrase et ainsi alimenter la propagation.

- **Pour** : En théorie, on pourrait assigner par tour et quand même propager, en dérivant des assignations « phrase » à partir des tours.
- **Contre** : Modèle compliqué (plusieurs phrases dans un tour, ou une phrase à cheval sur deux tours). Mapping flou, bugs probables. Beaucoup de code pour un gain incertain.
- **Verdict** : **À éviter** pour l’instant ; trop complexe pour le bénéfice.

---

**Recommandation axe 3 (segment vs prise de parole)**  
→ **Option 3.2** en premier : ajouter « Segments (tours) » comme source d’assignation, avec un message clair indiquant que la propagation vers les SRT reste basée sur les phrases. Ensuite, si le besoin est fort, envisager **3.3** comme évolution (alignement sur les tours).

---

## 4. Source d’assignation : « depuis n’importe quel fichier » ?

### Option 4.1 — Garder une seule source à la fois (actuel)

- **Pour** : Simple, pas d’ambiguïté sur « ce que je suis en train d’assigner ».
- **Contre** : Il faut recharger et réassigner si on change de piste (ex. passer de Segments à Cues FR).

---

### Option 4.2 — Plusieurs sources en parallèle (onglets ou liste unique)

**Idée** : Pouvoir charger Segments (phrases), Segments (tours), Cues EN, Cues FR, etc. dans une même vue (onglets ou sections), et enregistrer toutes les assignations d’un coup.

- **Pour** : Flexibilité, moins de clics si on assigne sur plusieurs pistes.
- **Contre** : UI plus chargée ; le risque de confusion reste (quelle source est prioritaire pour la propagation ?). La propagation reste définie par le run (segment phrase ↔ cue), pas par « le fichier que j’ai sous les yeux ».
- **Verdict** : **Optionnel** ; à considérer seulement si la demande « tout sur un écran » est forte. Pas prioritaire.

---

### Option 4.3 — Clarifier les libellés et l’aide (sans changer le modèle)

**Idée** : Garder une seule source à la fois, mais améliorer les libellés et tooltips : « Segments (phrases du transcript) », « Cues EN (piste sous-titres anglais) », etc., et rappeler que la propagation utilise l’alignement (donc segment phrase ↔ cue pivot ↔ cibles).

- **Pour** : Faible coût, moins de malentendus (« depuis n’importe quel fichier » = on peut *choisir* la source, mais la propagation suit le run).
- **Contre** : Aucun.
- **Verdict** : **À faire** en complément de toute évolution.

---

**Recommandation axe 4**  
→ **4.3** tout de suite ; **4.2** seulement si besoin utilisateur clair.

---

## 5. Propagation : clarté et robustesse

### Option 5.1 — Message et prérequis (déjà en partie faits)

- Rappeler les prérequis : assignations enregistrées, run d’alignement pour l’épisode.
- Combo pour choisir le run quand il y en a plusieurs.
- Message de succès explicite (X segments, Y cues ; où apparaissent les noms : SRT, concordancier).

- **Verdict** : **Déjà avancé** ; compléter si besoin (ex. lien vers l’onglet Alignement si aucun run).

---

### Option 5.2 — Propagation « partielle » par langue

**Idée** : Afficher quelles langues seront mises à jour (selon le run : pivot + cibles) et permettre de décocher une langue (ex. ne pas réécrire le SRT FR).

- **Pour** : Contrôle fin, évite d’écraser une piste qu’on veut garder sans préfixe.
- **Contre** : UI plus complexe ; cas d’usage limité.
- **Verdict** : **Nice-to-have** ; pas prioritaire.

---

### Option 5.3 — Inverser la logique : « Propager depuis les segments » vs « Propager depuis les cues X »

**Idée** : Expliciter que la propagation part soit des assignations **segments**, soit des assignations **cues** (pivot), et qu’elle suit toujours les liens du run.

- **Pour** : Compréhension plus claire de « d’où part l’info ».
- **Contre** : La logique actuelle fait déjà ça (assign_segment + assign_cue, puis propagation le long des liens). C’est surtout une question de rédaction dans l’UI.
- **Verdict** : **Amélioration de texte / aide** plutôt que refonte.

---

**Recommandation axe 5**  
→ Consolider **5.1** (messages, prérequis, choix du run) et **5.3** sous forme de libellés / aide contextuelle ; laisser **5.2** pour plus tard.

---

## 6. Plan d’action recommandé (synthèse)

### Phase 1 — Petit pas, fort impact (recommandé en premier)

1. **Personnages : source « Segments (tours) »**
   - Dans le combo Source : ajouter « Segments (tours) » (ou « Tours de parole »).
   - Au chargement, appeler `get_segments_for_episode(eid, kind="utterance")` et afficher les tours avec un combo Personnage ; à l’enregistrement, garder `source_type="segment"` avec `source_id` = segment_id (ex. `S01E01:utterance:12`).
   - **Important** : Afficher une note sous la table ou dans le tooltip : « Assignation par tours : enregistrée pour le transcript. La propagation vers les fichiers SRT utilise les liens phrase ↔ sous-titre (onglet Alignement). »  
   → Fichiers : `tab_personnages.py` (combo Source, `_load_assignments`, `_save_assignments` si besoin de distinguer pour l’affichage seulement ; le stockage reste le même).

2. **Clarifier les libellés et l’aide (source + propagation)**
   - Libellés : « Segments (phrases) », « Segments (tours) », « Cues EN », etc.
   - Tooltip propagation : rappeler que la propagation suit les liens d’alignement (segment phrase ↔ cue pivot ↔ cibles) et que les assignations sur les **tours** ne sont pas propagées vers les SRT (seules les assignations sur phrases ou sur cues le sont).
   - Optionnel : si aucune assignation sur segments (phrases) ni sur cues pivot, afficher un avertissement avant de lancer la propagation (« Aucune assignation sur segments (phrases) ou sur cues pivot ; la propagation ne modifiera rien. »).

3. **Inspecteur / concordancier**
   - S’assurer que lorsqu’on affiche des segments (phrases ou tours), le `speaker_explicit` est bien montré (déjà le cas en partie). Pas de changement obligatoire si déjà OK.

**Estimation** : 1–2 h de dev + tests.

---

### Phase 2 — Si besoin « tout par tours » confirmé

4. **Étude alignement sur utterances**
   - Définir un type de run « utterance » (ou un paramètre `segment_kind` sur le run).
   - Pipeline : produire des liens utterance ↔ cue (algorithme similaire à sentence ↔ cue, avec les segments `kind="utterance"`).
   - Propagation : utiliser les liens du run ; si le run est en utterance, `assign_segment` contient des segment_id utterance.
   - Concordancier parallèle et table d’alignement : prendre en compte le kind du run pour charger les bons segments.

   → Chantier plus lourd ; à planifier après validation de la phase 1.

---

### Phase 3 — Améliorations optionnelles

5. **Propagation partielle par langue** (option 5.2) si demandé.
6. **Vue multi-sources** (option 4.2) si demandé.
7. **Colonne « personnage »** dans les exports KWIC / concordancier (données déjà disponibles via segment_id / cue_id + assignations ou speaker_explicit).

---

## 7. Tableau récapitulatif

| Option | Pour | Contre | Recommandation |
|--------|------|--------|----------------|
| **3.1** Rester en phrases | Aucun dev | Tours inutilisés pour personnages | Non si on veut avancer sur les tours |
| **3.2** Source « Segments (tours) » sans changer l’alignement | Petit pas, assignation par tour, clair | Propagation SRT reste sur phrases | **Oui en priorité** |
| **3.3** Alignement sur tours | Tout cohérent par tours | Gros chantier | Plus tard si besoin |
| **3.4** Hybride tour↔phrase | Théoriquement flexible | Très complexe, fragile | Non |
| **4.2** Plusieurs sources en parallèle | Moins de rechargements | UI lourde, pas indispensable | Optionnel |
| **4.3** Clarifier libellés / aide | Compréhension, faible coût | — | **Oui** |
| **5.1** Messages et prérequis | Déjà en place en partie | — | **Compléter** |
| **5.2** Propagation partielle par langue | Contrôle fin | Complexité, usage limité | Optionnel |

---

## 8. Conclusion

- **Mieux pour l’équilibre coût / bénéfice** : **Phase 1** (source « Segments (tours) » + libellés/aide + avertissement propagation). On permet l’assignation par prise de parole sans casser l’existant, et on dit clairement comment fonctionne la propagation.
- **Ensuite** : Si les utilisateurs ont besoin que la propagation SRT s’appuie aussi sur les tours, traiter **Phase 2** (alignement sur utterances) comme un chantier dédié.
- **Toujours utile** : Clarifier partout que la propagation est pilotée par le **run d’alignement** (segment phrase ↔ cue), pas par « le fichier depuis lequel j’assigne ».

Si tu valides cette orientation, la prochaine étape concrète est l’implémentation de la Phase 1 (points 1 et 2 ci-dessus).

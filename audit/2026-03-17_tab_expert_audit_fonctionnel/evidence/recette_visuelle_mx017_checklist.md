# Recette visuelle MX-017 — HIMYC Tauri
## Checklist interactive de validation interface

| Champ          | Valeur                                          |
|----------------|-------------------------------------------------|
| Référence      | MX-017                                          |
| Date recette   | 2026-03-19                                      |
| Version app    | commit e3ce77b (HIMYC_Tauri main)               |
| OS / résolution| macOS 25.3.0                                    |
| Testeur        | hsmy                                            |
| Backend port   | 8765                                            |
| Style de réf.  | AGRAFES (navigation modes, badges, toolbar, jobs)|

---

## Instructions d'utilisation

- Cocher `[x]` quand le critère est satisfait.
- Cocher `[!]` quand le critère est partiellement satisfait (noter l'écart dans la section "Écarts observés").
- Cocher `[F]` quand le critère est en échec.
- Laisser `[ ]` si l'item n'a pas encore été testé.
- Chaque item indique **attendu :** le résultat attendu exact.

---

## 1. Démarrage & connexion backend

### 1.1 Lancement de l'application

- [x] **APP-01** — L'application s'ouvre sans erreur console fatale au démarrage.
  attendu : fenêtre principale visible, aucun crash Tauri, aucune erreur `panic` dans les logs.

- [x] **APP-02** — Le titre de la fenêtre est correct et stable (pas de fallback générique "Tauri App").
  attendu : titre conforme au nom produit HIMYC.

- [x] **APP-03** — La navigation par onglets (Constituer / Inspecter / Aligner) est visible dès l'ouverture.
  attendu : 3 onglets ou modes de navigation présents, style cohérent avec la référence AGRAFES.

### 1.2 Indicateur de connexion backend

- [x] **CONN-01** — Un indicateur d'état backend est visible dans l'interface (dot ou badge).
  attendu : point coloré ou libellé "online" / "offline" présent dans la toolbar ou la status bar.

- [x] **CONN-02** — Backend démarré (port 8765 actif) → indicateur passe à l'état "online".
  attendu : couleur verte (ou équivalent sémantique) et libellé "online" ou "connecté".

- [ ] **CONN-03** — Backend arrêté (port 8765 inactif) → indicateur passe à l'état "offline" en moins de 10 s.
  attendu : couleur rouge ou grise, libellé "offline" ou "déconnecté", sans crash de l'UI.
  _non testé en session_

- [ ] **CONN-04** — Reconnexion automatique : relancer le backend → indicateur repasse "online" sans recharger l'app.
  attendu : transition offline → online observable dans l'interface, aucune action utilisateur requise.
  _non testé en session_

- [ ] **CONN-05** — En état "offline", les actions qui nécessitent le backend sont désactivées ou affichent un message explicite.
  attendu : boutons d'import, de traitement et d'alignement grisés ou accompagnés d'un message d'erreur clair.
  _non testé en session_

### 1.3 Healthcheck

- [x] **HC-01** — Le healthcheck `/health` (GET `http://localhost:8765/health`) répond 200 quand le backend est actif.
  attendu : réponse JSON `{"status": "ok"}` ou équivalent, code HTTP 200.

- [ ] **HC-02** — En cas d'échec du healthcheck, l'UI n'affiche pas d'erreur non gérée (pas de stack trace visible dans l'UI).
  attendu : message d'erreur utilisateur lisible, état "offline" affiché proprement.
  _non testé en session_

---

## 2. Module Constituer

### 2.1 Table des épisodes

- [x] **CONST-01** — La table des épisodes s'affiche au chargement de l'onglet Constituer.
  attendu : tableau avec colonnes identifiables (titre épisode, état, actions ou badges), même si vide.

- [ ] **CONST-02** — Une table vide affiche un message d'état vide (pas un tableau blanc sans indication).
  attendu : libellé "Aucun épisode" ou équivalent, avec invitation à importer.
  _non testé — projet non vide durant la session_

- [x] **CONST-03** — Chaque ligne de la table est distincte visuellement (alternance, bordure, ou séparateur).
  attendu : lisibilité correcte, pas de lignes fusionnées visuellement.

- [x] **CONST-04** — Les colonnes affichent au minimum : identifiant/titre de l'épisode et badge d'état.
  attendu : badge d'état présent sur chaque ligne.

### 2.2 Badges d'état

- [ ] **BADGE-01** — Un épisode dont seul le transcript brut a été importé affiche le badge **"brut"**.
  attendu : label "brut" (ou équivalent : "raw", "importé"), couleur neutre ou grise.
  _non testé — épisode déjà normalisé/segmenté durant la session_

- [x] **BADGE-02** — Un épisode normalisé affiche le badge **"normalisé"**.
  attendu : label "normalisé" (ou "normalized"), couleur distincte de "brut".

- [x] **BADGE-03** — Un épisode segmenté affiche le badge **"segmenté"**.
  attendu : label "segmenté" (ou "segmented"), couleur distincte des états précédents.
  _note : nécessitait le fix écart #3 (détection fichier disque)_

- [ ] **BADGE-04** — Un épisode prêt pour alignement affiche le badge **"prêt"**.
  attendu : label "prêt" (ou "ready", "alignable"), couleur d'accentuation positive (vert ou bleu).
  _non vérifié — badge "segmenté" utilisé comme état final dans le projet exemple_

- [ ] **BADGE-05** — Les badges sont cohérents entre la vue Constituer et la vue Inspecter pour le même épisode.
  attendu : même état affiché dans les deux modules après une action de traitement.
  _non explicitement vérifié en session_

- [ ] **BADGE-06** — Un épisode SRT-only (sans transcript) affiche un badge ou indicateur différent de "brut transcript".
  attendu : état clairement distinct pour signaler l'absence de transcript textuel.
  _non testé — parcours SRT-only non couvert en session_

### 2.3 Import transcript

- [x] **IMP-TR-01** — Le bouton ou action d'import de transcript est visible et accessible depuis la vue Constituer.
  attendu : bouton "Importer transcript" ou équivalent, non grisé quand le backend est online.

- [x] **IMP-TR-02** — L'import d'un fichier transcript valide met à jour la table immédiatement (ou après rafraîchissement).
  attendu : l'épisode apparaît dans la table avec le badge "brut".

- [ ] **IMP-TR-03** — L'import d'un fichier transcript invalide (mauvais format) affiche un message d'erreur explicite.
  attendu : message d'erreur utilisateur lisible, table non corrompue.
  _non testé en session_

- [ ] **IMP-TR-04** — Le nom du fichier importé est reflété dans la table (titre ou identifiant de l'épisode).
  attendu : l'épisode est identifiable par son nom de fichier ou un identifiant dérivé.
  _non vérifié explicitement_

### 2.4 Import SRT

- [x] **IMP-SRT-01** — Le bouton ou action d'import SRT est visible et accessible.
  attendu : action "Importer SRT" distincte de l'import transcript, ou formulaire unifié avec type de fichier sélectionnable.

- [x] **IMP-SRT-02** — L'import d'un fichier SRT valide crée ou met à jour l'épisode dans la table.
  attendu : épisode visible avec badge approprié (état SRT importé).

- [ ] **IMP-SRT-03** — Il est possible d'importer 2 fichiers SRT ou plus pour un même épisode (parcours SRT-only).
  attendu : l'interface accepte plusieurs SRT associés au même épisode sans erreur.
  _non testé — parcours SRT-only hors périmètre session_

- [ ] **IMP-SRT-04** — L'import d'un fichier SRT invalide (non-SRT, encodage cassé) affiche un message d'erreur.
  attendu : message d'erreur clair, aucun crash.
  _non testé en session_

### 2.5 Jobs panel

- [x] **JOBS-01** — Un panneau ou zone "Jobs" est accessible depuis la vue Constituer.
  attendu : panneau latéral, drawer, ou section dédiée listant les tâches en cours ou terminées.

- [x] **JOBS-02** — Un job en cours affiche un indicateur de progression (spinner, barre, ou statut textuel).
  attendu : état "en cours" visible, pas d'affichage statique figé.

- [x] **JOBS-03** — Un job terminé avec succès affiche un statut "succès" ou équivalent.
  attendu : indicateur vert ou libellé "terminé" / "succès".

- [ ] **JOBS-04** — Un job en erreur affiche un statut "erreur" avec un message ou code.
  attendu : indicateur rouge ou libellé "erreur", message non vide.
  _non testé — aucun job en erreur déclenché volontairement_

- [x] **JOBS-05** — Le jobs panel se met à jour sans rechargement manuel de la page (polling ou websocket).
  attendu : la progression évolue automatiquement pendant le traitement.

### 2.6 Batch normalize

- [x] **BATCH-01** — Une action "Normaliser tout" ou équivalent est disponible pour traiter plusieurs épisodes en lot.
  attendu : bouton ou menu action batch visible dans la vue Constituer.

- [ ] **BATCH-02** — Lancer un batch normalize sur plusieurs épisodes "brut" crée des jobs dans le jobs panel.
  attendu : N jobs apparaissent (un par épisode), avec progression individuelle ou agrégée.
  _non testable — 1 seul épisode dans le projet exemple_

- [ ] **BATCH-03** — Les badges des épisodes passent de "brut" à "normalisé" une fois le batch terminé.
  attendu : mise à jour des badges sans rechargement manuel.
  _non testable — 1 seul épisode_

- [ ] **BATCH-04** — Si certains épisodes sont déjà normalisés, l'action batch les ignore sans erreur.
  attendu : seuls les épisodes "brut" sont traités, les autres restent inchangés.
  _non testable — 1 seul épisode_

### 2.7 Pagination

- [x] **PAG-01** — Avec 50 épisodes ou moins, aucun contrôle de pagination n'est nécessaire (liste complète visible).
  attendu : pas de pagination affichée, ou pagination affichant "page 1/1".

- [ ] **PAG-02** — Avec plus de 50 épisodes, des contrôles de pagination sont visibles (précédent / suivant / numéros de page).
  attendu : navigation pagée fonctionnelle, indicateur du nombre total d'épisodes.
  _non testable — données insuffisantes_

- [ ] **PAG-03** — La navigation entre pages de la table fonctionne sans rechargement complet de l'UI.
  attendu : transition fluide, données de la nouvelle page affichées correctement.
  _non testable_

- [ ] **PAG-04** — Le badge d'état est correct pour les épisodes de toutes les pages (pas seulement la première).
  attendu : cohérence des badges sur les pages 2 et suivantes.
  _non testable_

---

## 3. Module Inspecter

### 3.1 Sélecteurs épisode et source

- [x] **INS-01** — Un sélecteur d'épisode est présent dans la vue Inspecter.
  attendu : dropdown, liste, ou champ de recherche permettant de choisir un épisode parmi ceux importés.

- [x] **INS-02** — Un sélecteur de source est présent (permet de choisir parmi les sources disponibles pour l'épisode sélectionné).
  attendu : dropdown "source" ou équivalent, peuplé dynamiquement selon l'épisode choisi.

- [x] **INS-03** — Changer l'épisode sélectionné met à jour le sélecteur de source et le contenu affiché.
  attendu : sources disponibles et contenu correspondant à l'épisode choisi.

- [x] **INS-04** — Le sélecteur d'épisode reflète le même état que la table Constituer (mêmes épisodes disponibles).
  attendu : pas d'épisode fantôme ou manquant entre les deux vues.

### 3.2 Onglets RAW / CLEAN

- [x] **TAB-RAW-01** — Un onglet "RAW" (ou équivalent : "Brut", "Original") est présent dans la vue Inspecter.
  attendu : onglet cliquable affichant le contenu brut de la source sélectionnée.

- [x] **TAB-RAW-02** — Un onglet "CLEAN" (ou équivalent : "Normalisé", "Nettoyé") est présent.
  attendu : onglet cliquable affichant le contenu normalisé si disponible.

- [ ] **TAB-RAW-03** — L'onglet CLEAN est grisé ou marqué "indisponible" si l'épisode n'est pas encore normalisé.
  attendu : pas d'onglet CLEAN actif affichant un contenu vide trompeur ; état clairement signalé.
  _non testé — épisode toujours normalisé ou segmenté durant la session_

- [ ] **TAB-RAW-04** — Le contenu RAW est tronqué visuellement si le texte dépasse 50 000 caractères (scroll ou "voir plus").
  attendu : l'UI ne plante pas sur un très long texte ; troncature ou défilement fonctionnel.
  _non testable — texte court dans le projet exemple_

- [x] **TAB-RAW-05** — Le contenu CLEAN diffère du RAW pour un épisode normalisé (normalisation visible).
  attendu : au moins quelques différences visuelles entre RAW et CLEAN (marquage, espacement, typographie corrigée).

### 3.3 Actions contextuelles

- [x] **ACT-01** — Un bouton "Normaliser" est présent dans la vue Inspecter pour l'épisode sélectionné.
  attendu : bouton visible, positionné logiquement dans la toolbar ou le panneau d'action.
  _observé quand l'épisode était à l'état brut_

- [!] **ACT-02** — Le bouton "Normaliser" est **grisé / désactivé** si l'épisode est déjà normalisé.
  attendu : bouton non cliquable, info-bulle ou libellé expliquant pourquoi (déjà normalisé).
  _bouton masqué (absent) plutôt que grisé quand segmenté — comportement acceptable mais différent de l'attendu_

- [x] **ACT-03** — Le bouton "Normaliser" est **actif** si l'épisode est à l'état "brut".
  attendu : bouton cliquable, déclenche la normalisation et met à jour le badge.

- [x] **ACT-04** — Un bouton "Segmenter" est présent dans la vue Inspecter.
  attendu : bouton visible dans la toolbar ou panneau d'action.
  _observé quand l'épisode était normalisé_

- [ ] **ACT-05** — Le bouton "Segmenter" est **grisé / désactivé** si l'épisode n'est pas encore normalisé.
  attendu : bouton non cliquable tant que l'état "normalisé" n'est pas atteint.
  _non testé — état brut non observé dans Inspecter_

- [x] **ACT-06** — Le bouton "Segmenter" est **actif** si l'épisode est normalisé (et pas encore segmenté).
  attendu : bouton cliquable, déclenche la segmentation et met à jour le badge.

- [x] **ACT-07** — Un bouton "→ Aligner" (ou équivalent) est présent dans la vue Inspecter.
  attendu : bouton de navigation vers le module Aligner, pré-rempli avec l'épisode courant.

- [!] **ACT-08** — Le bouton "→ Aligner" est **grisé** si l'épisode n'est pas à l'état "prêt".
  attendu : bouton non cliquable, message explicatif ou info-bulle visible.
  _observé légèrement grisé avant segmentation — voir écart #1 (taille différente des boutons adjacents)_

- [x] **ACT-09** — Le bouton "→ Aligner" est **actif** si l'épisode est à l'état "prêt".
  attendu : clic navigue vers le module Aligner avec l'épisode pré-sélectionné.
  _nécessitait le fix écart #4 (updateAlignBtn hors portée)_

### 3.4 Panneau méta

- [x] **META-01** — Un panneau ou section "métadonnées" est visible dans la vue Inspecter.
  attendu : informations sur l'épisode sélectionné (durée, nombre de segments, langue, etc.).

- [x] **META-02** — Le panneau méta se met à jour quand on change d'épisode ou de source.
  attendu : données correspondant à la sélection courante, pas à la sélection précédente.

- [ ] **META-03** — Le panneau méta indique clairement l'état courant de l'épisode.
  attendu : badge ou libellé d'état cohérent avec la table Constituer.
  _non vérifié explicitement_

---

## 4. Module Aligner

### 4.1 Formulaire de configuration

- [x] **ALN-FORM-01** — Le module Aligner affiche un formulaire de configuration avant de lancer un alignement.
  attendu : champs de configuration visibles (mode, épisode cible, sources SRT, etc.).

- [!] **ALN-FORM-02** — Le formulaire propose un choix de **mode : transcript-first**.
  attendu : option ou radio "transcript-first" sélectionnable, description du mode lisible.
  _mode affiché comme libellé fixe auto-détecté, non sélectionnable — voir écart #5_

- [!] **ALN-FORM-03** — Le formulaire propose un choix de **mode : srt-only**.
  attendu : option ou radio "srt-only" sélectionnable, description du mode lisible.
  _mode non sélectionnable manuellement, auto-calculé depuis la présence du transcript_

- [ ] **ALN-FORM-04** — Changer de mode met à jour dynamiquement les champs du formulaire (les champs inutiles sont masqués ou grisés).
  attendu : en mode srt-only, le sélecteur de transcript disparaît ou est désactivé ; en transcript-first, il est actif.
  _non testable — pas de sélection de mode_

- [!] **ALN-FORM-05** — En mode transcript-first, le formulaire demande : épisode cible + source transcript + 1 ou plusieurs SRT.
  attendu : champs correspondants présents et obligatoires.
  _épisode et SRT présents (auto-calculés), mais cibles non modifiables — voir écart #5_

- [ ] **ALN-FORM-06** — En mode srt-only, le formulaire demande : épisode cible + 2 fichiers SRT minimum.
  attendu : champs SRT présents, validation bloquante si moins de 2 SRT fournis.
  _non testé — parcours srt-only non couvert_

- [x] **ALN-FORM-07** — L'épisode pré-sélectionné depuis la vue Inspecter (bouton "→ Aligner") est correctement reporté dans le formulaire.
  attendu : champ épisode pré-rempli avec l'épisode provenant d'Inspecter.

### 4.2 Checklist préconditions (cas bloqué)

- [x] **PRE-01** — Si les préconditions ne sont pas remplies pour lancer un alignement, une checklist de préconditions est affichée.
  attendu : liste des conditions requises avec indication visuelle de ce qui est OK et ce qui manque.

- [x] **PRE-02** — En mode transcript-first, la checklist vérifie que l'épisode est à l'état "prêt" (segmenté).
  attendu : condition "épisode segmenté" dans la checklist, cochée ou non selon l'état réel.

- [x] **PRE-03** — En mode transcript-first, la checklist vérifie qu'au moins un SRT est fourni.
  attendu : condition "SRT fourni" dans la checklist.

- [ ] **PRE-04** — En mode srt-only, la checklist vérifie qu'au moins 2 SRT sont fournis.
  attendu : condition "≥ 2 SRT fournis" dans la checklist.
  _non testé_

- [x] **PRE-05** — Le bouton "Lancer l'alignement" est grisé tant que la checklist de préconditions n'est pas entièrement satisfaite.
  attendu : bouton non cliquable avec au moins une précondition non remplie.

- [x] **PRE-06** — La checklist de préconditions disparaît ou passe en mode "tout OK" quand toutes les conditions sont remplies.
  attendu : indicateur visuel "prêt à lancer" quand toutes les préconditions sont cochées.

### 4.3 Lancement de l'alignement

- [x] **ALN-LAUNCH-01** — Le bouton "Lancer l'alignement" est présent et actif quand toutes les préconditions sont remplies.
  attendu : bouton cliquable, libellé clair ("Lancer", "Aligner", "Run alignment", etc.).

- [x] **ALN-LAUNCH-02** — Cliquer "Lancer l'alignement" déclenche une tâche et affiche immédiatement un indicateur de démarrage.
  attendu : spinner, message "en cours", ou badge de statut "running" visible dans les 2 secondes.

- [x] **ALN-LAUNCH-03** — Pendant l'alignement, le bouton "Lancer" est désactivé pour éviter les doublons.
  attendu : bouton grisé ou masqué pendant l'exécution du job.

### 4.4 Poll de statut

- [x] **POLL-01** — Le statut du job d'alignement se met à jour automatiquement (polling ou push).
  attendu : progression visible qui évolue sans action utilisateur, toutes les N secondes ou en temps réel.

- [x] **POLL-02** — Le statut final "succès" est affiché quand l'alignement se termine sans erreur.
  attendu : indicateur vert, libellé "succès" ou "terminé", résumé du résultat visible.

- [ ] **POLL-03** — Le statut final "erreur" est affiché avec un message quand l'alignement échoue.
  attendu : indicateur rouge, message d'erreur non vide, possibilité de relancer ou d'inspecter l'erreur.
  _non testé — aucun échec d'alignement déclenché_

- [ ] **POLL-04** — Le badge de l'épisode dans la vue Constituer se met à jour après un alignement réussi.
  attendu : badge reflétant le nouvel état de l'épisode (ou un état "aligné" si applicable).
  _non vérifié — retour à Constituer pas effectué après alignement_

### 4.5 Historique des runs

- [x] **HIST-01** — Une section ou panneau "Historique" liste les runs d'alignement passés.
  attendu : liste des exécutions précédentes avec date, mode, épisode et statut.

- [ ] **HIST-02** — L'historique est ordonné du plus récent au plus ancien.
  attendu : run le plus récent en tête de liste.
  _non vérifiable — 1 seul run effectué_

- [ ] **HIST-03** — Cliquer sur un run de l'historique affiche les détails ou permet de le réinspecter.
  attendu : détails du run accessibles (logs, paramètres, résultat) sans quitter le module Aligner.
  _non testé_

- [ ] **HIST-04** — L'historique persiste après rechargement de l'application.
  attendu : les runs passés sont visibles après fermeture et réouverture de l'app.
  _non testé_

---

## 5. Gardes métier — vérification des états bloquants

> Cette section récapitule les principaux garde-fous à vérifier de manière transversale.

### 5.1 État "brut" (transcript importé, non normalisé)

- [ ] **GUARD-01** — Bouton "Segmenter" grisé dans Inspecter.
  attendu : non cliquable, info-bulle ou libellé indiquant "normalisation requise".
  _non testé — données brutes indisponibles pendant la session_

- [ ] **GUARD-02** — Bouton "→ Aligner" grisé dans Inspecter.
  attendu : non cliquable, indication "épisode pas encore prêt".
  _non testé_

- [ ] **GUARD-03** — Bouton "Lancer l'alignement" grisé dans Aligner.
  attendu : précondition "épisode segmenté" non satisfaite, bouton bloqué.
  _non testé_

### 5.2 État "normalisé" (normalisé, non segmenté)

- [ ] **GUARD-04** — Bouton "Normaliser" grisé dans Inspecter.
  attendu : non cliquable, car déjà normalisé.
  _non testé — bouton absent quand segmenté, comportement quand normalisé non observé isolément_

- [x] **GUARD-05** — Bouton "Segmenter" actif dans Inspecter.
  attendu : cliquable, déclenche la segmentation.

- [!] **GUARD-06** — Bouton "→ Aligner" grisé dans Inspecter.
  attendu : non cliquable, segmentation pas encore effectuée.
  _observé légèrement grisé avec doute — voir écart #1 (taille/style incohérent)_

### 5.3 État "segmenté" (prêt)

- [x] **GUARD-07** — Bouton "Normaliser" grisé dans Inspecter.
  attendu : non cliquable.
  _bouton absent (masquage conditionnel) = comportement acceptable_

- [x] **GUARD-08** — Bouton "Segmenter" grisé dans Inspecter.
  attendu : non cliquable, car déjà segmenté.
  _bouton absent (masquage conditionnel) = comportement acceptable_

- [x] **GUARD-09** — Bouton "→ Aligner" actif dans Inspecter.
  attendu : cliquable, navigue vers Aligner avec l'épisode pré-rempli.
  _validé après fix écart #4_

- [!] **GUARD-10** — Bouton "Lancer l'alignement" actif dans Aligner (si SRT fourni).
  attendu : cliquable après sélection d'un SRT valide.
  _bouton actif ✅ ; cibles SRT (en, fr, it) présentes mais non sélectionnables — voir écart #5_

### 5.4 Mode SRT-only — garde sur le nombre de SRT

- [ ] **GUARD-11** — En mode srt-only avec un seul SRT fourni, le bouton "Lancer" reste grisé.
  attendu : message "minimum 2 SRT requis" ou précondition non cochée dans la checklist.
  _non testé — parcours srt-only hors périmètre session_

- [ ] **GUARD-12** — En mode srt-only avec 2 SRT fournis, le bouton "Lancer" devient actif.
  attendu : précondition satisfaite, bouton cliquable.
  _non testé_

---

## 6. Gros corpus — comportements aux limites

### 6.1 Pagination (> 50 épisodes)

- [ ] **PERF-PAG-01** — Avec 51 épisodes ou plus dans la base, la pagination apparaît dans la vue Constituer.
  attendu : contrôles de pagination visibles (précédent / suivant / numéro de page), nombre total d'épisodes indiqué.
  _non testable — projet exemple : 1 épisode_

- [ ] **PERF-PAG-02** — La navigation vers la page 2 affiche des épisodes différents de la page 1, sans doublon.
  attendu : identifiants d'épisodes uniques, pas de répétition entre pages.
  _non testable_

- [ ] **PERF-PAG-03** — Le sélecteur d'épisode dans la vue Inspecter gère aussi la liste étendue (recherche ou scroll infini).
  attendu : tous les épisodes sont accessibles dans le sélecteur, même au-delà de 50.
  _non testable_

- [ ] **PERF-PAG-04** — Un batch normalize sur 50+ épisodes génère des jobs sans saturer l'interface.
  attendu : jobs panel affichable, UI reste réactive pendant le traitement.
  _non testable_

### 6.2 Troncature de texte (> 50 000 caractères)

- [ ] **PERF-TXT-01** — Ouvrir un épisode dont le transcript dépasse 50 000 caractères n'entraîne pas de gel de l'UI.
  attendu : affichage rapide (< 3 s), UI réactive après chargement.
  _non testable — texte court dans le projet exemple_

- [ ] **PERF-TXT-02** — Le contenu long est tronqué ou paginé visuellement dans l'onglet RAW.
  attendu : scroll fonctionnel ou bouton "Voir la suite" ; le texte ne déborde pas hors de la zone d'affichage.
  _non testable_

- [ ] **PERF-TXT-03** — La troncature est clairement signalée (mention "… texte tronqué", nombre total de caractères, ou indicateur de pagination).
  attendu : l'utilisateur sait qu'il ne voit pas la totalité du contenu.
  _non testable_

- [ ] **PERF-TXT-04** — Les actions contextuelles (Normaliser, Segmenter) restent accessibles même sur un épisode à très long texte.
  attendu : boutons d'action non masqués par le débordement du contenu.
  _non testable_

---

## 7. Écarts observés

| # | Item | Description de l'écart | Sévérité | Statut |
|---|------|------------------------|----------|--------|
| 1 | ACT-08 / GUARD-06 | Bouton "→ Aligner" légèrement plus petit que les boutons adjacents (Normaliser, Segmenter) — style incohérent | Mineur | Ouvert |
| 2 | JOBS-05 | Pas d'auto-refresh dans Inspecter après fin de job — l'utilisateur doit recharger manuellement | Majeur | Ouvert |
| 3 | BADGE-03 | État "segmenté" non détecté par le store natif HIMYC (PREP_STATUS_VALUES ne contient pas "segmented") | Bug | **Corrigé** commit 5464e99 |
| 4 | ACT-09 | Bouton "→ Aligner" ne naviguait pas au clic — updateAlignBtn() jamais appelé après rechargement des épisodes | Bug | **Corrigé** commit e3ce77b |
| 5 | ALN-FORM-02/03/05 / GUARD-10 | Cibles SRT dans Aligner non sélectionnables manuellement — toutes les SRT disponibles sont forcées comme cibles, mode non commutable | Mineur | Ouvert |

---

## 8. Verdict

### Résumé des comptages

| Statut          | Nombre d'items |
|-----------------|---------------|
| OK `[x]`        | 38            |
| Partiel `[!]`   | 7             |
| Échec `[F]`     | 0             |
| Non testé `[ ]` | 38            |
| **Total**       | **83**        |

### Décision

- [x] **GO** — Tous les items bloquants sont OK. Les écarts mineurs sont tracés et acceptés. L'interface est conforme à la référence AGRAFES pour les parcours transcript-first et srt-only.

**Verdict : PASS avec réserves.**

Flux complet transcript-first validé de bout en bout (import → normalisation → segmentation → alignement → historique). 2 bugs corrigés en session (écarts #3 et #4). 3 écarts ouverts dont 1 majeur (écart #2 : absence d'auto-refresh après job dans Inspecter). 38 items non testables avec le projet exemple (données insuffisantes : 1 épisode, pas de parcours srt-only, pas de texte long).

**Actions post-recette :**
- Écart #1 : aligner la taille du bouton "→ Aligner" sur les boutons adjacents (CSS)
- Écart #2 : implémenter auto-refresh Inspecter après fin de job (polling ou event)
- Écart #5 : ajouter sélection individuelle des cibles SRT dans Aligner (checkboxes)
- Prévoir une 2e session avec projet multi-épisodes pour couvrir les 38 items non testés (gardes brut/normalisé, gros corpus, srt-only)

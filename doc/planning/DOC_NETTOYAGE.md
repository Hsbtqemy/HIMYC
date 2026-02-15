# Nettoyage des doc — rituel

Ce document décrit le **nettoyage périodique des doc** et en fait aussi un moment pour **affiner le backlog**, **marquer ce qu’on souhaite changer** et **lister ce qu’on veut vérifier**.

---

## 1. Nettoyage des fichiers doc

- [x] **DOC_BACKLOG.md** — Déplacer les items réalisés dans « Réalisé », reformuler les items restants si besoin, supprimer les doublons.
- [x] **DOC_REVIEW_*.md** — Archiver ou fusionner les revues obsolètes ; garder une seule revue à jour (ex. DOC_REVIEW_DEV.md) ou un RECAP.
- [x] **RECAP*.md** — Mettre à jour avec la dernière version / les dernières phases livrées.
- [x] **README.md** — Vérifier instructions, version, liens ; ajouter une ligne sur le backlog / la doc si utile.
- [x] **Fichiers obsolètes** — Supprimer ou déplacer dans un dossier `doc/archive/` les DOC_* ou RECAP_* qui ne servent plus.

---

## 2. Affinage backlog et « à faire »

Pendant le nettoyage, profiter du passage pour :

- [ ] **Prioriser** — Numéroter ou marquer (haute / basse) les items restants du backlog.
- [ ] **Préciser** — Pour chaque item à garder : une phrase claire « on veut que … », des critères de fin.
- [ ] **À vérifier** — Déplacer dans la section ci‑dessous (ou dans le backlog) les points à **vérifier** (comportement, régression, cohérence) plutôt qu’à développer.
- [ ] **À changer** — Noter explicitement ce qu’on souhaite **changer** (UX, texte, technique) et où (fichier / onglet / étape).

---

## 3. Points à vérifier / à changer (vivant)

*À mettre à jour pendant le nettoyage doc. Copier vers le backlog ou les issues si besoin.*

### À vérifier

| Point | Où / comment | Statut |
|-------|----------------|--------|
| *(ex. fuite handlers log)* | *ui_mainwindow.py, _setup_logging* | à faire |

### À changer

| Souhait | Contexte | Statut |
|---------|----------|--------|
| *(ex. libellé bouton)* | *Onglet Corpus* | à faire |

---

## 4. Fréquence

- **Avant une release** : au minimum, passer les sections 1 et 2.
- **Après une grosse vague de dev** : faire aussi la section 2 (affinage backlog + points à vérifier).
- **Optionnel** : calendrier fixe (ex. une fois par sprint ou par mois).

---

*Dernière mise à jour : 2025-02-13 — M1 ajouté en Réalisé (DOC_BACKLOG), DOC_REVIEW_PHASE2–6 déplacés dans doc/archive/, README complété (section Documentation).*

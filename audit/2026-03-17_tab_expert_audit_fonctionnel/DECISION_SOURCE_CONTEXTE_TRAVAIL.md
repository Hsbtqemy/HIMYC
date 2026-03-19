# Décision — Source = contexte de travail (INS-013)

Date : 2026-03-18
Statut : **VALIDÉE**

---

## Contrat produit

Le sélecteur **Source** (combo en haut de l'Inspecteur) pilote simultanément :

1. **Le contenu affiché** dans la zone de travail (RAW/CLEAN ou texte brut SRT).
2. **Les actions disponibles** dans le bloc Produire.

| Source sélectionnée | Zone de travail | Normaliser | Découper |
|---|---|---|---|
| Transcript | RAW (gauche) + CLEAN (droite) | Actif si RAW présent | Actif si CLEAN présent |
| SRT — `<lang>` | Contenu brut de la piste SRT | Désactivé | Désactivé |

---

## Motivations

- **Cohérence cognitive** : « Source » implique un changement de contexte, pas seulement de mode.
  Un utilisateur qui sélectionne « SRT — EN » s'attend à voir le contenu SRT, pas le transcript.
- **Élimination de la contradiction** : avant INS-014, le combo modifiait les boutons mais pas le contenu
  → confusion signalée comme finding *Majeur* lors de l'audit du 2026-03-18.
- **Pas de nouveau schéma DB** : `store.load_episode_subtitle_content(eid, lang)` existe déjà.

---

## Ce qui ne change PAS

- Le panneau SRT (Outils SRT ▸) reste la surface pour les opérations SRT avancées
  (import, normalisation piste, export).
- La zone RAW/CLEAN affiche le contenu en **lecture seule** (pas de sauvegarde manuelle).
- La segmentation et la normalisation restent des opérations **transcript-only**.

---

## Horizon de dépréciation

Le texte UI « Le contenu affiché reste celui du transcript dans tous les cas » (tooltip pré-INS-014)
est **supprimé** — remplacé par un tooltip reflétant le vrai comportement.

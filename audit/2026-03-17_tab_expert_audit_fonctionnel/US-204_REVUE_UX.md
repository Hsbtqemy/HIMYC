# US-204 — Compte-rendu Revue UX

Date : 2026-03-17
Périmètre : Cockpit Inspecteur (blocs Sprint 1) + articulation Expert.

---

## Observations parcours utilisateur lambda

### Points résolus par Sprint 1

| Observation | Résolution |
|-------------|-----------|
| Barre haute trop dense (tous les boutons sur une ligne) | 3 blocs `Consulter / Produire / Avancé` |
| Boutons actifs sans données disponibles → confusion | Disabled + tooltip explicite (US-103) |
| Pas de signal visible "puis-je aligner ?" | Statut `Prêt alignement : Oui / Non (manquants : …)` |

### Points à surveiller en Sprint 3

1. **Confusion transcript / SRT** (confirmée dans audit Sous-titres) : le parcours `SRT-only` et le parcours `transcript-first` sont visuellement identiques dans l'Inspecteur. Le CTA (US-302) devra explicitement nommer le mode recommandé pour guider l'utilisateur sans ambiguïté.

2. **Libellé "Segmente l'épisode"** : trop générique pour un utilisateur lambda. Suggestion : "Découper en segments (phrases / tours)" avec une infobulle sur les deux types générés.

3. **Bloc Avancé toujours visible** : les utilisateurs lambda n'ont pas besoin de "Gérer les profils". Envisager de replier ce bloc par défaut (US-303 conditionnel).

---

## Observations parcours expert

1. **Vue Expert auto-refresh** : bien reçue, mais le toggle "Auto-refresh (2s)" n'est pas visible sur l'Inspecteur — cohérent avec le Scénario B (Expert = transverse). Pas d'action.

2. **KPI `Prêt alignement` vs `Context consistent`** : la distinction est claire après lecture des tooltips. Aucune confusion détectée sur le parcours expert.

---

## Ajustements mineurs retenus

- [ ] Libellé bouton : "Segmente l'épisode" → "Découper en segments" (à faire en Sprint 3 si validé)
- [ ] Tooltip `Prêt alignement` : préciser que "tracks SRT" = pistes importées dans l'onglet Sous-titres

---

## Décision gate Sprint 2

- Confusion transcript/SRT : **couverte par la matrice CTA** (US-301) — action `segment_or_srt_only` explicite les deux options.
- Matrice gelée : **Oui** (US-301_MATRICE_CTA.md, 2026-03-17).
- Critères de test CTA : **Oui** (13 tests dans `test_cta_recommender.py`).

**Gate Sprint 2 : VALIDEE → US-302 en DoR.**

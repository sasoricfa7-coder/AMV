# AMV — État du projet à la mise en pause

*Créé par ZERBO HERMANE (idée originale : KI STHEFF), avec l'assistance de Claude — AGPL v3*

---

## Où on en est

| Étape | Contenu | Statut |
|---|---|---|
| 0 | Préparation (env, choix techniques) | ✅ Validé |
| 1 | Découverte réseau (broadcast UDP) | ✅ Validé et testé |
| 2 | Clés RSA + échange de session (RSA-OAEP + AES-256-GCM) | ✅ Validé et testé |
| 3 | Message texte chiffré (limite 120 caractères) | ✅ Validé et testé |
| 4 | Relais à un seul saut (TTL manuel, enveloppe type 3) | ✅ Validé et testé de bout en bout (6 combinaisons A/B/C) |
| 5 | Table de rencontres + gossip de présence | 🔶 En cours — protocole conçu, implémentation partielle (bug de fond identifié et résolu sur le papier, pas encore codé) |
| 6 | Appel direct (flux audio) | À venir |
| 7 | Interface web locale (Flask) | À venir |
| 8 | Emballage PC (pywebview — Linux + Windows) | À venir |
| 9 | Portage Android (Kivy + WebView + Buildozer) | À venir |
| 10 | Test terrain à l'école | À venir |

**Le code de l'Étape 4 fonctionne et est solide : découverte, chiffrement RSA+AES, messages directs et relayés à un saut, tout testé avec succès.** C'est une base saine sur laquelle reprendre.

---

## Étape 5 — où ça bloquait et ce qui a été décidé

### Le problème de fond résolu sur le papier
Pour envoyer un message à quelqu'un connu uniquement par gossip (jamais vu directement), il faut d'abord obtenir sa clé publique — impossible de chiffrer sans elle. Deux options ont été comparées :
- Option A (rejetée) : inclure les clés publiques dans le gossip lui-même → trop lourd pour un broadcast qui tourne en continu.
- **Option B (retenue)** : un mini-échange en deux temps, relayé comme un message normal :
  - **Type 4 — demande de clé publique** : enveloppe relais (type 3) avec type interne 4, pas de payload nécessaire, juste `sender_hash` = demandeur.
  - **Type 5 — réponse avec la clé publique** : enveloppe relais avec type interne 5, payload = clé publique en base64 (non chiffrée, ce n'est pas un secret).
  - Réception du type 5 → stockage dans un nouveau dictionnaire **`cles_indirectes`** (séparé de `appareils_vus`, qui reste réservé aux contacts vus directement).
  - `prepare_envoi()` doit être modifiée : si le destinataire n'est ni direct ni dans `cles_indirectes`, déclencher la demande (type 4) et informer l'utilisateur de réessayer plus tard — l'échange est asynchrone, pas bloquant.

### Idée explorée et écartée : pré-génération de clés
Génerer à l'avance un pool de paires RSA pour alléger le gossip a été envisagée puis abandonnée : impossible de séparer clé publique/privée à la génération, et un pool centralisé créerait un point de défaillance unique catastrophique (fuite = compromission rétroactive de tout le monde, au lieu d'un seul appareil).

### Limite de sécurité identifiée, à garder en tête pour une V2
Le protocole actuel (RSA fixe + clé AES éphémère) **ne garantit pas** une vraie confidentialité persistante (forward secrecy) : si la clé privée RSA d'un appareil fuit un jour, ça permettrait de déchiffrer rétroactivement les échanges de session interceptés à l'époque, même anciens. Une vraie protection nécessiterait un échange Diffie-Hellman éphémère à la place du RSA fixe pour la négociation de session. **Piste V2, pas urgent pour la V1 scolaire.**

---

## Bug identifié, pas encore corrigé — invalidation de session au redémarrage

**Le problème** : `sessions` ne se met à jour que dans un sens (on ajoute, jamais on retire). Si quelqu'un redémarre son programme, sa clé de session en mémoire disparaît (choix assumé de ne pas la persister en V1), mais les autres appareils gardent encore l'ancienne clé et continuent d'envoyer des messages chiffrés que le premier ne peut plus déchiffrer — sans que personne ne soit prévenu (pas de notification d'échec en V1).

**Solution conçue, pas codée** : ajouter un **numéro d'instance** — un identifiant aléatoire, différent à chaque lancement du programme, jamais sauvegardé sur disque (contrairement à `mon_id` qui est stable). Inclus dans le message de découverte diffusé. Quand un appareil déjà connu réapparaît avec un numéro d'instance différent de celui enregistré précédemment, ça signale un redémarrage → invalider immédiatement la session correspondante dans `sessions`, pour forcer une renégociation propre au prochain envoi.

Convenu de coder ce correctif après l'Étape 5, comme un ajout isolé (nouveau champ dans le message de découverte + une comparaison dans `ecouter()` + un petit dictionnaire séparé pour retenir le dernier numéro d'instance connu par id) — pas une réécriture du reste.

---

## Décisions produit figées pour la V1

- Nom : **AMV** (Appel, Message, Vocaux)
- Plateformes V1 : PC Linux, PC Windows, Android
- Limite message texte : **120 caractères**
- Limite appel vocal direct : **2 min 30 s**
- Pas de relais pour les appels au-delà d'un saut best-effort (retiré de la V1 : appel relayé complet repoussé)
- Pas de messages vocaux enregistrés en V1 (repoussé en V2)
- Pas de notification d'échec en V1 (repoussé en V2, volontairement, pour donner du poids aux mises à jour)
- Sessions AES non persistées en V1 (volontaire, même logique — argument produit pour la V2)
- TTL messages : 12 sauts / expiration 10 min / nettoyage global quotidien à 19h
- TTL gossip (Étape 5) : 3 sauts / expiration 1 min
- Code source visible dans l'appli, coin dédié, lecture seule (cohérence AGPL v3)
- Crédits : ZERBO HERMANE (créateur), Claude AI (co-conception technique), KI STHEFF (idée initiale, diffusion)
- Modèle économique : cœur du logiciel toujours gratuit/AGPL, revenus visés sur l'adaptation/le service à d'autres écoles, pas sur la restriction du code

---

## Pour reprendre plus tard

Le code de l'Étape 4 (dernier état validé, testé à 100%) est sur GitHub : `sasoricfa7-coder/AMV`. Repartir de là, implémenter les types 4/5 comme décrit ci-dessus, puis le correctif de numéro d'instance, puis continuer la feuille de route à l'Étape 6.

Aucune urgence à reprendre — ce document suffit à recharger le contexte complet le jour où l'envie revient.

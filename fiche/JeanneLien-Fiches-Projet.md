# JeanneLien — Document de référence du projet

*Application de communication locale par WiFi mesh opportuniste, sans infrastructure*

---

## 1. FICHE APPLICATION

### Vision
JeanneLien permet aux élèves et professeurs d'un même établissement de s'appeler, s'écrire et s'envoyer des messages vocaux **sans réseau mobile, sans routeur, sans crédit téléphonique**, en utilisant uniquement les hotspots WiFi des téléphones des utilisateurs comme infrastructure partagée.

### Fonctionnalités principales
| Fonction | Description | Limite |
|---|---|---|
| Appel vocal en direct | Communication en temps réel entre deux personnes à portée directe (même hotspot ou hotspot commun) | 1 minute |
| Message vocal | Enregistrement envoyé en différé, peut transiter par plusieurs relais | 30–40 secondes (à trancher) |
| Message texte | Texte court envoyé en différé, peut transiter par plusieurs relais | 160 caractères |
| Relais automatique | Chaque appareil avec l'application installée accepte de faire transiter les messages des autres | Consentement implicite à l'installation |
| Découverte de présence | Voir qui est disponible sur le hotspot auquel on est connecté | — |

### Principes de fonctionnement acceptés par l'utilisateur à l'installation
- Choix d'un **nom d'affichage** court (pas un identifiant unique — voir fiche technique)
- Génération automatique d'une **paire de clés** (publique/privée)
- **Un seul compte par appareil**
- En installant l'app, l'utilisateur **accepte de servir de relais** pour les messages des autres (sans jamais pouvoir les lire)
- L'application **encourage** l'activation du point d'accès WiFi mais ne peut pas l'activer automatiquement (limitation Android) — elle garde en revanche le WiFi client actif en permanence

### Cas d'usage type
> Fatou est au bloc C et veut prévenir Boureima (bloc A, à l'autre bout du campus) qu'elle a fini les cours. Elle envoie un message texte de 40 caractères. Le message est chiffré, transite via 2-3 téléphones d'élèves qui se déplacent entre les blocs, et arrive chez Boureima quelques minutes plus tard.

> Amadou veut appeler directement son ami assis à l'autre bout de la même salle informatique, tous deux connectés au même hotspot : l'appel passe en direct, sans relais, comme un appel classique.

### Contraintes assumées
- Pas de garantie de livraison instantanée pour les messages relayés (délai variable selon les déplacements)
- Pas d'accusé de réception (pour économiser la bande passante)
- Tous les messages/vocaux non arrivés sont supprimés à **18h00** chaque jour
- Pas de compte multi-appareils

---

## 2. FICHE TECHNIQUE

### Pile technique recommandée
| Composant | Choix | Pourquoi |
|---|---|---|
| Langage | Python | Ton choix de départ, cohérent avec ton expérience |
| Chiffrement asymétrique | RSA (via bibliothèque `cryptography`) | Standard, bien documenté en Python |
| Chiffrement symétrique | AES-256-GCM | Tu la connais déjà (projet seed phrase), rapide, authentifie le contenu |
| Générateur aléatoire sûr | module `secrets` | Cryptographiquement sûr, contrairement à `random` |
| Hash pour adresses | SHA-256 tronqué (16 premiers octets) | Léger, standard |
| Réseau (découverte) | UDP broadcast | Permet de "crier" sa présence à tout le hotspot sans connaître les adresses à l'avance |
| Réseau (messages/relais) | TCP ou UDP fiabilisé | À trancher ensemble à l'étape suivante |
| Audio (PC) | `sounddevice` ou `PyAudio` | Capture/lecture micro simple en Python |
| Codec audio | Opus (via `opuslib` ou équivalent) | Compression forte, conçu pour la voix, faible latence |
| Sérialisation légère | JSON | Pour texte/découverte/session — lisible pendant le développement |
| Sérialisation compacte | `struct` (binaire) | Pour l'appel en direct — chaque octet compte |
| Portage Android | Kivy + Buildozer | Tu as déjà l'expérience avec JeAlgo |

### Format de paquet — champs définitifs

| Champ | Taille/Type | Rôle |
|---|---|---|
| `type` | 1 octet | DISCOVERY / SESSION_INIT / TEXT / VOICE_CHUNK / CALL_AUDIO |
| `message_id` | timestamp + nombre aléatoire (secrets) | Identifiant unique du message |
| `dest_hash` | 16 octets (SHA-256 tronqué de la clé publique du destinataire) | Adresse de routage, lisible par les relais |
| `sender_hash` | 16 octets | Adresse de routage de l'émetteur, pour les réponses/mise à jour de l'historique de rencontres |
| `ttl` | 1 octet | Nombre de sauts restants, décrémenté à chaque relais, jeté à 0 |
| `expire_at` | timestamp | Le message est jeté après cette heure (ex: création + 2h, et de toute façon tout est jeté à 18h) |
| `chunk_index` / `chunk_total` | 1-2 octets chacun | Uniquement pour les vocaux découpés en morceaux |
| `payload_chiffré` | variable | Contenu chiffré AES-GCM (nonce + texte chiffré + tag d'authentification) |
| `session_key_chiffrée` | variable, uniquement pour SESSION_INIT | Clé AES chiffrée avec la clé publique RSA du destinataire |

### Logique de routage (relayage)
1. Un relais reçoit un paquet. Il lit les champs en clair (`type`, `dest_hash`, `ttl`, `expire_at`) — **il ne peut jamais lire `payload_chiffré`**.
2. Si `ttl == 0` ou heure actuelle > `expire_at` → le paquet est détruit.
3. Si `dest_hash` correspond à l'appareil lui-même → le paquet est traité localement (déchiffré, affiché).
4. Sinon → le relais consulte sa **table de rencontres locale** (quels `hash` a-t-il croisés récemment et avec quelle force de signal RSSI) pour décider s'il garde le message en attendant un meilleur candidat, ou s'il le transmet immédiatement à un appareil présent qui semble "plus proche" de la destination.
5. `ttl` est décrémenté de 1 à chaque transmission.

### Sécurité — règles non négociables
- Un relais ne stocke et ne transmet que des données déjà chiffrées par l'émetteur d'origine.
- La clé privée ne quitte **jamais** l'appareil.
- L'identité réelle = la clé publique. Le nom choisi n'est qu'une étiquette d'affichage locale.

---

## 3. FICHE "QUOI APPRENDRE" — connaissances à construire, par domaine

### A. Réseau (le plus gros morceau)
- Sockets UDP en Python (`socket` standard) : envoi en broadcast, réception, gestion des ports
- Différence UDP (rapide, non fiable) vs TCP (fiable, plus lent) — et pourquoi on choisit l'un ou l'autre selon le type de message
- Notion de thread / asyncio pour gérer plusieurs connexions en même temps sans bloquer l'application

### B. Cryptographie appliquée (tu as déjà une bonne base)
- RSA : génération de paires de clés, chiffrement/déchiffrement (bibliothèque `cryptography`, module `hazmat`)
- AES-GCM : tu l'as déjà pratiqué, mais ici en mode "clé de session éphémère" plutôt que mot de passe fixe
- Hashing (SHA-256) pour créer les adresses courtes
- Notion de "nonce" (ne jamais réutiliser le même avec la même clé AES)

### C. Audio
- Capture et lecture audio en Python (`sounddevice`)
- Notion d'échantillonnage (sample rate), de format audio (PCM)
- Compression avec un codec vocal (Opus) — pourquoi c'est nécessaire pour la bande passante

### D. Sérialisation / format binaire
- Module `struct` en Python : comment empaqueter des entiers/octets dans un format binaire compact
- JSON pour les cas où la lisibilité prime sur la taille

### E. Mobile (Android)
- Kivy : bases de l'interface (tu l'as déjà pratiqué avec JeAlgo)
- Buildozer : packaging APK (déjà fait aussi)
- Permissions Android (accès WiFi, micro, arrière-plan) et limites de l'arrière-plan depuis Android 8+
- `plyer` ou bibliothèques équivalentes pour accéder à l'état du WiFi depuis Kivy

---

## 4. FEUILLE DE ROUTE — étapes de construction, dans l'ordre

### Étape 0 — Préparation
- Environnement Python (venv), installation des bibliothèques (`cryptography`, `sounddevice`, etc.)
- Décider : TCP ou UDP pour les messages non-appel (à faire ensemble à la prochaine session)

### Étape 1 — Découverte (PC uniquement pour commencer)
- Un appareil annonce sa présence en broadcast UDP (nom + clé publique)
- Les autres appareils sur le même hotspot le détectent et l'affichent dans une liste

### Étape 2 — Échange de clés / établissement de session
- Générer la paire RSA à l'installation (simulation sur PC d'abord)
- Implémenter le message SESSION_INIT (clé AES chiffrée en RSA)

### Étape 3 — Message texte direct (sans relais)
- Deux appareils sur le même hotspot s'échangent un texte chiffré AES, limite 160 caractères

### Étape 4 — Relais à un seul saut
- Test avec 3 PC : A envoie à C en passant par B, avec `ttl`, `dest_hash`, `expire_at`

### Étape 5 — Table de rencontres et score de progression
- Chaque appareil garde en mémoire les `hash` croisés récemment avec un horodatage et un RSSI approximatif
- Logique de décision : "je garde ou je transmets ce message ?"

### Étape 6 — Message vocal découpé
- Enregistrement, découpage en morceaux, envoi, reconstruction uniquement si tous les morceaux arrivent

### Étape 7 — Appel en direct (flux audio continu)
- Format binaire compact, envoi UDP continu, limite 1 minute

### Étape 8 — Portage Android
- Adapter chaque brique validée sur PC vers Kivy/Buildozer

### Étape 9 — Test terrain à l'école
- Ajustement des limites (160 caractères, durée vocal/appel) selon usage réel
- Ajustement du TTL et du délai d'expiration selon la taille réelle du campus

---

*Prochaine étape suggérée : trancher TCP vs UDP pour les messages, puis attaquer l'Étape 1 (découverte).*

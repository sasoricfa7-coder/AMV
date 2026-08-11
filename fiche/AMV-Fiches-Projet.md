# AMV — Appel, Message, Vocaux
### Document de référence du projet

*Application de communication locale par WiFi mesh opportuniste, sans infrastructure*

---

## 1. FICHE APPLICATION

### Vision
AMV permet aux élèves et professeurs d'un même établissement de s'appeler, s'écrire et s'envoyer des messages vocaux **sans réseau mobile, sans routeur, sans crédit téléphonique**, en utilisant uniquement les hotspots WiFi des téléphones des utilisateurs comme infrastructure partagée. Le système est conçu pour pouvoir être adopté par d'autres écoles — chaque déploiement se reconnaît comme n'appartenant pas au même réseau "habituel".

### Fonctionnalités principales
| Fonction | Description | Limite |
|---|---|---|
| Appel vocal en direct | Communication en temps réel entre deux personnes à portée directe | 1 minute (à confirmer) |
| Message vocal | Enregistrement envoyé en différé, peut transiter par plusieurs relais | 40 secondes |
| Message texte | Texte court envoyé en différé, peut transiter par plusieurs relais | 160 caractères |
| Relais automatique | Chaque appareil avec l'application installée accepte de faire transiter les messages des autres, sans jamais pouvoir les lire | Consentement implicite à l'installation |
| Découverte de présence | Voir qui est disponible sur le hotspot auquel on est connecté | — |
| Notification d'échec | Si un message est détruit (TTL épuisé ou expiré), l'émetteur en est informé | — |
| Diffusion d'urgence | Un appareil qui s'éloigne de toute la zone diffuse en urgence ses messages en attente à n'importe quel relais visible, plutôt que de les emporter hors de portée | — |

### Principes acceptés à l'installation
- Choix d'un **nom d'affichage** court (juste une étiquette — voir fiche technique)
- Génération automatique d'une **paire de clés**, la clé privée étant gardée dans le stockage sécurisé matériel de l'appareil (Android Keystore / équivalent), **inaccessible même à l'application elle-même** — seules des opérations de signature/déchiffrement peuvent être demandées à la puce
- **Un seul compte par appareil**
- En installant l'app, l'utilisateur **accepte de servir de relais** pour les messages des autres
- L'application encourage l'activation du point d'accès WiFi (ne peut pas l'activer automatiquement — limitation Android) mais garde le WiFi client actif en permanence

### Anti-contrefaçon
Chaque version officielle de l'application est signée numériquement par une clé que le créateur possède seul (même principe que la puce d'une carte bancaire). Chaque appareil vérifie cette signature avant d'accepter de communiquer avec un autre — une version modifiée ou pirate est automatiquement rejetée par le réseau.

### Contraintes assumées
- Pas de garantie de livraison instantanée pour les messages relayés
- Pas d'accusé de réception "lu" façon WhatsApp (trop coûteux en bande passante) — seulement une notification d'échec si le message n'arrive jamais
- Tous les messages/vocaux non arrivés sont supprimés à **18h00**, et de toute façon au plus tard 3h après leur envoi
- Pas de compte multi-appareils

---

## 2. FICHE TECHNIQUE

### Architecture générale — moteur natif + interface web locale
Le cœur réseau (découverte, chiffrement, relais) doit être un programme natif : un navigateur ne peut pas ouvrir de sockets bruts, lire le WiFi, ou tourner fiablement en arrière-plan. On sépare donc :

- **Le moteur (Python)** — géré par Sasori : réseau (sockets UDP/TCP), chiffrement, logique de relais, table de rencontres, gestion des clés. Expose une petite API locale via un serveur web embarqué (Flask).
- **L'interface (HTML/CSS/JS)** — gérée par Claude : boutons, liste de contacts, bulles de messages, écran d'appel. Communique avec le moteur Python via `localhost` uniquement.
- **Emballage "application"** :
  - PC : `pywebview` (fenêtre native contenant l'interface, sans barre d'adresse de navigateur)
  - Android : Kivy (déjà maîtrisé via JeAlgo) avec une WebView interne affichant la même interface

### Pile technique
| Composant | Choix | Pourquoi |
|---|---|---|
| Langage moteur | Python | Compétence de Sasori |
| Interface | HTML/CSS/JS via serveur local Flask | Compétence de Claude, ressenti "application" |
| Chiffrement asymétrique | RSA (`cryptography`) | Standard, bien documenté |
| Chiffrement symétrique | AES-256-GCM | Déjà pratiqué (projet seed phrase) |
| Stockage clé privée | Android Keystore / stockage matériel sécurisé (mobile), clé chiffrée par mot de passe local (PC) | Empêche l'extraction de la clé, même par l'app elle-même |
| Générateur aléatoire sûr | module `secrets` | Cryptographiquement sûr |
| Hash pour adresses | SHA-256 tronqué (16 octets) | Léger, standard |
| Découverte | UDP broadcast | Annonce de présence sur le hotspot |
| Messages/vocaux relayés | TCP (par saut) | Livraison intacte garantie à chaque saut sans réinventer un système de renvoi |
| Appel en direct | UDP | Priorité à la latence, perte tolérée |
| Codec audio | Opus | Compression forte, conçu pour la voix |
| Sérialisation légère | JSON | Découverte, session, texte |
| Sérialisation compacte | `struct` (binaire) | Flux d'appel en direct |
| Signature anti-contrefaçon | Signature numérique de l'app (type signature APK renforcée) | Rejette les versions modifiées |
| Portage Android | Kivy + Buildozer + WebView | Expérience déjà acquise avec JeAlgo |

### Format de paquet — champs définitifs
| Champ | Taille/Type | Rôle |
|---|---|---|
| `type` | 1 octet | DISCOVERY / SESSION_INIT / TEXT / VOICE_CHUNK / CALL_AUDIO / NOTIFY_ECHEC |
| `message_id` | timestamp + nombre aléatoire (`secrets`) | Identifiant unique |
| `dest_hash` | 16 octets (SHA-256 tronqué clé publique destinataire) | Adresse de routage |
| `sender_hash` | 16 octets | Adresse de routage émetteur (pour réponses et NOTIFY_ECHEC) |
| `ttl` | 1 octet, valeur de départ **12** | Sauts restants, décrémenté à chaque relais |
| `expire_at` | timestamp | Création + 3h maximum (ou 18h si plus tôt) |
| `chunk_index` / `chunk_total` | 1-2 octets | Uniquement pour vocaux découpés |
| `payload_chiffré` | variable | AES-GCM (nonce + texte chiffré + tag) |
| `session_key_chiffrée` | variable, SESSION_INIT uniquement | Clé AES chiffrée avec RSA du destinataire |

### Logique de routage
1. Relais reçoit un paquet, lit uniquement les champs en clair.
2. `ttl == 0` ou expiré → paquet détruit, un `NOTIFY_ECHEC` est généré et routé vers `sender_hash`.
3. `dest_hash` = l'appareil lui-même → traitement local (déchiffrement, affichage).
4. Sinon → consultation de la table de rencontres locale (RSSI + historique) pour choisir de garder ou transmettre.
5. **Mode diffusion d'urgence** : si le signal de tous les hotspots connus faiblit simultanément (l'appareil quitte la zone), tous les messages en attente sont immédiatement envoyés au premier relais visible, sans attendre un meilleur candidat.
6. **Propagation sans déplacement humain** : un appareil situé dans une zone de recouvrement entre deux hotspots peut cycler automatiquement sa connexion entre les deux réseaux (quelques secondes sur chacun) pour relayer sans qu'un humain ait besoin de se déplacer — mais cela nécessite qu'au moins un appareil soit physiquement présent dans la zone de recouvrement.

### Sécurité — règles non négociables
- Un relais ne stocke et ne transmet que des données déjà chiffrées.
- La clé privée ne quitte jamais la puce sécurisée de l'appareil — même l'application ne peut pas la lire directement.
- L'identité réelle = la clé publique. Le nom choisi n'est qu'une étiquette locale.
- L'application vérifie la signature numérique de son propre code / des autres appareils avant toute communication.

---

## 3. FICHE "QUOI APPRENDRE" — par domaine

### A. Réseau
- Sockets UDP/TCP en Python (`socket` standard) : broadcast, connexions, ports
- Threading/asyncio pour gérer plusieurs connexions sans bloquer
- Notion de client web local (Flask) pour exposer une API à l'interface

### B. Cryptographie appliquée
- RSA (génération, chiffrement/déchiffrement) via `cryptography`
- AES-GCM en mode clé de session éphémère
- SHA-256 pour les adresses courtes
- Signature numérique (différent du chiffrement — vérifie l'authenticité, pas la confidentialité)
- Notion de stockage sécurisé matériel (Keystore)

### C. Audio
- Capture/lecture (`sounddevice`)
- Échantillonnage, format PCM
- Compression Opus

### D. Sérialisation
- `struct` pour le binaire compact
- JSON pour la lisibilité pendant le développement

### E. Mobile / emballage "application"
- Kivy + WebView (déjà en partie maîtrisé via JeAlgo)
- Buildozer (déjà pratiqué)
- `pywebview` pour la version PC

### F. Ce que Claude prend en charge
- Toute l'interface HTML/CSS/JS (boutons, listes, bulles de messages, écran d'appel)
- L'intégration de cette interface avec le serveur Flask local de Sasori

---

## 4. FEUILLE DE ROUTE

### Étape 0 — Préparation
- Environnement Python (venv), bibliothèques (`cryptography`, `sounddevice`, `flask`)
- Choix confirmé : UDP pour découverte/appel, TCP pour messages/vocaux relayés

### Étape 1 — Découverte (PC uniquement pour commencer)
- Annonce de présence en broadcast UDP (nom + clé publique)
- Affichage de la liste des appareils détectés

### Étape 2 — Échange de clés / session
- Génération de la paire RSA (simulation stockage sécurisé sur PC)
- Implémentation SESSION_INIT (clé AES chiffrée en RSA)

### Étape 3 — Message texte direct (sans relais)
- Échange chiffré AES entre deux appareils sur le même hotspot, 160 caractères

### Étape 4 — Relais à un seul saut
- Test avec 3 PC : `ttl`, `dest_hash`, `expire_at`, `NOTIFY_ECHEC`

### Étape 5 — Table de rencontres et diffusion d'urgence
- Mémoire des `hash` croisés récemment (horodatage + RSSI approximatif)
- Logique de décision garder/transmettre
- Détection de perte de signal généralisée → diffusion d'urgence

### Étape 6 — Message vocal découpé
- Enregistrement, découpage, reconstruction uniquement si tous les morceaux arrivent (40s max)

### Étape 7 — Appel en direct
- Flux binaire compact, UDP continu, 1 minute (à confirmer)

### Étape 8 — Interface web locale
- Serveur Flask exposant l'API du moteur
- Claude construit l'interface HTML/CSS/JS par-dessus

### Étape 9 — Emballage "application"
- PC : `pywebview`
- Android : Kivy + WebView + Buildozer

### Étape 10 — Test terrain à l'école
- Ajustement des limites et délais selon usage réel

---

*Prochaine étape suggérée : confirmer la durée d'appel, puis attaquer l'Étape 1 (découverte).*


from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization as seria
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM as AES

import sys
import socket as sc
import time as tm
import threading as tr
import secrets as sr
import os   
import base64 as b64

def dechiffrer_aes(cle_aes_chiffree, ma_cle_privee) :
    cle_dechiffree = ma_cle_privee.decrypt(
        cle_aes_chiffree,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return cle_dechiffree

def sauvegarde_recharge() :
    mon_fichier = "id.txt"

    if os.path.exists(mon_fichier) :
        with open(mon_fichier, "r", encoding="utf-8") as f :
            return f.read().strip()
    else :
        mon_id = sr.token_hex(8)
        with open(mon_fichier, "w") as f :
            f.write(mon_id)
        return mon_id
         
def generation_rsa() :
    mon_fichier = "private_key.pem"

    if os.path.exists(mon_fichier) :
        with open(mon_fichier, "rb") as f :
            cle = seria.load_pem_private_key(f.read() , password=None)
            return cle
    else :
        # Création d'une nouvelle clé privée
        nouvelle_cle_prive = rsa.generate_private_key(
            public_exponent = 65537,
            key_size = 2048
        )

        sauvegarde = nouvelle_cle_prive.private_bytes(
            encoding = seria.Encoding.PEM,
            format=seria.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=seria.NoEncryption()
        )

        with open(mon_fichier, "wb") as f :
            f.write(sauvegarde)
            return nouvelle_cle_prive

def transforme_base_64(ma_cle_publique) :
    pem_bytes = ma_cle_publique.public_bytes(
        encoding=seria.Encoding.PEM,
        format=seria.PublicFormat.SubjectPublicKeyInfo
    )
    return b64.b64encode(pem_bytes).decode('utf-8')

def chiffrer_aes(cle_aes, cle_publique_b64) :
    # On decode la base 64 en octet
    pem_bytes = b64.b64decode(cle_publique_b64)

    # On recharge la clé publique rsa
    cle_publique = seria.load_pem_public_key(pem_bytes)
    # 3. On chiffre la clé AES avec la méthode OAEP recommandée

    cle_chiffree = cle_publique.encrypt(
        cle_aes,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return cle_chiffree

def traiter_cas_message(id_destinataire, reste) :
    global appareils_vus, sessions, table_rencontre
    with verrou :
        if id_destinataire in appareils_vus :
            nom = appareils_vus[id_destinataire]["nom"]
        elif id_destinataire in table_rencontre :
            nom = table_rencontre[id_destinataire]["nom"]
        else :
            nom = "Inconnu"

        if not session_valide(id_destinataire) :
            print(f"Pas de clé de session {id_destinataire}")
            return
        cle = sessions[id_destinataire]
    texte = dechiffrer_message((reste[:12]), (reste[12:]), cle )
                    
    print(f"\n {nom} : {texte}")
        
def ecouter_tcp() :
    global sessions, ma_cle_prive, port_optionnel, appareils_vus, mon_id, sessions_instance
    s_tcp = sc.socket(sc.AF_INET, sc.SOCK_STREAM)
    s_tcp.setsockopt(sc.SOL_SOCKET, sc.SO_REUSEADDR, 1)
    s_tcp.bind(('', port_optionnel))
    s_tcp.listen(5) 

    with verrou :
        id_tempo = mon_id

    while True :
        try :
            connexion, adresse = s_tcp.accept()
            # 1. On reçoit la taille du message (4 octets)
            taille_donnees = connexion.recv(4)
            if not taille_donnees:
                connexion.close()
                continue
            taille_message = int.from_bytes(taille_donnees, 'big')

            # 2. Boucle sécurisée pour accumuler exactement le nombre d'octets attendus
            donnees_chiffrees = b""
            while len(donnees_chiffrees) < taille_message :
                morceau = connexion.recv(taille_message - len(donnees_chiffrees))
                if not morceau:
                    break
                donnees_chiffrees += morceau

            type_message = int (donnees_chiffrees[0])
            reste = donnees_chiffrees[1:]
            #print(f"Tout - type_message : {len(reste)}")
            id_destinataire = (reste[:16]).decode("utf-8")
            reste = reste[16:]

            match type_message : # Avec match l'ajout d'un nouveau type de donnée est facile

                case 1 :
                    cle = dechiffrer_aes(reste, ma_cle_prive)
                    print(f"\n[TCP] Clé AES reçue avec succès de {id_destinataire} depuis {adresse[0]} ! Taille : {taille_message} octets.")
                    with verrou :
                        sessions[id_destinataire] = cle
                        sessions_instance[id_destinataire] = (
                            appareils_vus.get(id_destinataire, {}).get("instance")
                            or table_rencontre.get(id_destinataire, {}).get("instance")
                        )   

                case 2 :
                    traiter_cas_message(id_destinataire, reste)                    

                case 3 : # La j'ai l'ID du destinataire final et aussi le reste qui contient l'idée de l'émetteur
        
                    id_emeteur = reste[:16].decode("utf-8")
                    reste = reste[16:]

                    compteur = int(reste[0])
                    reste = reste[1:]
                    type_message = int(reste[0])
                    reste = reste[1:]

                    if compteur <= 1 :
                        print("[Routage] Message jeté (TTL expiré)")
                        connexion.close()
                        continue

                    compteur -= 1
                    
                    if id_destinataire != id_tempo :

                        # Étape 1 : est-ce que je connais le destinataire en direct ?
                        with verrou :
                            direct = id_destinataire in appareils_vus
                            if direct :
                                ip = appareils_vus[id_destinataire]["ip"]
                                port = int(appareils_vus[id_destinataire]["port"])

                        if not direct :                    
                            id_relais = prepare_envoi_relais(id_destinataire)
                            with verrou :
                                if id_relais == "" or id_relais not in appareils_vus :
                                    print("[Routage] Destinataire hors de portée.")
                                    connexion.close()
                                    continue
                                ip = appareils_vus[id_relais]["ip"]
                                port = int(appareils_vus[id_relais]["port"])


                        tout = construire_envellope_relais(id_destinataire, id_emeteur, compteur, type_message, reste)
                        taille = renvoi_taille(tout)
                        valide = envoi_tout(port, ip, taille, tout)

                        if not valide :
                            print("Echec d'envoie")
                            connexion.close()
                            continue

    #produit_final = type_indication + destinataire_final + mon_propre_id + compteur + type_message + message_chiffrer
                    else :
                        match type_message :
                            case 1 :
                                cle = dechiffrer_aes(reste, ma_cle_prive)
                                print(f"\n[TCP] Clé AES reçue avec succès de {id_emeteur}! Taille : {taille_message} octets.")
                                print(f"\n Clé : {cle.hex()}")
                                with verrou :
                                    sessions[id_emeteur] = cle      
                                    sessions_instance[id_emeteur] = (
                                        appareils_vus.get(id_emeteur, {}).get("instance")
                                        or table_rencontre.get(id_emeteur, {}).get("instance")
                                    )                         
                            case 2 :
                                traiter_cas_message(id_emeteur, reste)

            connexion.close()
        except Exception as e :
            print(e)

def envoyer_cle_session(id_destinataire) :
    global appareils_vus, sessions, table_rencontre

    with verrou :
        if id_destinataire in appareils_vus :
            cle_public = appareils_vus[id_destinataire] ["Clé_publique"]
            direct = True
        elif id_destinataire in table_rencontre :
            cle_public = table_rencontre[id_destinataire]["cle_pub_b64"]
            direct = False
        else : 
            print("Le destinataire n'est pas en ligne.")
            return

    # 1. Génération de la clé AES aléatoire
    cle_aes = sr.token_bytes(32)
        
    # 2. Chiffrement de la clé AES avec la clé publique RSA du destinataire
    cle_aes_chiffree = chiffrer_aes(cle_aes, cle_public)

    paquet_interne = b'\x01' + mon_id.encode("utf-8") + cle_aes_chiffree

    if direct == True :
        message = paquet_interne
        with verrou :
            ip_dest = appareils_vus[id_destinataire] ["ip"]
            port_dest = int(appareils_vus[id_destinataire]["port"])
        taille_message = len(message)
        taille_message_bytes = taille_message.to_bytes(4, 'big')

        valide = envoi_tout(port_dest, ip_dest, taille_message_bytes, message)

    else :
        id_relais = prepare_envoi_relais(id_destinataire)
        if id_relais == "" :
            print("Destinataire hors ligne.")
            return
        message = construire_envellope_relais(id_destinataire, mon_id, 3, 1, cle_aes_chiffree)
            
        with verrou :
            ip_dest = appareils_vus[id_relais]["ip"]
            port_dest = int(appareils_vus[id_relais]["port"])
        taille_message = len(message)
        taille_message_bytes = taille_message.to_bytes(4, 'big')

        valide = envoi_tout(port_dest, ip_dest, taille_message_bytes, message)

    if valide != False :
        with verrou :
            sessions[id_destinataire] = cle_aes
            sessions_instance[id_destinataire] = (
                appareils_vus.get(id_destinataire, {}).get("instance")
                or table_rencontre.get(id_destinataire, {}).get("instance")
            )
        print(f"Clé AES envoyée à {id_destinataire}")
    else :
        print("Echec d'envoi")
    return valide
            
        


#-----------------------------------------------------------------------------------------------------------------------------
verrou = tr.Lock()

nom = input("Entrez votre nom d'affichage : ").strip()
while nom == "" or "|" in nom or ";" in nom or ":" in nom :
    print("Nom invalide (pas de |, ; ou :).")
    nom = input("Entrez votre nom d'affichage : ").strip()
    
mon_id = sauvegarde_recharge()
numero_instance = sr.token_hex(4)
ma_cle_prive = generation_rsa()
ma_cle_publique = ma_cle_prive.public_key()
ma_cle_publique_b64 = transforme_base_64(ma_cle_publique)

port_optionnel = 55555
if len(sys.argv) > 1 :
    port_optionnel = int(sys.argv[1])

nom_final = mon_id + "|" + nom + "|" + ma_cle_publique_b64 + "|" + str(port_optionnel) + "|" + numero_instance
ip = None
dernier_vu = tm.time()
appareils_vus = {} 
sessions = {} 
table_rencontre = {}
sessions_instance = {}
index_rotation = 0
#------------------------------------------------------------------------------------------------------------------------------

def purge_19h() :
    global appareils_vus, sessions, table_rencontre, sessions_instance, numero_instance, nom_final
    t0 = tm.localtime()
    derniere_purge = (t0.tm_year, t0.tm_mon, t0.tm_mday)
    while True :
        t = tm.localtime()
        jour = (t.tm_year, t.tm_mon, t.tm_mday)
        if t.tm_hour == 19 and derniere_purge != jour :
            with verrou :
                appareils_vus.clear()
                sessions.clear()
                table_rencontre.clear()
                sessions_instance.clear()
            derniere_purge = jour
            numero_instance = sr.token_hex(4)
            nom_final = mon_id + "|" + nom + "|" + ma_cle_publique_b64 + "|" + str(port_optionnel) + "|" + numero_instance
            print("\n[Purge] 19h00 — tout a été réinitialisé.")
        tm.sleep(20)

def session_valide(id_cible) :
    # ⚠️ À appeler SOUS verrou
    if id_cible not in sessions :
        return False

    if id_cible in appareils_vus :
        instance_actuelle = appareils_vus[id_cible].get("instance")
    elif id_cible in table_rencontre :
        instance_actuelle = table_rencontre[id_cible].get("instance")
    else :
        instance_actuelle = None

    instance_stockee = sessions_instance.get(id_cible)

    if instance_actuelle is not None and instance_stockee is not None and instance_actuelle != instance_stockee :
        del sessions[id_cible]
        if id_cible in sessions_instance :
            del sessions_instance[id_cible]
        return False

    return True

def ecouter() :
    global appareils_vus, mon_id, sessions, sessions_instance
    s_ecoute = creer_sc()
    s_ecoute.bind(('', 12345))
    while True :
        try :
            donnee, adresse_ip = s_ecoute.recvfrom(4096)
            donnee = donnee.decode("utf-8")
            L = donnee.split("|")
            if len(L) >= 5 :
                if L[0] == mon_id :
                    continue
                id_emeteur = L[0]
                instance_recue = L[4]

                with verrou :
                    ancienne = sessions_instance.get(id_emeteur)
                    if ancienne is not None and ancienne != instance_recue :
                        if id_emeteur in sessions :
                            del sessions[id_emeteur]
                        del sessions_instance[id_emeteur]
                        print(f"[Session] {id_emeteur} a redémarré, session invalidée")

                    appareils_vus[id_emeteur] = {
                        "nom" : L[1],
                        "ip" : adresse_ip[0],
                        "Clé_publique" : L[2],
                        "dernier_vu" : tm.time(),
                        "port" : int(L[3]),
                        "instance" : instance_recue
                    }
            else :
                pass
        except Exception as e :
            print(e)

def ecouter_table() :
    global appareils_vus, mon_id, table_rencontre
    s_ecoute = creer_sc()
    s_ecoute.bind(('', 54321))
    with verrou :
        id_tempo = mon_id
    while True :
        try :
            donnee, adresse_ip = s_ecoute.recvfrom(4096)
            donnee = donnee.decode("utf-8")
            L = donnee.split(";")

            if len(L) >= 2 :
                id_emeteur = L[0]

                if id_emeteur == id_tempo :
                    continue
                if not L[1:] :
                    continue

                entrees = L[1:]

                for i in entrees :
                    morceau = i.split(":", 5)
                    
                    if len(morceau) < 6 :
                        continue
                        
                    id_cible = morceau[0]
                    timestamp = float(morceau[1])
                    ttl = int(morceau[2]) - 1
                    cle_pub_b64 = morceau[3]
                    nom_cible = morceau[4]
                    instance_cible = morceau[5]
                    if ttl <= 0 :
                        continue

                    with verrou :
                        if  (id_cible in table_rencontre and table_rencontre[id_cible]["dernier_vu"]  > timestamp) :
                            continue
                        if (id_cible in appareils_vus) or (id_cible == id_tempo) :
                            continue

                        table_rencontre[id_cible] = {
                            "cle_pub_b64" : cle_pub_b64 ,
                            "dernier_vu" : timestamp,
                            "saut_restant" : ttl,
                            "nom"         : nom_cible,
                            "via" : id_emeteur,
                            "instance"    : instance_cible,
                        } 

        except Exception as e :
            print(e)

def les_ouvriers() :
    ouvrier_emeteur = tr.Thread(target=emettre, daemon=True)
    ouvrier_emeteur.start()
    ouvrier_recepteur = tr.Thread(target=ecouter, daemon=True)
    ouvrier_recepteur.start()
    ouvrier_presence = tr.Thread(target=liste_présence, daemon=True)
    ouvrier_presence.start()
    ouvrier_tcp = tr.Thread(target=ecouter_tcp, daemon=True)
    ouvrier_tcp.start()
    ouvrier_table_rencontre = tr.Thread(target=nettoyer_table_renconte, daemon=True)
    ouvrier_table_rencontre.start()
    ouvrier_ecouter_table = tr.Thread(target=ecouter_table, daemon=True)
    ouvrier_ecouter_table.start()
    ouvrier_emmission_table = tr.Thread(target=emission_table, daemon=True)
    ouvrier_emmission_table.start()
    ouvrier_purge = tr.Thread(target=purge_19h, daemon=True)
    ouvrier_purge.start()
    
def nettoyer_table_renconte() : # je ferai d'abord le plus simple avant de voir ecouter
    global table_rencontre
    
    try : 
        while True :
            with verrou :
                for i in list(table_rencontre) :
                    if (tm.time() - table_rencontre[i]["dernier_vu"] >= 60) :
                        del table_rencontre[i]
            tm.sleep(3)

    except Exception as e :
        print(e)

def emission_table() :
    global appareils_vus, mon_id, index_rotation
    s = creer_sc()
    adresse = '<broadcast>'
    port_gossip = 54321

    while True :
        tm.sleep(3)
        candidat = []

        with verrou :
            id_tempo = mon_id
            indirect = dict(table_rencontre)
            tout_appareils = dict(appareils_vus)

        voisin_direct = []
        for i in tout_appareils :
            voisin_direct.append(i)

        if voisin_direct :
            for i in voisin_direct :
                morceau = f"{i}:{tm.time()}:3:{tout_appareils[i]['Clé_publique']}:{tout_appareils[i]['nom']}:{tout_appareils[i]['instance']}"
                candidat.append(morceau)

        if indirect :
            for i, info in indirect.items() :
                morceau = f"{i}:{info['dernier_vu']}:{info['saut_restant']}:{info['cle_pub_b64']}:{info['nom']}:{info['instance']}"
                candidat.append(morceau)

        if candidat :
            candidat.sort()
            n = len(candidat)
            selection = []
            for k in range(min(3, n)) :
                indice = (index_rotation + k) % n 
                selection.append(candidat[indice])
                
            index_rotation = (index_rotation + 3) % n
            donnee_final = id_tempo + ";" + ";".join(selection)
            
        else :
            donnee_final = id_tempo
        try :
            s.sendto(donnee_final.encode("utf-8"), (adresse, port_gossip))
                
        except Exception as e :
            print(e)

def liste_présence() :
    global appareils_vus
    try :
        while True :
            with verrou :
                for i in list(appareils_vus) :
                    if (tm.time() - appareils_vus[i]["dernier_vu"]) >= 10 :
                        del appareils_vus[i]
            tm.sleep(3)
    except Exception as e :
        print(e)
        pass
    
def emettre() :
    global nom_final
    s = creer_sc()
    donnee = nom_final.encode('utf-8')
    adresse = '<broadcast>'
    port = 12345
    while True :
        s.sendto(donnee, (adresse, port))
        tm.sleep(3)

def creer_sc() :
    s = sc.socket(sc.AF_INET, sc.SOCK_DGRAM)
    s.setsockopt(sc.SOL_SOCKET, sc.SO_REUSEADDR, 1)
    s.setsockopt(sc.SOL_SOCKET, sc.SO_BROADCAST, 1)
    return s

def chiffrer_message(texte, cle_session) :
    # On génère le nonce unique de 12 octets
    nonce = sr.token_bytes(12)
    texte_octets = texte.encode("utf-8")
    
    # On chiffre avec la vraie clé AES de session (32 octets) et le nonce
    texte_chiffre = AES(cle_session).encrypt(nonce, texte_octets, None)
    return nonce, texte_chiffre

def dechiffrer_message(nonce, texte_chiffre, cle_session) :
    try :
        texte_dechiffre = AES(cle_session).decrypt(nonce, texte_chiffre, None)
        return texte_dechiffre.decode("utf-8")
    except Exception as e :
        # En cas de corruption ou de mauvaise clé/nonce
        print(e)
        return None     

def envoi_tout(port, ip, m1, m2="") :

        # 3. Connexion TCP vers le port spécifique du destinataire
        try :
            s_client = sc.socket(sc.AF_INET, sc.SOCK_STREAM)
            s_client.connect((ip, port))
        
            s_client.sendall(m1)
            if m2 != "" :
                s_client.sendall(m2) 
            s_client.close()

            return True

        except Exception as e :
            print(e)
            return False
            
def construire_envellope_relais(destinataire_final, mon_propre_id, compteur, type_message, message_chiffrer) :
    type_indication = b'\x03'
    destinataire_final = destinataire_final.encode("utf-8")
    mon_propre_id = mon_propre_id.encode("utf-8")
    compteur = compteur.to_bytes(1, "big")
    type_message = type_message.to_bytes(1, "big")

    produit_final = type_indication + destinataire_final + mon_propre_id + compteur + type_message + message_chiffrer
    return produit_final

def prepare_envoi_relais(id_destinataire) :
    global table_rencontre, appareils_vus
    with verrou :
        if id_destinataire not in table_rencontre :
            return ""
        via = table_rencontre[id_destinataire]["via"]
        if (appareils_vus) and (via in appareils_vus) :
            return via
        if not appareils_vus :
            return ""
        return next(iter(appareils_vus))


def prepare_envoi() : # le but lui il doit s'assurer que tout est bon
    global appareils_vus, sessions, mon_id

    valide = True # Pour eviter les failles 
    id_destinataire = input("Entrez l'ID du destinaitaire : ").strip()

    print("Info : le message doit être non vide et maximum 80 caractères")
    message = input("Entrez votre message : ").strip()
    while message == "" or len(message) > 80 : # Car on peut se tromper appuyer sur entrée
        print("Message invalide")
        message = input("Entrez votre message : ").strip()

    # --- 1. Décider la route ---
    with verrou :
        if id_destinataire == mon_id :
            print(f"{message}")
            return
        if id_destinataire in appareils_vus :
            route = "direct"
        elif id_destinataire in table_rencontre :
            route = "relais"
        else :
            route = "inconnu"
    if route == "inconnu" :
        print("Destinataire hors de portée.")
        return

    # --- 2. Négociation de session si besoin (HORS verrou) ---
    with verrou :
        besoin = not session_valide(id_destinataire)
    if besoin :
        valide = envoyer_cle_session(id_destinataire)
        if not valide :
            print("Échec de la négociation de session")
            return

    # --- 3. Récupérer la clé AES ---
    with verrou :
        if id_destinataire not in sessions :
            print("Session perdue entre-temps.")
            return
        cle = sessions[id_destinataire]

    # --- 4. Chiffrer le message ---
    nonce, texte = chiffrer_message(message, cle)  
    message_chiffrer = nonce + texte

    # --- 5. Construire le paquet final ---
    if route == "direct" :
        tout = b'\x02' + mon_id.encode("utf-8") + message_chiffrer # ici pourquoi on n'a pas encoder message ??
        id_choisi = id_destinataire
    else :
        id_relais = prepare_envoi_relais(id_destinataire)
        if not id_relais :
            print("Aucun relais disponible")
            return
        tout = construire_envellope_relais(id_destinataire, mon_id, 3, 2, message_chiffrer)
        id_choisi = id_relais

    with verrou :
        if id_choisi not in appareils_vus :
            print("[Envoi] Destinataire disparu entre-temps.")
            return
        ip = appareils_vus[id_choisi]["ip"]
        port = int(appareils_vus[id_choisi]["port"])

    # --- 6. Envoyer ---
    taille = renvoi_taille(tout)
    valide = envoi_tout(port, ip, taille, tout)
    if not valide :
        print("Échec d'envoi")
        return

def renvoi_taille(tout) : # Je vais le garder malgré et aussi les sous fonctions m'aident à mieux me repérer
    taille_message = len(tout)
    taille_message_bytes = taille_message.to_bytes(4, 'big')
    return taille_message_bytes 


def affichage() :
    print(f"{nom}")
    print("\n--- MENU ---\n")
    print("1. Afficher les appareils connectés")
    print("2. Envoyer un message")
    print("3. Nettoyer l'écran")
    print("4. Quitter")

def menu() :
    global appareils_vus , table_rencontre
    with verrou :
        direct = dict(appareils_vus)
        indirect = dict(table_rencontre)

    if not direct and not indirect :
        print("Aucun appareil détecté pour le moment.")
        return
        
    if direct :
        print("\n--- Appareils directs ---")
        for identifiant, info in direct.items() :
            print(f"[DIRECT]   ID: {identifiant} | Nom: {info['nom']} | IP: {info['ip']} | Port: {info['port']}")
    if indirect :
        print("\n--- Contacts indirects (via gossip) ---")
        for identifiant, info in indirect.items() :
            print(f"[INDIRECT] ID: {identifiant} | Nom: {info['nom']} | TTL: {info['saut_restant']} | via: {info['via']}")
        

def main():
    les_ouvriers()
    
    tm.sleep(1) 

    while True :
        affichage()
        choix = input("Votre choix : ").strip()

        match choix :
            case "1" :
                menu()

            case "2" :
                prepare_envoi()

            case "3" : 
                os.system("clear")
            case "4" :
                print("Fermeture du programme...")
                return
            case _ :
                print("Choix invalide, réessayez.")

if __name__ == "__main__":
    main()

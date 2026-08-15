
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
        
def ecouter_tcp() :
    global sessions, ma_cle_prive, port_optionnel, appareils_vus, mon_id
    s_tcp = sc.socket(sc.AF_INET, sc.SOCK_STREAM)
    s_tcp.setsockopt(sc.SOL_SOCKET, sc.SO_REUSEADDR, 1)
    s_tcp.bind(('', port_optionnel))
    s_tcp.listen(5) 

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
            print(f"Tout - type_message : {len(reste)}")
            id_destinataire = (donnees_chiffrees[:16]).decode("utf-8")
            reste = donnees_chiffrees[16:]

            match type_message : # Avec match l'ajout d'un nouveau type de donnée est facile

                case 1 :
                    cle = dechiffrer_aes(reste, ma_cle_prive)
                    print(f"\n[TCP] Clé AES reçue avec succès de {id_destinataire} depuis {adresse[0]} ! Taille : {taille_message} octets.")
                    print(f"\n Clé : {cle.hex()}")
                    with verrou :
                        sessions[id_destinataire] = cle

                case 2 :
                    
                    with verrou :
                        nom = appareils_vus[id_destinataire]["nom"]
                        cle = sessions[id_destinataire]
                    texte = dechiffrer_message((reste[:12]), (reste[12:]), cle )
                    
                    print(f"\n {nom} : {texte}")

                case 3 : # La j'ai l'ID du destinataire final et aussi le reste qui contient l'idée de l'émetteur
                    id_emeteur = reste[:16].decode("utf-8")
                    reste = reste[16:] # On retir l'ID de l'émetteur car ca ne nous sert pas.
                    print(f"Tout - type_message - id_emeteur : {len(reste)}")
                    compteur = int(reste[0])
                    if compteur == 0 :
                        print("Message jeté")
                        continue
                    reste = reste[1:] # On supprime aussi le compteur donc il ne reste  : Type de message et message chiffré
                    print(f"Tout - type_message - id_emeteur - TTL : {len(reste)}")
                    if id_destinataire != mon_id : # Je gère d'abord le cas ou je ne suis qu'un seul simple relais
                        with verrou :
                            if id_destinataire not in appareils_vus :
                                print("Echec : Destinataire n'est pas en ligne")
                                continue
                            else :
                                port = appareils_vus[id_destinataire]["port"]
                                ip = appareils_vus[id_destinataire]["ip"]
                                
                        compteur -= 1 # Ici je décremente le compteur
                        tout = (b'\x02') + id_emeteur.encode("utf-8") + reste # ici le type est remis à 2
                        taille = renvoi_taille(tout)
                        valide = envoi_tout(port, ip, taille, tout)
                        if not valide :
                            print("Echec d'envoi")
                            continue

                    else :
                        type_message = int (reste[0])
                        reste = reste[1:]
                        print("Reste qui arrive chez le bon destinataire - type de message {len(reste)}")
                        match type_message :
                            case 2 : # Je pense dans l'avenir quand on ajoutera les vocaux ou autres
                                with verrou :
                                    nom = appareils_vus[id_emeteur]["nom"]
                                    cle = sessions[id_emeteur]
                                texte = dechiffrer_message((reste[:12]), (reste[12:]), cle )
                    
                                print(f"\n {nom} : {texte}")  

            connexion.close()
        except Exception as e :
            print(e)

def envoyer_cle_session(id_destinataire) :
    global appareils_vus, sessions

    #with verrou : ca sera à son appel qu'on met le verrou
    info_appareil = appareils_vus[id_destinataire]
        
    ip_dest = info_appareil["ip"]
    cle_pub_b64 = info_appareil["Clé_publique"]
    port_dest = int(info_appareil["port"])

    # 1. Génération de la clé AES aléatoire
    cle_aes = sr.token_bytes(32)
    
    # 2. Chiffrement de la clé AES avec la clé publique RSA du destinataire
    cle_aes_chiffree = chiffrer_aes(cle_aes, cle_pub_b64)
    
    try :
        
        # 4. Envoi de la taille puis du message complet
        id_coder = mon_id.encode("utf-8")
        message = (b'\x01') + id_coder + cle_aes_chiffree
        taille_message = len(message)
        taille_message_bytes = taille_message.to_bytes(4, 'big')

        valide = envoi_tout(port_dest, ip_dest, taille_message_bytes, message)

        if valide :
            # 5. Stockage local de la clé AES dans les sessions
            #with verrou :  ca sera à son appel qu'on met le verrou
            sessions[id_destinataire] = cle_aes
            
            print(f"\n[TCP] Clé AES générée et envoyée avec succès à {info_appareil['nom']} ({ip_dest}:{port_dest}) !")
            print(f"\n Clé : {cle_aes.hex()}")
            return valide
        else :
            return valide 
        
    except Exception as e :
        print(f"\n[Erreur TCP] Impossible d'envoyer la clé : {e}")


#-----------------------------------------------------------------------------------------------------------------------------
verrou = tr.Lock()
nom = input("Entrez votre nom d'affichage : ")
while nom == "" :
    nom = input("Entrez votre nom d'affichage : ")
    
mon_id = sauvegarde_recharge()
ma_cle_prive = generation_rsa()
ma_cle_publique = ma_cle_prive.public_key()
ma_cle_publique_b64 = transforme_base_64(ma_cle_publique)

port_optionnel = 55555
if len(sys.argv) > 1 :
    port_optionnel = int(sys.argv[1])

nom_final = mon_id + "|" + nom + "|" + ma_cle_publique_b64 + "|" + str(port_optionnel)
ip = None
dernier_vu = tm.time()
appareils_vus = {} 
sessions = {} 
#------------------------------------------------------------------------------------------------------------------------------


def ecouter() :
    global appareils_vus, mon_id
    s_ecoute = creer_sc()
    s_ecoute.bind(('', 12345))
    while True :
        try :
            donnee, adresse_ip = s_ecoute.recvfrom(4096)
            donnee = donnee.decode("utf-8")
            L = donnee.split("|")
            if len(L) >= 4 :
                chaque_appareil = {"nom" : L[1], "ip" : adresse_ip[0], "Clé_publique" : L[2], "dernier_vu" : tm.time(), "port" : int(L[3])}
                with verrou :
                    if L[0] == mon_id :
                        continue
                    appareils_vus[L[0]] = chaque_appareil 
            else :
                pass
        except Exception as e  :
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

def prepare_envoi_relais() :
    global appareils_vus, sessions, mon_id

    valide = True # Pour eviter les failles 
    destinataire_final = input("Entrez l'ID du destinataire final : ")
    with verrou :
        if destinataire_final not in appareils_vus :
            print("Le destinataire n'est plus en ligne.")
            return

    print("Info : le message doit être non vide et maximum 160 caractères")
    message = input("Entrez votre message : ")
    while len(message) > 160 or message == "" :         
            message = input("Entrez votre message : ")

    compteur = 3

    with verrou :
        if destinataire_final not in sessions :
            valide = envoyer_cle_session(destinataire_final)

    if not valide :
        print("Echec")
        return

    with verrou :
        cle = sessions[destinataire_final]

    nonce, texte = chiffrer_message(message, cle)
    message_chiffrer = nonce + texte
    with verrou :
        mon_propre_id = mon_id
    type_message = 3

    produit_final =  construire_envellope_relais(destinataire_final, mon_propre_id, compteur, type_message, message_chiffrer)
    taille = renvoi_taille(produit_final)

    while True :
        print ("1. Entrez le relais par lequel vous voulez transiter : ")
        print("2. Annuler")
        choix = input()

        match choix :
            case "1" :
                relais_choisis = input("Entrez l'ID de votre transiteur : ")
                with verrou :
                    if relais_choisis not in appareils_vus :
                        print("Le transiteur n'est plus en ligne")
                        return
                    ip = appareils_vus[relais_choisis] ["ip"] # Tout est sous verrou
                    port = appareils_vus[relais_choisis] ["port"]
                        
                if not valide :
                    print("Echec")
                    return

                valide = envoi_tout(port, ip, taille , produit_final)
                if not valide :
                    print("Echec")
                return

            case "2" :
                print("Annulation...")
                return

            case _ :
                print("Entrée invalide")
    
def renvoi_taille(tout) : # Je vais le garder malgré et aussi les sous fonctions m'aident à mieux me repérer
    taille_message = len(tout)
    taille_message_bytes = taille_message.to_bytes(4, 'big')
    return taille_message_bytes 

















def prepare_envoi() : # le but lui il doit s'assurer que tout est bon
    global appareils_vus, sessions, mon_id

    valide = True # Pour eviter les failles 
    id_destinataire = input("Entrez l'ID du destinaitaire : ").strip()
    with verrou :
        if id_destinataire not in appareils_vus :
            print("Le destinataire n'est plus en ligne")
            return

    print("Info : le message doit être non vide et maximum 160 caractères")
    message = input("Entrez votre message : ").strip()
    while message == "" or len(message) > 160 : # Car on peut se tromper appuyer sur entrée
        print("Message invalide")
        message = input("Entrez votre message : ").strip()

    with verrou :
        if id_destinataire not in sessions :
            valide = envoyer_cle_session(id_destinataire)
    if not valide :
        print("Echec")
        return

    with verrou :
        cle = sessions[id_destinataire]

    nonce, texte = chiffrer_message(message, cle)

    tout = (b'\x02') + mon_id.encode("utf-8") + nonce + texte
        

    taille = renvoi_taille(tout)

    with verrou :
        ip = appareils_vus[id_destinataire]["ip"]
        port = int(appareils_vus[id_destinataire]["port"])

    valide = envoi_tout(port, ip, taille , tout)

    if not valide :
        return















def main():
    les_ouvriers()
    
    tm.sleep(1) 

    while True :
        print("\n--- MENU ---")
        print("1. Afficher les appareils connectés")
        #print("2. Envoyer une clé de session à un appareil") Plus nécessaire prepare_envoi va s'en charger
        print("2. Envoyer un message")
        print("3. Envoyer un message via un relais")
        print("4. Quitter")

        choix = input("Votre choix : ").strip()

        match choix :
            case "1" :
                with verrou :
                    if not appareils_vus :
                        print("Aucun appareil détecté pour le moment.")
                    else :
                        for identifiant, info in appareils_vus.items() :
                            print(f"ID: {identifiant} | Nom: {info['nom']} | IP: {info['ip']} | Port: {info['port']}")

            case "2" :
                prepare_envoi()
            case "3" :
                prepare_envoi_relais()
            case "4" :
                print("Fermeture du programme...")
                return
            case _ :
                print("Choix invalide, réessayez.")

if __name__ == "__main__":
    main()

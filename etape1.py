from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization as seria
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

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
    global sessions, ma_cle_prive, port_optionnel
    s_tcp = sc.socket(sc.AF_INET, sc.SOCK_STREAM)
    s_tcp.setsockopt(sc.SOL_SOCKET, sc.SO_REUSEADDR, 1)
    s_tcp.bind(('', port_optionnel))
    s_tcp.listen(5) 

    while True :
        try :
            connexion, adresse = s_tcp.accept()
            # On reçoit la clé chiffrée
            donnees_chiffrees = connexion.recv(4096) 
            L = [donnees_chiffrees[:16], donnees_chiffrees[16:]]
            # On déchiffre avec notre clé privée RSA
            L[1] = dechiffrer_aes(L[1], ma_cle_prive)
            cle_a_decoder = L[0]
            L[0] = cle_a_decoder.decode("utf-8")

            with verrou :
                sessions[L[0]] = L[1]
            print(f"\n[TCP] Clé AES reçue avec succès de {L[0]} depuis {adresse[0]} ! Taille : {len(L[1])} octets.")
            connexion.close()
        except Exception as e :
            pass

def envoyer_cle_session(id_destinataire) :
    global appareils_vus, sessions
    
    with verrou :
        if id_destinataire not in appareils_vus :
            print("Erreur : cet appareil n'est plus dans la liste.")
            return
        
        info_appareil = appareils_vus[id_destinataire]
        ip_dest = info_appareil["ip"]
        cle_pub_b64 = info_appareil["Clé_publique"]
        port_dest = int(info_appareil["port"])

    # 1. Génération de la clé AES aléatoire
    cle_aes = sr.token_bytes(32)
    
    # 2. Chiffrement de la clé AES avec la clé publique RSA du destinataire
    cle_aes_chiffree = chiffrer_aes(cle_aes, cle_pub_b64)
    
    try :
        # 3. Connexion TCP vers le port spécifique du destinataire
        s_client = sc.socket(sc.AF_INET, sc.SOCK_STREAM)
        s_client.connect((ip_dest, port_dest))
        
        # 4. Envoi de la clé chiffrée
        id_coder = mon_id.encode("utf-8")
        s_client.sendall((id_coder + cle_aes_chiffree))
        s_client.close()
        
        # 5. Stockage local de la clé AES dans les sessions
        with verrou :
            sessions[id_destinataire] = cle_aes
            
        print(f"\n[TCP] Clé AES générée et envoyée avec succès à {info_appareil['nom']} ({ip_dest}:{port_dest}) !")
        
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

# Correction : conversion du port en string pour la concaténation
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
        except Exception :
            pass        

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
    except Exception :
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

def main():
    les_ouvriers()
    
    tm.sleep(1) 

    while True :
        print("\n--- MENU ---")
        print("1. Afficher les appareils connectés")
        print("2. Envoyer une clé de session à un appareil")
        print("3. Quitter")

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
                identifiant = input("Entrez l'ID de l'appareil destinataire : ").strip()
                envoyer_cle_session(identifiant)

            case "3" :
                print("Fermeture du programme...")
                return
            case _ :
                print("Choix invalide, réessayez.")

if __name__ == "__main__":
    main()

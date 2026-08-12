from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization as seria

import socket as sc
import time as tm
import threading as tr
import secrets as sr
import os
import base64 as b64

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

verrou = tr.Lock()
nom = input("Entrez votre nom d'affichage : ")
while nom == "" :
    nom = input("Entrez votre nom d'affichage : ")
    
mon_id = sauvegarde_recharge()
ma_cle_prive = generation_rsa()
ma_cle_publique = ma_cle_prive.public_key()

ma_cle_publique_b64 = transforme_base_64(ma_cle_publique)

nom_final = mon_id + "|" + nom + "|" + ma_cle_publique_b64
ip = None
dernier_vu = tm.time()
appareils_vus = {}

def ecouter() :
    global appareils_vus, mon_id
    s_ecoute = creer_sc()
    s_ecoute.bind(('', 12345))
    while True :
        try :
            donnee, adresse_ip = s_ecoute.recvfrom(4096)
            donnee = donnee.decode("utf-8")
            L = donnee.split("|")
            if len(L) >= 3 :
                chaque_appareil = {"nom" : L[1], "ip" : adresse_ip[0], "Clé_publique" : L[2], "dernier_vu" : tm.time()}
                with verrou :
                    if L[0] == mon_id :
                        continue
                    appareils_vus[L[0]] = chaque_appareil 
            else :
                pass
        except Exception :
            pass        

def les_ouvriers() :
    ouvrier_emeteur = tr.Thread(target=emettre)
    ouvrier_emeteur.start()
    ouvrier_recepteur = tr.Thread(target=ecouter)
    ouvrier_recepteur.start()
    ouvrier_presence = tr.Thread(target=liste_présence)
    ouvrier_presence.start()
    
def liste_présence() :
    global appareils_vus
    try :
        while True :
            with verrou :
                for i in list(appareils_vus) :
                    print(i, end=" ")
                    for j in appareils_vus[i] :
                        print(appareils_vus[i][j], end=" ")
      
                    if (tm.time() - appareils_vus[i]["dernier_vu"]) >= 10 :
                        del appareils_vus[i]
                print()
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
    s.return s if False else s # syntaxique propre ci-dessous
    return s

def main():
    les_ouvriers()

if __name__ == "__main__":
    main()

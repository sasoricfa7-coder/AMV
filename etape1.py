import socket as sc
import time as tm
import threading as tr
import secrets as sr
import os

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
            

verrou = tr.Lock()
nom = input("Entrez votre nom d'affichage : ")
while nom == "" :
    nom = input("Entrez votre nom d'affichage : ")
    
mon_id = sauvegarde_recharge() # Il permet aux autres de nous reconnaitre
nom_final = mon_id + "|" + nom
ip = None
dernier_vu = tm.time()
appareils_vus = {}

def ecouter() :
    global appareils_vus, mon_id
    s_ecoute = creer_sc()
    s_ecoute.bind(('', 12345))
    while True :
        try :
            donnee, adresse_ip = s_ecoute.recvfrom(1024)
            donnee = donnee.decode("utf-8")
            L = donnee.split("|")
            if len(L) >= 2 :
                chaque_appareil = {"nom" : L[1], "ip" : adresse_ip[0], "dernier_vu" : tm.time()}
                with verrou :
                    if L[0] == mon_id :
                        continue
                    appareils_vus [L[0]] = chaque_appareil 
            else :
                pass
        except :
            pass        

def les_ouvriers() :
    # Emeteur
    ouvrier_emeteur = tr.Thread(target=emettre)
    ouvrier_emeteur.start()
    #Recepteur
    ouvrier_recepteur = tr.Thread(target=ecouter)
    ouvrier_recepteur.start()
    #Verifie la présence
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
                print() # Ligne vide pour aérer l'affichage de la liste
                tm.sleep(3)
                
    except :
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
    # Permet de réutiliser le port sans déclencher d'Address already in use
    s.setsockopt(sc.SOL_SOCKET, sc.SO_REUSEADDR, 1)
    s.setsockopt(sc.SOL_SOCKET, sc.SO_BROADCAST, 1)
    return s

les_ouvriers()


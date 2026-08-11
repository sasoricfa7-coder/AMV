import socket as sc
import time as tm
import threading as tr

verrou = tr.Lock()
nom = input("Entrez votre nom d'affichage : ")
while nom == "" :
    nom = input("Entrez votre nom d'affichage : ")
    
mon_id = "Test" # Il permet aux autres de nous reconnaitre
nom_final = nom + "|" + mon_id
ip = None
dernier_vu = tm.time()
chaque_appareil = {"nom" : nom, "ip" : ip, "dernier_vu" : dernier_vu}
appareils_vus = {mon_id : chaque_appareil}

def ecouter() :
    global appareils_vus
    s_ecoute = creer_sc()
    s_ecoute.bind(('', 12345))
    while True :
        donnee, adresse_ip = s_ecoute.recvfrom(1024)
        donnee = donnee.decode("utf-8")
        L = donnee.split("|")
        chaque_appareil = {"nom" : L[0], "ip" : adresse_ip[0], "dernier_vu" : tm.time()}
        with verrou :
            appareils_vus [L[1]] = chaque_appareil

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
    
def emettre() :
    global nom_final
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

s = creer_sc()
les_ouvriers()

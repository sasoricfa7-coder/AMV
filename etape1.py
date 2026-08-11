import socket as sc
import time as tm
import threading as tr

def ecouter() :
    s_ecoute = creer_sc()
    s_ecoute.bind(('', 12345))
    while True :
        donnee, adresse_ip = s_ecoute.recvfrom(1024)
        print(f"{adresse_ip} : {donnee}")

def les_ouvriers() :
    # Emeteur
    ouvrier_emeteur = tr.Thread(target=emettre)
    ouvrier_emeteur.start()
    #Recepteur
    ouvrier_recepteur = tr.Thread(target=ecouter)
    ouvrier_recepteur.start()
    
def emettre() :
    donnee = "Actif".encode('utf-8')
    adresse = '<broadcast>'
    port = 12345
    while True :
        s.sendto(donnee, (adresse, port))
        tm.sleep(3)

def creer_sc() :
    s = sc.socket(sc.AF_INET, sc.SOCK_DGRAM)
    s.setsockopt(sc.SOL_SOCKET, sc.SO_BROADCAST, 1)
    return s

s = creer_sc()
les_ouvriers()
print("Hello world") # Pour voir si les thread marche

import network
import time
from machine import Pin, ADC
import dht
import ujson
from umqtt.simple import MQTTClient

# --- 1. CONFIGURATION ---
MQTT_BROKER    = "broker.emqx.io" 
MQTT_CLIENT_ID = "ensa_fes_final_v2026_" + str(time.ticks_ms())
MQTT_TOPIC     = "exam/iot/telemetrie/voiture1"

# --- 2. MATÉRIEL  ---
moteur_pin = Pin(12, Pin.IN, Pin.PULL_UP) # Bouton Rouge (Moteur)
sos_pin    = Pin(13, Pin.IN, Pin.PULL_UP) # Bouton Vert (SOS)
sensor_temp = dht.DHT22(Pin(15))          # Capteur DHT22
pot_adc     = ADC(Pin(34))                # Potentiomètre (Batterie)

# --- 3. ÉTAT DU SYSTÈME ---
moteur_lance = False      
dernier_etat_bouton = 1   
lat, lon = 34.03313, -5.00028 # Départ : Fès
carburant = 100.0
compteur_mqtt = 0 

# --- 4. CONNEXION WIFI ---
sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
sta_if.connect('Wokwi-GUEST', '')
print("Recherche WiFi...")
while not sta_if.isconnected(): 
    time.sleep(0.5)
print("✅ WiFi OK")

# --- 5. CONNEXION MQTT ---
client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, keepalive=60)
def connecter_mqtt():
    try:
        client.connect()
        print("✅ MQTT CONNECTÉ")
    except:
        print("❌ Erreur MQTT")

connecter_mqtt()

# --- 6. BOUCLE PRINCIPALE ---
while True:
    # A. Lecture rapide (0.1s) pour ne pas rater le clic
    etat_actuel_bouton = moteur_pin.value()
    sos_on = (sos_pin.value() == 0) # True si bouton Vert pressé
    
    # Détection du clic sur bouton Rouge (Pin 12)
    if etat_actuel_bouton == 0 and dernier_etat_bouton == 1:
        moteur_lance = not moteur_lance
        print("🔄 Moteur :", "DÉMARRAGE" if moteur_lance else "ARRÊT")
        time.sleep(0.2) # Anti-rebond
    
    dernier_etat_bouton = etat_actuel_bouton

    # Sécurité : Le SOS coupe le moteur
    if sos_on:
        moteur_lance = False

    # B. Gestion de l'envoi réseau (Toutes les 2 secondes environ)
    compteur_mqtt += 1
    
    if compteur_mqtt >= 20: # 20 * 0.1s = 2 secondes
        try:
            sensor_temp.measure()
            temp = sensor_temp.temperature()
        except:
            temp = 25.0
            
        batt = int((pot_adc.read() / 4095.0) * 100)
        
        vitesse = 0
        statut = "Moteur OFF"
        
        if sos_on:
            statut = "SOS ACTIVE"
            vitesse = 0
        elif moteur_lance:
            vitesse = 40
            statut = "En circulation"
            if carburant > 0:
                carburant -= 0.1
                # Mouvement fluide vers le Nord-Est de Fès
                lat += 0.00015
                lon += 0.00008
        
        # Payload JSON optimisé pour Node-RED (Worldmap + Gauges)
        payload = {
            "name": "Vehicule_ENSA",  # INDISPENSABLE pour la carte
            "lat": lat,
            "lon": lon,
            "vitesse": vitesse,
            "batterie": batt,
            "carburant": int(carburant),
            "temp_moteur": temp,
            "sos": sos_on,
            "statut": statut,
            "icon": "car" if not sos_on else "warning"
        }
        
        try:
            client.publish(MQTT_TOPIC, ujson.dumps(payload))
            print("📡 Données envoyées | SOS:", sos_on, "| Vit:", vitesse)
        except:
            print("🔌 Reconnexion MQTT...")
            connecter_mqtt()
            
        compteur_mqtt = 0 

    time.sleep(0.1) # Réactivité pour le bouton

import threading
import json
import time
import sys
import os
import socket

from servidor import iniciar_servidor
from cliente import registrar_nodo, gestionar_descarga, publicar_torrent, obtener_lista_torrents, descargar_torrent_tracker
from utilerias import cargar_estado_descarga, crear_estado_descarga

def obtener_ip_local_salida():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def cargar_config():
    if not os.path.exists("config_nodo.json"):
        sys.exit(1)
    with open("config_nodo.json", "r") as f:
        return json.load(f)

def seleccionar_torrent(config):
    ruta_torrents = "../Archivos/torrents"
    os.makedirs(ruta_torrents, exist_ok=True)

    torrents_locales = [x for x in os.listdir(ruta_torrents) if x.endswith(".json")]
    
    if torrents_locales:
        print("\n--- Torrents Locales ---")
        for i, nombre in enumerate(torrents_locales):
            print(f"{i+1}. {nombre}")
        print(f"{len(torrents_locales)+1}. Buscar en Tracker (Nube)")
    else:
        print("\nNo hay torrents locales. Buscando en Tracker...")

    opcion = -1
    try:
        opcion = int(input("Selecciona: ")) - 1
    except:
        return None

    # Si eligió un local
    if 0 <= opcion < len(torrents_locales):
        ruta = f"{ruta_torrents}/{torrents_locales[opcion]}"
        with open(ruta, "r") as f:
            return json.load(f)
    
    # Si eligió buscar en Tracker o no había locales
    print("Consultando Tracker...")
    lista_nube = obtener_lista_torrents(config["tracker_ip"], config["tracker_puerto"])
    
    if not lista_nube:
        print("El Tracker no tiene torrents registrados.")
        return None

    print("\n--- Torrents en Tracker ---")
    for i, nombre in enumerate(lista_nube):
        print(f"{i+1}. {nombre}")
    
    try:
        idx = int(input("Descargar cual: ")) - 1
        nombre_elegido = lista_nube[idx]
        datos_torrent = descargar_torrent_tracker(config["tracker_ip"], config["tracker_puerto"], nombre_elegido)
        
        if datos_torrent:
            ruta_guardado = f"{ruta_torrents}/{nombre_elegido}.torrent.json"
            with open(ruta_guardado, "w") as f:
                json.dump(datos_torrent, f, indent=4)
            return datos_torrent
    except:
        pass
    
    return None

def registrar_en_tracker(config, torrent, estado):
    ip = obtener_ip_local_salida()
    info_nodo = {
        "id_nodo": config["id_nodo"],
        "ip": ip,
        "puerto": config["puerto"],
        "archivos": [{
            "id": torrent["id"],
            "nombre": torrent["nombre"],
            "porcentaje": estado["porcentaje"]
        }]
    }
    registrar_nodo(config["tracker_ip"], config["tracker_puerto"], info_nodo)
    print(f"Status: {estado['porcentaje']}%")

def ciclo_principal(config, torrent):
    estado = cargar_estado_descarga()
    ruta_completo = f"../Archivos/completos/{torrent['nombre']}"
    
    if not estado or estado.get("id") != torrent["id"]:
        if os.path.exists(ruta_completo):
            estado = crear_estado_descarga(torrent)
            estado["porcentaje"] = 100
            print("Archivo completo detectado. Soy SEEDER.")
            
            # AUTOMATIZACION: Subir torrent al tracker
            ruta_t = f"../Archivos/torrents/{torrent['nombre']}.torrent.json"
            if os.path.exists(ruta_t):
                with open(ruta_t, "r") as f:
                    contenido = json.load(f)
                publicar_torrent(config["tracker_ip"], config["tracker_puerto"], torrent["nombre"], contenido)
                print("Torrent publicado en Tracker autom.")
        else:
            estado = crear_estado_descarga(torrent)
            print("Iniciando nueva descarga...")
    else:
        print("Recuperando estado previo...")

    registrar_en_tracker(config, torrent, estado)

    if estado["porcentaje"] < 100:
        gestionar_descarga(torrent, config["tracker_ip"], config["tracker_puerto"], config["id_nodo"])
        print("Descarga finalizada.")
        registrar_en_tracker(config, torrent, estado)
    
    while True:
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    config = cargar_config()
    torrent = seleccionar_torrent(config)
    if not torrent:
        sys.exit(1)

    print(f"\n=== NODO: {config['id_nodo']} ===")
    hilo_servidor = threading.Thread(target=iniciar_servidor, args=(config["puerto"],), daemon=True)
    hilo_servidor.start()

    ciclo_principal(config, torrent)
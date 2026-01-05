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
    if not os.path.exists(ruta_torrents):
        os.makedirs(ruta_torrents, exist_ok=True)

    torrents_locales = [x for x in os.listdir(ruta_torrents) if x.endswith(".json")]

    print("\n--- SELECCION DE TORRENT ---")
    print("1. Buscar en Tracker (Nube)")
    for i, nombre in enumerate(torrents_locales):
        print(f"{i+2}. Local: {nombre}")

    try:
        opcion_str = input("Elige: ")
        opcion = int(opcion_str)
    except:
        return None

    if opcion == 1:
        print("Consultando Tracker...")
        lista = obtener_lista_torrents(config["tracker_ip"], config["tracker_puerto"])
        
        if not lista:
            print("El Tracker no tiene archivos registrados.")
            return None

        for i, nombre in enumerate(lista):
            print(f"{i+1}. {nombre}")
        
        try:
            idx = int(input("Descargar cual: ")) - 1
            if 0 <= idx < len(lista):
                nombre = lista[idx]
                datos = descargar_torrent_tracker(config["tracker_ip"], config["tracker_puerto"], nombre)
                
                if datos:
                    ruta_guardada = f"{ruta_torrents}/{nombre}.torrent.json"
                    with open(ruta_guardada, "w") as f:
                        json.dump(datos, f, indent=4)
                    return datos
        except:
            pass
        return None

    else:
        idx = opcion - 2
        if 0 <= idx < len(torrents_locales):
            ruta = f"{ruta_torrents}/{torrents_locales[idx]}"
            with open(ruta, "r") as f:
                return json.load(f)
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
        else:
            estado = crear_estado_descarga(torrent)
            print("Iniciando nueva descarga...")
    else:
        print("Recuperando estado previo...")

    if estado["porcentaje"] == 100:
        ruta_t = f"../Archivos/torrents/{torrent['nombre']}.torrent.json"
        if os.path.exists(ruta_t):
            try:
                with open(ruta_t, "r") as f:
                    contenido = json.load(f)
                print(f"Publicando {torrent['nombre']} en Tracker...")
                publicar_torrent(config["tracker_ip"], config["tracker_puerto"], torrent["nombre"], contenido)
            except:
                pass

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

    print(f"\n=== INICIANDO PEER: {config['id_nodo']} ===")

    hilo_servidor = threading.Thread(
        target=iniciar_servidor,
        args=(config["puerto"],),
        daemon=True
    )
    hilo_servidor.start()

    ciclo_principal(config, torrent)
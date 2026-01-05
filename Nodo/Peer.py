import threading
import json
import time
import sys
import os
import socket

from servidor import iniciar_servidor
from cliente import registrar_nodo, gestionar_descarga
from utilerias import cargar_estado_descarga, crear_estado_descarga


def obtener_ip_local_salida():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


def cargar_config():
    if not os.path.exists("config_nodo.json"):
        print("Error: Falta config_nodo.json")
        sys.exit(1)

    with open("config_nodo.json", "r") as f:
        return json.load(f)


def seleccionar_torrent():
    ruta_torrents = "../Archivos/torrents"
    if not os.path.exists(ruta_torrents):
        os.makedirs(ruta_torrents, exist_ok=True)
        print(f"Carpeta {ruta_torrents} creada. Coloca archivos .torrent.json ahí.")
        return None

    torrents = [x for x in os.listdir(ruta_torrents) if x.endswith(".torrent.json") or x.endswith(".json")]
    if not torrents:
        print(f"No hay torrents en {ruta_torrents}")
        return None

    print("\nTorrents disponibles:")
    for i, nombre in enumerate(torrents):
        print(f"{i+1}. {nombre}")

    try:
        opcion = int(input("Selecciona un torrent: ")) - 1
        if opcion < 0 or opcion >= len(torrents):
            print("Opción inválida")
            return None
    except:
        print("Entrada inválida")
        return None

    ruta = f"{ruta_torrents}/{torrents[opcion]}"
    with open(ruta, "r") as f:
        return json.load(f)


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
    print(f"Nodo registrado: {config['id_nodo']} | {ip}:{config['puerto']} | {estado['porcentaje']}%")


def ciclo_principal(config, torrent):
    estado = cargar_estado_descarga()
    if not estado or estado.get("id") != torrent["id"]:
        estado = crear_estado_descarga(torrent)
        print("Iniciando nueva descarga...")
    else:
        print("Recuperando estado previo...")

    registrar_en_tracker(config, torrent, estado)

    if estado["porcentaje"] < 100:
        print("Iniciando descarga...")
        gestionar_descarga(torrent, config["tracker_ip"], config["tracker_puerto"], config["id_nodo"])
        print("Descarga completada. Modo SEEDER activo.")
    else:
        print("Archivo completo. Modo SEEDER activo.")

    while True:
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            print("Apagando nodo...")
            sys.exit(0)


if __name__ == "__main__":
    config = cargar_config()

    torrent = seleccionar_torrent()
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

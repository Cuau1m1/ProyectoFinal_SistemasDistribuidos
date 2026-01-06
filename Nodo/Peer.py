import threading
import json
import time
import sys
import os
import socket

from servidor import iniciar_servidor
from cliente import registrar_nodo, gestionar_descarga, publicar_torrent, obtener_lista_torrents, descargar_torrent_tracker
from utilerias import (
    cargar_estado_descarga,
    crear_estado_descarga,
    crear_estado_seeder,
    obtener_ruta_estado
)


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
    rol = "SEEDER" if estado["porcentaje"] == 100 else "LEECHER"
    print(f"[NODO] IP: {ip} | Rol: {rol} | Progreso: {estado['porcentaje']}%")

def ciclo_principal(config, torrent):

    ruta_completo = f"../Archivos/completos/{torrent['nombre']}"

    # --- DETERMINAR ESTADO ---
    if os.path.exists(ruta_completo):
        print(f" Archivo físico detectado: {torrent['nombre']}")
        estado = crear_estado_seeder(torrent)
        print("Estado forzado a 100% (Modo Seeder Automático).")
    else:
        estado = cargar_estado_descarga(torrent["id"])

        if not estado:
            estado = crear_estado_descarga(torrent)
            print("Iniciando nueva descarga (0%)...")
        else:
            print(f"Recuperando progreso previo: {estado['porcentaje']}%")

    # --- REGISTRO EN TRACKER ---
    registrar_en_tracker(config, torrent, estado)

    # --- DESCARGA SI ES LEECHER ---
    if estado["porcentaje"] < 100:
        gestionar_descarga(
            torrent,
            config["tracker_ip"],
            config["tracker_puerto"],
            config["id_nodo"]
        )
        print("Descarga finalizada.")
        estado["porcentaje"] = 100
        registrar_en_tracker(config, torrent, estado)

    # --- MANTENER PEER VIVO ---
    while True:
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            sys.exit(0)
def publicar_torrents_seeder(config):
    ruta_torrents = "../Archivos/torrents"
    if not os.path.exists(ruta_torrents):
        return

    for archivo in os.listdir(ruta_torrents):
        if not archivo.endswith(".torrent.json"):
            continue

        ruta = os.path.join(ruta_torrents, archivo)
        with open(ruta, "r") as f:
            torrent = json.load(f)

        publicar_torrent(
            config["tracker_ip"],
            config["tracker_puerto"],
            torrent["nombre"],
            torrent
        )
        print(f"[SEEDER] Torrent publicado en tracker: {torrent['nombre']}")
def publicar_todos_los_torrents(config):
    carpeta_torrents = "torrents"

    if not os.path.exists(carpeta_torrents):
        print("[SEEDER] No existe la carpeta de torrents.")
        return

    archivos = os.listdir(carpeta_torrents)

    for nombre in archivos:
        if not nombre.endswith(".torrent.json"):
            continue

        ruta = os.path.join(carpeta_torrents, nombre)

        try:
            with open(ruta, "r") as f:
                torrent = json.load(f)

            estado = {
                "progreso": 100,
                "tamano_total": torrent["tamano_total"],
                "chunks_completados": torrent["num_chunks"],
                "es_seeder": True
            }

            registrar_en_tracker(config, torrent, estado)
            print(f"[SEEDER] Publicado: {torrent['nombre_archivo']} (100%)")

        except Exception as e:
            print(f"[SEEDER] Error publicando {nombre}: {e}")


if __name__ == "__main__":
    config = cargar_config()

    print(f"\n=== INICIANDO PEER: {config['id_nodo']} ===")
    ip = obtener_ip_local_salida()
    print(f"[NODO] Conectándose desde IP: {ip} (puerto {config['puerto']})")

    hilo_servidor = threading.Thread(
        target=iniciar_servidor,
        args=(config["puerto"],),
        daemon=True
    )
    hilo_servidor.start()

    # --- SEEDER AUTOMÁTICO ---
    if config["id_nodo"].startswith("SEEDER"):
        publicar_todos_los_torrents(config)
        while True:
            time.sleep(10)

    # --- LEECHER ---
    torrent = seleccionar_torrent(config)
    if not torrent:
        sys.exit(1)

    ciclo_principal(config, torrent)

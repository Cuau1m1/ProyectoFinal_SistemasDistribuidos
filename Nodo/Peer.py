import threading
import json
import time
import sys
import os
import socket

from servidor import iniciar_servidor
from cliente import (
    registrar_nodo,
    gestionar_descarga,
    publicar_torrent,
    obtener_lista_torrents,
    descargar_torrent_tracker
)
from utilerias import (
    cargar_estado_descarga,
    crear_estado_descarga,
    crear_estado_seeder
)

# =========================
# UTILIDADES
# =========================

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
        print("No existe config_nodo.json")
        sys.exit(1)
    with open("config_nodo.json", "r") as f:
        return json.load(f)


# =========================
# SELECCIÓN DE TORRENT
# =========================

def seleccionar_torrent(config):
    ruta_torrents = "../Archivos/torrents"
    os.makedirs(ruta_torrents, exist_ok=True)

    torrents_locales = [x for x in os.listdir(ruta_torrents) if x.endswith(".torrent.json")]

    print("\n--- SELECCION DE TORRENT ---")
    print("1. Buscar en Tracker (Nube)")
    for i, nombre in enumerate(torrents_locales):
        print(f"{i + 2}. Local: {nombre}")

    try:
        opcion = int(input("Elige: "))
    except:
        return None

    # --- BUSCAR EN TRACKER ---
    if opcion == 1:
        print("Consultando Tracker...")
        lista = obtener_lista_torrents(config["tracker_ip"], config["tracker_puerto"])

        if not lista:
            print("El Tracker no tiene archivos registrados.")
            return None

        for i, nombre in enumerate(lista):
            print(f"{i + 1}. {nombre}")

        try:
            idx = int(input("Descargar cual: ")) - 1
            if 0 <= idx < len(lista):
                nombre = lista[idx]
                datos = descargar_torrent_tracker(
                    config["tracker_ip"],
                    config["tracker_puerto"],
                    nombre
                )
                if datos:
                    ruta = os.path.join(ruta_torrents, f"{nombre}.torrent.json")
                    with open(ruta, "w") as f:
                        json.dump(datos, f, indent=4)
                    return datos
        except:
            return None

    # --- LOCAL ---
    else:
        idx = opcion - 2
        if 0 <= idx < len(torrents_locales):
            ruta = os.path.join(ruta_torrents, torrents_locales[idx])
            with open(ruta, "r") as f:
                return json.load(f)

    return None


# =========================
# REGISTRO EN TRACKER
# =========================

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


# =========================
# CICLO PRINCIPAL
# =========================

def ciclo_principal(config, torrent):
    ruta_completo = f"../Archivos/completos/{torrent['nombre']}"

    # --- ESTADO ---
    if os.path.exists(ruta_completo):
        estado = crear_estado_seeder(torrent)
        print(f"Archivo completo detectado: {torrent['nombre']} (Seeder)")
    else:
        estado = cargar_estado_descarga(torrent["id"])
        if not estado:
            estado = crear_estado_descarga(torrent)
            print("Iniciando nueva descarga (0%)...")
        else:
            print(f"Recuperando progreso previo: {estado['porcentaje']}%")

    registrar_en_tracker(config, torrent, estado)

    # --- DESCARGA ---
    if estado["porcentaje"] < 100:
        gestionar_descarga(
            torrent,
            config["tracker_ip"],
            config["tracker_puerto"],
            config["id_nodo"]
        )
        estado["porcentaje"] = 100
        registrar_en_tracker(config, torrent, estado)

    while True:
        time.sleep(10)


# =========================
# SEEDER AUTOMÁTICO
# =========================

def publicar_todos_los_torrents(config):
    ruta_torrents = "../Archivos/torrents"

    if not os.path.exists(ruta_torrents):
        print("[SEEDER] No existe la carpeta de torrents.")
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

        print(f"[SEEDER] Torrent publicado: {torrent['nombre']}")


# =========================
# MAIN

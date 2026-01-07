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


def cargar_config():
    if not os.path.exists("config_nodo.json"):
        print("[ERROR] No existe config_nodo.json")
        sys.exit(1)
    with open("config_nodo.json", "r") as f:
        return json.load(f)


def seleccionar_torrent(config):
    ruta_torrents = "../Archivos/torrents"
    os.makedirs(ruta_torrents, exist_ok=True)

    torrents_locales = [x for x in os.listdir(ruta_torrents) if x.endswith(".json")]

    print("\n--- SELECCION DE TORRENT ---")
    print("1. Buscar en Tracker (Nube)")
    for i, nombre in enumerate(torrents_locales):
        print(f"{i+2}. Local: {nombre}")

    try:
        opcion = int(input("Elige: ").strip())
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
            idx = int(input("Descargar cual: ").strip()) - 1
            if 0 <= idx < len(lista):
                nombre = lista[idx]
                datos = descargar_torrent_tracker(
                    config["tracker_ip"],
                    config["tracker_puerto"],
                    nombre
                )

                if datos:
                    ruta_guardada = f"{ruta_torrents}/{nombre}.torrent.json"
                    with open(ruta_guardada, "w") as f:
                        json.dump(datos, f, indent=4)
                    return datos
        except:
            pass

        return None

    # opción local
    idx = opcion - 2
    if 0 <= idx < len(torrents_locales):
        ruta = f"{ruta_torrents}/{torrents_locales[idx]}"
        with open(ruta, "r") as f:
            return json.load(f)

    return None


def registrar_en_tracker(config, torrent, estado):
    ip = config.get("ip_publica")
    if not ip:
        print("[ERROR] ip_publica no definida en config_nodo.json")
        return

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
        print(f"Archivo físico detectado: {torrent['nombre']}")
        estado = crear_estado_seeder(torrent)
        print("Estado forzado a 100% (Modo Seeder Automático).")
    else:
        estado = cargar_estado_descarga(torrent["id"])

        # 🔥 Estado inconsistente: 100% sin archivo físico
        if estado and estado.get("porcentaje") == 100:
            print("Estado inconsistente detectado (100% sin archivo físico). Reiniciando descarga.")
            estado = None

        if not estado:
            estado = crear_estado_descarga(torrent)
            print("Iniciando nueva descarga (0%)...")
        else:
            print(f"Recuperando progreso previo: {estado['porcentaje']}%")

    # asegurar estado más reciente
    estado = cargar_estado_descarga(torrent["id"]) or estado

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

        # recargar estado real al terminar
        estado = cargar_estado_descarga(torrent["id"]) or estado
        registrar_en_tracker(config, torrent, estado)

    # --- MANTENER PEER VIVO ---
    while True:
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            sys.exit(0)


def publicar_todos_los_torrents(config):
    ruta_torrents = "../Archivos/torrents"
    if not os.path.exists(ruta_torrents):
        print("[SEEDER] No existe la carpeta ../Archivos/torrents")
        return

    torrents = [x for x in os.listdir(ruta_torrents) if x.endswith(".torrent.json")]
    if not torrents:
        print("[SEEDER] No hay torrents para publicar.")
        return

    for nombre in torrents:
        ruta = os.path.join(ruta_torrents, nombre)
        try:
            with open(ruta, "r") as f:
                torrent = json.load(f)

            publicar_torrent(
                config["tracker_ip"],
                config["tracker_puerto"],
                torrent["nombre"],
                torrent
            )
            print(f"[SEEDER] Torrent publicado: {torrent['nombre']}")
        except Exception as e:
            print(f"[SEEDER] Error publicando {nombre}: {e}")


if __name__ == "__main__":
    config = cargar_config()

    print(f"\n=== INICIANDO PEER: {config['id_nodo']} ===")
    ip = config.get("ip_publica", "IP_NO_DEFINIDA")
    print(f"[NODO] Conectándose desde IP pública: {ip} (puerto {config['puerto']})")

    hilo_servidor = threading.Thread(
        target=iniciar_servidor,
        args=(config["puerto"],),
        daemon=True
    )
    hilo_servidor.start()

    # ================= SEEDER =================
    if config["id_nodo"].startswith("SEEDER"):
        publicar_todos_los_torrents(config)

        ruta_torrents = "../Archivos/torrents"
        if os.path.exists(ruta_torrents):
            for archivo in os.listdir(ruta_torrents):
                if not archivo.endswith(".torrent.json"):
                    continue

                ruta = os.path.join(ruta_torrents, archivo)
                with open(ruta, "r") as f:
                    torrent = json.load(f)

                estado = crear_estado_seeder(torrent)
                registrar_en_tracker(config, torrent, estado)

        print("[SEEDER] Listo y anunciando archivos.")
        while True:
            time.sleep(10)

    # ================= LEECHER =================
    print("[DEBUG] Entrando a modo LEECHER")
    torrent = seleccionar_torrent(config)
    if not torrent:
        print("No se seleccionó ningún torrent. Saliendo.")
        sys.exit(1)

    ciclo_principal(config, torrent)

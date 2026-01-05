import socket
import json
import threading
import os
import time

from utilerias import (
    escribir_chunk,
    verificar_hash_chunk,
    marcar_chunk_completado,
    cargar_estado_descarga,
    crear_estado_descarga,
    obtener_chunks_faltantes
)

MAX_DESCARGAS_CONCURRENTES = 4


# ---------------- TRACKER ----------------

def enviar_mensaje_tracker(ip, puerto, mensaje):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, puerto))
    s.send(json.dumps(mensaje).encode())
    respuesta = s.recv(4096)
    s.close()
    return respuesta


def registrar_nodo(tracker_ip, tracker_puerto, info_nodo):
    mensaje = {"tipo": "REGISTRO", "datos": info_nodo}
    enviar_mensaje_tracker(tracker_ip, tracker_puerto, mensaje)


def consultar_peers(tracker_ip, tracker_puerto, id_archivo):
    mensaje = {"tipo": "CONSULTA", "datos": {"id_archivo": id_archivo}}
    respuesta = enviar_mensaje_tracker(tracker_ip, tracker_puerto, mensaje)
    return json.loads(respuesta.decode())["datos"]["peers"]


def actualizar_progreso(tracker_ip, tracker_puerto, id_nodo, id_archivo, porcentaje):
    mensaje = {
        "tipo": "ACTUALIZAR",
        "datos": {
            "id_nodo": id_nodo,
            "id_archivo": id_archivo,
            "porcentaje": porcentaje
        }
    }
    enviar_mensaje_tracker(tracker_ip, tracker_puerto, mensaje)

#----
def menu_principal():
    print("\n=== MENU PEER ===")
    print("1. Agregar torrent")
    print("2. Ver progreso de descargas")
    print("3. Salir")
    return input("Opción: ")


def seleccionar_torrent():
    ruta = "../Archivos/torrents"
    torrents = os.listdir(ruta)

    if not torrents:
        print("No hay torrents disponibles")
        return None

    print("Escoge un archivo de la lista:")
    for t in torrents:
        print(f"- {t}")

    nombre = input("Archivo: ")
    ruta_torrent = f"{ruta}/{nombre}"

    if not os.path.exists(ruta_torrent):
        print("Torrent no encontrado")
        return None

    with open(ruta_torrent, "r") as f:
        return json.load(f)


def ver_progreso(estado):
    if not estado:
        print("No hay descargas activas")
        return

    print("\n--- PROGRESO ---")
    print(f"Archivo: {estado['nombre']}")
    print(f"Progreso: {estado['porcentaje']}%")
    print(f"Chunks: {len(estado['chunks_completados'])}/{estado['total_chunks']}")



def solicitar_chunk(ip, puerto, id_archivo, indice, tamano_chunk, hash_esperado, estado):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, puerto))

    solicitud = {
        "tipo": "GET_CHUNK",
        "datos": {
            "id_archivo": id_archivo,
            "indice_chunk": indice,
            "tamano_chunk": tamano_chunk
        }
    }

    s.send(json.dumps(solicitud).encode())

    encabezado = json.loads(s.recv(4096).decode())
    tamano = encabezado["tamano_datos"]

    datos = b""
    while len(datos) < tamano:
        datos += s.recv(4096)

    s.close()

    if verificar_hash_chunk(datos, hash_esperado):
        ruta = f"../Archivos/parciales/{estado['nombre']}"
        escribir_chunk(ruta, indice, datos, tamano_chunk)
        marcar_chunk_completado(estado, indice)
        mostrar_estado_nodo(estado)


# ---------------- GESTOR DE DESCARGA ----------------
def gestionar_descarga(torrent, tracker_ip, tracker_puerto, id_nodo):
    estado = cargar_estado_descarga()
    if not estado:
        estado = crear_estado_descarga(torrent)

    while estado["porcentaje"] < 100:
        chunks_faltantes = obtener_chunks_faltantes(estado)
        peers = consultar_peers(tracker_ip, tracker_puerto, torrent["id"])

        if not peers:
            time.sleep(2)
            continue

        hilos = []

        for indice in chunks_faltantes:
            if len(hilos) >= MAX_DESCARGAS_CONCURRENTES:
                for h in hilos:
                    h.join()
                hilos = []

            peer = peers[indice % len(peers)]
            hash_esperado = torrent["hash_chunks"][indice]

            hilo = threading.Thread(
                target=solicitar_chunk,
                args=(
                    peer["ip"],
                    peer["puerto"],
                    torrent["id"],
                    indice,
                    torrent["tamano_chunk"],
                    hash_esperado,
                    estado
                )
            )

            hilo.start()
            hilos.append(hilo)

        for h in hilos:
            h.join()

        actualizar_progreso(
            tracker_ip,
            tracker_puerto,
            id_nodo,
            torrent["id"],
            estado["porcentaje"]
        )


# ---------------- VISUAL ----------------

def mostrar_estado_nodo(estado):
    print("\n--- ESTADO DEL NODO ---")
    print(f"Archivo: {estado['nombre']}")
    print(f"Progreso: {estado['porcentaje']}%")
    print(f"Chunks: {len(estado['chunks_completados'])}/{estado['total_chunks']}")

    if estado["porcentaje"] == 100:
        print("Rol: SEEDER")
    else:
        print("Rol: LEECHER")

    print("-----------------------\n")

if __name__ == "__main__":
    with open("config_nodo.json", "r") as f:
        config = json.load(f)

    tracker_ip = config["tracker_ip"]
    tracker_puerto = config["tracker_puerto"]
    id_nodo = config["id_nodo"]
    ip = obtener_ip_publica()
    puerto = config["puerto"]

    estado = None

    while True:
        opcion = menu_principal()

        if opcion == "1":
            torrent = seleccionar_torrent()
            if not torrent:
                continue

            estado = cargar_estado_descarga()
            if not estado:
                estado = crear_estado_descarga(torrent)

            info_nodo = {
                "id_nodo": id_nodo,
                "ip": ip,
                "puerto": puerto,
                "archivos": [
                    {
                        "id": torrent["id"],
                        "porcentaje": estado["porcentaje"]
                    }
                ]
            }

            registrar_nodo(tracker_ip, tracker_puerto, info_nodo)
            print("Torrent agregado y nodo registrado en tracker")

            gestionar_descarga(torrent, tracker_ip, tracker_puerto, id_nodo)

        elif opcion == "2":
            ver_progreso(estado)

        elif opcion == "3":
            print("Saliendo...")
            break

        else:
            print("Opción no válida")

def obtener_ip_publica():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


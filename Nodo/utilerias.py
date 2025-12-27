# utilerias.py concentra las funciones de manejo de archivos, fragmentacion e integridad, pero se
#implementan como utiladades independientes para facilitar concurrencia y tolerancia a fallos 

import os
import json
import hashlib

def generar_torrent(ruta_archivo, tamano_chunk, tracker_ip, tracker_puerto):
    nombre = os.path.basename(ruta_archivo)
    tamano_total = os.path.getsize(ruta_archivo)
    hash_chunks = []

    with open(ruta_archivo, "rb") as archivo:
        while True:
            datos = archivo.read(tamano_chunk)
            if not datos:
                break
            hash_chunk = hashlib.sha256(datos).hexdigest()
            hash_chunks.append(hash_chunk)

    total_chunks = len(hash_chunks)
    id_archivo = hashlib.sha256(nombre.encode()).hexdigest()

    torrent = {
        "id": id_archivo,
        "nombre": nombre,
        "tamano_total": tamano_total,
        "tamano_chunk": tamano_chunk,
        "total_chunks": total_chunks,
        "hash_chunks": hash_chunks,
        "tracker_ip": tracker_ip,
        "tracker_puerto": tracker_puerto
    }

    os.makedirs("../Archivos/torrents", exist_ok=True)
    ruta_torrent = f"../Archivos/torrents/{nombre}.torrent.json"

    with open(ruta_torrent, "w") as archivo_torrent:
        json.dump(torrent, archivo_torrent, indent=4)

    return ruta_torrent


# -> Lectura y escritura de chunks

def leer_chunk(ruta_archivo, indice_chunk, tamano_chunk):
    with open(ruta_archivo, "rb") as archivo:
        archivo.seek(indice_chunk * tamano_chunk)
        return archivo.read(tamano_chunk)


def escribir_chunk(ruta_archivo, indice_chunk, datos, tamano_chunk):
    os.makedirs(os.path.dirname(ruta_archivo), exist_ok=True)

    with open(ruta_archivo, "r+b" if os.path.exists(ruta_archivo) else "wb") as archivo:
        archivo.seek(indice_chunk * tamano_chunk)
        archivo.write(datos)


def verificar_hash_chunk(datos, hash_esperado):
    hash_calculado = hashlib.sha256(datos).hexdigest()
    return hash_calculado == hash_esperado
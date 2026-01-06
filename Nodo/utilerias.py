# utilerias.py concentra las funciones de manejo de archivos, fragmentacion e integridad, pero se
#implementan como utiladades independientes para facilitar concurrencia y tolerancia a fallos 

import os
import json
import hashlib


# Torrent
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

    ruta_torrents = os.path.join("Archivos", "torrents")
    os.makedirs(ruta_torrents, exist_ok=True)

    ruta_torrent = os.path.join(
        ruta_torrents,
        f"{nombre}.torrent.json"
    )

    with open(ruta_torrent, "w") as archivo_torrent:
        json.dump(torrent, archivo_torrent, indent=4)

    return ruta_torrent


# Chunks

def leer_chunk(ruta_archivo, indice, tamanio_chunk):
    try:
        with open(ruta_archivo, "rb") as f:
            f.seek(indice * tamanio_chunk)
            datos = f.read(tamanio_chunk)
            return datos if datos else b""
    except FileNotFoundError:
        return b""


def escribir_chunk(ruta_archivo, indice, datos, tamano_chunk):
    # 1. Asegurar que la carpeta exista
    directorio = os.path.dirname(ruta_archivo)
    if directorio:
        os.makedirs(directorio, exist_ok=True)
    
    # 2. Definir el modo de escritura (AQUÍ FALLABA ANTES)
    if os.path.exists(ruta_archivo):
        modo = "r+b"  
    else:
        modo = "wb"   # Escritura binaria nueva (si no existe)
    
    # 3. Escribir los datos
    with open(ruta_archivo, modo) as f:
        f.seek(indice * tamano_chunk)
        f.write(datos)
        f.flush()
        os.fsync(f.fileno()) # Forzar guardado en disco físico

def verificar_hash_chunk(datos, hash_esperado):
    hash_calculado = hashlib.sha256(datos).hexdigest()
    return hash_calculado == hash_esperado


#Estado

def obtener_ruta_estado(id_torrent):
    carpeta = "estados"
    os.makedirs(carpeta, exist_ok=True)
    return os.path.join(carpeta, f"{id_torrent}.json")

def crear_estado_descarga(torrent):
    ruta = obtener_ruta_estado(torrent["id"])
    estado = {
        "id": torrent["id"],
        "nombre": torrent["nombre"],
        "tamano_total": torrent["tamano_total"],
        "tamano_chunk": torrent["tamano_chunk"],
        "total_chunks": torrent["total_chunks"],
        "chunks_completados": [],
        "porcentaje": 0
    }
    with open(ruta, "w") as archivo:
        json.dump(estado, archivo, indent=4)
    return estado

def cargar_estado_descarga(id_torrent):
    ruta = obtener_ruta_estado(id_torrent)
    if not os.path.exists(ruta):
        return None
    with open(ruta, "r") as archivo:
        return json.load(archivo)


def guardar_estado_descarga(estado):
    ruta = obtener_ruta_estado(estado["id"])
    with open(ruta, "w") as archivo:
        json.dump(estado, archivo, indent=4)

def marcar_chunk_completado(estado, indice_chunk):
    if indice_chunk not in estado["chunks_completados"]:
        estado["chunks_completados"].append(indice_chunk)
        estado["porcentaje"] = calcular_porcentaje(estado)
        ruta = obtener_ruta_estado(estado["id"])
        guardar_estado_descarga(estado, ruta)

def obtener_chunks_faltantes(estado):
    return [
        i for i in range(estado["total_chunks"])
        if i not in estado["chunks_completados"]
    ]

def calcular_porcentaje(estado):
    completados = len(estado["chunks_completados"])
    total = estado["total_chunks"]
    return int((completados / total) * 100)


def crear_estado_seeder(torrent):
    ruta = obtener_ruta_estado(torrent["id"])
    estado = {
        "id": torrent["id"],
        "nombre": torrent["nombre"],
        "tamano_total": torrent["tamano_total"],
        "tamano_chunk": torrent["tamano_chunk"],
        "total_chunks": torrent["total_chunks"],
        "chunks_completados": list(range(torrent["total_chunks"])),
        "porcentaje": 100
    }
    with open(ruta, "w") as archivo:
        json.dump(estado, archivo, indent=4)
    return estado

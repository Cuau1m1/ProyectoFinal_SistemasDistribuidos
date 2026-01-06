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

MAX_DESCARGAS_CONCURRENTES = 2

# --- Función Auxiliar para leer bytes exactos ---
def recibir_exacto(socket_cliente, cantidad):
    buffer = b""
    while len(buffer) < cantidad:
        chunk = socket_cliente.recv(cantidad - len(buffer))
        if not chunk: raise Exception("Conexión cerrada prematuramente")
        buffer += chunk
    return buffer

# ---------------- TRACKER ----------------

def enviar_mensaje_tracker(ip, puerto, mensaje):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, puerto))
    s.send(json.dumps(mensaje).encode())
    respuesta = s.recv(16384) # Aumentado buffer
    s.close()
    return respuesta

def registrar_nodo(tracker_ip, tracker_puerto, info_nodo):
    mensaje = {"tipo": "REGISTRO", "datos": info_nodo}
    try:
        enviar_mensaje_tracker(tracker_ip, tracker_puerto, mensaje)
    except Exception as e:
        print(f"Error registrando en tracker: {e}")

def consultar_peers(tracker_ip, tracker_puerto, id_archivo):
    mensaje = {"tipo": "CONSULTA", "datos": {"id_archivo": id_archivo}}
    try:
        respuesta = enviar_mensaje_tracker(tracker_ip, tracker_puerto, mensaje)
        return json.loads(respuesta.decode())["datos"]["peers"]
    except:
        return []

def actualizar_progreso(tracker_ip, tracker_puerto, id_nodo, id_archivo, porcentaje):
    mensaje = {
        "tipo": "ACTUALIZAR",
        "datos": {
            "id_nodo": id_nodo,
            "id_archivo": id_archivo,
            "porcentaje": porcentaje
        }
    }
    try:
        enviar_mensaje_tracker(tracker_ip, tracker_puerto, mensaje)
    except:
        pass

# ---------------- FUNCIONES NUEVAS (PUBLICAR / DESCARGAR) ----------------

def publicar_torrent(tracker_ip, tracker_puerto, nombre_archivo, contenido_torrent):
    mensaje = {
        "tipo": "PUBLICAR_TORRENT",
        "datos": {
            "nombre": nombre_archivo,
            "contenido": contenido_torrent
        }
    }
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((tracker_ip, tracker_puerto))
        s.send(json.dumps(mensaje).encode())
        s.close()
    except Exception as e:
        print(f"Error publicando torrent: {e}")

def obtener_lista_torrents(tracker_ip, tracker_puerto):
    mensaje = {"tipo": "LISTAR_TORRENTS", "datos": {}}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((tracker_ip, tracker_puerto))
        s.send(json.dumps(mensaje).encode())
        datos = s.recv(16384)
        s.close()
        return json.loads(datos.decode())["datos"]
    except:
        return []

def descargar_torrent_tracker(tracker_ip, tracker_puerto, nombre_archivo):
    print(f"--- DEBUG: Pidiendo {nombre_archivo} al Tracker {tracker_ip} ---")
    mensaje = {
        "tipo": "DESCARGAR_TORRENT",
        "datos": {"nombre": nombre_archivo}
    }
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10) # Damos buen tiempo
        s.connect((tracker_ip, tracker_puerto))
        s.send(json.dumps(mensaje).encode())
        
        # --- CAMBIO IMPORTANTE: RECIBIR EN BUCLE ---
        datos_totales = b""
        while True:
            try:
                paquete = s.recv(4096)
                if not paquete: break # Si el servidor cierra, terminamos
                datos_totales += paquete
            except socket.timeout:
                break
        
        s.close()
        # -------------------------------------------
        
        if not datos_totales:
            print("--- DEBUG: Tracker cerró sin mandar datos ---")
            return None

        print(f"--- DEBUG: Recibidos {len(datos_totales)} bytes ---")
        
        # Intentamos decodificar el JSON completo
        respuesta = json.loads(datos_totales.decode())
        
        if respuesta["tipo"] == "ARCHIVO_TORRENT":
            return respuesta["datos"]
        else:
            print(f"--- DEBUG: Tracker error: {respuesta}")
            
    except json.JSONDecodeError as e:
        print(f" ERROR JSON INCOMPLETO: {e}")
        print(f"   Datos recibidos (parcial): {datos_totales[:100]}...") # Muestra el inicio para ver si hay basura
    except Exception as e:
        print(f" ERROR DE RED: {e}")
        pass
    return None
# ---------------- P2P CLIENTE ----------------

def solicitar_chunk(ip, puerto, nombre_archivo, indice, tamano_chunk, hash_esperado, estado):
    try:
        # --- DEBUG: Ver qué intenta hacer el hilo ---
        print(f"   --> Intentando conectar a {ip}:{puerto} (Chunk {indice})...")

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # TIMEOUT: 5 segundos. Si no responde en este tiempo, suelta el error (no se congela)
        s.settimeout(5) 
        
        s.connect((ip, puerto))
        
        # --- DEBUG: Confirmar conexión ---
        print(f"   --> ¡Conectado a {ip}! Pidiendo datos...") 

        solicitud = {
            "tipo": "GET_CHUNK",
            "datos": {
                "id_archivo": nombre_archivo,
                "indice_chunk": indice,
                "tamano_chunk": tamano_chunk
            }
        }
        s.send(json.dumps(solicitud).encode())

        # 1. Leer Header de tamaño fijo (10 bytes)
        # Nota: Asegúrate de que recibir_exacto esté definida arriba en tu archivo
        header_len = recibir_exacto(s, 10)
        tamano_json = int(header_len.decode())
        
        # 2. Leer JSON con los metadatos
        json_bytes = recibir_exacto(s, tamano_json)
        encabezado = json.loads(json_bytes.decode())
        
        # 3. Leer el contenido del video (Chunk)
        tamano_video = encabezado["tamano_datos"]
        datos = recibir_exacto(s, tamano_video)

        s.close()

        # Validar integridad
        if verificar_hash_chunk(datos, hash_esperado):
            ruta = f"../Archivos/parciales/{estado['nombre']}"
            escribir_chunk(ruta, indice, datos, tamano_chunk)
            
            # Actualizar UI y marcar completado
            marcar_chunk_completado(estado, indice)
            mostrar_estado_nodo(estado)
        else:
            print(f"⚠️ Hash incorrecto en chunk {indice} (Se reintentará).")
            
    except socket.timeout:
        print(f"⏰ TIMEOUT: El nodo {ip} tardó demasiado en responder el chunk {indice}.")
    except ConnectionRefusedError:
        print(f"⛔ RECHAZADO: El nodo {ip} rechazó la conexión (¿Puerto cerrado?).")
    except Exception as e:
        print(f"❌ ERROR en chunk {indice}: {e}")
def gestionar_descarga(torrent, tracker_ip, tracker_puerto, id_nodo):
    estado = cargar_estado_descarga()
    if not estado:
        estado = crear_estado_descarga(torrent)

    print(f"Iniciando descarga de: {torrent['nombre']} ({estado['porcentaje']}%)")
    # print(f"🕵️ DEBUG: ...")  <-- ELIMINADO

    while estado["porcentaje"] < 100:
        chunks_faltantes = obtener_chunks_faltantes(estado)
        peers = consultar_peers(tracker_ip, tracker_puerto, torrent["id"])

        if peers:
            # Filtro silencioso (Anti-Canibalismo)
            peers_filtrados = []
            for p in peers:
                if p.get("id_nodo") != id_nodo:
                    peers_filtrados.append(p)
                # else:
                    # print(...) <-- ELIMINADO EL PRINT DE "ME ELIMINÉ"
            peers = peers_filtrados

        if not peers:
            # Usamos end='\r' para que sobreescriba la línea y no llene la pantalla
            print("💤 Esperando peers disponibles...   ", end="\r")
            time.sleep(3)
            continue

        hilos = []
        for i, indice in enumerate(chunks_faltantes):
            if i >= MAX_DESCARGAS_CONCURRENTES: break 

            peer = peers[indice % len(peers)]
            
            # Sin print de "Conectando a..."
            hilo = threading.Thread(
                target=solicitar_chunk,
                args=(
                    peer["ip"],
                    peer["puerto"],
                    torrent["nombre"], 
                    indice,
                    torrent["tamano_chunk"],
                    torrent["hash_chunks"][indice],
                    estado
                )
            )
            hilo.start()
            hilos.append(hilo)

        for h in hilos:
            h.join()

        actualizar_progreso(tracker_ip, tracker_puerto, id_nodo, torrent["id"], estado["porcentaje"])
    
        if not hilos:
            time.sleep(1)

def mostrar_estado_nodo(estado):
    print(f"\rProgreso: {estado['porcentaje']}% | Chunks: {len(estado['chunks_completados'])}/{estado['total_chunks']}", end="")
    if estado["porcentaje"] == 100:
        print("\n DESCARGA COMPLETADA. Eres SEEDER.")

def obtener_ip_publica():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

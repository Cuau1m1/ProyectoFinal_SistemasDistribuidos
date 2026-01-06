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

# Puedes probar subir a 4 si la red es estable, pero 2 es muy seguro.
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
    respuesta = s.recv(16384) 
    s.close()
    return respuesta

def registrar_nodo(tracker_ip, tracker_puerto, info_nodo):
    mensaje = {"tipo": "REGISTRO", "datos": info_nodo}
    try:
        enviar_mensaje_tracker(tracker_ip, tracker_puerto, mensaje)
    except Exception as e:
        # Solo imprimimos si falla el registro inicial, es importante saberlo
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

# ---------------- FUNCIONES DE GESTIÓN DE TORRENTS ----------------

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
    print(f"Descargando metadatos de {nombre_archivo}...")
    mensaje = {
        "tipo": "DESCARGAR_TORRENT",
        "datos": {"nombre": nombre_archivo}
    }
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect((tracker_ip, tracker_puerto))
        s.send(json.dumps(mensaje).encode())
        
        datos_totales = b""
        while True:
            try:
                paquete = s.recv(4096)
                if not paquete: break
                datos_totales += paquete
            except socket.timeout:
                break
        s.close()
        
        if not datos_totales: return None

        respuesta = json.loads(datos_totales.decode())
        
        if respuesta["tipo"] == "ARCHIVO_TORRENT":
            return respuesta["datos"]
        else:
            print(f"Error del Tracker: {respuesta}")
            
    except Exception as e:
        print(f"Error al obtener .torrent: {e}")
    return None

# ---------------- P2P CLIENTE (SILENCIOSO) ----------------

def solicitar_chunk(ip, puerto, nombre_archivo, indice, tamano_chunk, hash_esperado, estado):
    try:
        # SILENCIADO: print(f"   --> Intentando conectar a {ip}:{puerto}...")

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5) # Mantenemos el timeout de seguridad
        s.connect((ip, puerto))
        
        # SILENCIADO: print(f"   --> ¡Conectado!...") 

        solicitud = {
            "tipo": "GET_CHUNK",
            "datos": {
                "id_archivo": nombre_archivo,
                "indice_chunk": indice,
                "tamano_chunk": tamano_chunk
            }
        }
        s.send(json.dumps(solicitud).encode())

        header_len = recibir_exacto(s, 10)
        tamano_json = int(header_len.decode())
        
        json_bytes = recibir_exacto(s, tamano_json)
        encabezado = json.loads(json_bytes.decode())
        
        tamano_video = encabezado["tamano_datos"]
        datos = recibir_exacto(s, tamano_video)

        s.close()

        if verificar_hash_chunk(datos, hash_esperado):
            ruta = f"../Archivos/parciales/{estado['nombre']}"
            escribir_chunk(ruta, indice, datos, tamano_chunk)
            
            marcar_chunk_completado(estado, indice)
            mostrar_estado_nodo(estado)
        else:
            # Fallo de Hash silencioso (se reintentará automáticamente)
            pass 
            
    except (socket.timeout, ConnectionRefusedError, ConnectionResetError):
        # Fallos de red silenciosos (comunes en P2P, se reintentan)
        pass
    except Exception as e:
        # Solo imprimimos errores graves de sistema
        print(f"\n❌ Error crítico en chunk {indice}: {e}")

def gestionar_descarga(torrent, tracker_ip, tracker_puerto, id_nodo):
    estado = cargar_estado_descarga()
    if not estado:
        estado = crear_estado_descarga(torrent)

    print(f"Iniciando descarga de: {torrent['nombre']} ({estado['porcentaje']}%)")

    while estado["porcentaje"] < 100:
        chunks_faltantes = obtener_chunks_faltantes(estado)
        peers = consultar_peers(tracker_ip, tracker_puerto, torrent["id"])

        if peers:
            peers_filtrados = []
            for p in peers:
                # --- FILTRO LIMPIO Y FUNCIONAL ---
                peer_id = p.get("id_nodo")
                id_remoto = str(peer_id).strip().upper() if peer_id else "NONE"
                mi_id = str(id_nodo).strip().upper()

                # Solo agregamos si el ID es diferente
                if id_remoto != mi_id:
                    peers_filtrados.append(p)
            
            peers = peers_filtrados

        if not peers:
            print("💤 Esperando peers disponibles...   ", end="\r")
            time.sleep(3)
            continue

        hilos = []
        for i, indice in enumerate(chunks_faltantes):
            if i >= MAX_DESCARGAS_CONCURRENTES: break 

            peer = peers[indice % len(peers)]
            
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
    # Barra de progreso limpia que se sobrescribe a sí misma (\r)
    print(f"\r Progreso: {estado['porcentaje']}% | Chunks: {len(estado['chunks_completados'])}/{estado['total_chunks']}", end="")
    if estado["porcentaje"] == 100:
        print("\n✨ ¡DESCARGA COMPLETADA! Eres un SEEDER. ✨")

def obtener_ip_publica():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"
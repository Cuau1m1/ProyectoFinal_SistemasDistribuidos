import socket
import threading
import json
import os
from utilerias import leer_chunk

def manejar_cliente(conexion):
    try:
        datos_raw = conexion.recv(4096)
        if not datos_raw: 
            return
            
        encabezado = json.loads(datos_raw.decode())
        datos = encabezado["datos"]
        
        # Lógica de rutas
        nombre_archivo = datos["id_archivo"]
        ruta_parcial = f"../Archivos/parciales/{nombre_archivo}"
        ruta_completa = f"../Archivos/completos/{nombre_archivo}"
        
        # Prioridad al completo
        ruta = ruta_completa if os.path.exists(ruta_completa) else ruta_parcial
        
        if not os.path.exists(ruta):
            # Si no existe, cerramos conexión silenciosamente (o podrías imprimir error)
            conexion.close()
            return  

        # Leer chunk
        chunk = leer_chunk(ruta, datos["indice_chunk"], datos["tamano_chunk"])

        # Preparar respuesta
        respuesta = {
            "indice_chunk": datos["indice_chunk"], 
            "tamano_datos": len(chunk)
        }
        json_bytes = json.dumps(respuesta).encode()
        
        # Header de tamaño fijo (10 bytes) para el protocolo robusto
        header_len = f"{len(json_bytes):010d}".encode() 
        
        # --- ENVÍO CON SENDALL (CRÍTICO PARA AWS) ---
        conexion.sendall(header_len) 
        conexion.sendall(json_bytes)
        conexion.sendall(chunk)
        # --------------------------------------------
        
    except Exception as e:
        print(f"Error servidor manejando cliente: {e}")
    finally:
        conexion.close()
def iniciar_servidor(puerto):
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
    servidor.bind(("0.0.0.0", puerto))
    servidor.listen()
    print(f"Servidor escuchando en puerto {puerto}...")

    while True:
        try:
            conexion, _ = servidor.accept()
            hilo = threading.Thread(target=manejar_cliente, args=(conexion,))
            hilo.start()
        except:
            pass
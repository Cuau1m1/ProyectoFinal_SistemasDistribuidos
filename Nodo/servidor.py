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

        indice = datos["indice_chunk"]
        tamano_chunk = datos["tamano_chunk"]
        nombre_archivo = datos["id_archivo"] 
        
        ruta_parcial = f"../Archivos/parciales/{nombre_archivo}"
        ruta_completa = f"../Archivos/completos/{nombre_archivo}"

        if os.path.exists(ruta_completa):
            ruta = ruta_completa
        else:
            ruta = ruta_parcial
        
        if not os.path.exists(ruta):
            conexion.close()
            return  

        chunk = leer_chunk(ruta, indice, tamano_chunk)

        respuesta = {
            "indice_chunk": indice,
            "tamano_datos": len(chunk)
        }

        # Agregamos un salto de linea (b'\n') para separar el JSON del Video
        mensaje_json = json.dumps(respuesta).encode() + b"\n"
        conexion.send(mensaje_json)
        conexion.send(chunk)
        # ---------------------------
        
    except Exception as e:
        pass
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
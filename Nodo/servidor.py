import socket
import threading
import json
from utilerias import leer_chunk

def manejar_cliente(conexion):
    encabezado = json.loads(conexion.recv(4096).decode())
    datos = encabezado["datos"]

    indice = datos["indice_chunk"]
    tamano_chunk = datos["tamano_chunk"]
    ruta = f"../Archivos/parciales/{datos['id_archivo']}"

    chunk = leer_chunk(ruta, indice, tamano_chunk)

    respuesta = {
        "indice_chunk": indice,
        "tamano_datos": len(chunk)
    }

    conexion.send(json.dumps(respuesta).encode())
    conexion.send(chunk)
    conexion.close()


def iniciar_servidor(puerto):
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind(("0.0.0.0", puerto))
    servidor.listen()

    while True:
        conexion, _ = servidor.accept()
        hilo = threading.Thread(target=manejar_cliente, args=(conexion,))
        hilo.start()

#tracker  Servidor o rastreador central 
import socket
import json
import threading

nodos = {}

def manejar_nodo(conexion):
    datos = json.loads(conexion.recv(4096).decode())

    tipo = datos["tipo"]
    info = datos["datos"]

    if tipo == "REGISTRO":
        nodos[info["id_nodo"]] = info

    elif tipo == "CONSULTA":
        peers = []
        for nodo in nodos.values():
            for archivo in nodo["archivos"]:
                if archivo["id"] == info["id_archivo"]:
                    peers.append({
                        "ip": nodo["ip"],
                        "puerto": nodo["puerto"]
                    })
        respuesta = {
            "tipo": "RESPUESTA",
            "datos": { "peers": peers }
        }
        conexion.send(json.dumps(respuesta).encode())

    elif tipo == "ACTUALIZAR":
        if info["id_nodo"] in nodos:
            for archivo in nodos[info["id_nodo"]]["archivos"]:
                if archivo["id"] == info["id_archivo"]:
                    archivo["porcentaje"] = info["porcentaje"]

    conexion.close()


def iniciar_tracker(puerto):
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind(("0.0.0.0", puerto))
    servidor.listen()

    while True:
        conexion, _ = servidor.accept()
        hilo = threading.Thread(target=manejar_nodo, args=(conexion,))
        hilo.start()



#visual 
def mostrar_estado_tracker():
    print("\n=== ESTADO DEL TRACKER ===")
    for nodo_id, info in nodos.items():
        print(f"Nodo: {nodo_id} | {info['ip']}:{info['puerto']}")
        for archivo in info["archivos"]:
            print(f"  Archivo: {archivo['id']} | {archivo['porcentaje']}%")
    print("==========================\n")

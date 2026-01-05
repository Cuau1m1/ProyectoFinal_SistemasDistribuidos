import socket
import json
import threading

nodos = {}
torrents_repo = {}
lock_nodos = threading.Lock()

def manejar_nodo(conexion):
    datos_raw = conexion.recv(16384)
    if not datos_raw:
        conexion.close()
        return

    try:
        datos = json.loads(datos_raw.decode())
    except:
        conexion.close()
        return

    tipo = datos["tipo"]
    info = datos["datos"]

    if tipo == "REGISTRO":
        with lock_nodos:
            nodos[info["id_nodo"]] = info

    elif tipo == "CONSULTA":
        peers = []
        with lock_nodos:
            for nodo in nodos.values():
                for archivo in nodo["archivos"]:
                    if (archivo["id"] == info["id_archivo"] and archivo["porcentaje"] >= 20):
                        peers.append({
                            "ip": nodo["ip"],
                            "puerto": nodo["puerto"],
                            "nombre": archivo.get("nombre", "desconocido")
                        })
        respuesta = {
            "tipo": "RESPUESTA",
            "datos": {"peers": peers}
        }
        conexion.send(json.dumps(respuesta).encode())

    elif tipo == "ACTUALIZAR":
        with lock_nodos:
            if info["id_nodo"] in nodos:
                for archivo in nodos[info["id_nodo"]]["archivos"]:
                    if archivo["id"] == info["id_archivo"]:
                        archivo["porcentaje"] = info["porcentaje"]

    elif tipo == "PUBLICAR_TORRENT":
        with lock_nodos:
            torrents_repo[info["nombre"]] = info["contenido"]
    
    elif tipo == "LISTAR_TORRENTS":
        lista = list(torrents_repo.keys())
        respuesta = {
            "tipo": "RESPUESTA_LISTA",
            "datos": lista
        }
        conexion.send(json.dumps(respuesta).encode())

    elif tipo == "DESCARGAR_TORRENT":
        nombre = info["nombre"]
        if nombre in torrents_repo:
            respuesta = {
                "tipo": "ARCHIVO_TORRENT",
                "datos": torrents_repo[nombre]
            }
        else:
            respuesta = {"tipo": "ERROR", "datos": {}}
        conexion.send(json.dumps(respuesta).encode())

    conexion.close()
    mostrar_estado_tracker()

def iniciar_tracker(puerto):
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind(("0.0.0.0", puerto))
    servidor.listen()
    print(f"Tracker iniciado en puerto {puerto}")
    while True:
        conexion, _ = servidor.accept()
        hilo = threading.Thread(target=manejar_nodo, args=(conexion,))
        hilo.start()

def mostrar_estado_tracker():
    print("\n=== ESTADO DEL TRACKER ===")
    print(f"Torrents Indexados: {len(torrents_repo)}")
    for nodo_id, info in nodos.items():
        print(f"Nodo: {nodo_id} | {info['ip']}:{info['puerto']}")
        for archivo in info["archivos"]:
            print(f"  Archivo: {archivo.get('nombre', 'DESCONOCIDO')} | {archivo['porcentaje']}%")
    print("==========================\n")

if __name__ == "__main__":
    iniciar_tracker(5000)
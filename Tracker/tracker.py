#tracker  Servidor o rastreador central 
import socket
import json
import threading

nodos = {}
lock_nodos = threading.Lock()

def manejar_nodo(conexion):
    datos_raw = conexion.recv(4096)
    if not datos_raw:
        conexion.close()
        return

    datos = json.loads(datos_raw.decode())
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
                    if (
                        archivo["id"] == info["id_archivo"]
                        and archivo["porcentaje"] >= 20
                    ):
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

    conexion.close()
    mostrar_estado_tracker()


def iniciar_tracker(puerto):
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind(("0.0.0.0", puerto))
    servidor.listen()

    print(f"Tracker iniciado en puerto {puerto}")
    print("Esperando nodos...\n")

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
            estado = "VISIBLE" if archivo["porcentaje"] >= 20 else "OCULTO"
            print(
                f"  Archivo: {archivo.get('nombre', 'DESCONOCIDO')} "
                f"| {archivo['porcentaje']}% | {estado}"
            )
    print("==========================\n")



if __name__ == "__main__":
    iniciar_tracker(5000)

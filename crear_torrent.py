from Nodo.utilerias import generar_torrent

import os

ruta_base = os.path.join("Archivos", "completos")


archivos = os.listdir(ruta_base)

print("Archivos disponibles para crear torrent:")
for i, nombre in enumerate(archivos):
    print(f"{i+1}. {nombre}")

opcion = int(input("Selecciona un archivo: ")) - 1
archivo_seleccionado = archivos[opcion]

ruta_archivo = f"{ruta_base}/{archivo_seleccionado}"

generar_torrent(
    ruta_archivo,
    1024 * 1024,
    "44.219.142.29",
    5000
)


print("Torrent creado para:", archivo_seleccionado)

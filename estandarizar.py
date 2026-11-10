#!/usr/bin/env python3
"""
Pasa las fotos crudas de origen/ a fotos/ con nombres uniformes y arma inventario.csv.

Las fotos de Ecofactory ya llegan con un nombre estructurado:

    <material>_<estructura>_<manija>_<medida>_<color>_<NN>.jpg
    friselina_fuelle-inferior_flexible_45x39x10_azul marino_01.jpg

Lo que hace este script:
  1. Normaliza cada token (NFC, minusculas, sin acentos, espacios -> "-").
  2. Traduce cada token al valor LITERAL de la planilla del catalogo con equivalencias.json.
     Un token que no esta en el mapa aborta: el script nunca adivina.
  3. Copia la foto a fotos/ con el nombre limpio (la medida va con el valor de la planilla:
     30x39x10 -> 30x40-10) y descarta duplicados exactos por md5.

Las fotos NO se redimensionan: pesan menos de 2 MB y miden ~1500 px, que es lo que WhatsApp
muestra igual. Los bytes quedan intactos.

Modo incremental: lo que ya esta en inventario.csv (por md5) no se toca, solo se apendean
las filas nuevas.

Uso:
    python3 estandarizar.py            # dry-run: muestra la tabla de renombres
    python3 estandarizar.py --aplicar  # copia a fotos/ y escribe inventario.csv
"""

import csv
import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
ORIGEN = os.path.join(AQUI, "origen")
FOTOS = os.path.join(AQUI, "fotos")
INVENTARIO = os.path.join(AQUI, "inventario.csv")
EQUIVALENCIAS = os.path.join(AQUI, "equivalencias.json")

CAMPOS = ("material", "estructura", "manija", "medida", "color")
EXTENSIONES = {".jpg": ".jpg", ".jpeg": ".jpg", ".png": ".png"}
RE_LIMPIO = re.compile(r"^[a-z0-9-]+(_[a-z0-9-]+){5}\.(jpg|png)$")
COLUMNAS = ["nombre_nuevo", "material", "estructura", "manija", "medida", "color",
            "origen", "md5", "bytes"]
# La URL base de jsDelivr mide 64 chars: con 75 de nombre la URL entra en una linea del PDF.
MAX_NOMBRE = 75


def normalizar(token):
    """'Azul Marino' / 'riñon' -> 'azul-marino' / 'rinon'."""
    # macOS guarda los nombres en NFD: sin pasar a NFC la ñ no se reconoce como una letra.
    t = unicodedata.normalize("NFC", token).lower().strip()
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s_]+", "-", t)


def slug(valor):
    """'30x40+10' -> '30x40-10'."""
    return re.sub(r"[^a-z0-9]+", "-", normalizar(valor)).strip("-")


def md5(ruta):
    h = hashlib.md5()
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 16), b""):
            h.update(bloque)
    return h.hexdigest()


def leer_inventario():
    if not os.path.exists(INVENTARIO):
        return []
    with open(INVENTARIO, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def parsear(nombre, eq):
    """Devuelve (fila, None) o (None, motivo)."""
    base, ext = os.path.splitext(nombre)
    if ext.lower() not in EXTENSIONES:
        return None, "extension %s" % ext
    tokens = base.split("_")
    if len(tokens) != 6:
        return None, "tiene %d campos, se esperan 6" % len(tokens)
    *crudos, numero = tokens
    if not numero.isdigit():
        return None, "el ultimo campo (%s) no es un numero" % numero

    fila = {}
    claves = []
    for campo, crudo in zip(CAMPOS, crudos):
        clave = normalizar(crudo)
        valor = eq[campo].get(clave)
        if valor is None:
            return None, "%s '%s' no esta en equivalencias.json" % (campo, clave)
        fila[campo] = valor
        claves.append(slug(valor) if campo == "medida" else clave)

    fila["nombre_nuevo"] = "%s_%02d%s" % ("_".join(claves), int(numero), EXTENSIONES[ext.lower()])
    return fila, None


def main(aplicar):
    with open(EQUIVALENCIAS, encoding="utf-8") as fh:
        eq = json.load(fh)
    previas = leer_inventario()
    md5_previos = {r["md5"] for r in previas}
    nombres_previos = {r["nombre_nuevo"] for r in previas}

    nuevas, errores, duplicados = [], [], []
    vistos = {}
    for nombre in sorted(os.listdir(ORIGEN)):
        if nombre.startswith("."):
            continue
        ruta = os.path.join(ORIGEN, nombre)
        hash_ = md5(ruta)
        if hash_ in md5_previos:
            continue
        if hash_ in vistos:
            duplicados.append((nombre, vistos[hash_]))
            continue
        fila, motivo = parsear(nombre, eq)
        if motivo:
            errores.append((nombre, motivo))
            continue
        nuevo = fila["nombre_nuevo"]
        if not RE_LIMPIO.match(nuevo):
            errores.append((nombre, "nombre final invalido: %s" % nuevo))
            continue
        if len(nuevo) > MAX_NOMBRE:
            errores.append((nombre, "nombre final de %d chars (tope %d)" % (len(nuevo), MAX_NOMBRE)))
            continue
        if nuevo in nombres_previos or any(n["nombre_nuevo"] == nuevo for n in nuevas):
            errores.append((nombre, "colisiona con %s: subi el numero del final" % nuevo))
            continue
        vistos[hash_] = nombre
        fila.update(origen=nombre, md5=hash_, bytes=os.path.getsize(ruta))
        nuevas.append(fila)

    for f in nuevas:
        print("  %-62s -> %s" % (f["origen"], f["nombre_nuevo"]))
    for nombre, otro in duplicados:
        print("  DUPLICADO  %s == %s (se descarta)" % (nombre, otro))
    if errores:
        print("\n  %d ERRORES, no se escribe nada:" % len(errores))
        for nombre, motivo in errores:
            print("    %s: %s" % (nombre, motivo))
        sys.exit(1)

    print("\n  %d nuevas · %d ya publicadas · %d duplicadas" % (len(nuevas), len(previas), len(duplicados)))
    if not aplicar:
        print("  dry-run: corre con --aplicar para copiar y escribir el inventario")
        return

    os.makedirs(FOTOS, exist_ok=True)
    for f in nuevas:
        shutil.copy2(os.path.join(ORIGEN, f["origen"]), os.path.join(FOTOS, f["nombre_nuevo"]))
    with open(INVENTARIO, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(previas + nuevas)
    print("  listo: fotos/ e inventario.csv actualizados")


if __name__ == "__main__":
    main("--aplicar" in sys.argv)

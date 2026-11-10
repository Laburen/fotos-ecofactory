#!/usr/bin/env python3
"""
Genera el catalogo de fotos de Ecofactory que se sube a la KB de Olivia en laburen.com.

Lee inventario.csv y escribe catalogos/catalogo-fotos-ecofactory-DD_MM_AAAA.{md,pdf}. Una
seccion por MODELO de bolsa (material + estructura + manija + medida, que es lo que define la
bolsa en la planilla) y adentro una linea por foto con su color.

Los valores van escritos IGUAL que en la planilla del catalogo ("Riñon", "30x40+10", "Azul
marino"): Olivia busca la foto con los valores que le devolvio consultar_catalogo.

La fecha va en el nombre y tambien impresa abajo del titulo: el PDF se sube a mano a la KB y el
nombre del archivo puede no sobrevivir a la subida.

Uso:
    python3 generar_catalogo.py              # genera .md + .html + .pdf
    python3 generar_catalogo.py --verificar  # curl -I sobre todas las URLs (despues del push)
"""

import csv
import datetime
import html
import os
import subprocess
import sys
import time
from collections import OrderedDict, defaultdict

GITHUB_USER = "Laburen"
REPO = "fotos-ecofactory"
BRANCH = "main"
SUBDIR = "fotos"

# jsDelivr y no raw.githubusercontent: raw sirve todo como octet-stream y WhatsApp lo muestra
# como documento. La rama va explicita (@main): sin ella jsDelivr resuelve la version y cachea
# esa consulta aparte, y un repo recien creado puede quedar en 404 un buen rato (le paso a
# fotos-byd-simone). jsDelivr cachea ~12 h: para reemplazar una foto, subila con otro nombre.

AQUI = os.path.dirname(os.path.abspath(__file__))
INVENTARIO = os.path.join(AQUI, "inventario.csv")
SALIDA = os.path.join(AQUI, "catalogos")

HOY = datetime.date.today()
FECHA_ARCHIVO = HOY.strftime("%d_%m_%Y")
FECHA_TEXTO = HOY.strftime("%d/%m/%Y")

CHROME = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
          "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser")

# Una URL que no entra en el ancho de pagina se parte en dos lineas, y una URL partida la
# extrae mal el parser de la KB. Base de 64 chars + nombre de <= 75 (lo garantiza
# estandarizar.py). A 6.5pt en Menlo entran ~139 chars en los 192 mm utiles de un A4.
MAX_CHARS_URL = 139

INTRO = (
    "Este documento lista las fotos reales de las bolsas de Ecofactory. Cada bolsa se "
    "identifica por material, estructura, manija y medida, escritos igual que en el catálogo "
    "de productos. Para enviar una foto al cliente hay que copiar la URL <b>exacta</b> y "
    "pasarla a <code>send_files</code>. Las URLs no se arman a mano ni se deducen del nombre "
    "de otro archivo: si una bolsa no aparece en este documento, no hay fotos de esa bolsa."
)


def url_de(nombre):
    return "https://cdn.jsdelivr.net/gh/%s/%s@%s/%s/%s" % (GITHUB_USER, REPO, BRANCH, SUBDIR, nombre)


def titulo_modelo(r):
    """'Friselina · Fuelle inferior · Manija Flexible · 30x40+10'."""
    return "%s · %s · Manija %s · %s" % (r["material"], r["estructura"], r["manija"], r["medida"])


def leer_inventario():
    if not os.path.exists(INVENTARIO):
        sys.exit("no encuentro %s: corre estandarizar.py --aplicar primero" % INVENTARIO)
    with open(INVENTARIO, encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh))
    if not filas:
        sys.exit("el inventario esta vacio")

    por_modelo = defaultdict(list)
    for r in filas:
        por_modelo[titulo_modelo(r)].append(r)
    return OrderedDict(
        (m, sorted(por_modelo[m], key=lambda r: (r["color"], r["nombre_nuevo"])))
        for m in sorted(por_modelo)
    ), filas


def colores(fotos):
    return sorted({r["color"] for r in fotos})


def etiqueta(r):
    """
    Una foto, autodescripta. Repite el modelo entero a proposito: la KB parte el documento en
    chunks y un chunk puede empezar en la mitad de la lista, sin el titulo de la seccion.
    """
    return "%s · Color %s" % (titulo_modelo(r), r["color"])


def render_md(por_modelo):
    L = ["# Catálogo de fotos Ecofactory", "", "Generado el %s." % FECHA_TEXTO, ""]
    L.append(INTRO.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))
    L.append("")
    L.append("Bolsas con fotos: %s." % "; ".join(por_modelo))
    L.append("")
    for modelo, fotos in por_modelo.items():
        L += ["---", "", "## %s" % modelo, ""]
        L.append("Fotos disponibles de la bolsa %s: %d." % (modelo, len(fotos)))
        L.append("")
        L.append("Colores con fotos de esta bolsa: %s. No hay fotos de esta bolsa en ningún "
                 "otro color." % ", ".join(colores(fotos)))
        L.append("")
        for r in fotos:
            L.append("- **%s** — %s" % (etiqueta(r), url_de(r["nombre_nuevo"])))
        L += ["", "Fin de las fotos de la bolsa %s." % modelo, ""]
    return "\n".join(L)


def render_html(por_modelo):
    e = html.escape
    P = ["""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Catálogo de fotos Ecofactory</title><style>
@page { margin: 14mm 9mm; }
body { font: 11pt/1.5 -apple-system, "Helvetica Neue", Arial, sans-serif; color: #111; }
h1 { font-size: 20pt; margin: 0 0 1.5mm; }
.fecha { font-size: 9pt; color: #666; margin: 0 0 4mm; }
h2 { font-size: 13pt; margin: 6mm 0 2mm; padding: 2mm 3mm; color: #fff; background: #1f4d2b;
     page-break-after: avoid; }
.intro { background: #f4f4f5; border-left: 3px solid #777; padding: 3mm 4mm;
         margin-bottom: 4mm; font-size: 9.5pt; }
.indice { font-size: 9pt; margin-bottom: 4mm; }
section { page-break-inside: avoid; }
.meta { font-size: 9pt; color: #555; margin: 0 0 2mm; }
.foto { margin-bottom: 2.2mm; page-break-inside: avoid; }
.lbl { font-weight: 600; font-size: 9.5pt; }
/* nowrap: una URL partida la extrae mal el parser de la KB y send_files recibe una URL rota */
.url { font-family: "SF Mono", Menlo, monospace; font-size: 6.5pt; color: #14418b;
       white-space: nowrap; }
.fin { font-size: 8.5pt; color: #666; font-style: italic; margin-top: 2mm; }
</style></head><body>
<h1>Catálogo de fotos Ecofactory</h1>
<p class="fecha">Generado el %s.</p>
<div class="intro">%s</div>""" % (FECHA_TEXTO, INTRO)]
    P.append('<p class="indice"><b>Bolsas con fotos:</b> %s.</p>' % e("; ".join(por_modelo)))
    for modelo, fotos in por_modelo.items():
        P.append("<section><h2>%s</h2>" % e(modelo))
        P.append('<p class="meta">Fotos disponibles de la bolsa %s: %d.<br>Colores con fotos de '
                 'esta bolsa: %s. No hay fotos de esta bolsa en ningún otro color.</p>'
                 % (e(modelo), len(fotos), e(", ".join(colores(fotos)))))
        for r in fotos:
            P.append('<div class="foto"><span class="lbl">%s</span><br><span class="url">%s</span></div>'
                     % (e(etiqueta(r)), e(url_de(r["nombre_nuevo"]))))
        P.append('<p class="fin">Fin de las fotos de la bolsa %s.</p></section>' % e(modelo))
    P.append("</body></html>")
    return "\n".join(P)


def a_pdf(ruta_html, ruta_pdf):
    chrome = next((c for c in CHROME if os.path.exists(c)), None)
    if not chrome:
        print("  ! no encontre Chrome ni Brave: queda solo el .md y el .html")
        return False
    r = subprocess.run([chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        "--print-to-pdf=%s" % ruta_pdf, "file://%s" % ruta_html],
                       capture_output=True)
    if not os.path.exists(ruta_pdf):
        print("  ! Chrome no genero el PDF: %s" % r.stderr.decode()[:300])
        return False
    return True


def generar():
    por_modelo, filas = leer_inventario()
    os.makedirs(SALIDA, exist_ok=True)

    largas = [url_de(r["nombre_nuevo"]) for r in filas if len(url_de(r["nombre_nuevo"])) > MAX_CHARS_URL]
    if largas:
        sys.exit("%d URLs pasan los %d chars y se partirian en el PDF:\n  %s"
                 % (len(largas), MAX_CHARS_URL, "\n  ".join(largas)))

    nombre = "catalogo-fotos-ecofactory-%s" % FECHA_ARCHIVO
    md, ht, pdf = (os.path.join(SALIDA, nombre + ext) for ext in (".md", ".html", ".pdf"))
    with open(md, "w", encoding="utf-8") as fh:
        fh.write(render_md(por_modelo))
    with open(ht, "w", encoding="utf-8") as fh:
        fh.write(render_html(por_modelo))
    ok = a_pdf(ht, pdf)

    for modelo, fotos in por_modelo.items():
        print("  %-60s %d  (%s)" % (modelo, len(fotos), ", ".join(colores(fotos))))
    print("\n  %d fotos en %d bolsas" % (len(filas), len(por_modelo)))
    print("  A la KB va: %s" % (pdf if ok else md))


def verificar():
    _, filas = leer_inventario()
    urls = sorted({url_de(r["nombre_nuevo"]) for r in filas})
    print("Verificando %d URLs\n" % len(urls))

    def probar(u):
        r = subprocess.run(["curl", "-sIL", "-o", "/dev/null", "-w", "%{http_code} %{content_type}", u],
                           capture_output=True, text=True)
        code, _, ctype = r.stdout.partition(" ")
        return code, ctype.strip() or "?"

    fallas = []
    for u in urls:
        code, ctype = probar(u)
        for espera in (2, 5, 10):  # 403 es rate limit de jsDelivr: solo eso se reintenta
            if code != "403":
                break
            time.sleep(espera)
            code, ctype = probar(u)
        if not (code == "200" and ctype.startswith("image/")):
            fallas.append((u, code, ctype))
        time.sleep(0.15)
    if fallas:
        print("%d de %d FALLARON:" % (len(fallas), len(urls)))
        for u, code, ctype in fallas:
            print("  HTTP %s  %s  %s" % (code, ctype, u))
        print("\n404 recien pusheado: jsDelivr tarda unos minutos en ver el repo. Volve a correr.")
        sys.exit(1)
    print("%d/%d en HTTP 200 con content-type de imagen." % (len(urls), len(urls)))


if __name__ == "__main__":
    verificar() if "--verificar" in sys.argv else generar()

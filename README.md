# Fotos Ecofactory

Fotos reales de las bolsas de Ecofactory, con nombres uniformes, en un repo público para que las
URLs (jsDelivr) sean estables. Olivia, el agente de Ecofactory, las encuentra en la KB a través del
catálogo PDF y las manda con `send_files`.

Mismo circuito que [`fotos-byd-simone`](https://github.com/Laburen/fotos-byd-simone) y
[`fotos-dalian`](https://github.com/Laburen/fotos-dalian).

## Convención de nombres

```
<material>_<estructura>_<manija>_<medida>_<color>_<NN>.jpg
friselina_fuelle-inferior_flexible_45x40-10_azul-marino_01.jpg
```

Todo en minúscula, solo `a-z 0-9 - _`. La medida va con el valor de la planilla (`45x40+10` →
`45x40-10`).

## Los valores son los de la planilla del catálogo

Olivia busca la foto con los valores que le devuelve `consultar_catalogo`. Por eso el catálogo de
fotos escribe material, estructura, manija, medida y color **literalmente igual** que la hoja
`1-Base de Datos de Formatos` (`Riñon`, `30x40+10`, `Azul marino`). La traducción vive en
`equivalencias.json`, y si aparece un token que no está ahí, `estandarizar.py` corta: nunca adivina.

Las fotos vinieron con `30x39x10` y `45x39x10`, que en la planilla son `30x40+10` y `45x40+10` (la
KB vieja del cliente las nombraba con 39). Si el cliente cambia la medida en la planilla, se
actualiza `equivalencias.json` y se regenera el catálogo.

## Qué hay acá

| | |
|---|---|
| `fotos/` | Las fotos publicadas, en una carpeta plana. No se redimensionan: pesan menos de 2 MB. |
| `origen/` | Las fotos crudas tal como llegan. **Fuera de git.** |
| `equivalencias.json` | Token del nombre crudo → valor literal de la planilla. |
| `inventario.csv` | Una fila por foto: nombre, valores de la planilla, origen, md5, bytes. |
| `estandarizar.py` | `origen/` → `fotos/` + `inventario.csv`. Solo stdlib. |
| `generar_catalogo.py` | `inventario.csv` → `catalogos/*.md` + `*.pdf` con las URLs de jsDelivr. |
| `catalogos/` | Un `.md` + `.pdf` por fecha. El PDF del día es el que se sube a la KB. |

## Cómo agregar fotos

1. Copiá las fotos crudas a `origen/` con el nombre `material_estructura_manija_medida_color_NN.jpg`.
2. `python3 estandarizar.py` → dry-run. Si un token no está en `equivalencias.json`, agregalo con
   el valor exacto de la planilla.
3. `python3 estandarizar.py --aplicar`
4. `git add fotos/ inventario.csv equivalencias.json && git commit && git push`. Hasta acá las URLs
   dan 404.
5. `python3 generar_catalogo.py` y, unos minutos después del push, `python3 generar_catalogo.py --verificar`.
6. Commiteá el catálogo y subí el PDF del día a la KB de Olivia, borrando el anterior.

Para **reemplazar** una foto ya publicada, subila con otro número: jsDelivr cachea unas 12 h.

#!/usr/bin/env python3
"""Agrega propuestas nuevas de Canva a la lista del tablero "Control de Propuestas ORO".

Uso:
  python3 tools/tablero_propuestas.py --html tablero.html --cambios cambios.json --out tablero_nuevo.html
  python3 tools/tablero_propuestas.py --html tablero.html --ids        # imprime los ids de Canva que ya están en el tablero

cambios.json:
{
  "agregar": [ {"id","cliente","nombre","titulo","ciudad","emisora","valor","notas","fecha","url","carpeta"} ],
  "versiones": [ {"de": "<id de la propuesta existente>", "nueva": {"id","titulo","fecha","url", "valor"?, "notas"?, "ciudad"?, "emisora"?}} ]
}
- valor en pesos (entero) o null; fecha AAAA-MM-DD (fecha de creación en Canva, hora Bogotá).
- Una versión nueva conserva el id de la propuesta (así no se pierden estado, ejecutivos ni salidas),
  pasa la versión anterior a "versiones" y guarda el id de Canva vigente en "canvaId".
"""
import argparse, json, re, sys

CAMPOS = ["id", "cliente", "nombre", "titulo", "ciudad", "emisora", "valor", "notas", "fecha", "url", "carpeta"]
RX = re.compile(r"(const P0 = )(\[.*?\])(;\s*\n)", re.S)


def cargar(html):
    m = RX.search(html)
    if not m:
        sys.exit("No se encontró 'const P0 = [...]' en el HTML del tablero.")
    return m, json.loads(m.group(2))


def ids(p0):
    s = set()
    for p in p0:
        s.add(p["id"])
        if p.get("canvaId"):
            s.add(p["canvaId"])
        s.update(v["id"] for v in p.get("versiones", []))
    return s


def fecha_ok(f):
    return isinstance(f, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--cambios")
    ap.add_argument("--out")
    ap.add_argument("--ids", action="store_true")
    a = ap.parse_args()
    html = open(a.html, encoding="utf-8").read()
    m, p0 = cargar(html)
    if a.ids:
        print("\n".join(sorted(ids(p0))))
        return
    if not (a.cambios and a.out):
        sys.exit("Faltan --cambios y --out")
    c = json.load(open(a.cambios, encoding="utf-8"))
    conocidos = ids(p0)
    por_id = {p["id"]: p for p in p0}
    n_add = n_ver = 0

    for e in c.get("agregar", []):
        falt = [k for k in CAMPOS if k not in e]
        if falt:
            sys.exit(f"Propuesta {e.get('id')} sin campos: {falt}")
        if e["id"] in conocidos:
            print(f"Omitida (ya existe): {e['id']} {e['titulo']}")
            continue
        if not fecha_ok(e["fecha"]):
            sys.exit(f"Fecha inválida en {e['id']}: {e['fecha']}")
        if e["valor"] is not None:
            e["valor"] = int(round(float(e["valor"])))
        nuevo = {k: e[k] for k in CAMPOS}
        nuevo["notas"] = nuevo["notas"] or ""
        nuevo["anio"] = int(e["fecha"][:4])
        nuevo["versiones"] = []
        p0.append(nuevo)
        conocidos.add(e["id"])
        n_add += 1

    for v in c.get("versiones", []):
        base, nv = por_id.get(v["de"]), v["nueva"]
        if not base:
            sys.exit(f"No existe la propuesta {v['de']} para agregarle versión")
        if nv["id"] in conocidos:
            print(f"Omitida (versión ya registrada): {nv['id']}")
            continue
        if not fecha_ok(nv["fecha"]):
            sys.exit(f"Fecha inválida en {nv['id']}: {nv['fecha']}")
        anterior = {"id": base.get("canvaId") or base["id"], "titulo": base["titulo"], "fecha": base["fecha"], "url": base["url"]}
        base["versiones"] = [anterior] + base.get("versiones", [])
        base["canvaId"], base["titulo"], base["fecha"], base["url"] = nv["id"], nv["titulo"], nv["fecha"], nv["url"]
        base["anio"] = int(nv["fecha"][:4])
        if "valor" in nv:
            base["valor"] = None if nv["valor"] is None else int(round(float(nv["valor"])))
        for k in ("notas", "ciudad", "emisora", "nombre"):
            if nv.get(k) is not None:
                base[k] = nv[k]
        conocidos.add(nv["id"])
        n_ver += 1

    p0.sort(key=lambda p: p["fecha"], reverse=True)
    nuevo_js = json.dumps(p0, ensure_ascii=False)
    out = html[: m.start(2)] + nuevo_js + html[m.end(2):]
    open(a.out, "w", encoding="utf-8").write(out)
    print(f"Listo: {n_add} propuestas nuevas, {n_ver} versiones nuevas. Total en el tablero: {len(p0)}.")


if __name__ == "__main__":
    main()

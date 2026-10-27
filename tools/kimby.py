#!/usr/bin/env python3
"""Genera kimby/data.json (cifrado) para la landing "Activación Kimby".

Uso:
  python3 tools/kimby.py --db carpeta_db --clave "CONTRASEÑA" --out kimby/data.json

  --db     carpeta con la base del artefacto "Control Merch Kimby" exportada con ArtifactData (action list, out_dir):
             <db>/config/main.json, <db>/config/salidas.json, <db>/movimientos/*.json,
             <db>/reportes/<idCoordinador>/salidas/*.json,
             <db>/supervision/<idSupervisor>/parts/*.json (copia consolidada con los reportes del coordinador general)
  --clave  contraseña del cliente. NO se guarda en el repositorio.
  --out    archivo de salida.

  --resumen  (opcional) JSON con el resumen de aprendizajes que redactó la tarea semanal a partir de los informes:
             {"general": "párrafo", "positivo": ["..."], "ajustar": ["..."], "ciudades": {"bog": "...", ...}}
             Si no se pasa, se conserva el resumen que ya traía --out (se descifra con la misma contraseña).
  --textos   (opcional) archivo donde se escribe, SOLO para redactar el resumen (nunca se publica ni se sube al
             repositorio), el texto de los informes por ciudad: actividad, novedades, recomendaciones, flujo y calificación.

Solo se publica lo que muestra la pestaña Kimby: ciudades, productos, salidas (fecha y PDV), movimientos de
inventario y, de cada reporte, ciudad, fecha, PDV, merch entregado, ventas, flujo de personas y calificación del PDV,
más el resumen redactado. Nunca los textos originales de los informes, fotos, ubicación GPS, coordinadores ni
enlaces de evidencias.
"""
import argparse, base64, glob, json, os, re, sys, unicodedata
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

ITER = 100_000
BOGOTA = timezone(timedelta(hours=-5))
# Merch por salida del esquema inicial (lo presupuestado). Desde CAMBIO el coordinador puede entregar hasta el doble.
ORIG = {"delantal": 6, "botilito": 6, "lonchera": 4, "portacomidas": 3, "setbbq": 1, "sanduchera": 1, "bolsa": 21}
CAMBIO = "2026-10-16"


def norm(pw):
    s = unicodedata.normalize("NFD", pw).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", "", s).lower()


def num_(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    if isinstance(d, dict) and "data" in d and isinstance(d["data"], dict) and set(d) <= {"id", "data", "version", "updatedAt"}:
        d = d["data"]
    return d


def derive(clave, salt):
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(norm(clave).encode())


def previous_resumen(path, clave):
    """Resumen que ya publicó el archivo de salida (si existe y la contraseña coincide)."""
    try:
        d = json.load(open(path, encoding="utf-8"))
        u = base64.b64decode
        pt = AESGCM(derive(clave, u(d["s"]))).decrypt(u(d["i"]), u(d["c"]), None)
        return json.loads(pt).get("resumen")
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--clave", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--resumen")
    ap.add_argument("--textos")
    a = ap.parse_args()

    main_cfg = load(os.path.join(a.db, "config", "main.json"))
    sal_cfg = load(os.path.join(a.db, "config", "salidas.json"))
    cities = [{"id": c["id"], "name": c.get("name", c["id"])} for c in main_cfg.get("cities", [])]
    products = []
    for p in main_cfg.get("products", []):
        base = ORIG.get(p["id"])
        if base is None:
            base = num_(p.get("perSalida")) / 2
            print(f"AVISO: el producto {p['id']} no está en ORIG; se asume que el esquema inicial es la mitad de perSalida.")
        elif num_(p.get("perSalida")) not in (base, base * 2):
            print(f"AVISO: perSalida de {p['id']} en el tablero ({p.get('perSalida')}) no coincide con el esquema inicial ({base}) ni con el doble.")
        products.append({"id": p["id"], "name": p.get("name", p["id"]), "base": base, "doble": base * 2,
                         **({"bolsa": True} if p.get("bolsa") else {})})
    salidas = [{"id": s["id"], "city": s["city"], "date": s["date"], "pdv": s.get("pdv", "")}
               for s in sal_cfg.get("list", []) if s.get("id") and s.get("date")]

    movs = []
    for f in sorted(glob.glob(os.path.join(a.db, "movimientos", "*.json"))):
        m = load(f)
        movs.append({k: m[k] for k in ("tipo", "ciudad", "origen", "destino", "estado", "items", "fecha", "guia") if k in m})

    reps, upd, full = {}, {}, {}

    def add(sid, r):
        t = r.get("updatedAt") or 0
        if sid in reps and upd[sid] >= t:
            return
        upd[sid] = t
        reps[sid] = {"city": r.get("city", ""), "date": r.get("date", ""), "pdv": r.get("pdv", ""),
                     "entregado": r.get("entregado") or {}, "ventas": r.get("ventas") or 0,
                     "flujo": r.get("flujo") or "", "rating": r.get("pdvRating")}
        full[sid] = r

    # Copia consolidada que el tablero publica para el supervisor: incluye los reportes que el
    # coordinador general carga desde su propia cuenta (no aparecen en la colección "reportes").
    for f in glob.glob(os.path.join(a.db, "supervision", "*", "parts", "rep*.json")):
        for sid, r in (load(f).get("reps") or {}).items():
            add(sid, r)
    # Reportes de cada coordinador (si son más recientes, reemplazan a los de la copia consolidada).
    for f in glob.glob(os.path.join(a.db, "reportes", "*", "salidas", "*.json")):
        add(os.path.splitext(os.path.basename(f))[0], load(f))

    if not cities or not products or not salidas:
        sys.exit("Faltan datos: revisa que existan config/main.json y config/salidas.json en --db.")

    resumen = None
    if a.resumen:
        resumen = json.load(open(a.resumen, encoding="utf-8"))
    else:
        resumen = previous_resumen(a.out, a.clave)
        print("Resumen de aprendizajes: " + ("se conserva el anterior (no se pasó --resumen)." if resumen else "SIN RESUMEN."))
    if a.textos:
        names = {c["id"]: c["name"] for c in cities}
        out_t = {}
        for sid, r in sorted(full.items(), key=lambda kv: (kv[1].get("city", ""), kv[1].get("date", ""))):
            out_t.setdefault(names.get(r.get("city"), r.get("city")), []).append({
                "fecha": r.get("date"), "pdv": r.get("pdv"), "flujo": r.get("flujo"), "calificacion_pdv": r.get("pdvRating"),
                "ventas": r.get("ventas"), "actividad": (r.get("actividad") or "").strip(),
                "novedades": (r.get("novedades") or "").strip(), "recomendaciones": (r.get("recomendaciones") or "").strip()})
        json.dump(out_t, open(a.textos, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    now = datetime.now(BOGOTA)
    payload = {"config": {"cities": cities, "products": products}, "salidas": salidas, "movs": movs,
               "reps": reps, "cambio": CAMBIO, "resumen": resumen, "at": now.isoformat(timespec="seconds")}

    salt, iv = os.urandom(16), os.urandom(12)
    key = derive(a.clave, salt)
    ct = AESGCM(key).encrypt(iv, json.dumps(payload, ensure_ascii=False).encode(), None)
    b = lambda x: base64.b64encode(x).decode()
    out = {"version": 1, "actualizado": payload["at"], "iter": ITER, "s": b(salt), "i": b(iv), "c": b(ct)}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w", encoding="utf-8"))

    print(f"Actualizado: {payload['at']}")
    for c in cities:
        n = sum(1 for s in salidas if s["city"] == c["id"])
        h = sum(1 for s in salidas if s["city"] == c["id"] and s["id"] in reps)
        print(f"{c['name']}: {h} de {n} salidas reportadas")
    tr = [m for m in movs if m.get("tipo") == "traslado" and m.get("estado") == "despachado"]
    print(f"Envíos en tránsito: {len(tr)}")


if __name__ == "__main__":
    main()

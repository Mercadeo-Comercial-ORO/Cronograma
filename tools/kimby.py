#!/usr/bin/env python3
"""Genera kimby/data.json (cifrado) para la landing "Activación Kimby".

Uso:
  python3 tools/kimby.py --db carpeta_db --clave "CONTRASEÑA" --out kimby/data.json

  --db     carpeta con la base del artefacto "Control Merch Kimby" exportada con ArtifactData (action list, out_dir):
             <db>/config/main.json, <db>/config/salidas.json, <db>/movimientos/*.json,
             <db>/reportes/<idCoordinador>/salidas/*.json
  --clave  contraseña del cliente. NO se guarda en el repositorio.
  --out    archivo de salida.

Solo se publica lo que muestra la pestaña Kimby: ciudades, productos, salidas (fecha y PDV), movimientos de
inventario y, de cada reporte, ciudad, fecha, PDV, merch entregado y ventas. Nunca textos de los informes,
novedades, fotos, ubicación GPS, coordinadores ni enlaces de evidencias.
"""
import argparse, base64, glob, json, os, re, sys, unicodedata
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

ITER = 100_000
BOGOTA = timezone(timedelta(hours=-5))


def norm(pw):
    s = unicodedata.normalize("NFD", pw).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", "", s).lower()


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    if isinstance(d, dict) and "data" in d and isinstance(d["data"], dict) and set(d) <= {"id", "data", "version", "updatedAt"}:
        d = d["data"]
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--clave", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    main_cfg = load(os.path.join(a.db, "config", "main.json"))
    sal_cfg = load(os.path.join(a.db, "config", "salidas.json"))
    cities = [{"id": c["id"], "name": c.get("name", c["id"])} for c in main_cfg.get("cities", [])]
    products = [{k: p[k] for k in ("id", "name", "perSalida", "bolsa") if k in p} for p in main_cfg.get("products", [])]
    salidas = [{"id": s["id"], "city": s["city"], "date": s["date"], "pdv": s.get("pdv", "")}
               for s in sal_cfg.get("list", []) if s.get("id") and s.get("date")]

    movs = []
    for f in sorted(glob.glob(os.path.join(a.db, "movimientos", "*.json"))):
        m = load(f)
        movs.append({k: m[k] for k in ("tipo", "ciudad", "origen", "destino", "estado", "items", "fecha", "guia") if k in m})

    reps, upd = {}, {}
    for f in glob.glob(os.path.join(a.db, "reportes", "*", "salidas", "*.json")):
        sid = os.path.splitext(os.path.basename(f))[0]
        r = load(f)
        t = r.get("updatedAt") or 0
        if sid in reps and upd[sid] >= t:
            continue
        upd[sid] = t
        reps[sid] = {"city": r.get("city", ""), "date": r.get("date", ""), "pdv": r.get("pdv", ""),
                     "entregado": r.get("entregado") or {}, "ventas": r.get("ventas") or 0}

    if not cities or not products or not salidas:
        sys.exit("Faltan datos: revisa que existan config/main.json y config/salidas.json en --db.")

    now = datetime.now(BOGOTA)
    payload = {"config": {"cities": cities, "products": products}, "salidas": salidas, "movs": movs,
               "reps": reps, "at": now.isoformat(timespec="seconds")}

    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(norm(a.clave).encode())
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

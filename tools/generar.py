#!/usr/bin/env python3
"""Genera data.json (cifrado por ciudad) para la landing del cronograma ORO.

Uso:
  python3 tools/generar.py --tablero tablero.html --db carpeta_db --claves claves.json --out data.json

  --tablero  HTML del tablero "Control de Propuestas ORO" (de él se extrae la lista de propuestas de Canva).
  --db       carpeta con los documentos exportados del tablero: <db>/estado/*.json, <db>/manuales/*.json y <db>/ejecutivos/*.json
  --claves   JSON {"maestra": "...", "digital": "...", "ciudades": {"Barranquilla": "...", ...}}. NO se guarda en el repositorio.
  --out      archivo de salida (data.json en la raíz del repositorio).

Solo se publican las salidas de hoy en adelante (hora de Bogotá) de propuestas "en ejecución" o "ejecutadas",
con cliente, actividad, emisora, fecha, horario y notas de ejecución. Nunca valores, GIP ni ejecutivos.
"""
import argparse, base64, glob, hashlib, json, os, re, sys, unicodedata
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

ITER = 100_000
INDEX_SALT = "oro-cronograma-v1"
BOGOTA = timezone(timedelta(hours=-5))


def norm(pw):
    s = unicodedata.normalize("NFD", pw).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", "", s).lower()


def key_id(pw):
    return hashlib.sha256((INDEX_SALT + "|" + norm(pw)).encode()).hexdigest()[:24]


def encrypt(obj, pw):
    salt, iv = os.urandom(16), os.urandom(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER)
    key = kdf.derive(norm(pw).encode())
    ct = AESGCM(key).encrypt(iv, json.dumps(obj, ensure_ascii=False).encode(), None)
    b = lambda x: base64.b64encode(x).decode()
    return {"s": b(salt), "i": b(iv), "c": b(ct)}


def load_p0(path):
    html = open(path, encoding="utf-8").read()
    m = re.search(r"const P0 = (\[.*?\]);\s*\n", html, re.S)
    if not m:
        sys.exit("No se encontró la lista de propuestas (const P0) en el HTML del tablero.")
    return json.loads(m.group(1))


def load_dir(path):
    out = {}
    for f in glob.glob(os.path.join(path, "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        if isinstance(d, dict) and "data" in d and isinstance(d["data"], dict) and set(d) <= {"id", "data", "version", "updatedAt"}:
            d = d["data"]
        out[os.path.splitext(os.path.basename(f))[0]] = d
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tablero", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--claves", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    p0 = load_p0(a.tablero)
    estado = load_dir(os.path.join(a.db, "estado"))
    manuales = load_dir(os.path.join(a.db, "manuales"))
    ejecutivos = load_dir(os.path.join(a.db, "ejecutivos"))
    ex_nombre = lambda i: (ejecutivos.get(i) or {}).get("nombre") or ""
    claves = json.load(open(a.claves, encoding="utf-8"))

    base = [{"id": p["id"], "cliente": p.get("cliente", ""), "nombre": p.get("nombre", ""), "emisora": p.get("emisora", "Olímpica"), "manual": False} for p in p0]
    for mid, m in manuales.items():
        base.append({"id": mid, "cliente": m.get("cliente") or "Sin cliente", "nombre": m.get("nombre", ""), "emisora": m.get("emisora") or "Olímpica", "manual": True})

    now = datetime.now(BOGOTA)
    hoy = now.strftime("%Y-%m-%d")
    por_ciudad = {}
    for p in base:
        e = estado.get(p["id"]) or {}
        st = e.get("estadoEj") or ("ejecutada" if e.get("ejecutada") else "pendiente")
        if st == "pendiente" or not isinstance(e.get("ejecuciones"), list):
            continue
        emisora = (not p["manual"] and e.get("emisora")) or p["emisora"]
        for x in e["ejecuciones"]:
            ciudad = (x.get("ciudad") or "").strip()
            sal = sorted(
                [{"f": s.get("fecha", ""), "a": s.get("inicio", ""), "b": s.get("fin", "")} for s in x.get("salidas", []) if s.get("fecha", "") >= hoy],
                key=lambda s: (s["f"], s["a"]),
            )
            if not ciudad or not sal:
                continue
            por_ciudad.setdefault(ciudad, []).append({
                "id": p["id"], "cliente": p["cliente"], "nombre": p["nombre"], "emisora": emisora,
                "estado": st, "notas": (e.get("notasEjecucion") or "").strip(), "salidas": sal,
                "digital": bool(e.get("incluyeDigital")) and x.get("digital") is not False,
                "ejecutivos": [n for n in (ex_nombre(i) for i in (e.get("ejecutivos") or [])) if n],
            })
    for v in por_ciudad.values():
        v.sort(key=lambda it: (it["salidas"][0]["f"], it["salidas"][0]["a"], it["cliente"]))

    actualizado = now.strftime("%Y-%m-%dT%H:%M:%S-05:00")
    llaves = {}
    ciudades_cl = claves.get("ciudades", {})
    for ciudad, pw in ciudades_cl.items():
        llaves[key_id(pw)] = encrypt({"tipo": "ciudad", "ciudad": ciudad, "items": por_ciudad.get(ciudad, [])}, pw)
    llaves[key_id(claves["maestra"])] = encrypt({"tipo": "maestra", "ciudades": por_ciudad}, claves["maestra"])
    # Equipo digital: todas las ciudades, solo actividades en ejecución marcadas con actividades digitales
    digital = {c: [i for i in v if i["estado"] == "en_ejecucion" and i["digital"]] for c, v in por_ciudad.items()}
    digital = {c: v for c, v in digital.items() if v}
    if claves.get("digital"):
        llaves[key_id(claves["digital"])] = encrypt({"tipo": "digital", "ciudades": digital}, claves["digital"])
    data = {"version": 1, "actualizado": actualizado, "iter": ITER, "salt": INDEX_SALT, "llaves": llaves}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    sin_clave = sorted(set(por_ciudad) - set(ciudades_cl))
    print(f"Actualizado {actualizado}. Ciudades con actividades: " + ", ".join(f"{c} ({sum(len(i['salidas']) for i in v)} salidas)" for c, v in sorted(por_ciudad.items())))
    print("Equipo digital: " + (", ".join(f"{c} ({len(v)} actividades)" for c, v in sorted(digital.items())) or "sin actividades digitales en ejecución"))
    if sin_clave:
        print("ATENCIÓN: ciudades con actividades pero sin contraseña (solo visibles con la maestra): " + ", ".join(sin_clave))


if __name__ == "__main__":
    main()

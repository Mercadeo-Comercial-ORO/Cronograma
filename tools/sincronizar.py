#!/usr/bin/env python3
"""Lleva las salidas de los tableros de control de activaciones (Kimby, Buscapina) al tablero
"Control de Propuestas ORO", para que su cronograma y la landing muestren siempre las mismas fechas.

Uso:
  python3 tools/sincronizar.py --db carpeta_db --fuente Kimby=carpeta_kimby --fuente Buscapina=carpeta_buscapina --out carpeta_salida

  --db      exportación del tablero de propuestas (<db>/estado/*.json).
  --fuente  NOMBRE=carpeta con la exportación del tablero de control (<carpeta>/config/main.json y config/salidas.json).
            Se puede repetir. NOMBRE debe estar en FUENTES.
  --out     carpeta donde se escribe un JSON por propuesta que cambió (<id>.json con {"ejecuciones", "actualizado"})
            y cambios.json con el resumen [{"id","version","archivo","detalle"}]. Si nada cambió, cambios.json queda vacío ([]).

Reglas:
- Las fechas de cada ciudad se reemplazan por las del tablero de control (todas, pasadas y futuras).
- Horario de cada salida: el del tablero de control si lo tiene; si no, el que ya tenía esa fecha en el tablero de
  propuestas; si no, el horario más usado en esa ciudad; si no, el horario por defecto de la fuente.
- Se conservan presupuesto, GIP, valores por medio y la marca de digital de cada ciudad.
- Una ciudad nueva en el tablero de control se agrega como ciudad de ejecución; una ciudad que ya no está se deja igual.
"""
import argparse, glob, json, os, re, unicodedata
from collections import Counter
from datetime import datetime, timezone

# id de la propuesta en el tablero "Control de Propuestas ORO" y horario por defecto de cada tablero de control
FUENTES = {
    "Kimby": {"propuesta": "m-muybyqiy0paz", "ini": "10:00", "fin": "12:00"},
    "Buscapina": {"propuesta": "DAHWnuk-270", "ini": "15:00", "fin": "20:00"},
}


def nk(t):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", t or "").encode("ascii", "ignore").decode().lower())


def cargar(path):
    d = json.load(open(path, encoding="utf-8"))
    ver = d.get("version") if isinstance(d, dict) else None
    if isinstance(d, dict) and isinstance(d.get("data"), dict) and set(d) <= {"id", "data", "version", "updatedAt"}:
        d = d["data"]
    return d, ver


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--fuente", action="append", default=[])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cambios = []

    for f in a.fuente:
        nombre, carpeta = f.split("=", 1)
        cfg = FUENTES[nombre]
        pid = cfg["propuesta"]
        ruta = os.path.join(a.db, "estado", pid + ".json")
        if not os.path.exists(ruta):
            print(f"{nombre}: la propuesta {pid} no tiene estado en el tablero; no se sincroniza.")
            continue
        est, ver = cargar(ruta)
        main_cfg, _ = cargar(os.path.join(carpeta, "config", "main.json"))
        sal_cfg, _ = cargar(os.path.join(carpeta, "config", "salidas.json"))
        nombres = {c["id"]: c.get("name") or c["id"] for c in main_cfg.get("cities", [])}
        por_ciudad = {}
        for s in sal_cfg.get("list", []):
            if s.get("date"):
                por_ciudad.setdefault(nombres.get(s.get("city"), s.get("city")), []).append(s)

        ejecs = [dict(x) for x in (est.get("ejecuciones") or [])]
        detalle = []
        for ciudad, lista in por_ciudad.items():
            x = next((e for e in ejecs if nk(e.get("ciudad")) == nk(ciudad)), None)
            if x is None:
                x = {"ciudad": ciudad, "salidas": [], "gip": "", "dist": {}, "presupuesto": None,
                     "digital": bool(est.get("incluyeDigital"))}
                ejecs.append(x)
            previas = {s.get("fecha"): s for s in x.get("salidas", [])}
            comun = Counter((s.get("inicio", ""), s.get("fin", "")) for s in x.get("salidas", []) if s.get("inicio"))
            h_ini, h_fin = comun.most_common(1)[0][0] if comun else (cfg["ini"], cfg["fin"])
            nuevas = []
            for s in sorted(lista, key=lambda s: s["date"]):
                p = previas.get(s["date"]) or {}
                si, sf = s.get("ini") or s.get("horaInicio") or "", s.get("fin") or s.get("horaFin") or ""
                if si or sf:  # el tablero de control trae horario: manda
                    ini, fin = si or p.get("inicio") or h_ini, sf or p.get("fin") or h_fin
                    if ini and fin and fin <= ini:
                        ini, fin = (si, "") if si else ("", sf)
                else:
                    ini, fin = p.get("inicio") or h_ini, p.get("fin") or h_fin
                nuevas.append({"fecha": s["date"], "inicio": ini, "fin": fin})
            antes = [(s.get("fecha"), s.get("inicio"), s.get("fin")) for s in sorted(x.get("salidas", []), key=lambda s: s.get("fecha", ""))]
            despues = [(s["fecha"], s["inicio"], s["fin"]) for s in nuevas]
            if antes != despues:
                quitadas = sorted(set(previas) - {s["fecha"] for s in nuevas})
                agregadas = sorted({s["fecha"] for s in nuevas} - set(previas))
                horario = sum(1 for s in nuevas if s["fecha"] in previas and
                              (previas[s["fecha"]].get("inicio"), previas[s["fecha"]].get("fin")) != (s["inicio"], s["fin"]))
                partes = []
                if agregadas: partes.append("nuevas " + ", ".join(agregadas))
                if quitadas: partes.append("quitadas " + ", ".join(quitadas))
                if horario: partes.append(f"{horario} con horario distinto")
                detalle.append(f"{ciudad}: " + "; ".join(partes))
                x["salidas"] = nuevas
                x["inicio"], x["cierre"] = nuevas[0]["fecha"], nuevas[-1]["fecha"]
        if detalle:
            archivo = os.path.join(a.out, pid + ".json")
            json.dump({"ejecuciones": ejecs, "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")},
                      open(archivo, "w", encoding="utf-8"), ensure_ascii=False)
            cambios.append({"id": pid, "fuente": nombre, "version": ver, "archivo": archivo, "detalle": detalle})
            print(f"{nombre}: " + " | ".join(detalle))
        else:
            print(f"{nombre}: sin cambios")
    json.dump(cambios, open(os.path.join(a.out, "cambios.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()

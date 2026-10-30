#!/usr/bin/env python3
"""Construye el portal de gerencia (carpeta gerencia/ del repositorio): vistas de solo lectura de los tableros
de Claude, cifradas con una sola contraseña, para verlas sin cuenta de Claude.

Uso:
  python3 tools/gerencia.py --faltantes --datos DIR
      Imprime (JSON) los ids de fotos que todavía no están cifrados en gerencia/f, por tablero.
  python3 tools/gerencia.py --datos DIR --apps DIR_APPS --fotos DIR_FOTOS --clave CLAVE --claves claves.json [--out gerencia]

  --datos  exportación de las bases (ArtifactData con out_dir), una carpeta por tablero:
           DIR/buscapina, DIR/comarrico, DIR/kimby, DIR/tablero  (cada una con <colección>/<doc>.json)
  --apps   HTML completo leído de cada tablero (Artifact read): DIR_APPS/buscapina.html, comarrico.html, kimby.html, tablero.html
  --fotos  fotos descargadas: DIR_FOTOS/<tablero>/<id>.<ext> (solo hacen falta las que imprime --faltantes)
  --clave  contraseña del portal de gerencia (nunca se escribe en el repositorio)
  --claves JSON con "maestra" (cronograma general) y "kimby" (landing Kimby); viajan cifrados al portal.

Todo lo que se publica va cifrado con AES-GCM (clave PBKDF2 de la contraseña): HTML de las vistas, datos y fotos.
"""
import argparse, base64, glob, io, json, os, re, sys, time
from datetime import datetime, timezone, timedelta
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

SAL = b"oro-gerencia-v1"
ITER = 150000
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEX = re.compile(r"\b[0-9a-f]{32}\b")
KIMBY_DEMO_UID = "u_CjltZQvds22K8ShFdkSkqg"   # coordinador de Barranquilla: sus reportes sirven de ejemplo
OWNER_UID = "u_poWye5htYCnR8u4OFuW9hA"

# vista -> (tablero de origen, título, configuración)
NOTA_RESUMEN = ('<div class="__gnota" role="note"><b>Importante:</b> estas cifras no corresponden al total real ejecutado por el área. '
                'Solo incluyen las propuestas registradas en este reporte, creado en Claude por el área de Estrategia Comercial y '
                'Activaciones en agosto de 2026.</div>')
NOTA_KIMBY = ('<div class="__gnota" role="note"><b>Vista de ejemplo.</b> Así registra cada coordinador de ORO sus salidas: '
              'el formulario muestra la ciudad de <b>Barranquilla</b> como ejemplo, pero el mismo proceso se hace en cada ciudad '
              '(Bogotá, Medellín y Cartagena). En la segunda pestaña está el control de merch con los escenarios A y B y las '
              'recomendaciones. Lo que llenes aquí no se guarda en el tablero real.</div>')
KM_CSS_DEMO = ".k2-main>.sc-t,.k2-main>.intro,.k2-main>section.sec:not(:has(#merch)){display:none!important}"

# vista -> (tablero de origen, título, configuración)
VISTAS = {
    "resumen": ("tablero", "Resumen de propuestas · ORO", {
        "owner": True, "uid": OWNER_UID, "can": False, "ls": {"oro-view": "resumen"},
        "css": "#tab-lista,#tab-gantt,#tab-config{display:none!important}",
        "nota": {"sel": "#view-resumen", "pos": "afterbegin", "html": NOTA_RESUMEN}}),
    "buscapina": ("buscapina", "Informes Buscapina · ORO", {
        "owner": True, "uid": OWNER_UID, "tabs": ["informes"], "ls": {"buscapina-tab": "informes"}, "selector": True}),
    "comarrico": ("comarrico", "Informes Comarrico · ORO", {
        "owner": True, "uid": OWNER_UID, "tabs": ["informes"], "ls": {"comarrico-tab": "informes"}, "selector": True,
        "extra": [{"n": "Informe al cliente", "href": "comarrico-informe.html"}]}),
    "comarrico-informe": ("comarrico", "Scorecard Comarrico · ORO", {"generado": "scorecard_comarrico"}),
    "kimby-reportes": ("kimby", "Reportes coordinadores Kimby · ORO", {
        "owner": True, "uid": OWNER_UID, "tabs": ["reportar", "kimby"], "ls": {"kimby-tab": "reportar"},
        "nombres": {"reportar": "Reportar salida (ejemplo Barranquilla)", "kimby": "Control de merch: escenarios A y B"},
        "css": "label.f:has(#r-city),.btns:has(#r-savedir){display:none!important}", "rol": "Coordinador · Barranquilla (ejemplo)", "kmcss": KM_CSS_DEMO,
        "nota": {"sel": "main", "pos": "beforebegin", "html": NOTA_KIMBY},
        "parches": [["root.innerHTML=`<style>${KM_CSS}</style>", "root.innerHTML=`<style>${KM_CSS}${window.__KMCSS||''}</style>"]],
        "demo": True}),
}


def clave_aes(pw):
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=SAL, iterations=ITER).derive(pw.strip().encode())


def cifrar(key, datos):
    iv = os.urandom(12)
    return iv + AESGCM(key).encrypt(iv, datos, None)


def leer_db(carpeta, filtro=None):
    db = {}
    for f in glob.glob(os.path.join(carpeta, "**", "*.json"), recursive=True):
        ruta = os.path.relpath(f, carpeta)[:-5].replace(os.sep, "/")
        if ruta.count("/") % 2 != 1 or (filtro and not filtro(ruta)):
            continue
        d = json.load(open(f, encoding="utf-8"))
        if isinstance(d, dict) and set(d) <= {"id", "data", "version", "updatedAt"} and isinstance(d.get("data"), dict):
            d = d["data"]
        db[ruta] = d
    return db


def db_vista(vista, datos):
    origen = VISTAS[vista][0]
    carpeta = os.path.join(datos, origen)
    if vista == "kimby-reportes":
        # vista de control general, con Barranquilla como primera ciudad (la que abre el formulario de ejemplo)
        db = leer_db(carpeta, lambda r: r.split("/")[0] in ("config", "movimientos", "reportes", "asignacion"))
        main = db.get("config/main")
        if main and main.get("cities"):
            main["cities"].sort(key=lambda c: c.get("id") != "baq")
        return db
    return leer_db(carpeta)


def ids_fotos(obj):
    return set(HEX.findall(json.dumps(obj, ensure_ascii=False)))


def limpiar_html(html):
    """Quita el esqueleto que agrega la publicación y adapta el código a la vista de gerencia."""
    # solo el envoltorio del principio y del final: el código de las apps arma otros HTML dentro de sus textos
    html = re.sub(r"^\s*<!doctype html>\s*<html>\s*<head>.*?</head>\s*<body>", "", html, count=1, flags=re.I | re.S)
    html = re.sub(r"</body>\s*</html>\s*$", "", html, count=1, flags=re.I)
    html = re.sub(r"^\s*<title>.*?</title>", "", html, count=1, flags=re.I | re.S)
    html = html.replace("/_blob/", "data:,ph-")
    html = html.replace("function tabsDef(){", "function tabsDef(){return window.__TF(tabsDef0())}function tabsDef0(){", 1)
    return html.strip()


PAGINA = """<!doctype html>
<html lang="es" data-vista="{vista}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>{titulo}</title>
<style>html,body{{margin:0}}#__g{{font:15px system-ui,sans-serif;color:#666178;padding:40px 20px;text-align:center}}
@media (prefers-color-scheme:dark){{html{{background:#14121d}}}}</style>
<script src="app.js?v={ver}"></script>
</head><body><div id="__g">Cargando…</div></body></html>
"""


def ahora_bogota():
    return datetime.now(timezone.utc) - timedelta(hours=5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", required=True)
    ap.add_argument("--apps")
    ap.add_argument("--fotos")
    ap.add_argument("--clave")
    ap.add_argument("--claves")
    ap.add_argument("--out", default=os.path.join(RAIZ, "gerencia"))
    ap.add_argument("--faltantes", action="store_true")
    a = ap.parse_args()

    dbs = {v: db_vista(v, a.datos) for v in VISTAS}
    out_f = os.path.join(a.out, "f")
    os.makedirs(out_f, exist_ok=True)

    # fotos que usa cada tablero (en sus datos y en su HTML)
    por_tablero = {}
    for v, (origen, _, _) in VISTAS.items():
        if origen == "tablero":
            continue
        ids = ids_fotos({k: x for k, x in dbs[v].items() if origen != "kimby" or k.startswith(f"reportes/{KIMBY_DEMO_UID}/")})
        if a.apps and os.path.exists(os.path.join(a.apps, origen + ".html")):
            ids |= set(re.findall(r"/_blob/([0-9a-f]{32})", open(os.path.join(a.apps, origen + ".html"), encoding="utf-8").read()))
        por_tablero.setdefault(origen, set()).update(ids)
    faltan = {t: sorted(i for i in ids if not os.path.exists(os.path.join(out_f, i + ".bin"))) for t, ids in por_tablero.items()}

    if a.faltantes:
        print(json.dumps(faltan, indent=1))
        return
    if not (a.apps and a.clave and a.claves):
        sys.exit("Faltan --apps, --clave y --claves")
    key = clave_aes(a.clave)
    claves = json.load(open(a.claves, encoding="utf-8"))

    # 1. fotos nuevas (reducidas a 1600 px como máximo)
    from PIL import Image
    nuevas, sin_archivo = 0, []
    for t, ids in faltan.items():
        for i in ids:
            src = (glob.glob(os.path.join(a.fotos or "", t, i + ".*")) or glob.glob(os.path.join(a.fotos or "", "*", i + ".*")))
            if not src:
                sin_archivo.append(i)
                continue
            raw = open(src[0], "rb").read()
            try:
                im = Image.open(io.BytesIO(raw))
                if im.format == "JPEG" and max(im.size) > 1600:
                    im.thumbnail((1600, 1600))
                    b = io.BytesIO()
                    im.convert("RGB").save(b, "JPEG", quality=80, optimize=True)
                    raw = b.getvalue()
            except Exception:
                pass
            open(os.path.join(out_f, i + ".bin"), "wb").write(cifrar(key, raw))
            nuevas += 1

    # 2. vistas: HTML de la app + datos, cifrados
    ver = str(int(time.time()))
    os.makedirs(os.path.join(a.out, "d"), exist_ok=True)
    resumen = []
    for v, (origen, titulo, cfg) in VISTAS.items():
        cfg = dict(cfg)
        if cfg.get("generado"):
            import importlib
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            html = importlib.import_module(cfg.pop("generado")).html(dbs[v])
            dbs[v] = {}
        else:
            html = limpiar_html(open(os.path.join(a.apps, origen + ".html"), encoding="utf-8").read())
        for viejo, nuevo in cfg.pop("parches", []):
            if viejo in html:
                html = html.replace(viejo, nuevo)
            else:
                print(f"AVISO: {v}: no se pudo aplicar un ajuste al código del tablero (cambió el tablero).")
        if "tabsDef0" not in html and cfg.get("tabs"):
            print(f"AVISO: {v}: no se encontró tabsDef(); se muestran todas las pestañas del tablero.")
        carga = dict(cfg, html=html, db=dbs[v], titulo=titulo)
        open(os.path.join(a.out, "d", v + ".bin"), "wb").write(cifrar(key, json.dumps(carga, ensure_ascii=False).encode()))
        open(os.path.join(a.out, v + ".html"), "w", encoding="utf-8").write(PAGINA.format(vista=v, titulo=titulo, ver=ver))
        resumen.append(f"{v}: {len(dbs[v])} documentos")

    # 3. datos del portal (contraseñas de las otras landings y fecha)
    hub = {"maestra": claves["maestra"], "kimby": claves["kimby"],
           "actualizado": ahora_bogota().strftime("%Y-%m-%d %H:%M")}
    open(os.path.join(a.out, "d", "hub.bin"), "wb").write(cifrar(key, json.dumps(hub, ensure_ascii=False).encode()))
    # versión para evitar caché vieja del cargador
    idx = os.path.join(a.out, "index.html")
    if os.path.exists(idx):
        s = open(idx, encoding="utf-8").read()
        open(idx, "w", encoding="utf-8").write(re.sub(r"app\.js\?v=\d+", f"app.js?v={ver}", s))
    print("Portal de gerencia generado: " + "; ".join(resumen) + f". Fotos nuevas cifradas: {nuevas}.")
    if sin_archivo:
        print(f"AVISO: {len(sin_archivo)} fotos sin archivo descargado (se verán vacías): " + ", ".join(sin_archivo[:10]))


if __name__ == "__main__":
    main()

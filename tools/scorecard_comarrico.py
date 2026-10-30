"""Scorecard final de la activación Comarrico (portal de gerencia). Lo usa tools/gerencia.py.

html(db) recibe la base exportada del tablero Comarrico ({ruta: documento}) y devuelve el HTML de la vista
(estilos + contenido + script del PDF). Las fotos van como data:,ph-<id> y las resuelve gerencia/app.js.
Los aprendizajes son fijos: la activación terminó el 25 de octubre de 2026 y se redactaron con los informes.
"""
import html as H
import json
from datetime import date

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

APRENDIZAJES = {
    "general": (
        "La activación Comarrico con Olímpica Stereo hizo 10 salidas en Barranquilla y Soledad entre el 13 y el 25 de "
        "octubre de 2026. En las tiendas de barrio, el combo de urgencia (2 pastas Comarrico + 2 salchichas Cunit) fue el "
        "más vendido en casi todas las salidas, y la presencia de la emisora atrajo compradores nuevos al punto. Las tiendas "
        "del suroccidente, Los Robles y Soledad tuvieron la mejor respuesta. Las Megatiendas mostraron el mayor potencial de "
        "venta por punto, con el cierre del 25 de octubre como la salida de mayores ventas, aunque al comienzo hubo "
        "dificultades de ingreso por falta de comunicación entre el cliente y la tienda. Las principales novedades fueron "
        "tiendas cerradas o sin producto Comarrico y Cunit, puntos programados que no eran tiendas y la lluvia en la última semana."),
    "positivo": [
        "El combo de urgencia fue el preferido por los compradores: es el de menor valor y el más fácil de decidir.",
        "La activación con la emisora atrajo nuevos compradores y buen tráfico, sobre todo en el suroccidente, Los Robles y Soledad.",
        "Las Megatiendas concentraron las ventas más altas por punto; en Megatiendas Lo Nuestro la respuesta del público fue excelente.",
        "La salida de cierre en Megatienda (25 de octubre) logró las mayores ventas de la activación, con 8 bonos de consumo entregados.",
    ],
    "ajustar": [
        "Confirmar antes de cada salida que las tiendas tengan producto Comarrico y Cunit: en varias no había producto y no se pudo activar.",
        "Validar la ruta con anticipación: algunos puntos programados eran restaurantes, otro quedaba fuera de la ciudad y otro no tenía dirección.",
        "Asegurar con el cliente la autorización de ingreso a cada Megatienda y llegar entre 11:30 y 11:45 a. m. para montar la ruleta.",
        "Tener un plan para lluvia: en la última semana el clima redujo la participación.",
        "Reforzar el mensaje de calidad del producto: algunos compradores asociaron la marca con «la más económica».",
    ],
    "duenos": [
        ("15 oct", "En una Megatienda la administración informó que no había recibido el correo de autorización, por eso no se pudo ingresar a tiempo."),
        ("21 oct", "Una tienda no pudo activarse porque no le había llegado el producto Comarrico ni Cunit."),
        ("24 oct", "Un autoservicio prefirió no participar en la actividad."),
        ("17 oct", "Tenderos con buena disposición: en algunas tiendas la respuesta y la recordación de la marca fueron muy buenas."),
    ],
    "clientes": [
        ("14–23 oct", "El combo de urgencia fue el más comprado en las tiendas de barrio."),
        ("16 oct", "La activación de la emisora atrajo nuevos compradores en las tiendas del suroccidente."),
        ("17 oct", "En una Megatienda con mucho tráfico, algunas personas dijeron que no compraban porque es la marca más económica."),
        ("22 oct", "En Megatiendas Lo Nuestro la respuesta del público fue excelente."),
        ("24 oct", "Con lluvia la participación fue moderada, aunque una vez escampó la Megatienda se pudo activar."),
    ],
}


def _num(x):
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _pesos(v):
    return "$ " + f"{round(v):,}".replace(",", ".")


def _n(v):
    return f"{round(v):,}".replace(",", ".")


def _d1(v):
    return f"{v:.1f}".replace(".", ",")


def _fecha(iso, larga=False):
    d = date.fromisoformat(iso)
    if larga:
        return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"
    return f"{DIAS[d.weekday()][:3]} {d.day} {MESES[d.month - 1][:3]}"


def _gauge(pct, cls, val, sub):
    import math
    p = max(0.0, min(1.0, pct))
    a = math.pi * (1 - p)
    x, y = 110 + 90 * math.cos(a), 110 - 90 * math.sin(a)
    arc = f'<path class="br" d="M20 110 A90 90 0 0 1 {x:.2f} {y:.2f}"/>' if p > 0.001 else ""
    return (f'<figure class="g {cls}"><svg viewBox="0 0 220 122" aria-hidden="true"><path class="tr" d="M20 110 A90 90 0 0 1 200 110"/>{arc}</svg>'
            f'<figcaption><b>{H.escape(val)}</b><span>{H.escape(sub)}</span></figcaption><span class="e0">0%</span><span class="e1">100%</span></figure>')


def datos(db):
    main = db.get("config/main", {})
    prods = main.get("products", [])
    salidas = sorted(db.get("config/salidas", {}).get("list", []), key=lambda s: s["date"])
    reps = {}
    for ruta, d in db.items():
        if ruta.startswith("reportes/") and ruta.count("/") == 3:
            sid = d.get("salidaId") or ruta.rsplit("/", 1)[1]
            if sid not in reps or (d.get("updatedAt") or 0) >= (reps[sid].get("updatedAt") or 0):
                reps[sid] = d
    bolsa = {p["id"] for p in prods if p.get("bolsa")}
    filas = []
    for s in salidas:
        r = reps.get(s["id"])
        prog = len(s.get("tiendas", []))
        if not r:
            filas.append({"s": s, "r": None, "prog": prog})
            continue
        ts = r.get("tiendas", [])
        act = [t for t in ts if _num(t.get("ventas")) > 0 or any(_num(v) > 0 for v in (t.get("entregado") or {}).values())]
        ent = {k: _num(v) for k, v in (r.get("entregado") or {}).items()}
        premios = sum(v for k, v in ent.items() if k not in bolsa)
        ventas = _num(r.get("ventas")) or sum(_num(t.get("ventas")) for t in ts)
        mega = any(t.get("mega") for t in ts)
        filas.append({"s": s, "r": r, "prog": prog, "visit": len(ts), "act": len(act), "ent": ent, "premios": premios,
                      "ventas": ventas, "efe": _num(r.get("efectividad")), "mega": mega,
                      "flujo": [t.get("flujo") for t in ts if t.get("flujo") is not None]})
    return main, prods, filas


def html(db):
    main, prods, filas = datos(db)
    hechas = [f for f in filas if f["r"]]
    marca = main.get("marca", {})
    logo_c = (marca.get("logoCliente") or "").replace("/_blob/", "data:,ph-")
    logo_e = (marca.get("logoEmisora") or "").replace("/_blob/", "data:,ph-")
    bolsa = {p["id"] for p in prods if p.get("bolsa")}
    n_sal, n_hechas = len(filas), len(hechas)
    prog = sum(f["prog"] for f in filas)
    visit = sum(f["visit"] for f in hechas)
    act = sum(f["act"] for f in hechas)
    ventas = sum(f["ventas"] for f in hechas)
    premios = sum(f["premios"] for f in hechas)
    bolsas = sum(v for f in hechas for k, v in f["ent"].items() if k in bolsa)
    ticket = ventas / premios if premios else 0
    efe = sum(f["efe"] for f in hechas) / n_hechas if n_hechas else 0
    flujos = [x for f in hechas for x in f["flujo"] if x]
    flujo = sum(flujos) / len(flujos) if flujos else 0
    megas = [f for f in hechas if f["mega"]]
    v_mega = sum(_num(t.get("ventas")) for f in hechas for t in f["r"].get("tiendas", []) if t.get("mega"))
    ini, fin = filas[0]["s"]["date"], filas[-1]["s"]["date"]

    # merch: plan (merch de la salida o perSalida) frente a lo entregado
    filas_m = []
    for p in prods:
        plan = sum(_num((f["s"].get("merch") or {}).get(p["id"], p.get("perSalida"))) for f in filas)
        entregado = sum(f["ent"].get(p["id"], 0) for f in hechas)
        filas_m.append((p, plan, entregado))

    # tiendas con más ventas
    tiendas = []
    for f in hechas:
        for t in f["r"].get("tiendas", []):
            if _num(t.get("ventas")) > 0:
                tiendas.append((_num(t.get("ventas")), t, f["s"]["date"]))
    tiendas.sort(key=lambda x: -x[0])
    vmax = max([f["ventas"] for f in hechas] or [1])

    e = H.escape
    sal_rows = "".join(
        f'<tr><td class="nowrap"><b>{e(_fecha(f["s"]["date"], True).capitalize())}</b>{"<small>Megatienda</small>" if f["r"] and f["mega"] else ""}</td>'
        + (f'<td class="r">{f["act"]} de {f["prog"]}</td><td class="bar-c"><span class="bar" style="width:{max(2, 100 * f["ventas"] / vmax):.1f}%"></span><b>{_pesos(f["ventas"])}</b></td>'
           f'<td class="r">{_n(f["premios"])}</td><td class="r">{_pesos(f["ventas"] / f["premios"]) if f["premios"] else "—"}</td>'
           f'<td class="r">{_d1(f["efe"])} / 5</td>' if f["r"] else '<td colspan="5" class="mini">Sin reporte</td>')
        + "</tr>" for f in filas)
    m_rows = "".join(
        f'<tr><td><b>{e(p["name"])}</b></td><td class="r">{_n(plan)}</td><td class="r">{_n(ent)}</td>'
        f'<td class="r">{(f"{100 * ent / plan:.0f} %" if plan else "—")}</td></tr>' for p, plan, ent in filas_m)
    t_rows = "".join(
        f'<tr><td class="r mini">{i + 1}</td><td><b>{e(t.get("nombre", ""))}</b>{"<small>Megatienda</small>" if t.get("mega") else ""}</td>'
        f'<td>{e((t.get("barrio") or "—").title())}</td><td class="nowrap">{e(_fecha(d))}</td><td class="r">{_pesos(v)}</td></tr>'
        for i, (v, t, d) in enumerate(tiendas[:10]))
    fotos = ""
    for f in hechas:
        fs = (f["r"].get("fotos") or {})
        ids = (fs.get("inicio") or [])[:1] + (fs.get("cierre") or [])[:1]
        if ids:
            fotos += (f'<figure class="ph"><div>' + "".join(f'<img src="data:,ph-{e(i)}" alt="Foto de la salida del {e(_fecha(f["s"]["date"], True))}">' for i in ids)
                      + f'</div><figcaption>{e(_fecha(f["s"]["date"], True).capitalize())}</figcaption></figure>')
    A = APRENDIZAJES
    li = lambda xs: "".join(f"<li>{e(x)}</li>" for x in xs)
    cm = lambda xs: "".join(f'<tr><td class="nowrap"><b>{e(a)}</b></td><td>{e(b)}</td></tr>' for a, b in xs)
    st = iter(range(1, 20))

    return f"""<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@75..100,500..900&family=Figtree:wght@400;500;600;700&display=swap">
<style>{CSS}</style>
<header class="band"><div class="band-in">
<img class="k" src="{e(logo_c)}" alt="Comarrico">
<div class="band-title"><h1>Scorecard Activación Comarrico</h1><p>Resultados finales · Olímpica Stereo · Barranquilla</p></div>
<img class="o" src="{e(logo_e)}" alt="Olímpica Stereo">
</div></header>
<nav class="tabs"><div class="tabs-in"><a href="comarrico.html">Informes por salida</a><a href="comarrico-informe.html" aria-current="page">Informe al cliente</a>
<button type="button" class="btn pri" id="pdf">Descargar informe en PDF</button></div></nav>
<main id="sc">
<section class="intro" aria-label="Qué fue esta actividad">
  <p><b>Actividad finalizada.</b> Olímpica Stereo y Comarrico recorrieron tiendas de barrio y Megatiendas de Barranquilla y Soledad. En cada punto, quienes compraban un combo de pastas Comarrico y salchichas Cunit jugaban la ruleta de premios; en las Megatiendas además se entregaron bonos de consumo de $100.000.</p>
  <dl><div><dt>Periodo:</dt> <dd>{e(_fecha(ini, True))} al {e(_fecha(fin, True))} de 2026</dd></div><div><dt>Salidas:</dt> <dd>{n_hechas} de {n_sal} ejecutadas</dd></div><div><dt>Puntos:</dt> <dd>tiendas de barrio y Megatiendas</dd></div></dl>
</section>

<section class="sec" aria-labelledby="h0">
  <div class="sec-h"><span class="step">{next(st)} · Aclaraciones</span><h2 id="h0">Cómo leer este scorecard</h2></div>
  <div class="panel acl"><dl>
    <div><dt>Salida ejecutada</dt><dd>Día de ruta con informe de cierre del coordinador de ORO.</dd></div>
    <div><dt>Tienda activada</dt><dd>Punto donde hubo ventas o se entregó merch. Las tiendas programadas que estaban cerradas, sin producto o que no eran tiendas no cuentan como activadas.</dd></div>
    <div><dt>Ventas</dt><dd>Valor de los combos que compraron los participantes, según la planilla de cada punto.</dd></div>
    <div><dt>Ticket promedio</dt><dd>Ventas ÷ premios entregados (sin contar las bolsas de cambrel).</dd></div>
    <div><dt>Efectividad</dt><dd>Calificación de 1 a 5 que el coordinador da a cada tienda según la respuesta del punto; la de la salida es el promedio.</dd></div>
  </dl></div>
</section>

<section class="sec" aria-labelledby="h1">
  <div class="sec-h"><span class="step">{next(st)} · Resumen general</span><h2 id="h1">Así terminó la activación</h2></div>
  <div class="panel"><div class="big2">
    <div class="gwrap">{_gauge(n_hechas / n_sal if n_sal else 0, "s1", f"{100 * n_hechas / n_sal:.0f} %" if n_sal else "—", f"{n_hechas} de {n_sal}")}<div><div class="gt">Salidas ejecutadas</div><div class="gs">Todas las salidas programadas se realizaron.</div></div></div>
    <div class="gwrap">{_gauge(act / prog if prog else 0, "s2", f"{100 * act / prog:.0f} %" if prog else "—", f"{act} de {prog}")}<div><div class="gt">Tiendas activadas</div><div class="gs">Frente a las tiendas programadas en la ruta ({visit} visitadas).</div></div></div>
    <div class="gwrap">{_gauge(efe / 5, "s1", _d1(efe), "de 5")}<div><div class="gt">Efectividad promedio</div><div class="gs">Promedio de las calificaciones de las salidas.</div></div></div>
  </div></div>
  <div class="kpis">
    <div class="kpi"><span class="l">Ventas totales</span><span class="v">{_pesos(ventas)}</span><span class="s">Combos vendidos en las {n_hechas} salidas</span></div>
    <div class="kpi"><span class="l">Premios entregados</span><span class="v">{_n(premios)}</span><span class="s">Más {_n(bolsas)} bolsas de cambrel</span></div>
    <div class="kpi"><span class="l">Ticket promedio</span><span class="v">{_pesos(ticket)}</span><span class="s">Ventas por cada premio entregado</span></div>
    <div class="kpi"><span class="l">Megatiendas</span><span class="v">{len(megas)} salidas</span><span class="s">{_pesos(v_mega)} en ventas ({100 * v_mega / ventas:.0f} % del total)</span></div>
    <div class="kpi"><span class="l">Flujo de personas</span><span class="v">{_d1(flujo)} / 5</span><span class="s">Promedio por tienda activada</span></div>
    <div class="kpi"><span class="l">Venta promedio por salida</span><span class="v">{_pesos(ventas / n_hechas if n_hechas else 0)}</span><span class="s">Ventas ÷ salidas ejecutadas</span></div>
  </div>
</section>

<section class="sec" aria-labelledby="h2">
  <div class="sec-h"><span class="step">{next(st)} · Por salida</span><h2 id="h2">Resultados de cada salida</h2><p>La barra compara las ventas de cada salida con la de mayores ventas.</p></div>
  <div class="tbl-wrap"><table><thead><tr><th>Salida</th><th class="r">Tiendas activadas</th><th>Ventas</th><th class="r">Premios</th><th class="r">Ticket</th><th class="r">Efectividad</th></tr></thead>
  <tbody>{sal_rows}<tr class="foot"><td>Total</td><td class="r">{act} de {prog}</td><td>{_pesos(ventas)}</td><td class="r">{_n(premios)}</td><td class="r">{_pesos(ticket)}</td><td class="r">{_d1(efe)} / 5</td></tr></tbody></table></div>
</section>

<section class="sec res" aria-labelledby="h3">
  <div class="sec-h"><span class="step">{next(st)} · Aprendizajes</span><h2 id="h3">Lo que vimos en las salidas</h2><p>Resumen de los informes de cierre de los coordinadores de ORO.</p></div>
  <div class="panel">
    <p class="main">{e(A["general"])}</p>
    <div class="cols"><div class="col pos"><h4>Lo positivo</h4><ul>{li(A["positivo"])}</ul></div><div class="col adj"><h4>Para tener en cuenta en una próxima activación</h4><ul>{li(A["ajustar"])}</ul></div></div>
    <div class="cmt"><h4>Comentarios clave</h4>
      <div class="tbl-wrap"><table><thead><tr><th style="width:110px">Fecha</th><th>De los tenderos y administradores de los puntos</th></tr></thead><tbody>{cm(A["duenos"])}</tbody></table></div>
      <div class="tbl-wrap"><table><thead><tr><th style="width:110px">Fecha</th><th>De los compradores y participantes</th></tr></thead><tbody>{cm(A["clientes"])}</tbody></table></div>
    </div>
  </div>
</section>

<section class="sec" aria-labelledby="h4">
  <div class="sec-h"><span class="step">{next(st)} · Merch</span><h2 id="h4">Merch planeado frente a entregado</h2><p>Lo planeado es la cantidad prevista por salida en toda la activación; los bonos de consumo solo se entregaban en Megatiendas.</p></div>
  <div class="tbl-wrap"><table><thead><tr><th>Producto</th><th class="r">Planeado</th><th class="r">Entregado</th><th class="r">Cumplimiento</th></tr></thead><tbody>{m_rows}</tbody></table></div>
</section>

<section class="sec" aria-labelledby="h5">
  <div class="sec-h"><span class="step">{next(st)} · Puntos de venta</span><h2 id="h5">Las 10 tiendas con más ventas</h2></div>
  <div class="tbl-wrap"><table><thead><tr><th class="r">#</th><th>Tienda</th><th>Barrio</th><th>Salida</th><th class="r">Ventas</th></tr></thead><tbody>{t_rows}</tbody></table></div>
</section>

{f'''<section class="sec" aria-labelledby="h6">
  <div class="sec-h"><span class="step">{next(st)} · Evidencias</span><h2 id="h6">Inicio y cierre de cada salida</h2></div>
  <div class="gal">{fotos}</div>
</section>''' if fotos else ""}
<p class="foot-n">Fuente: informes de cierre registrados por el coordinador de ORO en el tablero de control de la activación.</p>
</main>
<script>{JS}</script>
"""


CSS = r"""
:root{
  --bg:#f5f3ee; --surface:#ffffff; --surface-2:#ece8df; --line:#dcd5c8;
  --fg:#1e1c17; --muted:#68625a;
  --brand:#d4121b; --brand-ink:#ffffff; --sun:#ffc60b;
  --band:#13261c; --band-fg:#f3f0e8; --g2:#1f7a45;
  --ok:#1f7a45; --ok-bg:#e3f2e8; --warn:#9a5a00; --warn-bg:#fdf0d3;
  --display:"Archivo","Arial Narrow",Arial,sans-serif; --body:"Figtree",system-ui,-apple-system,"Segoe UI",sans-serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#121511; --surface:#1b201a; --surface-2:#252b23; --line:#363d33; --fg:#eef0ea; --muted:#a7ae9f;
  --brand:#ff4a4f; --band:#0b130e; --g2:#5fd18f; --ok:#5fd18f; --ok-bg:#16301f; --warn:#f2b54a; --warn-bg:#3a2a0e; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#121511; --surface:#1b201a; --surface-2:#252b23; --line:#363d33; --fg:#eef0ea; --muted:#a7ae9f;
  --brand:#ff4a4f; --band:#0b130e; --g2:#5fd18f; --ok:#5fd18f; --ok-bg:#16301f; --warn:#f2b54a; --warn-bg:#3a2a0e; color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--body);font-size:15px;line-height:1.45}
h1,h2,h3{font-family:var(--display);font-weight:800;margin:0;text-wrap:balance}
h2{font-stretch:85%;font-size:22px}
p{margin:0}
.mini{font-size:13px;color:var(--muted)}
header.band{background:var(--band);color:var(--band-fg);border-bottom:4px solid var(--sun)}
.band-in{max-width:1120px;margin:0 auto;padding:14px 16px;display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.band-in img.k{height:58px;width:auto}.band-in img.o{height:52px;width:auto}
.band-title{flex:1;min-width:200px}
.band-title h1{font-stretch:80%;font-weight:850;font-size:clamp(22px,4vw,30px);letter-spacing:.01em;text-transform:uppercase;line-height:1}
.band-title p{margin:4px 0 0;color:#c8cdbf;font-size:13px}
nav.tabs{background:var(--surface);border-bottom:1px solid var(--line);position:sticky;top:var(--gbar,0px);z-index:5}
.tabs-in{max-width:1120px;margin:0 auto;padding:0 16px;display:flex;align-items:center;gap:4px;flex-wrap:wrap}
.tabs-in a{color:var(--muted);text-decoration:none;font-weight:600;font-size:14px;padding:13px 12px;border-bottom:3px solid transparent}
.tabs-in a[aria-current]{color:var(--fg);border-bottom-color:var(--brand)}
.tabs-in .btn{margin-left:auto}
.btn{appearance:none;border:1px solid var(--line);background:var(--surface);color:var(--fg);font:600 14px var(--body);padding:9px 15px;border-radius:7px;cursor:pointer}
.btn.pri{background:var(--brand);border-color:var(--brand);color:var(--brand-ink)}
.btn[disabled]{opacity:.6;cursor:wait}
main{max-width:1120px;margin:0 auto;padding:22px 16px 40px;display:flex;flex-direction:column;gap:34px;background:var(--bg)}
.foot-n{color:var(--muted);font-size:12px}
.sec{display:flex;flex-direction:column;gap:14px}
.sec-h{display:flex;flex-direction:column;gap:3px}
.sec-h .step{font-size:11px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--brand)}
.sec-h p{color:var(--muted);font-size:14px;max-width:70ch}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:18px}
.intro{background:var(--band);color:var(--band-fg);border-radius:12px;padding:20px 22px;display:flex;flex-direction:column;gap:12px}
.intro p{font-size:15px;max-width:80ch}
.intro dl{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px 22px;margin:0;font-size:13px;color:#c8cdbf}
.intro dt{display:inline;font-weight:700;color:#fff}.intro dd{display:inline;margin:0}
.acl dl{display:grid;gap:12px;margin:0}.acl dl>div{font-size:14px;max-width:90ch}.acl dt{font-weight:800;font-family:var(--display);font-stretch:90%;text-transform:uppercase;font-size:13px;margin-bottom:2px}.acl dd{margin:0}
.g{position:relative;margin:0;width:100%;max-width:230px}
.g svg{display:block;width:100%;height:auto;overflow:visible}
.g path{fill:none;stroke-width:17;stroke-linecap:round}
.g .tr{stroke:var(--line)}
.g.s1 .br{stroke:var(--brand)}.g.s2 .br{stroke:var(--g2)}
.g figcaption{position:absolute;left:0;right:0;bottom:6%;display:flex;flex-direction:column;align-items:center;gap:2px}
.g b{font-family:var(--display);font-stretch:80%;font-weight:850;font-size:clamp(26px,6vw,36px);line-height:1;font-variant-numeric:tabular-nums}
.g figcaption span{font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}
.g .e0,.g .e1{position:absolute;bottom:-17px;font-size:10px;color:var(--muted)}
.g .e0{left:5%}.g .e1{right:2%}
.gwrap{display:flex;flex-direction:column;align-items:center;gap:20px;text-align:center}
.gwrap .gt{font-weight:700;font-size:14px}
.gwrap .gs{font-size:13px;color:var(--muted);max-width:30ch}
.big2{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:26px 20px;padding:10px 4px 6px}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media (max-width:860px){.kpis{grid-template-columns:repeat(2,1fr)}}
@media (max-width:480px){.kpis{grid-template-columns:1fr}}
.kpi{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px 16px;display:flex;flex-direction:column;gap:3px}
.kpi .l{font-size:11px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--muted)}
.kpi .v{font-family:var(--display);font-stretch:80%;font-weight:850;font-size:clamp(22px,4vw,28px);line-height:1.1;font-variant-numeric:tabular-nums}
.kpi .s{font-size:12.5px;color:var(--muted)}
.tbl-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);font-weight:700;background:var(--surface-2);line-height:1.25}
th.r,td.r{text-align:right;font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:0}
tr.foot td{background:var(--surface-2);font-weight:700}
td small{display:block;color:var(--brand);font-size:11.5px;font-weight:600}
td.bar-c{min-width:200px;position:relative}
td.bar-c .bar{display:block;height:8px;border-radius:4px;background:var(--brand);opacity:.85;margin:4px 0 4px}
td.bar-c b{font-variant-numeric:tabular-nums}
.nowrap{white-space:nowrap}
.res p.main{font-size:16px;line-height:1.6;max-width:80ch;text-align:justify;hyphens:auto}
.res .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-top:16px}
.res .col{border-radius:10px;padding:14px 16px}
.res h4{margin:0 0 8px;font-size:12px;letter-spacing:.08em;text-transform:uppercase}
.res .col ul{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:6px;font-size:14px}
.res .pos{background:var(--ok-bg)}.res .pos h4{color:var(--ok)}
.res .adj{background:var(--warn-bg)}.res .adj h4{color:var(--warn)}
.cmt{margin-top:18px;display:flex;flex-direction:column;gap:12px}
.gal{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.gal figure{margin:0;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:8px;display:flex;flex-direction:column;gap:6px}
.gal figure div{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.gal img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:6px;background:var(--surface-2)}
.gal figcaption{font-size:13px;font-weight:600}
@media (max-width:700px){th,td{padding:7px 8px;font-size:13px}td.bar-c{min-width:150px}}
.pdf-mode{width:1100px!important;max-width:none!important}
"""

JS = r"""
(function(){
  const btn=document.getElementById('pdf');
  const load=(src,test)=>new Promise((ok,ko)=>{if(test())return ok();const s=document.createElement('script');s.src=src;s.onload=()=>ok();s.onerror=()=>ko(new Error('No se pudo cargar '+src));document.head.appendChild(s);});
  btn&&btn.addEventListener('click',async()=>{
    const t=btn.textContent;btn.disabled=true;btn.textContent='Preparando PDF…';
    const main=document.getElementById('sc'),head=document.querySelector('header.band');
    try{
      await load('https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js',()=>window.html2canvas);
      await load('https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js',()=>window.jspdf);
      await Promise.all([...main.querySelectorAll('img')].map(i=>i.complete&&!/^data:image\/gif/.test(i.src)?0:new Promise(r=>{i.addEventListener('load',r,{once:true});setTimeout(r,4000);})));
      main.classList.add('pdf-mode');
      const bg=getComputedStyle(document.body).backgroundColor;
      const {jsPDF}=window.jspdf;const pdf=new jsPDF({orientation:'portrait',unit:'pt',format:'a4'});
      const W=pdf.internal.pageSize.getWidth(),Hh=pdf.internal.pageSize.getHeight(),M=24,CW=W-2*M;let y=M;
      const blocks=[head,...main.children];
      for(const el of blocks){
        const c=await html2canvas(el,{scale:2,backgroundColor:bg,useCORS:true,logging:false,windowWidth:1150});
        const h=c.height*CW/c.width;
        if(h<=Hh-2*M){ if(y+h>Hh-M){pdf.addPage();y=M;} pdf.addImage(c.toDataURL('image/jpeg',0.9),'JPEG',M,y,CW,h);y+=h+14; }
        else{ const pagePx=Math.floor((Hh-2*M)*c.width/CW);let off=0;if(y>M){pdf.addPage();y=M;}
          while(off<c.height){const sl=document.createElement('canvas');sl.width=c.width;sl.height=Math.min(pagePx,c.height-off);
            sl.getContext('2d').drawImage(c,0,off,c.width,sl.height,0,0,c.width,sl.height);
            const sh=sl.height*CW/c.width;pdf.addImage(sl.toDataURL('image/jpeg',0.9),'JPEG',M,y,CW,sh);off+=sl.height;
            if(off<c.height){pdf.addPage();y=M;}else y+=sh+14;}
        }
      }
      pdf.save('scorecard-comarrico.pdf');
    }catch(e){btn.textContent='No se pudo generar el PDF';await new Promise(r=>setTimeout(r,2500));}
    finally{main.classList.remove('pdf-mode');btn.disabled=false;btn.textContent=t;}
  });
})();
"""

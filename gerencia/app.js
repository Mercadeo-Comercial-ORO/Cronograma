/* Portal de gerencia ORO: carga una vista cifrada de un tablero y la ejecuta con una base de datos en memoria
   (solo lectura real: nada de lo que se haga aquí se guarda en los tableros). */
(function () {
  "use strict";
  var VISTA = document.documentElement.getAttribute("data-vista");
  var KN = "oro-gerencia-k", PFX = "data:,ph-", RX = /^(?:data:,ph-|(?:https?:\/\/[^\/]+)?\/_blob\/)([0-9a-f]{32})/;
  var kb = null;
  try { kb = localStorage.getItem(KN); } catch (e) {}
  if (!kb) { location.replace("./?v=" + encodeURIComponent(VISTA)); return; }

  var raw = Uint8Array.from(atob(kb), function (c) { return c.charCodeAt(0); });
  var keyP = crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["decrypt"]);
  var nativeFetch = window.fetch.bind(window);
  function dec(buf) {
    var u = new Uint8Array(buf);
    return keyP.then(function (k) { return crypto.subtle.decrypt({ name: "AES-GCM", iv: u.slice(0, 12) }, k, u.slice(12)); });
  }
  function bin(url) {
    return nativeFetch(url, { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.arrayBuffer(); }).then(dec);
  }

  /* ---------- fotos ---------- */
  var PH = {};
  function foto(id) {
    if (!PH[id]) PH[id] = bin("f/" + id + ".bin").then(function (b) {
      var u = new Uint8Array(b), t = (u[0] === 0x52 && u[1] === 0x49) ? "image/webp" : (u[0] === 0x89 ? "image/png" : "image/jpeg");
      return URL.createObjectURL(new Blob([b], { type: t }));
    });
    return PH[id];
  }
  function fix(el) {
    ["src", "href"].forEach(function (a) {
      var v = el.getAttribute && el.getAttribute(a), m = v && RX.exec(v);
      if (m) {
        var id = m[1];
        el.setAttribute(a, a === "src" ? "data:image/gif;base64,R0lGODlhAQABAAAAACw=" : "#");
        foto(id).then(function (u) { el.setAttribute(a, u); }).catch(function () {});
      }
    });
  }
  function scan(root) {
    if (root.nodeType !== 1) return;
    fix(root);
    root.querySelectorAll('[src^="' + PFX + '"],[href^="' + PFX + '"],[src*="/_blob/"],[href*="/_blob/"]').forEach(fix);
  }
  new MutationObserver(function (ms) {
    ms.forEach(function (m) {
      if (m.type === "attributes") fix(m.target);
      else m.addedNodes.forEach(scan);
    });
  }).observe(document.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: ["src", "href"] });
  window.fetch = function (u, o) {
    var m = typeof u === "string" && RX.exec(u);
    if (m) return foto(m[1]).then(function (x) { return nativeFetch(x); });
    return nativeFetch(u, o);
  };

  /* ---------- base de datos en memoria (misma forma que la del tablero) ---------- */
  var D = new Map(), LS = [], DEMO = false, ULT = 0;
  ["pointerdown", "keydown"].forEach(function (ev) { addEventListener(ev, function () { ULT = Date.now(); }, true); });
  var clone = function (x) { return x == null ? x : JSON.parse(JSON.stringify(x)); };
  var parent = function (p) { return p.slice(0, p.lastIndexOf("/")); };
  var leaf = function (p) { return p.slice(p.lastIndexOf("/") + 1); };
  function dsnap(p) { return { id: leaf(p), exists: D.has(p), ref: doc(p), data: function () { return clone(D.get(p)); } }; }
  function qsnap(c) {
    var docs = [];
    D.forEach(function (v, p) { if (parent(p) === c) docs.push(dsnap(p)); });
    docs.sort(function (a, b) { return a.id < b.id ? -1 : 1; });
    return { docs: docs, size: docs.length, empty: !docs.length, forEach: function (f) { docs.forEach(f); } };
  }
  function notify(p) {
    if (DEMO && Date.now() - ULT < 4000) aviso("Demostración: el cambio se ve solo en esta pantalla y no llega al tablero real.");
    LS.forEach(function (l) {
      if (l.kind === "doc" && l.path === p) setTimeout(function () { l.cb(dsnap(p)); });
      if (l.kind === "col" && l.path === parent(p)) setTimeout(function () { l.cb(qsnap(l.path)); });
    });
  }
  function listen(kind, path, cb) {
    var l = { kind: kind, path: path, cb: cb }; LS.push(l);
    setTimeout(function () { cb(kind === "doc" ? dsnap(path) : qsnap(path)); });
    return function () { var i = LS.indexOf(l); if (i >= 0) LS.splice(i, 1); };
  }
  function setPath(o, k, v) {
    var ks = k.split("."), x = o;
    for (var i = 0; i < ks.length - 1; i++) { if (typeof x[ks[i]] !== "object" || x[ks[i]] === null) x[ks[i]] = {}; x = x[ks[i]]; }
    var last = ks[ks.length - 1];
    if (v && typeof v === "object" && v.__delete__) delete x[last]; else x[last] = clone(v);
  }
  function doc(p) {
    return {
      id: leaf(p), path: p,
      onSnapshot: function (cb) { return listen("doc", p, cb); },
      get: function () { return Promise.resolve(dsnap(p)); },
      set: function (d, o) { var base = (o && o.merge && D.get(p)) ? clone(D.get(p)) : {}; Object.keys(d || {}).forEach(function (k) { base[k] = clone(d[k]); }); D.set(p, base); notify(p); return Promise.resolve(); },
      update: function (d) { var base = clone(D.get(p)) || {}; Object.keys(d || {}).forEach(function (k) { setPath(base, k, d[k]); }); D.set(p, base); notify(p); return Promise.resolve(); },
      delete: function () { D.delete(p); notify(p); return Promise.resolve(); },
      collection: function (s) { return col(p + "/" + s); }
    };
  }
  function col(c) {
    return {
      id: leaf(c), path: c,
      doc: function (id) { return doc(c + "/" + (id || Math.random().toString(36).slice(2, 12))); },
      onSnapshot: function (cb) { return listen("col", c, cb); },
      get: function () { return Promise.resolve(qsnap(c)); },
      add: function (d) { var r = doc(c + "/" + Math.random().toString(36).slice(2, 12)); return r.set(d).then(function () { return r; }); }
    };
  }
  var DB = { doc: doc, collection: col };

  function aviso(t) {
    var n = document.getElementById("__gmsg");
    if (!n) { n = document.createElement("div"); n.id = "__gmsg"; document.body.appendChild(n); }
    n.textContent = t; n.hidden = false; clearTimeout(n._t); n._t = setTimeout(function () { n.hidden = true; }, 4500);
  }


  /* selector de salida en los informes (las tarjetas .rep-card que pinta el tablero) */
  var SEL = "";
  function selector() {
    var view = document.getElementById("view");
    if (!view) return;
    var cards = Array.prototype.slice.call(view.querySelectorAll("article.rep-card"));
    var head = view.querySelector(".sec-head .btns");
    var old = document.getElementById("__gsel");
    if (!cards.length || !head) { if (old) old.remove(); return; }
    var nombres = cards.map(function (c) { var h = c.querySelector("h3"); return h ? h.textContent.trim() : ""; });
    if (nombres.indexOf(SEL) < 0) SEL = "";
    var firma = nombres.join("|");
    if (!old || old.getAttribute("data-f") !== firma || old.parentNode !== head) {
      if (old) old.remove();
      var l = document.createElement("label"); l.className = "f"; l.id = "__gsel"; l.setAttribute("data-f", firma);
      l.style.minWidth = "220px"; l.textContent = "Salida";
      var s = document.createElement("select");
      s.innerHTML = '<option value="">Todas las salidas</option>' + nombres.map(function (n) { var o = document.createElement("option"); o.value = n; o.textContent = n; return o.outerHTML; }).join("");
      s.value = SEL;
      s.addEventListener("change", function () { SEL = s.value; aplicar(); });
      l.appendChild(s); head.appendChild(l); head.style.alignItems = "flex-end";
    }
    aplicar();
    function aplicar() { cards.forEach(function (c, i) { c.hidden = !!SEL && nombres[i] !== SEL; }); }
  }

  function ejecutar(P) {
    try { Object.keys(P.ls || {}).forEach(function (k) { localStorage.setItem(k, P.ls[k]); }); } catch (e) {}
    Object.keys(P.db || {}).forEach(function (p) { D.set(p, P.db[p]); });
    window.__TF = function (l) { var f = P.tabs ? l.filter(function (x) { return P.tabs.indexOf(x.id) >= 0; }) : l; if (!f.length) f = l; var N = P.nombres || {}; return f.map(function (x) { return N[x.id] ? { id: x.id, n: N[x.id] } : x; }); };
    var USER = {
      isOwner: function () { return Promise.resolve(!!P.owner); },
      id: function () { return Promise.resolve(P.uid || null); },
      can: function () { return Promise.resolve(P.can !== false); },
      name: function () { return Promise.resolve("Gerencia"); }
    };
    var DL = {
      save: function (o) {
        var b = o.data instanceof Blob ? o.data : new Blob([o.data], { type: /\.html?$/i.test(o.filename) ? "text/html" : (/\.csv$/i.test(o.filename) ? "text/csv" : "application/octet-stream") });
        var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = o.filename || "archivo";
        document.body.appendChild(a); a.click(); setTimeout(function () { a.remove(); }, 1000);
        return Promise.resolve();
      }
    };
    var AS = {
      upload: function (blob) {
        var id = Array.from(crypto.getRandomValues(new Uint8Array(16))).map(function (x) { return x.toString(16).padStart(2, "0"); }).join("");
        PH[id] = Promise.resolve(URL.createObjectURL(blob));
        return Promise.resolve({ id: id, url: PFX + id });
      }
    };
    window.claude = { use: function (c) { return Promise.resolve({ db: DB, user: USER, downloads: DL, assets: AS }[c] || null); } };

    document.title = P.titulo || document.title;
    var doc0 = new DOMParser().parseFromString("<!doctype html><html><head></head><body>" + P.html + "</body></html>", "text/html");
    var scripts = [];
    doc0.querySelectorAll("script").forEach(function (s) { scripts.push({ src: s.getAttribute("src"), text: s.textContent }); s.remove(); });
    var base = document.createElement("style");
    base.textContent = ":root{box-sizing:border-box}body{margin:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif}img{max-width:100%}[hidden]:not([hidden=until-found i]){display:none!important}" +
      ":root{--gbar:52px}body{padding-top:var(--gbar)!important}" +
      "#__gbar{position:fixed;top:0;left:0;right:0;height:var(--gbar);z-index:2147483000;display:flex;gap:10px;align-items:center;padding:0 14px;background:#1d1a2b;color:#fff;font:600 14px system-ui,-apple-system,sans-serif;box-shadow:0 2px 12px rgba(0,0,0,.3)}" +
      "#__gbar a{display:inline-flex;align-items:center;gap:8px;background:#ec6a16;color:#fff;text-decoration:none;border-radius:999px;padding:9px 18px;font-weight:700;white-space:nowrap}" +
      "#__gbar a:hover{background:#ff7d2b}#__gbar a:focus-visible{outline:3px solid #fff;outline-offset:2px}" +
      "#__gbar .t{opacity:.85;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0}" +
      "#__gbar .d{background:#fff;color:#1d1a2b;border-radius:999px;padding:5px 12px;font-size:12px;white-space:nowrap}" +
      "@media (max-width:560px){#__gbar .t{display:none}#__gbar .d{margin-left:auto}}" +
      "nav.tabs,.toolbar{top:var(--gbar)!important}.fi-prev{top:calc(var(--gbar) + 60px)!important}" +
      ".__gnota{max-width:1240px;margin:14px auto 0;padding:12px 16px;border-radius:10px;background:#fff1dc;color:#3a2a0e;border-left:5px solid #ec6a16;font:14px/1.5 system-ui,-apple-system,sans-serif}" +
      "main+.__gnota,.__gnota+main{}" +
      "#__gmsg{position:fixed;right:12px;bottom:12px;z-index:9999;max-width:min(360px,calc(100% - 24px));background:#1d1a2b;color:#fff;border-radius:10px;padding:10px 14px;font:13px system-ui,sans-serif;box-shadow:0 4px 14px rgba(0,0,0,.25)}" +
      "@media print{#__gbar,#__gmsg{display:none!important}}" + (P.css || "");
    document.head.appendChild(base);
    document.body.innerHTML = "";
    Array.from(doc0.head.childNodes).concat(Array.from(doc0.body.childNodes)).forEach(function (n) { document.body.appendChild(document.importNode(n, true)); });
    var bar = document.createElement("div"); bar.id = "__gbar";
    bar.innerHTML = '<a href="./">← Volver al Portal de Gerencia</a><span class="t"></span>' + (P.demo ? '<span class="d">Demostración: nada se guarda</span>' : "");
    bar.querySelector(".t").textContent = (P.titulo || "").replace(/ · ORO$/, "");
    document.body.insertBefore(bar, document.body.firstChild);
    window.__KMCSS = P.kmcss || "";
    if (P.rol) { var fixRol = function () { var r = document.getElementById("role"); if (r && r.textContent !== P.rol) r.textContent = P.rol; }; [300, 1200, 3000].forEach(function (ms) { setTimeout(fixRol, ms); }); }
    if (P.nota) { var tn = document.querySelector(P.nota.sel); if (tn) tn.insertAdjacentHTML(P.nota.pos || "afterbegin", P.nota.html); }
    if (P.extra) {
      var addX = function () { var tb = document.getElementById("tabs"); if (!tb || tb.querySelector(".__gx")) return; P.extra.forEach(function (x) { var b = document.createElement("button"); b.type = "button"; b.setAttribute("role", "tab"); b.className = "__gx"; b.textContent = x.n; b.addEventListener("click", function () { location.href = x.href; }); tb.appendChild(b); }); };
      new MutationObserver(addX).observe(document.body, { childList: true, subtree: true }); setTimeout(addX, 50);
    }
    DEMO = !!P.demo;
    if (P.selector) { var tq = null; new MutationObserver(function () { clearTimeout(tq); tq = setTimeout(selector, 60); }).observe(document.body, { childList: true, subtree: true }); }
    scan(document.body);
    (function run(i) {
      if (i >= scripts.length) return;
      var s = document.createElement("script");
      if (scripts[i].src) {
        s.src = scripts[i].src; s.onload = s.onerror = function () { run(i + 1); };
        document.body.appendChild(s);
      } else {
        s.textContent = scripts[i].text; document.body.appendChild(s); run(i + 1);
      }
    })(0);
  }

  function boot() {
    bin("d/" + VISTA + ".bin").then(function (b) { ejecutar(JSON.parse(new TextDecoder().decode(b))); }).catch(function () {
      try { localStorage.removeItem(KN); } catch (e) {}
      location.replace("./?v=" + encodeURIComponent(VISTA) + "&e=1");
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();

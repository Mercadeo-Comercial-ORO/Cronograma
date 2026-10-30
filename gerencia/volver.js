/* Barra fija "Volver al Portal de Gerencia" para las landings que se abren desde el portal (cronograma general y scorecard Kimby).
   Solo aparece en el dispositivo donde ya se entró al portal de gerencia. */
(function () {
  var k = null;
  try { k = localStorage.getItem("oro-gerencia-k"); } catch (e) {}
  if (!k) return;
  var base = document.currentScript ? document.currentScript.src.replace(/volver\.js.*$/, "") : "/Cronograma/gerencia/";
  function poner() {
    if (document.getElementById("__gbar")) return;
    var st = document.createElement("style");
    st.textContent = ":root{--gbar:52px}body{padding-top:var(--gbar)!important}" +
      "#__gbar{position:fixed;top:0;left:0;right:0;height:var(--gbar);z-index:2147483000;display:flex;gap:10px;align-items:center;padding:0 14px;background:#1d1a2b;color:#fff;font:600 14px system-ui,-apple-system,sans-serif;box-shadow:0 2px 12px rgba(0,0,0,.3)}" +
      "#__gbar a{display:inline-flex;align-items:center;gap:8px;background:#ec6a16;color:#fff;text-decoration:none;border-radius:999px;padding:9px 18px;font-weight:700;white-space:nowrap}" +
      "#__gbar a:hover{background:#ff7d2b}#__gbar a:focus-visible{outline:3px solid #fff;outline-offset:2px}" +
      "#__gbar span{opacity:.85;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}@media (max-width:560px){#__gbar span{display:none}}@media print{#__gbar{display:none}body{padding-top:0!important}}";
    document.head.appendChild(st);
    var bar = document.createElement("div"); bar.id = "__gbar";
    bar.innerHTML = '<a href="' + base + '">← Volver al Portal de Gerencia</a><span></span>';
    bar.querySelector("span").textContent = document.title.replace(/\s*[·|-]\s*ORO\s*$/, "");
    document.body.insertBefore(bar, document.body.firstChild);
  }
  if (document.body) poner(); else document.addEventListener("DOMContentLoaded", poner);
})();

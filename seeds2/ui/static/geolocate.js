// LOCALIZAÇÃO AUTOMÁTICA: UMA leitura de navigator.geolocation, somente após o clique do usuário
// (sem watchPosition, sem leituras em segundo plano). Nada é salvo aqui: os valores apenas preenchem o
// formulário, que o usuário confirma. Evento: {type:"geo", ok, lat, lon, accuracy, tz} | {type:"geo", ok:false, code}.
const PIN = `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.2" fill="currentColor"/><circle cx="12" cy="12" r="7.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 1.5v3.2M12 19.3v3.2M1.5 12h3.2M19.3 12h3.2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`;
const MESSAGES = {
  unsupported: "Este navegador não oferece geolocalização. Informe as coordenadas manualmente.",
  insecure: "A geolocalização exige conexão segura (HTTPS) ou acesso local (localhost). Informe as coordenadas manualmente.",
  denied: "Permissão de localização negada. Você pode autorizá-la nas configurações do navegador ou informar os dados manualmente.",
  unavailable: "Posição indisponível no momento. Informe as coordenadas manualmente.",
  timeout: "O navegador não respondeu a tempo. Tente novamente ou informe as coordenadas manualmente.",
};
function el(t, c, x) { const e = document.createElement(t); if (c) e.className = c; if (x !== undefined) e.textContent = x; return e; }
export default function (component) {
  const { data, setTriggerValue, parentElement } = component;
  let root = parentElement.querySelector(".geo");
  if (!root) {
    root = el("div", "sd geo");
    const btn = el("button", "geo-btn"); btn.type = "button";
    btn.innerHTML = `${PIN}<span>LOCALIZAÇÃO AUTOMÁTICA</span>`;
    btn.setAttribute("aria-describedby", "geo-msg");
    const msg = el("div", "geo-msg"); msg.id = "geo-msg"; msg.setAttribute("role", "status"); msg.setAttribute("aria-live", "polite");
    root.append(btn, msg);
    parentElement.appendChild(root);
    const send = (p) => root.__send && root.__send("action", { type: "geo", t: Date.now(), ...p });
    const tz = () => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (e) { return ""; } };
    const fail = (code) => { btn.setAttribute("aria-busy", "false"); msg.className = "geo-msg bad"; msg.textContent = MESSAGES[code] || MESSAGES.unavailable; send({ ok: false, code, tz: tz() }); };
    btn.addEventListener("click", () => {
      if (!("geolocation" in navigator) || !navigator.geolocation) return fail("unsupported");
      if (window.isSecureContext === false) return fail("insecure");
      btn.setAttribute("aria-busy", "true"); msg.className = "geo-msg"; msg.textContent = "Solicitando a posição ao navegador…";
      navigator.geolocation.getCurrentPosition((pos) => {
        btn.setAttribute("aria-busy", "false");
        const c = pos.coords;
        msg.className = "geo-msg ok";
        msg.textContent = `Coordenadas recebidas${isFinite(c.accuracy) ? ` (precisão estimada ±${Math.round(c.accuracy)} m)` : ""}. Revise e confirme o formulário para salvar.`;
        send({ ok: true, lat: c.latitude, lon: c.longitude, accuracy: isFinite(c.accuracy) ? c.accuracy : null, tz: tz() });
      }, (err) => fail(err && err.code === 1 ? "denied" : err && err.code === 3 ? "timeout" : "unavailable"),
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 0 });
    });
  }
  root.__send = setTriggerValue;
}

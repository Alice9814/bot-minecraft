(function () {
  "use strict";
  let logs = [];
  let currentState = {running:false,paused:false};

  const byId = id => document.getElementById(id);
  const call = (name, ...args) => {
    if (!window.protoNative || typeof window.protoNative.invoke !== "function") {
      appendLog("[UI] A comunicação com o aplicativo ainda não está disponível.");
      return;
    }
    window.protoNative.invoke(name,args);
  };

  function appendLog(line) {
    const text = String(line || "");
    if (!text) return;
    logs.push(text);
    if (logs.length > 1200) logs = logs.slice(-1200);
    const joined = logs.join("\n");
    const full = byId("fullLogs");
    const preview = byId("dashboardLogs");
    if (full) { full.textContent = joined; full.scrollTop = full.scrollHeight; }
    if (preview) {
      preview.textContent = logs.slice(-7).join("\n") || "Aguardando inicialização...";
      preview.scrollTop = preview.scrollHeight;
    }
  }

  function setState(running, paused) {
    currentState = {running:!!running,paused:!!paused};
    const label = !running ? "Parado" : paused ? "Pausado" : "Em execução";
    ["statusText","sideStatus"].forEach(id => {
      if (byId(id)) byId(id).textContent = id === "sideStatus" ? (running ? label : "Bot desconectado") : label;
    });
    ["statusDot","sideDot"].forEach(id => {
      if (byId(id)) byId(id).classList.toggle("running",!!running && !paused);
    });
    if (byId("startButton")) byId("startButton").disabled = !!running;
    if (byId("pauseButton")) {
      byId("pauseButton").disabled = !running;
      byId("pauseButton").textContent = paused ? "▶ Retomar" : "Ⅱ Pausar";
    }
    if (byId("stopButton")) byId("stopButton").disabled = !running;
  }

  function fillConfig(config) {
    const mc = config.minecraft || {};
    const ai = config.ai || {};
    const behavior = config.behavior || {};
    byId("hostInput").value = mc.host || "127.0.0.1";
    byId("portInput").value = mc.port || 25565;
    byId("usernameInput").value = mc.username || "ProtoBot";
    byId("authInput").value = mc.auth || "offline";
    byId("versionInput").value = mc.version || "26.2";
    byId("temperatureInput").value = ai.temperature ?? 0.7;
    byId("temperatureOutput").textContent = Number(byId("temperatureInput").value).toFixed(1);
    byId("mentionInput").checked = !!behavior.respond_only_when_mentioned;
    byId("serverAddress").textContent = (mc.host || "127.0.0.1") + ":" + (mc.port || 25565);
    byId("botName").textContent = mc.username || "ProtoBot";
    byId("authMode").textContent = mc.auth === "microsoft" ? "Microsoft" : "Offline";
    byId("temperatureValue").textContent = Number(ai.temperature ?? 0.7).toFixed(1);
  }

  function collectConfig() {
    return JSON.stringify({
      minecraft:{
        host:byId("hostInput").value.trim(),
        port:Number(byId("portInput").value || 25565),
        username:byId("usernameInput").value.trim(),
        auth:byId("authInput").value,
        version:byId("versionInput").value.trim() || "26.2"
      },
      ai:{model:"gemma-3-1b-it-Q4_K_M.gguf",temperature:Number(byId("temperatureInput").value)},
      behavior:{respond_only_when_mentioned:byId("mentionInput").checked}
    });
  }

  function showPage(name) {
    document.querySelectorAll(".page").forEach(page => page.classList.toggle("active",page.id === "page-" + name));
    document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active",item.dataset.section === name));
    const titles = {dashboard:"Visão geral",settings:"Configurações",console:"Console"};
    byId("pageTitle").textContent = titles[name] || "ProtoBot";
  }

  function receiveEvent(event) {
    if (!event || typeof event !== "object") return;
    if (event.type === "log") appendLog(event.text);
    else if (event.type === "clearLogs") { logs = []; appendLog("Logs limpos."); }
    else if (event.type === "state") setState(event.running,event.paused);
    else if (event.type === "config") {
      try { fillConfig(typeof event.value === "string" ? JSON.parse(event.value) : event.value); }
      catch(e) { appendLog("[UI] Erro ao carregar configurações: " + e); }
    }
  }

  function init() {
    document.querySelectorAll(".nav-item").forEach(item => item.addEventListener("click",() => showPage(item.dataset.section)));
    document.querySelectorAll("[data-go]").forEach(item => item.addEventListener("click",() => showPage(item.dataset.go)));
    byId("startButton").addEventListener("click",() => { call("saveConfig",collectConfig()); call("startBot"); });
    byId("pauseButton").addEventListener("click",() => call("togglePause"));
    byId("stopButton").addEventListener("click",() => call("stopBot"));
    byId("saveButton").addEventListener("click",() => call("saveConfig",collectConfig()));
    byId("clearLogsButton").addEventListener("click",() => call("clearLogs"));
    byId("forceQuitButton").addEventListener("click",() => call("forceQuit"));
    byId("temperatureInput").addEventListener("input",() => byId("temperatureOutput").textContent = Number(byId("temperatureInput").value).toFixed(1));
    document.addEventListener("proto-event",event => receiveEvent(event.detail));
    call("requestInitialData");
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded",init);
  else init();
})();
(() => {
  const listEl = document.getElementById("conversationList");
  let currentId = null;
  let activePersona=window.FRESH_PERSONA || {assistant_name:"Fresh AI",avatar_key:"partak",greeting:"Ahoj! S čím ti dnes pomůžu?"};
  let historyPersona=activePersona;
  const messagesEl = document.getElementById("messages");
  const promptEl = document.getElementById("prompt");
  const sendBtn = document.getElementById("sendButton");
  const newChatBtn = document.getElementById("newChat");
  const deleteChatBtn = document.getElementById("deleteChat");
  let startedNewDraft = new URLSearchParams(window.location.search).get("new") === "1";
  const productNameEl = document.querySelector(".product-name");
  const statusEl = document.getElementById("engineStatus");
  const installBar = document.getElementById("installBar");
  const installButton = document.getElementById("installButton");
  const installClose = document.getElementById("installClose");
  const installHint = document.getElementById("installHint");
  let busy = false;
  let history = [];
  let deferredInstallPrompt = null;

  async function request(url, options={}) {
    const res=await fetch(url,{credentials:"same-origin",cache:"no-store",...options,
      headers:{"X-CSRF-Token":window.FRESH_CSRF_TOKEN,...(options.headers||{})}});
    const body=await res.json().catch(()=>({}));
    if (!res.ok || !body.ok) throw new Error(body.error || `Chyba ${res.status}`);
    return body;
  }
  async function refreshConversations() {
    try {
      const data=await request("/api/conversations");
      listEl.innerHTML="";
      for (const item of data.conversations) {
        const btn=document.createElement("button");
        btn.type="button"; btn.className="history-item"+(item.id===currentId?" active":"");
        btn.textContent=item.title || "Nový chat";
        btn.addEventListener("click",()=>openConversation(item.id));
        listEl.appendChild(btn);
      }
      if (!data.conversations.length) listEl.innerHTML='<p class="history-empty">Zatím žádné konverzace.</p>';
      return data.conversations;
    } catch(e) { listEl.textContent="Historii nyní nelze načíst."; return []; }
  }
  async function openConversation(id) {
    if (busy) return;
    try {
      const data=await request(`/api/conversations/${encodeURIComponent(id)}`);
      currentId=id; startedNewDraft=false; history=data.messages; historyPersona=data.persona || window.FRESH_PERSONA;
      // The composer uses the CURRENT account persona; old bubbles keep their own.
      activePersona=window.FRESH_PERSONA;
      if (productNameEl) productNameEl.textContent=activePersona.assistant_name;
      deleteChatBtn.disabled=false;
      renderHistory(); await refreshConversations();
    } catch(e) { alert(e.message); }
  }
  async function startNew() {
    if(busy) return;
    startedNewDraft=true; currentId=null; deleteChatBtn.disabled=true;
    history=[]; activePersona=window.FRESH_PERSONA; historyPersona=activePersona;
    if (productNameEl) productNameEl.textContent=activePersona.assistant_name;
    renderHistory(); await refreshConversations(); promptEl.focus();
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>'"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[ch]));
  }
  function scrollToBottom() {
    requestAnimationFrame(() => {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    });
  }

  function renderRichText(text) {
    const parts = String(text).split(/```/);
    return parts.map((part, index) => {
      if (index % 2 === 1) {
        const clean = part.replace(/^\w+\n/, "");
        return `<pre><code>${escapeHtml(clean)}</code></pre>`;
      }
      let out = escapeHtml(part);
      out = out.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
      out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
      out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
      return out.replace(/\n/g, "<br>");
    }).join("");
  }
  function avatarHtml(persona=activePersona) {
    const valid=["profesor","student","studentka","tata","mama","rocker","partak","strateg"];
    const key=valid.includes(persona.avatar_key)?persona.avatar_key:"partak";
    return `<img src="/static/avatars/${key}-192.png" width="38" height="38" alt="" class="assistant-avatar">`;
  }
  function welcome() {
    messagesEl.innerHTML=`
      <div class="welcome personal-welcome">
        <div class="welcome-mark">${avatarHtml()}</div>
        <h1>${escapeHtml(activePersona.assistant_name)}</h1>
        <p class="hello-question">${escapeHtml(activePersona.greeting)}</p>
        <div class="suggestions">
          <button class="suggestion">Pomoz mi něco naplánovat</button>
          <button class="suggestion">Vysvětli mi složitou věc jednoduše</button>
          <button class="suggestion">Pojďme vymyslet něco nového</button>
        </div>
      </div>`;
    messagesEl.querySelectorAll(".suggestion").forEach(btn => btn.addEventListener("click", () => {
      promptEl.value = btn.textContent; autoResize(); promptEl.focus();
    }));
  }
  function appendMessage(role, content, meta = null, error = false) {
    const row = document.createElement("div");
    row.className = `message-row ${role}`;
    const bubblePersona = meta?.persona || activePersona;
    const label = role === "user" ? "Ty" : bubblePersona.assistant_name;
    let metaHtml = "";
    if (meta && window.FRESH_SHOW_MODEL_META) {
      const provider = meta.provider || "—";
      const model = meta.model || "—";
      const latency = meta.latency_ms ? `${(meta.latency_ms / 1000).toFixed(2)} s` : "—";
      metaHtml = `<div class="meta"><span>${escapeHtml(provider)}</span><span>${escapeHtml(model)}</span><span>${latency}</span></div>`;
    }
    row.innerHTML = `${role === "assistant" ? avatarHtml(bubblePersona) : ""}<div class="message"><div class="message-label">${escapeHtml(label)}</div><div class="bubble${error ? " error-bubble" : ""}">${renderRichText(content)}</div>${metaHtml}</div>`;
    messagesEl.appendChild(row);
    scrollToBottom();
    return row;
  }
  function renderHistory() {
    messagesEl.innerHTML = "";
    if (!history.length) { welcome(); return; }
    history.forEach(item => {
      const meta=(item.role==="assistant")?{...(item.meta||{}),persona:item.meta?.persona||historyPersona}:item.meta;
      appendMessage(item.role, item.content, meta || null);
    });
  }
  function typingRow() {
    const row = document.createElement("div");
    row.className = "message-row assistant";
    row.innerHTML = `${avatarHtml()}<div class="message"><div class="message-label">${escapeHtml(activePersona.assistant_name)}</div><div class="bubble"><span class="typing"><i></i><i></i><i></i></span></div></div>`;
    messagesEl.appendChild(row);
    scrollToBottom();
    return row;
  }
  async function send() {
    const message = promptEl.value.trim();
    if (!message || busy) return;
    if (messagesEl.querySelector(".welcome")) messagesEl.innerHTML = "";

    busy=true; sendBtn.disabled=true;
    if (!currentId) {
      try { const created=await request("/api/conversations",{method:"POST"}); currentId=created.id; activePersona=created.persona || activePersona;
        if (productNameEl) productNameEl.textContent=activePersona.assistant_name;
        deleteChatBtn.disabled=false; }
      catch(e) { busy=false;sendBtn.disabled=false;appendMessage("assistant",e.message,null,true);return; }
    }
    history.push({role:"user",content:message});
    appendMessage("user", message);
    promptEl.value = "";
    autoResize();
    const typing = typingRow();

    try {
      const data = await request("/api/chat", {
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({message,conversation_id:currentId})
      });
      typing.remove();
      if (data.persona) {
        activePersona=data.persona;
        if (productNameEl) productNameEl.textContent=activePersona.assistant_name;
      }
      const replyMeta={...(data.meta || {}),persona:activePersona};
      history.push({role: "assistant", content: data.reply, meta:replyMeta});
      appendMessage("assistant", data.reply, replyMeta);
      await refreshConversations();
    } catch (err) {
      typing.remove();
      appendMessage("assistant", `Nepodařilo se získat odpověď. ${err.message || "Zkus to prosím znovu."}`, null, true);
    } finally {
      busy = false;
      sendBtn.disabled = false;
      promptEl.focus();
    }
  }
  function autoResize() {
    promptEl.style.height = "auto";
    promptEl.style.height = `${Math.min(promptEl.scrollHeight, 170)}px`;
  }
  async function status() {
    try {
      const res = await fetch("/api/status", {cache: "no-store"});
      const data = await res.json();
      if (data.engine_ok) {
        statusEl.className = "status online";
        statusEl.innerHTML = '<span class="status-dot"></span><span>Fresh AI Engine online</span>';
      } else throw new Error();
    } catch (_) {
      statusEl.className = "status offline";
      statusEl.innerHTML = '<span class="status-dot"></span><span>Engine nedostupný</span>';
    }
  }

  function isStandalone() {
    return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  }

  function isIos() {
    return /iphone|ipad|ipod/i.test(window.navigator.userAgent);
  }

  function installDismissedRecently() {
    const value = Number(localStorage.getItem("fresh-ai-install-dismissed") || 0);
    return value && (Date.now() - value) < 7 * 24 * 60 * 60 * 1000;
  }

  function showInstallBar(mode = "prompt") {
    if (!installBar || isStandalone() || installDismissedRecently()) return;
    installBar.hidden = false;
    if (mode === "ios") {
      installButton.textContent = "Jak nainstalovat";
      installHint.textContent = "V Safari použij Sdílet → Přidat na plochu.";
    } else {
      installButton.textContent = "Instalovat aplikaci";
      installHint.textContent = "Měj chat po ruce jako samostatnou aplikaci.";
    }
  }

  function hideInstallBar() {
    if (installBar) installBar.hidden = true;
  }

  function setupPwaInstall() {
    if ("serviceWorker" in navigator) {
      window.addEventListener("load", () => {
        navigator.serviceWorker.register("/service-worker.js", {scope: "/"}).catch(() => undefined);
      });
    }

    if (isStandalone()) {
      hideInstallBar();
      return;
    }

    window.addEventListener("beforeinstallprompt", event => {
      event.preventDefault();
      deferredInstallPrompt = event;
      showInstallBar("prompt");
    });

    window.addEventListener("appinstalled", () => {
      deferredInstallPrompt = null;
      hideInstallBar();
      localStorage.removeItem("fresh-ai-install-dismissed");
    });

    if (isIos()) showInstallBar("ios");

    installButton?.addEventListener("click", async () => {
      if (isIos() && !deferredInstallPrompt) {
        alert("V Safari klepni na Sdílet a potom na Přidat na plochu.");
        return;
      }
      if (!deferredInstallPrompt) return;
      deferredInstallPrompt.prompt();
      try { await deferredInstallPrompt.userChoice; } catch (_) {}
      deferredInstallPrompt = null;
      hideInstallBar();
    });

    installClose?.addEventListener("click", () => {
      localStorage.setItem("fresh-ai-install-dismissed", String(Date.now()));
      hideInstallBar();
    });
  }

  sendBtn.addEventListener("click", send);
  promptEl.addEventListener("input", autoResize);
  promptEl.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault(); send();
    }
  });
  newChatBtn.addEventListener("click",startNew);
  document.getElementById("mobileQuickButton")?.addEventListener("click",startNew);
  deleteChatBtn.addEventListener("click",async()=>{
    if (!currentId || busy || !confirm("Smazat tuto konverzaci a všechny její zprávy?")) return;
    try {
      await request(`/api/conversations/${encodeURIComponent(currentId)}`,{method:"DELETE"});
      await startNew();
    } catch(e) { alert(e.message); }
  });

  renderHistory();
  refreshConversations().then(items => { if(items.length && !currentId && !startedNewDraft) openConversation(items[0].id); });
  status();
  setupPwaInstall();
  promptEl.focus();
})();

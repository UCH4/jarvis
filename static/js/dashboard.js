// URL dinámica: respeta el protocolo de la página (http o https)
// Así funciona desde localhost, desde WiFi Y desde el túnel Cloudflare
const API_HOST     = window.location.hostname;
const API_PORT_NUM = window.location.port || '5001';
const API_PROTO    = window.location.protocol; // 'http:' o 'https:'

// Si viene por el túnel (https, sin puerto) usamos la misma URL base sin puerto
const API = window.location.port
  ? `${API_PROTO}//${API_HOST}:${API_PORT_NUM}/api`
  : `${API_PROTO}//${API_HOST}/api`;

let pollInterval  = null;
let lastLogLen    = 0;
let currentStatus = 'idle';

// ─── INIT ─────────────────────────────────────────────
// Cada función es independiente: si una falla no bloquea las demás
async function init() {
  console.log("Iniciando la aplicación...");
  try {
    await Promise.allSettled([
      checkOllama(),
      loadModels(),
      loadVaults(),
      loadConfig(),
      loadVaultStats(),
    ]);
    setInterval(checkOllama, 10000);
  } catch (e) {
    console.error("Error durante la inicialización:", e);
  }
}

// ─── OLLAMA STATUS ─────────────────────────────────────────────
async function checkOllama() {
  const dot = document.getElementById('ollama-dot');
  const txt = document.getElementById('ollama-status-text');
  try {
    // AbortSignal.timeout() no existe en Chrome < 103 → usamos setTimeout manual
    const controller = new AbortController();
    const timer      = setTimeout(() => controller.abort(), 4000);
    const r = await fetch(`${API}/ollama-status`, { signal: controller.signal });
    clearTimeout(timer);
    const d = await r.json();
    if (d.running) {
      dot.className    = 'dot online';
      txt.textContent  = 'ollama · online';
    } else {
      dot.className    = 'dot offline';
      txt.textContent  = 'ollama · offline';
    }
  } catch {
    if (dot) dot.className   = 'dot offline';
    if (txt) txt.textContent = 'sin conexión';
  }
}

// ─── VAULTS ─────────────────────────────────────────────
async function loadVaults() {
  const sel = document.getElementById('vault-path');
  if (!sel) return;
  try {
    const r = await fetch(`${API}/vaults`);
    const d = await r.json();
    if (d.vaults && d.vaults.length > 0) {
      sel.innerHTML = '';
      d.vaults.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.path;
        opt.textContent = `${v.name} (${v.path})`;
        sel.appendChild(opt);
      });
    } else {
      sel.innerHTML = '<option value="">No se encontraron vaults</option>';
    }
  } catch (e) {
    sel.innerHTML = '<option value="">Error al cargar vaults</option>';
  }
}

// ─── MODELS ─────────────────────────────────────────────
async function loadModels() {
  const sel = document.getElementById('model-select');
  const sSel = document.getElementById('s-model');
  try {
    console.log("Elemento model-select:", document.getElementById('model-select')); // Log para depuración
    const r = await fetch(`${API}/models`);
    const d = await r.json();
    console.log("Respuesta de /api/models:", d); // Log para depuración
    const sel = document.getElementById('model-select');
    const sSel = document.getElementById('s-model');
    sel.innerHTML = '';
    sSel.innerHTML = '';
    if (d.models && d.models.length > 0) {
      d.models.forEach(m => {
        const opt = `<option value="${m}">${m}</option>`;
        sel.innerHTML += opt;
        sSel.innerHTML += opt;
      });
    } else {
      sel.innerHTML = '<option>sin modelos</option>';
    }
  } catch (e) {
    console.error("Error al cargar modelos:", e);
    const sel = document.getElementById('model-select');
    sel.innerHTML = '<option>Error al cargar modelos</option>';
  }
}
// ─── CONFIG ─────────────────────────────────────────────
// ─── CONFIG ─────────────────────────────────────────────
async function loadConfig() {
  try {
    const r = await fetch(`${API}/config`);
    const d = await r.json();
    
    // Configuración de rutas
    if (d.scan_path) document.getElementById('scan-path').value = d.scan_path;
    if (d.vault_path) document.getElementById('vault-path').value = d.vault_path;
    
    // Configuración persistente (IA y Watcher)
    if (d.user_config) {
      const u = d.user_config;
      if (document.getElementById('s-auto-sync'))   document.getElementById('s-auto-sync').checked   = u.auto_sync;
      if (document.getElementById('s-tool-search')) document.getElementById('s-tool-search').checked = u.tools_search;
      if (document.getElementById('s-tool-command')) document.getElementById('s-tool-command').checked = u.tools_command;
      if (u.analysis_model && document.getElementById('s-model')) {
        document.getElementById('s-model').value = u.analysis_model;
      }
      if (u.duplicate_threshold && document.getElementById('s-threshold')) {
        document.getElementById('s-threshold').value = u.duplicate_threshold;
      }
    }

    if (d.model) {
      const sel = document.getElementById('model-select');
      for (let o of sel.options) if (o.value === d.model) { o.selected = true; break; }
    }
  } catch(e) {
    console.error("Error cargando config:", e);
  }
}

async function saveSettings() {
  const cfg = {
    user_config: {
      auto_sync:     document.getElementById('s-auto-sync').checked,
      tools_search:  document.getElementById('s-tool-search').checked,
      tools_command: document.getElementById('s-tool-command').checked,
      analysis_model: document.getElementById('s-model').value,
      duplicate_threshold: parseFloat(document.getElementById('s-threshold').value)
    }
  };
  
  try {
    const r = await fetch(`${API}/config`, {
      method:'POST', 
      headers:{'Content-Type':'application/json'}, 
      body:JSON.stringify(cfg)
    });
    const res = await r.json();
    addLogLine('ok', 'Configuración guardada correctamente');
    // Recargar modelos si el servidor cambió algo
    await loadConfig();
  } catch(e) {
    addLogLine('error', 'Error guardando config: ' + e.message);
  }
}

async function loadVaultFiles() {
  const container = document.getElementById('recent-list');
  if (!container) return;
  
  try {
    const r = await fetch(`${API}/files`);
    const files = await r.json();
    
    container.innerHTML = '';
    if (!files || files.length === 0) {
      container.innerHTML = '<div class="empty"><div class="empty-icon">◈</div><div>No hay notas indexadas aún</div></div>';
      return;
    }
    
    files.forEach(f => {
      const div = document.createElement('div');
      div.className = 'result-item fade-in';
      div.innerHTML = `
        <div style="flex:1">
          <div class="result-name">${f.name}</div>
          <div class="result-cat">${f.path}</div>
        </div>
        <div class="result-cat" style="font-size:10px; margin-right:12px;">${f.date}</div>
        <button class="btn btn-ghost" style="padding:4px 8px; font-size:10px;" onclick="openFile('${f.path}')">Ver</button>
      `;
      container.appendChild(div);
    });
  } catch (e) {
    container.innerHTML = '<div class="empty">Error cargando biblioteca</div>';
  }
}

function openFile(path) {
  addLogLine('info', 'Abriendo nota: ' + path);
  // Aquí se podría integrar con Obsidian URI: obsidian://open?vault=...&file=...
}

// ─── SCAN ─────────────────────────────────────────────
async function startScan() {
  const scanPath = document.getElementById('scan-path').value.trim();
  const vaultPath = document.getElementById('vault-path').value.trim();
  const model = document.getElementById('model-select').value;

  if (!scanPath || !vaultPath) {
    addLogLine('error', 'Completá ambas rutas antes de iniciar');
    return;
  }

  // Reset UI
  document.getElementById('results-list').innerHTML = '<div class="empty"><div class="spin">◌</div><div>Procesando PDFs...</div></div>';
  document.getElementById('m-total').textContent = '0';
  document.getElementById('m-created').textContent = '0';
  document.getElementById('m-dupes').textContent = '0';
  document.getElementById('m-errors').textContent = '0';
  lastLogLen = 0;

  try {
    const r = await fetch(`${API}/scan`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({scan_path: scanPath, vault_path: vaultPath, model}),
    });
    const d = await r.json();
    if (d.error) { addLogLine('error', d.error); return; }

    document.getElementById('progress-section').style.display = 'block';
    document.getElementById('btn-scan').disabled = true;
    startPolling();
  } catch (e) {
    console.error("Error iniciando el escaneo:", e);
    addLogLine('error', 'Error iniciando el escaneo: ' + e.message);
  }
}

function startPolling() {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(pollStatus, 800);
}

async function pollStatus() {
  try {
    const r = await fetch(`${API}/status`);
    const d = await r.json();
    updateUI(d);
    if (d.status === 'done' || d.status === 'error') {
      clearInterval(pollInterval);
      pollInterval = null;
      document.getElementById('btn-scan').disabled = false;
      await loadVaultStats();
    }
  } catch {}
}

function updateUI(d) {
  // Status chip
  const chip = document.getElementById('status-chip');
  const chips = {idle:'chip-idle', running:'chip-running', done:'chip-done', error:'chip-error'};
  const labels = {idle:'● idle', running:'⬡ corriendo...', done:'✓ completado', error:'✗ error'};
  chip.className = `chip ${chips[d.status] || 'chip-idle'}`;
  chip.textContent = labels[d.status] || d.status;

  // Progress
  const pct = d.progress || 0;
  document.getElementById('progress-bar').style.width = pct + '%';
  document.getElementById('progress-pct').textContent = pct + '%';
  if (d.current_file) document.getElementById('progress-file').textContent = d.current_file;

  // Metrics
  document.getElementById('m-total').textContent = d.total || 0;
  document.getElementById('m-created').textContent = d.processed_n || 0;
  document.getElementById('m-dupes').textContent = d.duplicates_n || 0;
  document.getElementById('m-errors').textContent = d.errors_n || 0;

  // Log
  if (d.log && d.log.length > lastLogLen) {
    const newLines = d.log.slice(lastLogLen);
    newLines.forEach(line => {
      const lvl = line.includes('✓') || line.includes('ok') ? 'ok'
                : line.includes('⚠') ? 'warn'
                : line.includes('✗') || line.includes('Error') ? 'error'
                : line.includes('→') || line.includes('═══') ? 'action' : '';
      addLogLine(lvl, line);
    });
    lastLogLen = d.log.length;
  }

  // Results
  if (d.processed && d.processed.length > 0) {
    renderResults(d.processed);
  }
}

function addLogLine(level, text) {
  const container = document.getElementById('log-container');
  if (container.querySelector('.empty')) container.innerHTML = '';
  const div = document.createElement('div');
  div.className = `log-line ${level} fade-in`;
  div.textContent = text;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function clearLog() {
  document.getElementById('log-container').innerHTML = '<div class="empty"><div>Log limpiado</div></div>';
  lastLogLen = 0;
}

function renderResults(processed) {
  const list = document.getElementById('results-list');
  list.innerHTML = '';
  [...processed].reverse().forEach(item => {
    const r = item.result || item;
    const status = r.status || 'unknown';
    const badgeMap = {
      created: 'badge-created', duplicate: 'badge-duplicate',
      error: 'badge-error', skip: 'badge-skip',
    };
    const labelMap = {
      created: 'creada', duplicate: `duplicado ${r.similarity ? Math.round(r.similarity * 100) + '%' : ''}`,
      error: 'error', skip: 'omitido',
    };

    const div = document.createElement('div');
    div.className = 'result-item fade-in';
    const cat = r.analysis ? `${r.analysis.categoria || ''} › ${r.analysis.materia || ''}` : (r.similar_to || r.reason || '');
    div.innerHTML = `
      <div>
        <div class="result-name">${item.file || r.file || '—'}</div>
        <div class="result-cat">${cat}</div>
      </div>
      <div class="result-cat">${r.analysis ? r.analysis.dificultad || '' : ''}</div>
      <span class="badge ${badgeMap[status] || ''}">${labelMap[status] || status}</span>
    `;
    list.appendChild(div);
  });
}

// ─── VAULT STATS ─────────────────────────────────────────────
async function loadVaultStats() {
  const vaultPath = document.getElementById('vault-path').value.trim();
  if (!vaultPath) return;
  try {
    const r = await fetch(`${API}/vault-stats?vault_path=${encodeURIComponent(vaultPath)}`);
    const d = await r.json();

    document.getElementById('sm-notes').textContent   = d.notes || 0;
    document.getElementById('sm-folders').textContent = d.folders || 0;
    document.getElementById('sm-cats').textContent    = Object.keys(d.categories || {}).length;

    document.getElementById('v-notes').textContent   = d.notes || 0;
    document.getElementById('v-folders').textContent = d.folders || 0;
    document.getElementById('v-cats').textContent    = Object.keys(d.categories || {}).length;
    document.getElementById('v-types').textContent   = Object.keys(d.by_type || {}).length;

    // Category bars
    const catContainer = document.getElementById('cat-bars');
    const cats = d.categories || {};
    const maxVal = Math.max(...Object.values(cats), 1);
    catContainer.innerHTML = '';
    if (Object.keys(cats).length === 0) {
      catContainer.innerHTML = '<div class="empty"><div class="empty-icon">◈</div><div>Sin categorías aún</div></div>';
    } else {
      Object.entries(cats).sort((a,b) => b[1]-a[1]).forEach(([name, count]) => {
        const pct = Math.round((count / maxVal) * 100);
        const div = document.createElement('div');
        div.className = 'cat-item';
        div.innerHTML = `
          <div class="cat-name">${name}</div>
          <div class="cat-bar-bg"><div class="cat-bar-fill" style="width:${pct}%"></div></div>
          <div class="cat-count">${count}</div>
        `;
        catContainer.appendChild(div);
      });
    }

    // Recent notes
    const recentList = document.getElementById('recent-list');
    recentList.innerHTML = '';
    const recent = d.recent || [];
    if (recent.length === 0) {
      recentList.innerHTML = '<div class="empty"><div class="empty-icon">◈</div><div>Sin notas recientes</div></div>';
    } else {
      recent.forEach(n => {
        const parts = (n.path || '').split('/');
        const folder = parts.slice(0, -1).join(' › ');
        const div = document.createElement('div');
        div.className = 'result-item';
        div.innerHTML = `
          <div>
            <div class="result-name">${n.name}</div>
            <div class="result-cat">${folder}</div>
          </div>
          <div></div>
          <span class="badge badge-created">md</span>
        `;
        recentList.appendChild(div);
      });
    }
  } catch(e) {
    addLogLine('warn', 'No se pudo cargar stats: ¿el servidor está corriendo?');
  }
}

// ─── CHAT ─────────────────────────────────────────────
let chatBusy = false;
let mathJaxPromise = Promise.resolve();

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 140) + 'px';
}

function handleChatKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Convierte texto con saltos de línea y fórmulas LaTeX en HTML seguro.
 * Soporta: $...$ · $$...$$ · \(...\) · \[...\]
 */
function renderChatText(text) {
  const blocks = [];
  const save   = m => { blocks.push(m); return `\x00M${blocks.length - 1}\x00`; };
  let safe = text
    .replace(/\$\$[\s\S]+?\$\$/g,    save)   // display math $$...$$
    .replace(/\\\[[\s\S]+?\\\]/g,    save)   // display math \[...\]
    .replace(/\$[^$\n]+?\$/g,        save)   // inline math $...$
    .replace(/\\\([^\)]+?\\\)/g,     save);  // inline math \(...\)
  safe = escapeHtml(safe);
  // Parsear enlaces markdown: [texto](url)
  safe = safe.replace(/\[([^\]]+)\]\((obsidian:\/\/[^\)]+|http[^\)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
  // Parsear negritas **texto**
  safe = safe.replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>');
  safe = safe.replace(/\n/g, '<br>');
  return safe.replace(/\x00M(\d+)\x00/g, (_, i) => blocks[parseInt(i)]);
}

function appendMsg(role, text, sources = []) {
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = `msg ${role} fade-in`;

  const label = role === 'user' ? 'vos' : 'jarvis';
  let sourcesHtml = '';
  if (sources && sources.length > 0) {
    sourcesHtml = `<div class="msg-sources">` +
      sources.map(s => `<span class="source-tag" title="${s.path}">◈ ${s.title}</span>`).join('') +
      `</div>`;
  }

  div.innerHTML = `
    <div class="msg-label">${label}</div>
    <div class="msg-bubble">${renderChatText(text)}</div>
    ${sourcesHtml}
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;

  // Renderizar fórmulas LaTeX con MathJax
  if (window.MathJax && window.MathJax.typesetPromise) {
    mathJaxPromise = mathJaxPromise.then(() => {
      window.MathJax.typesetClear([div]);
      return window.MathJax.typesetPromise([div]);
    }).catch(err => console.warn('MathJax:', err));
  }
  return div;
}

function appendTyping() {
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'msg jarvis fade-in';
  div.id = 'typing-indicator';
  div.innerHTML = `
    <div class="msg-label">jarvis</div>
    <div class="typing-indicator">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function removeTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

async function sendChat() {
  if (chatBusy) return;
  const input = document.getElementById('chat-input');
  const question = input.value.trim();
  if (!question) return;

  chatBusy = true;
  document.getElementById('btn-chat').disabled = true;
  input.value = '';
  input.style.height = 'auto';

  appendMsg('user', question);
  appendTyping();

  try {
    const vaultPath = document.getElementById('vault-path').value.trim();
    const model     = document.getElementById('model-select').value;

    const r = await fetch(`${API}/chat`, {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({ question, vault_path: vaultPath, model }),
    });

    removeTyping();

    if (!r.ok) {
      throw new Error(`Error HTTP: ${r.status}`);
    }

    const reader = r.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let fullAnswer = "";
    let msgDiv = null;
    let bubbleEl = null;
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // guardar fragmento incompleto

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const d = JSON.parse(line);

          if (d.type === "sources") {
            msgDiv = appendMsg('jarvis', '', d.sources);
            bubbleEl = msgDiv.querySelector('.msg-bubble');
          } else if (d.type === "chunk") {
            fullAnswer += d.content;
            if (bubbleEl) {
              bubbleEl.innerHTML = renderChatText(fullAnswer);
              const container = document.getElementById('chat-messages');
              container.scrollTop = container.scrollHeight;
            }
          } else if (d.type === "error") {
            if (!msgDiv) appendMsg('jarvis', `Error: ${d.content}`);
            else bubbleEl.innerHTML += `<br><br><b>Error:</b> ${d.content}`;
          } else if (d.type === "done") {
            // Render final MathJax
            if (window.MathJax && window.MathJax.typesetPromise && msgDiv) {
              mathJaxPromise = mathJaxPromise.then(() => {
                window.MathJax.typesetClear([msgDiv]);
                return window.MathJax.typesetPromise([msgDiv]);
              }).catch(err => console.warn('MathJax:', err));
            }
          }
        } catch (err) {
          console.warn("Error parseando chunk de chat", err, line);
        }
      }
    }
  } catch (e) {
    removeTyping();
    appendMsg('jarvis', `Error de conexión: ${e.message}. ¿Está corriendo el servidor?`);
  } finally {
    chatBusy = false;
    document.getElementById('btn-chat').disabled = false;
    input.focus();
  }
}


function clearChat() {
  document.getElementById('chat-messages').innerHTML = `
    <div class="msg jarvis">
      <div class="msg-label">jarvis</div>
      <div class="msg-bubble">Chat limpiado. ¿En qué te puedo ayudar?</div>
    </div>
  `;
}

// ─── NETWORK INFO ─────────────────────────────────────────────
async function loadNetworkInfo() {
  try {
    const r = await fetch(`${API}/network-info`);
    const d = await r.json();
    const localEl  = document.getElementById('mobile-url');
    const tunnelEl = document.getElementById('tunnel-url');
    if (localEl)  localEl.textContent  = `http://${d.local_ip}:${d.port}`;
    if (tunnelEl) {
      if (d.tunnel_url) {
        tunnelEl.textContent = d.tunnel_url;
        tunnelEl.style.color = 'var(--green)';
      } else {
        tunnelEl.textContent = 'Inactivo — iniciá con: python3.12 jarvis_scanner.py --tunnel';
        tunnelEl.style.color = 'var(--amber)';
        tunnelEl.style.fontSize = '11px';
      }
    }
  } catch {
    const el = document.getElementById('mobile-url');
    if (el) el.textContent = 'No disponible (¿servidor corriendo?)';
  }
}

// ─── VIEW SWITCHING ─────────────────────────────────────────────
function switchView(name, el) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById(`view-${name}`).classList.add('active');
  el.classList.add('active');
  if (name === 'vault') {
    loadVaultStats();
    loadVaultFiles();
  }
  if (name === 'settings') loadNetworkInfo();
  if (name === 'chat')     document.getElementById('chat-input').focus();
}

async function runVaultCleanup() {
    if (!confirm("¿Seguro que querés limpiar duplicados? Se moverán a la carpeta '_Limpieza_Duplicados' en tu vault.")) return;
    
    const btn = document.getElementById('cleanupBtn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Limpiando...';
    btn.disabled = true;

    try {
        const r = await fetch(`${API_URL}/api/cleanup`, { method: 'POST' });
        const data = await r.json();
        if (data.deleted && data.deleted.length > 0) {
            alert(`Limpieza terminada: ${data.deleted.length} archivos duplicados movidos a la carpeta '_Limpieza_Duplicados'.`);
        } else {
            alert("No se encontraron duplicados evidentes.");
        }
    } catch (err) {
        alert("Error al limpiar vault: " + err);
    } finally {
        btn.innerHTML = 'Limpiar Duplicados';
        btn.disabled = false;
        loadVaultStats();
    }
}

// ─── START ─────────────────────────────────────────────
init();

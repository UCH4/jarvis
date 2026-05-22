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
let network       = null; // Vis.js network instance

// ─── INIT ─────────────────────────────────────────────
// Cada función es independiente: si una falla no bloquea las demás
async function init() {
  console.log("Iniciando la aplicación...");
  try {
    // 1. Poblar selectores (vaults, modelos, status de Ollama) en paralelo
    await Promise.allSettled([
      checkOllama(),
      loadModels(),
      loadVaults(),
    ]);

    // 2. Ahora que los selectores tienen opciones, aplicar la config guardada
    await loadConfig();

    // 3. Con el vault correcto seleccionado, cargar estadísticas
    await loadVaultStats();

    setInterval(checkOllama, 15000);
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
    console.warn("Error cargando vaults:", e);
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
    const scSel = document.getElementById('s-chat-model');
    sel.innerHTML = '';
    sSel.innerHTML = '';
    scSel.innerHTML = '';
    if (d.models && d.models.length > 0) {
      d.models.forEach(m => {
        const opt = `<option value="${m}">${m}</option>`;
        sel.innerHTML += opt;
        sSel.innerHTML += opt;
        scSel.innerHTML += opt;
      });
    } else {
      sel.innerHTML = '<option>sin modelos</option>';
      scSel.innerHTML = '<option>sin modelos</option>';
    }
  } catch (e) {
    console.error("Error al cargar modelos:", e);
    const sel = document.getElementById('model-select');
    sel.innerHTML = '<option>Error al cargar modelos</option>';
  }
}
// ─── CONFIG ─────────────────────────────────────────────
async function loadConfig() {
  try {
    const r = await fetch(`${API}/config`);
    const d = await r.json();
    
    // Configuración de rutas
    if (d.scan_path) document.getElementById('scan-path').value = d.scan_path;
    if (d.vault_path) {
      const vSel = document.getElementById('vault-path');
      // Si el vault no está en la lista (porque loadVaults no terminó o no está en obsidian.json)
      // lo agregamos temporalmente para que el valor sea válido.
      let exists = false;
      for (let i=0; i<vSel.options.length; i++) {
        if (vSel.options[i].value === d.vault_path) { exists = true; break; }
      }
      if (!exists) {
        const opt = document.createElement('option');
        opt.value = d.vault_path;
        opt.textContent = `Guardado: ${d.vault_path}`;
        vSel.appendChild(opt);
      }
      vSel.value = d.vault_path;
    }
    
    // Configuración persistente (IA y Watcher)
    if (d.user_config) {
      const u = d.user_config;
      if (document.getElementById('s-auto-sync'))   document.getElementById('s-auto-sync').checked   = u.auto_sync;
      if (document.getElementById('s-tool-search')) document.getElementById('s-tool-search').checked = u.tools_search;
      if (document.getElementById('s-tool-command')) document.getElementById('s-tool-command').checked = u.tools_command;
      if (document.getElementById('s-prefix-cache')) document.getElementById('s-prefix-cache').checked = u.prefix_cache;
      if (u.analysis_model && document.getElementById('s-model')) {
        document.getElementById('s-model').value = u.analysis_model;
      }
      if (u.chat_model && document.getElementById('s-chat-model')) {
        document.getElementById('s-chat-model').value = u.chat_model;
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
      prefix_cache:  document.getElementById('s-prefix-cache').checked,
      analysis_model: document.getElementById('s-model').value,
      chat_model:     document.getElementById('s-chat-model').value,
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

// ─── MANUSCRITO (foto) ─────────────────────────────────────────────
async function uploadHandwriting() {
  const inp = document.getElementById('handwriting-file');
  const out = document.getElementById('handwriting-output');
  const st = document.getElementById('handwriting-status');
  if (!inp || !inp.files || !inp.files[0]) {
    if (st) st.textContent = 'Elegí una imagen primero.';
    return;
  }
  const fd = new FormData();
  fd.append('image', inp.files[0]);
  if (st) st.textContent = 'Procesando…';
  if (out) out.value = '';
  try {
    const r = await fetch(`${API}/ingest/handwriting`, { method: 'POST', body: fd });
    const d = await r.json();
    if (!r.ok) {
      if (st) st.textContent = d.error || 'Error';
      if (out) out.value = '';
      return;
    }
    if (out) out.value = d.text || '';
    if (st) st.textContent = 'Listo (' + (d.backend || '') + ')';
  } catch (e) {
    if (st) st.textContent = 'Fallo de red: ' + e;
    if (out) out.value = '';
  }
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

async function handleChatFileUpload(e) {
  const file = e.target.files[0];
  if (!file) return;
  
  try {
    const text = await file.text();
    const input = document.getElementById('chat-input');
    const attachmentText = `\n\n### BORRADOR PARA REVISAR (${file.name}) ###\n\n${text}\n\n`;
    
    // Insertar el texto del archivo en el textarea
    input.value = input.value + attachmentText;
    autoResize(input);
    
    // Feedback visual
    appendMsg('jarvis', `📎 Archivo **${file.name}** adjuntado al borrador de tu mensaje. Escribí tu pregunta y dale a Preguntar cuando estés listo.`);
  } catch (error) {
    appendMsg('jarvis', `❌ Error al leer el archivo: ${error.message}`);
  }
  
  // Limpiar el input para permitir subir el mismo archivo de nuevo si se quiere
  e.target.value = '';
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
  const logo = document.querySelector('.logo-icon');
  if (logo) logo.classList.add('neural-pulse');
  
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
  const logo = document.querySelector('.logo-icon');
  if (logo) logo.classList.remove('neural-pulse');
  
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
      body:    JSON.stringify({ question, vault_path: vaultPath, model, mode: chatMode }),
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
          } else if (d.type === "terminal_approval") {
            showTerminalModal(d.command);
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


let pendingTerminalCommand = null;

function showTerminalModal(command) {
  pendingTerminalCommand = command;
  document.getElementById('terminal-command-display').textContent = command;
  document.getElementById('terminal-modal').classList.add('active');
}

async function closeTerminalModal(approved) {
  document.getElementById('terminal-modal').classList.remove('active');
  if (approved && pendingTerminalCommand) {
    appendMsg('user', `Ejecutando comando: ${pendingTerminalCommand}`);
    appendTyping();
    try {
      const r = await fetch(`${API}/terminal/execute`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ command: pendingTerminalCommand })
      });
      const d = await r.json();
      removeTyping();
      
      const statusIcon = d.status === 'success' ? '✅' : '❌';
      appendMsg('jarvis', `${statusIcon} Resultado del comando:\n\n\`\`\`bash\n${d.output}\n\`\`\`\n\n¿Necesitás algo más con este resultado?`);
    } catch (e) {
      removeTyping();
      appendMsg('jarvis', 'Error ejecutando comando terminal.');
    }
  } else {
    appendMsg('jarvis', 'Comando rechazado por el usuario. No ejecutaré esa acción.');
  }
  pendingTerminalCommand = null;
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
  if (name === 'settings') {
    loadNetworkInfo();
    refreshHealth();
  }
  if (name === 'chat')     document.getElementById('chat-input').focus();
  if (name === 'grafo')    loadGraph();
}

async function refreshHealth() {
  const grid = document.getElementById('health-grid');
  if (!grid) return;
  grid.innerHTML = '<div class="empty" style="padding: 20px;"><div class="spin">◌</div><div>Verificando modelos por subtarea...</div></div>';
  
  try {
    const r = await fetch(`${API}/models/health`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const health = await r.json();
    
    const taskLabels = {
      pdf_metadata: "📄 PDF Metadata", 
      chat: "💬 Chat", 
      chat_concise: "⚡ Quick",
      reasoning: "🧠 Razonamiento", 
      vision: "👁️ Visión", 
      hyde: "🔍 HyDE",
      multi_query: "🔀 Multi-Query", 
      intent_classify: "🏷️ Intent",
      professor: "🎓 Professor", 
      flashcards: "🃏 Flashcards",
      embed: "📐 Embeddings", 
      rerank: "📊 Rerank"
    };
    
    grid.innerHTML = Object.entries(health).map(([task, info]) => {
      const label = taskLabels[task] || task;
      const statusClass = info.status || 'missing';
      const statusLabel = statusClass.toUpperCase();
      const noteHtml = info.note ? `<div class="health-note">${info.note}</div>` : '';
      
      return `
        <div class="health-card ${statusClass}">
          <div class="task-name">${label}</div>
          <div class="model-name" title="${info.model}">${info.model} (${info.provider})</div>
          <span class="status-badge">${statusLabel}</span>
          ${noteHtml}
        </div>
      `;
    }).join('');
  } catch (e) {
    grid.innerHTML = `<div class="empty" style="padding: 20px; color: var(--red);">Error al verificar la salud de los modelos: ${e.message}</div>`;
  }
}


async function loadGraph() {
  const container = document.getElementById('knowledge-graph');
  const vaultPath = document.getElementById('vault-path').value.trim();
  if (!vaultPath) return;

  container.innerHTML = '<div class="empty"><div class="spin">◌</div><div>Construyendo grafo...</div></div>';

  try {
    const r = await fetch(`${API}/graph?vault_path=${encodeURIComponent(vaultPath)}`);
    const data = await r.json();

    if (!data.nodes || data.nodes.length === 0) {
      container.innerHTML = '<div class="empty"><div class="empty-icon">◈</div><div>No hay suficientes datos para el grafo</div></div>';
      return;
    }

    container.innerHTML = '';
    const nodes = new vis.DataSet(data.nodes);
    const edges = new vis.DataSet(data.edges);

    const options = {
      nodes: {
        shape: 'dot',
        size: 16,
        font: { size: 12, color: '#ffffff' },
        borderWidth: 2,
        shadow: true
      },
      edges: {
        width: 1,
        color: { inherit: 'from' },
        smooth: { type: 'continuous' }
      },
      groups: {
        note: { color: { background: '#00e5ff', border: '#008cff' } },
        materia: { color: { background: '#a78bfa', border: '#7c3aed' } },
        category: { color: { background: '#00ffa3', border: '#059669' } }
      },
      physics: {
        stabilization: true,
        barnesHut: { gravitationalConstant: -2000, centralGravity: 0.3, springLength: 95 }
      },
      interaction: { hover: true, tooltipDelay: 200 }
    };

    network = new vis.Network(container, { nodes, edges }, options);
    
    network.on("click", function (params) {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        const node = nodes.get(nodeId);
        if (node && node.group === 'note') {
          console.log("Nota seleccionada:", node.title);
          // Opcional: mostrar detalles o abrir en Obsidian
        }
      }
    });

  } catch (err) {
    console.error("Error al cargar grafo:", err);
    container.innerHTML = '<div class="empty">Error cargando el grafo de conocimiento</div>';
  }
}

async function runVaultCleanup() {
    if (!confirm("¿Seguro que querés limpiar duplicados? Se moverán a la carpeta '_Limpieza_Duplicados' en tu vault.")) return;
    
    const btn = document.getElementById('cleanupBtn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Limpiando...';
    btn.disabled = true;

    try {
        const r = await fetch(`${API}/cleanup`, { method: 'POST' });
        
        if (!r.ok) {
            const text = await r.text();
            let errorMsg = `Error ${r.status}`;
            try {
                const errData = JSON.parse(text);
                errorMsg = errData.message || errorMsg;
            } catch (e) {
                // Si no es JSON, mostrar un fragmento del texto o el status
                errorMsg = `Error del servidor (${r.status}). Verificá que el servidor esté actualizado y reiniciado.`;
            }
            alert("Error al limpiar vault: " + errorMsg);
            return;
        }

        const data = await r.json();
        if (data.deleted && data.deleted.length > 0) {
            alert(`Limpieza terminada: ${data.deleted.length} archivos duplicados movidos a la carpeta '_Limpieza_Duplicados'.`);
        } else {
            alert("No se encontraron duplicados evidentes.");
        }
    } catch (err) {
        alert("Error de conexión o proceso: " + err.message);
    } finally {
        btn.innerHTML = 'Limpiar Duplicados';
        btn.disabled = false;
        loadVaultStats();
    }
}

// ─── CHAT MODO PROFESOR ─────────────────────────────────────
let chatMode = 'normal';

function toggleChatMode() {
  const toggle = document.getElementById('chat-mode-toggle');
  const label = document.getElementById('mode-label');
  chatMode = toggle.checked ? 'professor' : 'normal';
  label.textContent = toggle.checked ? 'Modo Profesor 🎓' : 'Modo Normal';
  label.style.color = toggle.checked ? 'var(--purple)' : 'var(--text3)';
  
  if (chatMode === 'professor') {
    appendMsg('jarvis', '¡Excelente elección! Ahora te guiaré de forma socrática. En lugar de darte la respuesta directamente, te ayudaré a que la descubras por vos mismo usando tus propios apuntes.');
  } else {
    appendMsg('jarvis', 'Modo directo activado. Responderé a tus preguntas de forma concisa usando la información del vault.');
  }
}

async function generateExerciseUI() {
  appendTyping();
  try {
    const r = await fetch(`${API}/exercise`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ topic: "Conceptos clave del vault" })
    });
    const d = await r.json();
    removeTyping();
    
    if (d.error) {
      appendMsg('jarvis', 'No pude generar un ejercicio en este momento. Asegurate de tener notas indexadas.');
      return;
    }
    
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = 'msg jarvis fade-in';
    const exerciseId = 'ex-' + Date.now();
    
    div.innerHTML = `
      <div class="msg-label">jarvis 🎓</div>
      <div class="msg-bubble">
        <div class="exercise-card">
          <div class="exercise-title">${d.tipo} · EJERCICIO</div>
          <div class="exercise-body">${renderChatText(d.enunciado)}</div>
          <div class="exercise-hint">💡 <strong>Pista:</strong> ${d.pista}</div>
          <button class="exercise-sol-btn" onclick="toggleExerciseSolution('${exerciseId}')">Ver solución sugerida</button>
          <div id="${exerciseId}" class="exercise-sol-body">${renderChatText(d.solucion_oculta)}</div>
        </div>
      </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    
    // MathJax
    if (window.MathJax && window.MathJax.typesetPromise) {
      window.MathJax.typesetPromise([div]);
    }
  } catch (e) {
    removeTyping();
    appendMsg('jarvis', 'Error al generar ejercicio.');
  }
}

function toggleExerciseSolution(id) {
  const el = document.getElementById(id);
  const isHidden = !el.style.display || el.style.display === 'none';
  el.style.display = isHidden ? 'block' : 'none';
}

// ─── START ─────────────────────────────────────────────
init();


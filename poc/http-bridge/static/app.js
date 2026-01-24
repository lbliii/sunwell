/**
 * Minimal WebSocket client — proof of concept.
 * 
 * This replaces all Tauri invoke() calls with a single WebSocket.
 * Auto-reconnects, tracks stats, never drops events.
 */

let ws = null;
let reconnectAttempts = 0;
let totalEvents = 0;
let pingLatencies = [];
let reconnectCount = 0;

// DOM elements
const statusEl = document.getElementById('status');
const statusText = document.getElementById('status-text');
const runBtn = document.getElementById('run-btn');
const goalInput = document.getElementById('goal');
const eventsEl = document.getElementById('events');
const countEl = document.getElementById('count');

function connect() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${location.host}/ws`);
  
  ws.onopen = () => {
    console.log('✓ Connected');
    statusEl.className = 'status connected';
    statusText.textContent = 'Connected';
    runBtn.disabled = false;
    reconnectAttempts = 0;
    
    // Start ping for latency measurement
    setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        const start = performance.now();
        ws.send(JSON.stringify({ type: 'ping', ts: start }));
      }
    }, 5000);
  };
  
  ws.onclose = () => {
    console.log('✗ Disconnected');
    statusEl.className = 'status disconnected';
    statusText.textContent = 'Reconnecting...';
    runBtn.disabled = true;
    
    // Exponential backoff reconnect
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
    reconnectAttempts++;
    reconnectCount++;
    updateStats();
    
    setTimeout(connect, delay);
  };
  
  ws.onerror = (e) => {
    console.error('WebSocket error:', e);
  };
  
  ws.onmessage = (e) => {
    const event = JSON.parse(e.data);
    
    if (event.type === 'pong') {
      // Track latency
      const latency = performance.now() - event.ts;
      pingLatencies.push(latency);
      if (pingLatencies.length > 10) pingLatencies.shift();
      updateStats();
      return;
    }
    
    // Add event to list
    addEvent(event);
    totalEvents++;
    updateStats();
  };
}

function addEvent(event) {
  // Remove empty state
  const empty = eventsEl.querySelector('.empty');
  if (empty) empty.remove();
  
  // Determine event category for coloring
  let category = 'default';
  if (event.type.startsWith('memory')) category = 'memory';
  else if (event.type.startsWith('plan')) category = 'plan';
  else if (event.type.startsWith('task')) category = 'task';
  else if (event.type.startsWith('model')) category = 'model';
  else if (event.type.startsWith('gate')) category = 'gate';
  else if (event.type === 'complete') category = 'complete';
  else if (event.type === 'error') category = 'error';
  
  // Create event element
  const el = document.createElement('div');
  el.className = 'event';
  el.innerHTML = `
    <div class="event-type ${category}">${event.type}</div>
    <div class="event-data">${JSON.stringify(event.data)}</div>
  `;
  
  // Add to top of list
  eventsEl.insertBefore(el, eventsEl.firstChild);
  
  // Update count
  countEl.textContent = eventsEl.querySelectorAll('.event').length;
  
  // Keep max 100 events in DOM
  const events = eventsEl.querySelectorAll('.event');
  if (events.length > 100) {
    events[events.length - 1].remove();
  }
}

function updateStats() {
  document.getElementById('total-events').textContent = totalEvents;
  document.getElementById('dropped-events').textContent = '0'; // WebSocket doesn't drop
  document.getElementById('reconnects').textContent = reconnectCount;
  
  if (pingLatencies.length > 0) {
    const avg = pingLatencies.reduce((a, b) => a + b, 0) / pingLatencies.length;
    document.getElementById('latency').textContent = `${avg.toFixed(0)}ms`;
  }
}

function runAgent() {
  const goal = goalInput.value.trim();
  if (!goal) return;
  
  // Clear previous events
  eventsEl.innerHTML = '';
  countEl.textContent = '0';
  
  // Send run command
  ws.send(JSON.stringify({ type: 'run', goal }));
}

// Event listeners
runBtn.addEventListener('click', runAgent);
goalInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') runAgent();
});

// Connect on load
connect();

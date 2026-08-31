const els = {
  clientId: document.getElementById("client-id"),
  loginBtn: document.getElementById("login-btn"),
  statusPanel: document.getElementById("status-panel"),
  statusText: document.getElementById("status-text"),
  errorPanel: document.getElementById("error-panel"),
  errorText: document.getElementById("error-text"),
  resultPanel: document.getElementById("result-panel"),
  resultHeader: document.getElementById("result-header"),
  resultBody: document.getElementById("result-body"),
};

const STORAGE_KEY = "eveFitAdvisor.clientId";

function hide(el) { el.classList.add("hidden"); }
function show(el) { el.classList.remove("hidden"); }

function setStatus(text) {
  hide(els.errorPanel);
  hide(els.resultPanel);
  els.statusText.textContent = text;
  show(els.statusPanel);
}

function setError(text) {
  hide(els.statusPanel);
  hide(els.resultPanel);
  els.errorText.textContent = text;
  show(els.errorPanel);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderFit(fit, score, missing) {
  const frag = document.createDocumentFragment();
  frag.appendChild(el("div", "fit-name", fit.name));
  frag.appendChild(el("div", "fit-score", `${Math.round(score * 100)}% of listed skills trained to spec`));

  for (const slot of ["high", "mid", "low", "rig"]) {
    const items = fit[slot];
    if (items && items.length) {
      const row = el("div", "slot-row");
      row.appendChild(el("span", "slot-label", slot));
      row.appendChild(el("span", "slot-items", items.join(", ")));
      frag.appendChild(row);
    }
  }
  if (fit.drones && fit.drones.length) {
    const row = el("div", "slot-row");
    row.appendChild(el("span", "slot-label", "drone"));
    row.appendChild(el("span", "slot-items", fit.drones.join(", ")));
    frag.appendChild(row);
  }
  if (fit.charges && fit.charges.length) {
    const row = el("div", "slot-row");
    row.appendChild(el("span", "slot-label", "ammo"));
    row.appendChild(el("span", "slot-items", fit.charges.join(", ")));
    frag.appendChild(row);
  }

  if (missing && missing.length) {
    const block = el("div", "missing-block");
    block.appendChild(el("h3", null, "Train these to fly it exactly as listed:"));
    const sorted = [...missing].sort((a, b) => (b[2] - b[1]) - (a[2] - a[1]));
    for (const [name, have, need] of sorted) {
      const line = el("div", "missing-item");
      line.innerHTML = `${name}: level ${have} trained &rarr; need level <span class="need">${need}</span>`;
      block.appendChild(line);
    }
    frag.appendChild(block);
  } else {
    const block = el("div", "ready-block", "You can fly this fit exactly as listed. o7");
    frag.appendChild(block);
  }

  return frag;
}

function renderResult(data) {
  els.resultHeader.innerHTML = "";
  els.resultBody.innerHTML = "";

  const charLine = el("div", "char-line");
  charLine.innerHTML = `<span class="char-name">${data.char_name}</span> flying a <span class="ship-name">${data.ship_type_name}</span>`;
  els.resultHeader.appendChild(charLine);

  if (!data.covered) {
    const msg = el("p", null, `No curated fits on file yet for "${data.ship_type_name}".`);
    els.resultBody.appendChild(msg);
    const known = el("div", "known-ships", `Ships currently covered: ${data.known_ships.join(", ")}`);
    els.resultBody.appendChild(known);
    hide(els.statusPanel);
    hide(els.errorPanel);
    show(els.resultPanel);
    return;
  }

  els.resultBody.appendChild(renderFit(data.best.fit, data.best.score, data.best.missing));

  if (data.alternates && data.alternates.length) {
    const block = el("div", "alt-block");
    block.appendChild(el("h3", null, "Other fits on file for this ship"));
    for (const alt of data.alternates) {
      block.appendChild(el("div", "alt-row", `${alt.fit.name}: ${Math.round(alt.score * 100)}% skill match`));
    }
    els.resultBody.appendChild(block);
  }

  hide(els.statusPanel);
  hide(els.errorPanel);
  show(els.resultPanel);
}

async function handleLogin() {
  const clientId = els.clientId.value.trim();
  if (!clientId) {
    setError("Enter your ESI app's Client ID first.");
    return;
  }
  localStorage.setItem(STORAGE_KEY, clientId);

  els.loginBtn.disabled = true;
  setStatus("Opening your browser to log in via EVE SSO... approve the two read-only scopes there, then come back here.");

  try {
    const result = await window.pywebview.api.start_login(clientId);
    if (result.ok) {
      renderResult(result.data);
    } else {
      setError(result.error);
    }
  } catch (err) {
    setError(`Unexpected error: ${err}`);
  } finally {
    els.loginBtn.disabled = false;
  }
}

function init() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) els.clientId.value = saved;
  els.loginBtn.addEventListener("click", handleLogin);
}

if (window.pywebview) {
  init();
} else {
  window.addEventListener("pywebviewready", init);
}

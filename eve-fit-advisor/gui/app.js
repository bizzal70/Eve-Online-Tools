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
  settingsBtn: document.getElementById("settings-btn"),
  settingsPanel: document.getElementById("settings-panel"),
  accountsSection: document.getElementById("accounts-section"),
  accountsList: document.getElementById("accounts-list"),
  setupPanel: document.getElementById("setup-panel"),
  switchAccountLink: document.getElementById("switch-account-link"),
  cancelSwitchLink: document.getElementById("cancel-switch-link"),
  cancelSwitchWrap: document.getElementById("cancel-switch-wrap"),
  researchPanel: document.getElementById("research-panel"),
  researchLabel: document.getElementById("research-label"),
  anthropicKey: document.getElementById("anthropic-key"),
  anthropicKeyRow: document.getElementById("anthropic-key-row"),
  anthropicKeySaved: document.getElementById("anthropic-key-saved"),
  changeAnthropicKeyLink: document.getElementById("change-anthropic-key"),
  researchStyle: document.getElementById("research-style"),
  researchBtn: document.getElementById("research-btn"),
  researchStatus: document.getElementById("research-status"),
  researchResult: document.getElementById("research-result"),
};

const STORAGE_KEY = "eveFitAdvisor.clientId";
const ANTHROPIC_KEY_STORAGE = "eveFitAdvisor.anthropicKey";

let currentShip = null;
let savedAnthropicKey = "";

function showAnthropicKeySaved() {
  hide(els.anthropicKeyRow);
  show(els.anthropicKeySaved);
}

function showAnthropicKeyInput() {
  show(els.anthropicKeyRow);
  hide(els.anthropicKeySaved);
  els.anthropicKey.value = "";
  els.anthropicKey.focus();
}

// Returns the usable key, saving+collapsing it the first time it's typed.
function getAnthropicKey() {
  if (!els.anthropicKeyRow.classList.contains("hidden")) {
    const typed = els.anthropicKey.value.trim();
    if (typed) {
      savedAnthropicKey = typed;
      localStorage.setItem(ANTHROPIC_KEY_STORAGE, savedAnthropicKey);
      showAnthropicKeySaved();
    }
  }
  return savedAnthropicKey;
}

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

function renderFit(fit, score = null, missing = null) {
  const frag = document.createDocumentFragment();
  frag.appendChild(el("div", "fit-name", fit.name));
  if (fit.summary) {
    frag.appendChild(el("div", "fit-summary", fit.summary));
  }
  if (score !== null) {
    frag.appendChild(el("div", "fit-score", `${Math.round(score * 100)}% of listed skills trained to spec`));
  }

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

  if (missing !== null) {
    if (missing.length) {
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
  }

  return frag;
}

function renderVerifyResult(result) {
  const frag = document.createDocumentFragment();
  const verdictClass = result.still_recommended ? "verdict-good" : "verdict-bad";
  const verdictText = result.still_recommended ? "✓ Still looks current" : "⚠ May be outdated or incorrect";
  frag.appendChild(el("div", verdictClass, `${verdictText} (confidence: ${result.confidence})`));

  if (result.concerns && result.concerns.length) {
    const block = el("div", "missing-block");
    block.appendChild(el("h3", null, "Concerns"));
    for (const c of result.concerns) {
      block.appendChild(el("div", "missing-item", c));
    }
    frag.appendChild(block);
  }

  if (result.sources && result.sources.length) {
    const srcBlock = el("div", "alt-block");
    srcBlock.appendChild(el("h3", null, "Checked against"));
    for (const src of result.sources) {
      const row = el("div", "alt-row");
      const a = document.createElement("a");
      a.href = src.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = src.title || src.url;
      row.appendChild(a);
      srcBlock.appendChild(row);
    }
    frag.appendChild(srcBlock);
  }

  return frag;
}

function attachVerifyButton(container, shipName, fit) {
  const wrap = el("div", "verify-wrap");
  const btn = el("button", null, "Double-check this fit with Claude");
  btn.type = "button";
  const status = el("p", "hint");
  const resultDiv = el("div");

  btn.addEventListener("click", async () => {
    const apiKey = getAnthropicKey();
    if (!apiKey) {
      status.textContent = "Add your Anthropic API key in ⚙ Settings first.";
      return;
    }
    btn.disabled = true;
    resultDiv.innerHTML = "";
    status.textContent = "Checking against current sources... this can take up to a minute.";
    try {
      const result = await window.pywebview.api.verify_fit(shipName, fit, apiKey);
      if (result.ok) {
        status.textContent = "";
        resultDiv.appendChild(renderVerifyResult(result.result));
      } else {
        status.textContent = result.error;
      }
    } catch (err) {
      status.textContent = `Unexpected error: ${err}`;
    } finally {
      btn.disabled = false;
    }
  });

  wrap.appendChild(btn);
  wrap.appendChild(status);
  wrap.appendChild(resultDiv);
  container.appendChild(wrap);
}

function renderSlotProblems(problems) {
  const block = el("div", "slot-problem-block");
  block.appendChild(el("h3", null, "This fit doesn't actually fit the hull:"));
  for (const p of problems) {
    block.appendChild(el("div", null, p));
  }
  return block;
}

function renderFeasibility(feasibility) {
  if (!feasibility || feasibility.cpu_total === undefined) return null;
  const block = el("div", "feasibility-block");
  block.appendChild(el("h3", null, "Fitting estimate (conservative)"));
  block.appendChild(
    el(
      "div",
      feasibility.cpu_ok ? "feas-ok" : "feas-warn",
      `CPU: ${feasibility.cpu_used} / ${feasibility.cpu_total}  ${feasibility.cpu_ok ? "✓" : "⚠ over budget"}`
    )
  );
  block.appendChild(
    el(
      "div",
      feasibility.pg_ok ? "feas-ok" : "feas-warn",
      `Powergrid: ${feasibility.pg_used} / ${feasibility.pg_total}  ${feasibility.pg_ok ? "✓" : "⚠ over budget"}`
    )
  );
  block.appendChild(
    el(
      "p",
      "hint",
      "Estimate only — doesn't count skills like Weapon Upgrades that reduce module costs, so this can only under-estimate what actually fits, never over-promise."
    )
  );
  return block;
}

function showResearchPanelFor(shipName) {
  currentShip = shipName;
  els.researchLabel.textContent = `Research a fit for ${shipName} with Claude AI`;
  els.researchResult.innerHTML = "";
  els.researchStatus.textContent = "";
  show(els.researchPanel);
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
    showResearchPanelFor(data.ship_type_name);
    return;
  }

  els.resultBody.appendChild(renderFit(data.best.fit, data.best.score, data.best.missing));
  if (data.best.slot_problems && data.best.slot_problems.length) {
    els.resultBody.appendChild(renderSlotProblems(data.best.slot_problems));
  }
  const feasBlock = renderFeasibility(data.best.feasibility);
  if (feasBlock) els.resultBody.appendChild(feasBlock);
  if (data.best.stale) {
    els.resultBody.appendChild(
      el(
        "div",
        "stale-note",
        "⚠ This fit hasn't been checked recently (or ever) -- use \"Double-check this fit\" below to verify it's still current."
      )
    );
  }
  attachVerifyButton(els.resultBody, data.ship_type_name, data.best.fit);

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
  showResearchPanelFor(data.ship_type_name);
}

function showSetupPanel(canCancel) {
  hide(els.accountsSection);
  show(els.setupPanel);
  if (canCancel) show(els.cancelSwitchWrap); else hide(els.cancelSwitchWrap);
}

function showAccountsPanel() {
  hide(els.setupPanel);
  show(els.accountsSection);
}

function openSettings() {
  show(els.settingsPanel);
}

function closeSettings() {
  hide(els.settingsPanel);
}

function toggleSettings() {
  if (els.settingsPanel.classList.contains("hidden")) openSettings();
  else closeSettings();
}

async function refreshAccountsList() {
  const { last_used, characters } = await window.pywebview.api.list_accounts();
  els.accountsList.innerHTML = "";
  for (const acct of characters) {
    const row = el("div", "account-row");
    const useBtn = el("button", "use-btn", acct.char_name);
    useBtn.type = "button";
    useBtn.addEventListener("click", () => continueAs(acct.char_id));
    const forgetBtn = el("button", "forget-btn", "×");
    forgetBtn.type = "button";
    forgetBtn.title = "Forget this character";
    forgetBtn.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      await window.pywebview.api.forget_account(acct.char_id);
      await refreshAccountsList();
    });
    row.appendChild(useBtn);
    row.appendChild(forgetBtn);
    els.accountsList.appendChild(row);
  }
  return { last_used, characters };
}

async function continueAs(charId) {
  setStatus("Continuing...");
  try {
    const result = await window.pywebview.api.quick_login(charId);
    if (result.ok) {
      renderResult(result.data);
      closeSettings();
    } else if (result.expired) {
      setError(`${result.error} Log in again below.`);
      showSetupPanel(true);
    } else {
      setError(result.error);
    }
  } catch (err) {
    setError(`Unexpected error: ${err}`);
  }
}

async function handleLogin() {
  const clientId = els.clientId.value.trim();
  if (!clientId) {
    setError("Enter your ESI app's Client ID first.");
    return;
  }
  localStorage.setItem(STORAGE_KEY, clientId);

  els.loginBtn.disabled = true;
  setStatus("Opening your browser to log in via EVE SSO... approve the read-only scopes there, then come back here.");

  try {
    const result = await window.pywebview.api.start_login(clientId);
    if (result.ok) {
      renderResult(result.data);
      await refreshAccountsList();
      showAccountsPanel();
      closeSettings();
    } else {
      setError(result.error);
    }
  } catch (err) {
    setError(`Unexpected error: ${err}`);
  } finally {
    els.loginBtn.disabled = false;
  }
}

function categorizeWarning(name, fit) {
  return Object.prototype.hasOwnProperty.call(fit.skills || {}, name) ? "Skill" : "Module/Item";
}

function renderResearchResult(fit, warnings, slotProblems) {
  els.researchResult.innerHTML = "";
  els.researchResult.appendChild(renderFit(fit));

  if (slotProblems && slotProblems.length) {
    els.researchResult.appendChild(renderSlotProblems(slotProblems));
  }

  if (fit.notes && fit.notes.length) {
    const block = el("div", "notes-block");
    block.appendChild(el("h3", null, "Notes"));
    const list = document.createElement("ul");
    for (const n of fit.notes) {
      const li = document.createElement("li");
      li.textContent = n;
      list.appendChild(li);
    }
    block.appendChild(list);
    els.researchResult.appendChild(block);
  }

  if (warnings && warnings.length) {
    const warnBlock = el("div", "missing-block");
    warnBlock.appendChild(
      el("h3", null, "Couldn't verify these names against EVE's live item database (double-check spelling):")
    );
    for (const w of warnings) {
      warnBlock.appendChild(el("div", "missing-item", `${categorizeWarning(w, fit)}: ${w}`));
    }
    els.researchResult.appendChild(warnBlock);
  }

  if (fit.sources && fit.sources.length) {
    const srcBlock = el("div", "alt-block");
    srcBlock.appendChild(el("h3", null, "Sources"));
    for (const src of fit.sources) {
      const row = el("div", "alt-row");
      const a = document.createElement("a");
      a.href = src.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = src.title || src.url;
      row.appendChild(a);
      srcBlock.appendChild(row);
    }
    els.researchResult.appendChild(srcBlock);
  }

  const saveBtn = el("button", null, "Save this fit");
  saveBtn.type = "button";
  saveBtn.style.marginTop = "10px";
  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    await window.pywebview.api.save_researched_fit(currentShip, fit);
    els.researchStatus.textContent = "Saved -- it'll show up as an extra option next time you check this ship.";
  });
  els.researchResult.appendChild(saveBtn);
  attachVerifyButton(els.researchResult, currentShip, fit);
}

async function handleResearch() {
  const apiKey = getAnthropicKey();
  if (!apiKey) {
    els.researchStatus.textContent = "Enter your Anthropic API key first.";
    return;
  }
  if (!currentShip) return;

  els.researchBtn.disabled = true;
  els.researchResult.innerHTML = "";
  els.researchStatus.textContent = "Searching the web for current fits... this can take up to a minute.";

  try {
    const result = await window.pywebview.api.research_fit(currentShip, els.researchStyle.value.trim(), apiKey);
    if (result.ok) {
      els.researchStatus.textContent = "";
      renderResearchResult(result.fit, result.warnings, result.slot_problems);
    } else {
      els.researchStatus.textContent = result.error;
    }
  } catch (err) {
    els.researchStatus.textContent = `Unexpected error: ${err}`;
  } finally {
    els.researchBtn.disabled = false;
  }
}

async function init() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) els.clientId.value = saved;

  savedAnthropicKey = localStorage.getItem(ANTHROPIC_KEY_STORAGE) || "";
  if (savedAnthropicKey) {
    showAnthropicKeySaved();
  } else {
    showAnthropicKeyInput();
  }

  els.loginBtn.addEventListener("click", handleLogin);
  els.researchBtn.addEventListener("click", handleResearch);
  els.settingsBtn.addEventListener("click", toggleSettings);
  els.changeAnthropicKeyLink.addEventListener("click", (ev) => {
    ev.preventDefault();
    showAnthropicKeyInput();
  });
  els.switchAccountLink.addEventListener("click", (ev) => {
    ev.preventDefault();
    showSetupPanel(true);
  });
  els.cancelSwitchLink.addEventListener("click", (ev) => {
    ev.preventDefault();
    showAccountsPanel();
  });

  const { last_used, characters } = await refreshAccountsList();
  if (characters.length) {
    showAccountsPanel();
    if (last_used && characters.some((c) => String(c.char_id) === String(last_used))) {
      continueAs(last_used);
    } else {
      openSettings();
    }
  } else {
    showSetupPanel(false);
    openSettings();
  }
}

if (window.pywebview) {
  init();
} else {
  window.addEventListener("pywebviewready", init);
}

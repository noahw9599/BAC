const API = {
  catalog: "/api/catalog",
  setup: "/api/setup",
  drink: "/api/drink",
  state: "/api/state",
  reset: "/api/reset",
  feedback: "/api/feedback",
  authMe: "/api/auth/me",
  authRegister: "/api/auth/register",
  authLogin: "/api/auth/login",
  authLogout: "/api/auth/logout",
  sessionSave: "/api/session/save",
  sessionList: "/api/session/list",
  sessionLoad: "/api/session/load",
  favorites: "/api/favorites",
  sessionDates: "/api/session/dates",
};

const QUICK_ADD_IDS = ["bud-light", "white-claw-5", "truly", "vodka-soda", "ipa-typical", "red-wine"];
const STORAGE_LAST_DRINK = "drinking-buddy-last-drink";
const STORAGE_FAVORITES = "drinking-buddy-favorites";
const STORAGE_WATER_OZ = "drinking-buddy-water-oz";
const STORAGE_FRIENDS = "drinking-buddy-friends";
const STORAGE_FEEDBACK_DRAFT = "drinking-buddy-feedback-draft";
const MAX_FAVORITES = 6;
const MAX_FRIENDS = 12;

let bacChart = null;
let catalogFlat = [];
let catalogById = {};
let friends = [];
let currentUser = null;
let serverFavorites = [];
let savedSessionsCache = [];
let savedSessionDates = [];

function $(id) {
  return document.getElementById(id);
}

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function setAuthStatus(text) {
  const el = $("auth-status");
  if (el) el.textContent = text;
}

function setSessionStatus(text) {
  const el = $("session-status");
  if (el) el.textContent = text || "";
}

function todayYMD() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function setAuthUI(authenticated, user = null) {
  const setup = $("setup-section");
  const tracking = $("tracking-section");
  const logoutBtn = $("btn-logout");
  const loginBtn = $("btn-login");
  const registerBtn = $("btn-register");

  if (logoutBtn) logoutBtn.style.display = authenticated ? "block" : "none";
  if (loginBtn) loginBtn.style.display = authenticated ? "none" : "block";
  if (registerBtn) registerBtn.style.display = authenticated ? "none" : "block";

  if (!authenticated) {
    serverFavorites = [];
    refreshQuickAdd();
    savedSessionsCache = [];
    savedSessionDates = [];
    if (setup) setup.style.display = "none";
    if (tracking) tracking.style.display = "none";
    setAuthStatus("Sign in to save and reload past sessions.");
    const list = $("saved-session-list");
    if (list) list.innerHTML = "";
    const dateList = $("session-date-list");
    if (dateList) dateList.innerHTML = "";
    return;
  }

  const label = user?.display_name || user?.email || "user";
  setAuthStatus(`Signed in as ${label}`);
}

async function refreshAuth() {
  try {
    const data = await fetchJSON(API.authMe);
    currentUser = data.authenticated ? data.user : null;
    serverFavorites = [];
    setAuthUI(Boolean(currentUser), currentUser);
    if (currentUser) {
      await loadServerFavorites();
      await loadSavedSessions();
      await refreshState();
    }
  } catch (_) {
    currentUser = null;
    serverFavorites = [];
    setAuthUI(false);
  }
}

async function loadServerFavorites() {
  if (!currentUser) return;
  try {
    const data = await fetchJSON(API.favorites);
    serverFavorites = Array.isArray(data.favorites) ? data.favorites.slice(0, MAX_FAVORITES) : [];
    refreshQuickAdd();
  } catch (_) {
    serverFavorites = [];
  }
}

function getAuthPayload() {
  return {
    email: $("auth-email")?.value?.trim() || "",
    password: $("auth-password")?.value || "",
    display_name: $("auth-display-name")?.value?.trim() || "",
  };
}

async function authRegister() {
  const payload = getAuthPayload();
  await fetchJSON(API.authRegister, { method: "POST", body: JSON.stringify(payload) });
  await refreshAuth();
}

async function authLogin() {
  const payload = getAuthPayload();
  await fetchJSON(API.authLogin, { method: "POST", body: JSON.stringify(payload) });
  await refreshAuth();
}

async function authLogout() {
  await fetchJSON(API.authLogout, { method: "POST" });
  currentUser = null;
  setAuthUI(false);
}

function saveLastDrink(id) {
  try {
    sessionStorage.setItem(STORAGE_LAST_DRINK, id);
  } catch (_) {}
}

function getLastDrink() {
  try {
    return sessionStorage.getItem(STORAGE_LAST_DRINK);
  } catch (_) {
    return null;
  }
}

function getFavorites() {
  try {
    const raw = localStorage.getItem(STORAGE_FAVORITES);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.slice(0, MAX_FAVORITES) : [];
  } catch (_) {
    return [];
  }
}

function addDrinkUsed(catalogId) {
  const fav = getFavorites();
  const next = [catalogId, ...fav.filter((id) => id !== catalogId)].slice(0, MAX_FAVORITES);
  try {
    localStorage.setItem(STORAGE_FAVORITES, JSON.stringify(next));
  } catch (_) {}
  if (currentUser) {
    loadServerFavorites().catch(() => {});
  }
  refreshQuickAdd();
}

function getStoredNumber(key, fallback = 0) {
  try {
    const raw = localStorage.getItem(key);
    if (raw == null) return fallback;
    const parsed = parseFloat(raw);
    return Number.isFinite(parsed) ? parsed : fallback;
  } catch (_) {
    return fallback;
  }
}

function setStoredNumber(key, value) {
  try {
    localStorage.setItem(key, String(value));
  } catch (_) {}
}

function getStoredText(key, fallback = "") {
  try {
    const value = localStorage.getItem(key);
    return value == null ? fallback : String(value);
  } catch (_) {
    return fallback;
  }
}

function setStoredText(key, value) {
  try {
    localStorage.setItem(key, String(value));
  } catch (_) {}
}

function getWaterOz() {
  return Math.max(0, Math.round(getStoredNumber(STORAGE_WATER_OZ, 0)));
}

function setWaterOz(oz) {
  setStoredNumber(STORAGE_WATER_OZ, Math.max(0, Math.round(oz)));
}

function addWaterOz(oz) {
  setWaterOz(getWaterOz() + oz);
}

function loadFriends() {
  try {
    const raw = localStorage.getItem(STORAGE_FRIENDS);
    if (!raw) {
      friends = [];
      return;
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      friends = [];
      return;
    }
    friends = parsed
      .map((f) => ({
        id: String(f.id || ""),
        name: String(f.name || "").trim().slice(0, 24),
        drinks: Math.max(0, Math.round(f.drinks || 0)),
        waters: Math.max(0, Math.round(f.waters || 0)),
      }))
      .filter((f) => f.id && f.name)
      .slice(0, MAX_FRIENDS);
  } catch (_) {
    friends = [];
  }
}

function saveFriends() {
  try {
    localStorage.setItem(STORAGE_FRIENDS, JSON.stringify(friends.slice(0, MAX_FRIENDS)));
  } catch (_) {}
}

function friendRiskLabel(friend) {
  const net = friend.drinks - friend.waters * 0.5;
  if (net >= 6) return "High";
  if (net >= 4) return "Medium";
  if (net >= 2) return "Low";
  return "Light";
}

function renderFriends() {
  const list = $("friend-list");
  const summary = $("group-summary");
  if (!list || !summary) return;

  if (!friends.length) {
    list.innerHTML = "";
    summary.textContent = "No friends added yet.";
    return;
  }

  const top = [...friends].sort((a, b) => b.drinks - a.drinks)[0];
  const totalDrinks = friends.reduce((sum, f) => sum + f.drinks, 0);
  const totalWaters = friends.reduce((sum, f) => sum + f.waters, 0);
  summary.textContent = `Group drinks: ${totalDrinks} | Group waters: ${totalWaters} | Most drinks: ${top.name} (${top.drinks})`;

  list.innerHTML = "";
  friends.forEach((f) => {
    const row = document.createElement("div");
    row.className = "friend-row";

    const name = document.createElement("div");
    name.className = "friend-main";
    name.textContent = `${f.name} (${friendRiskLabel(f)})`;

    const counts = document.createElement("div");
    counts.className = "friend-counts";
    counts.textContent = `Drinks ${f.drinks} | Water ${f.waters}`;

    const actions = document.createElement("div");
    actions.className = "friend-actions";
    actions.innerHTML = `
      <button type="button" class="chip friend-action" data-friend-id="${f.id}" data-action="drink">+drink</button>
      <button type="button" class="chip friend-action" data-friend-id="${f.id}" data-action="water">+water</button>
      <button type="button" class="chip friend-action danger" data-friend-id="${f.id}" data-action="remove">remove</button>
    `;

    row.appendChild(name);
    row.appendChild(counts);
    row.appendChild(actions);
    list.appendChild(row);
  });
}

function addFriendFromInput() {
  const input = $("friend-name");
  if (!input) return;
  const name = input.value.trim().slice(0, 24);
  if (!name || friends.length >= MAX_FRIENDS) return;

  const id = `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
  friends.unshift({ id, name, drinks: 0, waters: 0 });
  friends = friends.slice(0, MAX_FRIENDS);
  input.value = "";
  saveFriends();
  renderFriends();
}

function applyFriendAction(friendId, action) {
  const idx = friends.findIndex((f) => f.id === friendId);
  if (idx < 0) return;
  const f = friends[idx];
  if (action === "drink") f.drinks += 1;
  if (action === "water") f.waters += 1;
  if (action === "remove") friends.splice(idx, 1);
  saveFriends();
  renderFriends();
}

function updateNightTools(state) {
  const waterProgress = $("water-progress");
  const waterHint = $("water-hint");
  const paceCoach = $("pace-coach");
  const drinkCount = state.drink_count ?? 0;
  const waterOz = getWaterOz();
  const targetOz = Math.max(8, drinkCount * 8);

  if (waterProgress) waterProgress.textContent = `${waterOz} / ${targetOz} oz`;

  if (waterHint) {
    const left = Math.max(0, targetOz - waterOz);
    waterHint.textContent = left > 0 ? `${left} oz to match a 1:1 drink-to-water pace.` : "Hydration target met.";
  }

  if (paceCoach) {
    const bac = state.bac_now ?? 0;
    const soberHours = state.hours_until_sober_from_now ?? 0;
    let msg = "Log drinks to get pacing advice.";
    if (bac >= 0.08) msg = "Pause now. Water only and plan a ride.";
    else if (bac >= 0.06) msg = "Take a 60+ min break before another drink.";
    else if (bac >= 0.04) msg = "Wait at least 45 min and drink water first.";
    else if (drinkCount >= 4 || soberHours >= 4) msg = "Keep spacing drinks to about 1 per hour.";
    else if (drinkCount > 0) msg = "Pace looks moderate. Keep alternating with water.";
    paceCoach.textContent = msg;
  }
}

function updateDriveAdvice(state) {
  const statusEl = $("drive-status");
  const msgEl = $("drive-message");
  const actionEl = $("drive-action");
  if (!statusEl || !msgEl || !actionEl) return;

  const advice = state.drive_advice;
  if (!advice) {
    statusEl.textContent = "No data yet";
    statusEl.className = "drive-status";
    msgEl.textContent = "Log drinks to see conservative guidance.";
    actionEl.textContent = "";
    return;
  }

  statusEl.textContent = advice.title || "Drive guidance";
  statusEl.className = `drive-status ${advice.status || ""}`;
  msgEl.textContent = advice.message || "";
  actionEl.textContent = advice.action || "";
}

function formatHoursShort(hours) {
  if (hours == null || !Number.isFinite(hours)) return "-";
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  if (h <= 0) return `${m}m`;
  return `${h}h ${m}m`;
}

function updateChartInsights(state) {
  const peakEl = $("peak-bac");
  const legalEl = $("below-legal-in");
  const riskEl = $("risk-zone");
  if (!peakEl || !legalEl || !riskEl) return;

  const curve = Array.isArray(state.curve) ? state.curve : [];
  const bac = state.bac_now ?? 0;
  const peak = curve.length ? Math.max(...curve.map((p) => p.bac || 0)) : state.bac_now || 0;
  peakEl.textContent = Number(peak).toFixed(3);

  let belowLegal = 0;
  if (bac >= 0.08) {
    belowLegal = null;
    for (const p of curve) {
      if ((p.t ?? 999) >= 0 && (p.bac ?? 0) < 0.08) {
        belowLegal = p.t;
        break;
      }
    }
  }
  legalEl.textContent = belowLegal == null ? ">24h" : formatHoursShort(belowLegal);

  if (bac >= 0.08) riskEl.textContent = "High";
  else if (bac >= 0.05) riskEl.textContent = "Elevated";
  else if (bac >= 0.02) riskEl.textContent = "Low";
  else riskEl.textContent = "Minimal";
}

function setupFeedbackTools() {
  const input = $("feedback-input");
  const emailLink = $("feedback-email-link");
  const copyBtn = $("btn-copy-feedback");
  const submitBtn = $("btn-submit-feedback");
  const ratingEl = $("feedback-rating");
  const contactEl = $("feedback-contact");
  const statusEl = $("feedback-status");
  if (!input || !emailLink) return;

  input.value = getStoredText(STORAGE_FEEDBACK_DRAFT, "");
  const updateEmailHref = () => {
    const body = encodeURIComponent(input.value.trim());
    emailLink.href = `mailto:noahw9599@gmail.com?subject=BAC%20Tracker%20Feedback&body=${body}`;
  };
  updateEmailHref();

  input.addEventListener("input", () => {
    setStoredText(STORAGE_FEEDBACK_DRAFT, input.value);
    updateEmailHref();
  });

  copyBtn?.addEventListener("click", async () => {
    const text = input.value.trim();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      copyBtn.textContent = "Copied";
      window.setTimeout(() => {
        copyBtn.textContent = "Copy feedback";
      }, 1200);
    } catch (_) {}
  });

  submitBtn?.addEventListener("click", async () => {
    const message = input.value.trim();
    if (!message) {
      if (statusEl) statusEl.textContent = "Add feedback text before sending.";
      return;
    }
    if (statusEl) statusEl.textContent = "Sending...";
    submitBtn.disabled = true;
    try {
      await fetchJSON(API.feedback, {
        method: "POST",
        body: JSON.stringify({
          message,
          rating: ratingEl?.value || null,
          contact: contactEl?.value?.trim() || null,
          context: {
            ua: navigator.userAgent,
            url: window.location.pathname,
          },
        }),
      });
      if (statusEl) statusEl.textContent = "Thanks, feedback sent.";
      input.value = "";
      if (ratingEl) ratingEl.value = "";
      if (contactEl) contactEl.value = "";
      setStoredText(STORAGE_FEEDBACK_DRAFT, "");
      updateEmailHref();
    } catch (err) {
      if (statusEl) statusEl.textContent = `Could not send: ${err.message}`;
    } finally {
      submitBtn.disabled = false;
    }
  });
}

function setupShareButton() {
  const btn = $("btn-share-app");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    const shareData = {
      title: "BAC Tracker",
      text: "Try this BAC tracking web app and send me feedback.",
      url: window.location.href,
    };
    try {
      if (navigator.share) {
        await navigator.share(shareData);
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(window.location.href);
        btn.textContent = "Link copied";
        window.setTimeout(() => {
          btn.textContent = "Share app with friends";
        }, 1200);
      }
    } catch (_) {}
  });
}

function formatReadableDate(ymd) {
  if (!ymd || !/^\d{4}-\d{2}-\d{2}$/.test(ymd)) return ymd || "";
  const [y, m, d] = ymd.split("-");
  return `${m}/${d}/${y}`;
}

function renderSessionDateChips() {
  const wrap = $("session-date-list");
  const input = $("session-date");
  if (!wrap || !input) return;
  wrap.innerHTML = "";
  savedSessionDates.slice(0, 21).forEach((d) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip saved-date";
    btn.dataset.date = d.session_date;
    btn.textContent = `${formatReadableDate(d.session_date)} (${d.session_count})`;
    if (input.value === d.session_date) btn.classList.add("active");
    wrap.appendChild(btn);
  });
}

function renderSavedSessions(items) {
  const list = $("saved-session-list");
  const input = $("session-date");
  if (!list) return;
  const selectedDate = input?.value || "";

  const filtered = selectedDate
    ? (items || []).filter((item) => item.session_date === selectedDate)
    : (items || []);

  renderSessionDateChips();

  if (!filtered || !filtered.length) {
    list.innerHTML = "";
    setSessionStatus(selectedDate ? `No sessions on ${formatReadableDate(selectedDate)}.` : "No saved sessions yet.");
    return;
  }

  setSessionStatus(selectedDate ? `${filtered.length} session(s) on ${formatReadableDate(selectedDate)}.` : `Saved sessions: ${filtered.length}`);
  list.innerHTML = "";
  filtered.forEach((item) => {
    const row = document.createElement("div");
    row.className = "friend-row";
    row.innerHTML = `
      <div class="friend-main">${item.name}</div>
      <div class="friend-counts">${item.created_at} | Drinks ${item.drink_count} | Date ${formatReadableDate(item.session_date)}</div>
      <div class="friend-actions">
        <button type="button" class="chip saved-load" data-session-id="${item.id}">Load</button>
      </div>
    `;
    list.appendChild(row);
  });
}

async function loadSavedSessions() {
  if (!currentUser) return;
  try {
    const [data, dates] = await Promise.all([fetchJSON(API.sessionList), fetchJSON(API.sessionDates)]);
    savedSessionsCache = data.items || [];
    savedSessionDates = dates.items || [];
    const dateInput = $("session-date");
    if (dateInput && !dateInput.value && savedSessionDates.length) {
      dateInput.value = savedSessionDates[0].session_date;
    }
    renderSavedSessions(savedSessionsCache);
  } catch (_) {
    savedSessionsCache = [];
    savedSessionDates = [];
    renderSavedSessions([]);
  }
}

async function saveCurrentSession() {
  const name = $("session-name")?.value?.trim() || "";
  if (!name) {
    setSessionStatus("Add a name before saving.");
    return;
  }
  try {
    await fetchJSON(API.sessionSave, { method: "POST", body: JSON.stringify({ name }) });
    $("session-name").value = "";
    setSessionStatus("Session saved.");
    await loadSavedSessions();
  } catch (err) {
    setSessionStatus(`Save failed: ${err.message}`);
  }
}

async function loadSavedSessionById(sessionId) {
  try {
    await fetchJSON(API.sessionLoad, {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    });
    setSessionStatus("Session loaded.");
    await refreshState();
  } catch (err) {
    setSessionStatus(`Load failed: ${err.message}`);
  }
}

function getQuickAddIds() {
  if (serverFavorites.length) {
    const used = new Set(serverFavorites);
    const defaults = QUICK_ADD_IDS.filter((id) => !used.has(id));
    return [...serverFavorites, ...defaults].slice(0, MAX_FAVORITES);
  }
  const fav = getFavorites();
  const used = new Set(fav);
  const defaults = QUICK_ADD_IDS.filter((id) => !used.has(id));
  return [...fav, ...defaults].slice(0, MAX_FAVORITES);
}

async function loadCatalog() {
  const { flat, by_category } = await fetchJSON(API.catalog);
  catalogFlat = flat || [];
  const sel = $("drink-catalog");
  const lastId = getLastDrink();

  if (by_category) {
    const order = ["beer", "seltzer", "wine", "liquor", "cocktail", "other"];
    sel.innerHTML = "";
    const cats = order.filter((c) => by_category[c]);
    let firstOpt = null;
    for (const cat of cats) {
      const optgroup = document.createElement("optgroup");
      optgroup.label = cat.charAt(0).toUpperCase() + cat.slice(1);
      for (const d of by_category[cat]) {
        const opt = document.createElement("option");
        opt.value = d.id;
        opt.textContent = d.name;
        optgroup.appendChild(opt);
        if (!firstOpt) firstOpt = opt;
        if (d.id === lastId) opt.selected = true;
      }
      sel.appendChild(optgroup);
    }
    if (!lastId && firstOpt) firstOpt.selected = true;
  } else if (catalogFlat.length) {
    sel.innerHTML = catalogFlat.map((d) => `<option value="${d.id}">${d.name}</option>`).join("");
    if (lastId) sel.value = lastId;
  }

  catalogById = {};
  (flat || []).forEach((d) => (catalogById[d.id] = d));
  refreshQuickAdd();
}

function refreshQuickAdd() {
  const quickEl = $("quick-add");
  if (!quickEl) return;
  const ids = getQuickAddIds();
  quickEl.innerHTML = "";
  for (const id of ids) {
    const d = catalogById[id] || catalogFlat.find((x) => x.id === id);
    if (!d) continue;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn quick-btn";
    btn.textContent = d.name;
    btn.dataset.catalogId = d.id;
    btn.addEventListener("click", () => addOneNow(d.id));
    quickEl.appendChild(btn);
  }
}

async function addOneNow(catalogId) {
  await addDrink(catalogId, 1, 0);
  saveLastDrink(catalogId);
  addDrinkUsed(catalogId);
}

async function addDrink(catalogId, count, hoursAgoVal) {
  const body = { catalog_id: catalogId, count, hours_ago: hoursAgoVal };
  await fetchJSON(API.drink, { method: "POST", body: JSON.stringify(body) });
  await refreshState();
}

async function setup() {
  const weight = parseFloat($("weight").value) || 160;
  const isMale = $("sex").value === "male";
  await fetchJSON(API.setup, {
    method: "POST",
    body: JSON.stringify({ weight_lb: weight, is_male: isMale }),
  });
  $("setup-section").style.display = "none";
  $("tracking-section").style.display = "block";
  await refreshState();
}

function getHoursAgo() {
  const active = document.querySelector(".time-ago-chips .chip.active");
  return active ? parseFloat(active.dataset.hours) : 0;
}

async function onAddCount(e) {
  const count = parseInt(e.target.dataset.count, 10) || 1;
  const catalogId = $("drink-catalog").value;
  if (!catalogId) return;
  await addDrink(catalogId, count, getHoursAgo());
  saveLastDrink(catalogId);
  addDrinkUsed(catalogId);
}

async function resetDrinks() {
  await fetchJSON(API.reset, { method: "POST" });
  setWaterOz(0);
  await refreshState();
}

function formatStopBy(hoursFromNow) {
  if (hoursFromNow <= 0) return "Stop now to feel better by then.";
  const h = Math.floor(hoursFromNow);
  const m = Math.round((hoursFromNow - h) * 60);
  if (h === 0) return `Stop in ~${m} min.`;
  return `Last drink in ~${h}h to feel better.`;
}

async function refreshState() {
  const hoursTarget = $("hours-until-target")?.value ? parseFloat($("hours-until-target").value) : null;
  const url = hoursTarget != null ? `${API.state}?hours_until_target=${hoursTarget}` : API.state;
  let state = null;
  try {
    state = await fetchJSON(url);
  } catch (err) {
    if (String(err.message || "").toLowerCase().includes("authentication")) {
      setAuthUI(false);
      return;
    }
    throw err;
  }

  if (!state.authenticated) {
    setAuthUI(false);
    return;
  }

  if (!state.configured) {
    $("setup-section").style.display = "block";
    $("tracking-section").style.display = "none";
    return;
  }

  $("setup-section").style.display = "none";
  $("tracking-section").style.display = "block";

  const bacEl = $("bac-now");
  if (bacEl) {
    bacEl.textContent = state.configured ? state.bac_now.toFixed(3) : "0.000";
    bacEl.classList.toggle("over-limit", state.bac_now >= 0.08);
  }

  const soberEl = document.querySelector("#sober-in");
  if (soberEl) soberEl.textContent = state.configured ? state.hours_until_sober_from_now.toFixed(1) + "h" : "-";

  const countEl = $("drinks-logged");
  if (countEl) countEl.textContent = state.drink_count ?? 0;

  const calEl = $("total-calories");
  if (calEl) calEl.textContent = state.total_calories ?? 0;

  const carbEl = $("total-carbs");
  if (carbEl) carbEl.textContent = state.total_carbs_g != null ? Math.round(state.total_carbs_g) : 0;

  const sugarEl = $("total-sugar");
  if (sugarEl) sugarEl.textContent = state.total_sugar_g != null ? Math.round(state.total_sugar_g) : 0;

  updateNightTools(state);
  updateDriveAdvice(state);
  updateChartInsights(state);

  const hangoverResult = $("hangover-result");
  const riskEl = $("hangover-risk");
  const stopEl = $("hangover-stop");
  const msgEl = $("hangover-message");
  if (state.hangover_plan && riskEl && stopEl && msgEl) {
    const p = state.hangover_plan;
    hangoverResult.style.display = "block";
    riskEl.textContent = `Risk: ${p.hangover_risk.toUpperCase()}`;
    riskEl.className = "hangover-risk " + p.hangover_risk;
    stopEl.textContent = formatStopBy(p.stop_by_hours_from_now);
    msgEl.textContent = p.message;
  } else if (hangoverResult) {
    hangoverResult.style.display = "none";
  }

  if (state.curve && state.curve.length) {
    const labels = state.curve.map((d) => d.t.toFixed(1));
    const data = state.curve.map((d) => d.bac);
    const legalLine = 0.08;

    if (bacChart) {
      bacChart.data.labels = labels;
      bacChart.data.datasets[0].data = data;
      bacChart.update("none");
    } else {
      const ctx = document.getElementById("bac-chart")?.getContext("2d");
      if (ctx) {
        bacChart = new Chart(ctx, {
          type: "line",
          data: {
            labels,
            datasets: [
              {
                label: "BAC (%)",
                data,
                borderColor: "#38bdf8",
                backgroundColor: "rgba(56, 189, 248, 0.15)",
                fill: true,
                tension: 0.2,
              },
              {
                label: "0.08% limit",
                data: labels.map(() => legalLine),
                borderColor: "#ef4444",
                borderDash: [6, 4],
                fill: false,
                pointRadius: 0,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: {
                title: { display: true, text: "Hours (0 = now)" },
                grid: { color: "rgba(255,255,255,0.06)" },
                ticks: { color: "#94a3b8", maxTicksLimit: 12 },
              },
              y: {
                min: 0,
                title: { display: true, text: "BAC (%)" },
                grid: { color: "rgba(255,255,255,0.06)" },
                ticks: { color: "#94a3b8" },
              },
            },
            plugins: { legend: { labels: { color: "#f1f5f9" } } },
          },
        });
      }
    }
  } else if (bacChart) {
    bacChart.data.labels = [];
    bacChart.data.datasets[0].data = [];
    bacChart.update("none");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {});
  }

  await loadCatalog();
  loadFriends();
  renderFriends();
  setupShareButton();
  setupFeedbackTools();
  await refreshAuth();

  $("btn-login")?.addEventListener("click", async () => {
    try {
      await authLogin();
    } catch (err) {
      setAuthStatus(`Login failed: ${err.message}`);
    }
  });

  $("btn-register")?.addEventListener("click", async () => {
    try {
      await authRegister();
    } catch (err) {
      setAuthStatus(`Register failed: ${err.message}`);
    }
  });

  $("btn-logout")?.addEventListener("click", async () => {
    try {
      await authLogout();
    } catch (err) {
      setAuthStatus(`Logout failed: ${err.message}`);
    }
  });

  $("btn-setup").addEventListener("click", setup);

  document.querySelectorAll(".btn-add").forEach((btn) => {
    btn.addEventListener("click", onAddCount);
  });

  document.querySelectorAll(".time-ago-chips .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".time-ago-chips .chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
    });
  });

  $("btn-reset").addEventListener("click", resetDrinks);
  $("hours-until-target").addEventListener("change", refreshState);

  $("btn-add-water")?.addEventListener("click", async () => {
    addWaterOz(8);
    await refreshState();
  });

  $("btn-add-friend")?.addEventListener("click", addFriendFromInput);
  $("friend-name")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") addFriendFromInput();
  });

  $("friend-list")?.addEventListener("click", (e) => {
    const target = e.target.closest(".friend-action");
    if (!target) return;
    applyFriendAction(target.dataset.friendId, target.dataset.action);
  });

  $("btn-save-session")?.addEventListener("click", saveCurrentSession);
  $("saved-session-list")?.addEventListener("click", async (e) => {
    const target = e.target.closest(".saved-load");
    if (!target) return;
    await loadSavedSessionById(target.dataset.sessionId);
  });
  $("session-date")?.addEventListener("change", () => {
    renderSavedSessions(savedSessionsCache);
  });
  $("btn-session-today")?.addEventListener("click", () => {
    const input = $("session-date");
    if (!input) return;
    input.value = todayYMD();
    renderSavedSessions(savedSessionsCache);
  });
  $("session-date-list")?.addEventListener("click", (e) => {
    const target = e.target.closest(".saved-date");
    if (!target) return;
    const input = $("session-date");
    if (!input) return;
    input.value = target.dataset.date || "";
    renderSavedSessions(savedSessionsCache);
  });
});

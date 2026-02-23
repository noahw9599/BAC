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
  accountProfile: "/api/account/profile",
  accountPrivacySummary: "/api/account/privacy-summary",
  accountEmergencyContacts: "/api/account/emergency-contacts",
  accountDelete: "/api/account/delete",
  sessionSave: "/api/session/save",
  sessionList: "/api/session/list",
  sessionLoad: "/api/session/load",
  favorites: "/api/favorites",
  sessionDates: "/api/session/dates",
  socialStatus: "/api/social/status",
  socialShare: "/api/social/share",
  socialRequest: "/api/social/request",
  socialLookup: "/api/social/user-lookup",
  socialInviteAccept: "/api/social/invite/accept",
  socialRespond: "/api/social/request/respond",
  socialFeed: "/api/social/feed",
  socialGroups: "/api/social/groups",
  socialGroupCreate: "/api/social/groups/create",
  socialGroupJoin: "/api/social/groups/join",
  guardianBase: "/api/social/groups",
  campusPresets: "/api/campus/presets",
  socialPrivacyRevokeAll: "/api/social/privacy/revoke-all",
  sessionDebrief: "/api/session/debrief",
  sessionEvents: "/api/session/events",
  sessionExport: "/api/session/export.csv",
};

const QUICK_ADD_IDS = ["vodka-cran", "vodka-diet-coke", "tequila-sprite", "tequila-soda", "white-claw-5", "bud-light"];
const STORAGE_LAST_DRINK = "drinking-buddy-last-drink";
const STORAGE_FAVORITES = "drinking-buddy-favorites";
const STORAGE_WATER_OZ = "drinking-buddy-water-oz";
const STORAGE_FRIENDS = "drinking-buddy-friends";
const STORAGE_TARGET_DATE = "drinking-buddy-target-date";
const STORAGE_TARGET_TIME = "drinking-buddy-target-time";
const STORAGE_PENDING_INVITE = "drinking-buddy-pending-invite";
const MAX_FAVORITES = 6;
const MAX_FRIENDS = 12;

let bacChart = null;
let catalogFlat = [];
let catalogById = {};
let catalogByCategory = {};
let friends = [];
let currentUser = null;
let serverFavorites = [];
let savedSessionsCache = [];
let savedSessionDates = [];
let authMode = "login";
let activeTab = "current";
let socialState = { share_with_friends: false, friends: [], incoming_requests: [] };
let socialGroups = [];
let activeGroupId = null;
let activeGroupSnapshot = null;
let guardianLinks = [];
let campusPresets = [];
let latestState = null;
let showAllSocialAlerts = false;
let attemptedAutoSetup = false;
let chartMode = "full";
let chartPaceEnabled = false;
let lastDeletedSessionEvent = null;
let emergencyContacts = [];
let selectedDrinkCategory = "all";

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

function switchTab(tabName) {
  const next = ["current", "history", "social", "account"].includes(tabName) ? tabName : "current";
  activeTab = next;
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${next}`);
  });
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === next);
  });
}

function initTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });
  switchTab("current");
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

  if (logoutBtn) logoutBtn.style.display = authenticated ? "block" : "none";

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
    renderSocialFeed([]);
    socialState = { share_with_friends: false, friends: [], incoming_requests: [] };
    emergencyContacts = [];
    renderEmergencyContacts();
    renderAccountPrivacySummary(null);
    renderSocialStatus();
    window.location.href = "/login";
    return;
  }

  const label = user?.display_name || user?.email || "user";
  setAuthStatus(`Signed in as ${label}`);
  if (setup) setup.style.display = "none";
  if (user?.default_weight_lb && $("weight")) {
    $("weight").value = Math.round(user.default_weight_lb);
  }
  if ($("sex") && typeof user?.is_male === "boolean") {
    $("sex").value = user.is_male ? "male" : "female";
  }
}

function renderMyFriendProfile() {
  const el = $("my-friend-profile");
  if (!el) return;
  if (!currentUser) {
    el.textContent = "";
    return;
  }
  const username = currentUser.username ? `@${currentUser.username}` : "(auto-assigned)";
  const inviteLink = currentUser.invite_code ? `${window.location.origin}/?invite=${encodeURIComponent(currentUser.invite_code)}` : "";
  el.textContent = `Your username: ${username}${inviteLink ? ` | Invite link: ${inviteLink}` : ""}`;
}

function populateAccountProfileForm() {
  if (!currentUser) return;
  if ($("acct-display-name")) $("acct-display-name").value = currentUser.display_name || "";
  if ($("acct-username")) $("acct-username").value = currentUser.username || "";
  if ($("acct-gender")) $("acct-gender").value = currentUser.is_male ? "male" : "female";
  if ($("acct-weight") && currentUser.default_weight_lb != null) {
    $("acct-weight").value = Math.round(currentUser.default_weight_lb);
  }
}

function updateAccountShareStatus() {
  const status = $("acct-share-status");
  const btn = $("btn-acct-share-toggle");
  const enabled = Boolean(socialState?.share_with_friends);
  if (status) status.textContent = enabled ? "Friend sharing is ON." : "Friend sharing is OFF.";
  if (btn) btn.textContent = enabled ? "Disable friend sharing" : "Enable friend sharing";
}

function renderAccountPrivacySummary(summary) {
  const el = $("acct-privacy-summary");
  if (!el) return;
  if (!summary) {
    el.textContent = "Privacy summary unavailable.";
    return;
  }
  const friendShare = summary.share_with_friends ? "ON" : "OFF";
  const groupShares = Number(summary.group_shares_enabled || 0);
  const guardianLinksCount = Number(summary.active_guardian_links || 0);
  el.textContent = `Friend sharing: ${friendShare} | Group shares enabled: ${groupShares} | Active guardian links: ${guardianLinksCount}`;
}

function renderEmergencyContacts() {
  const list = $("emergency-list");
  if (!list) return;
  list.innerHTML = "";
  if (!emergencyContacts.length) {
    list.innerHTML = `<div class="friend-row"><div class="friend-counts">No emergency contacts added yet.</div></div>`;
    return;
  }
  emergencyContacts.forEach((item) => {
    const row = document.createElement("div");
    row.className = "friend-row";
    row.innerHTML = `
      <div class="friend-main">${item.name}</div>
      <div class="friend-counts">${item.phone}</div>
      <div class="friend-actions">
        <button type="button" class="chip emergency-call" data-phone="${item.phone}">Call</button>
        <button type="button" class="chip danger emergency-delete" data-id="${item.id}">Remove</button>
      </div>
    `;
    list.appendChild(row);
  });
}

async function refreshAuth() {
  try {
    const data = await fetchJSON(API.authMe);
    currentUser = data.authenticated ? data.user : null;
    serverFavorites = [];
    setAuthUI(Boolean(currentUser), currentUser);
    renderMyFriendProfile();
    populateAccountProfileForm();
    if (currentUser) {
      attemptedAutoSetup = false;
      await processPendingInviteCode();
      await loadServerFavorites();
      await loadSavedSessions();
      await loadSocial();
      await loadAccountPrivacySummary();
      await loadEmergencyContacts();
      updateAccountShareStatus();
      await refreshState();
    } else {
      window.location.href = "/login";
    }
  } catch (_) {
    currentUser = null;
    serverFavorites = [];
    window.location.href = "/login";
    renderMyFriendProfile();
  }
}

async function loadAccountPrivacySummary() {
  if (!currentUser) return;
  try {
    const data = await fetchJSON(API.accountPrivacySummary);
    renderAccountPrivacySummary(data.summary || null);
  } catch (_) {
    renderAccountPrivacySummary(null);
  }
}

async function loadEmergencyContacts() {
  if (!currentUser) return;
  try {
    const data = await fetchJSON(API.accountEmergencyContacts);
    emergencyContacts = Array.isArray(data.contacts) ? data.contacts : [];
  } catch (_) {
    emergencyContacts = [];
  }
  renderEmergencyContacts();
}

function renderSocialStatus() {
  const shareStatus = $("social-share-status");
  const shareBtn = $("btn-group-share-toggle");
  const friendsList = $("social-friends-list");
  const reqList = $("social-requests-list");
  if (shareStatus) {
    const enabled = activeGroupSnapshot?.members?.find((m) => m.user_id === currentUser?.id)?.share_enabled;
    shareStatus.textContent = enabled ? "Group sharing ON for this group." : "Group sharing OFF for this group.";
  }
  if (shareBtn) {
    const enabled = activeGroupSnapshot?.members?.find((m) => m.user_id === currentUser?.id)?.share_enabled;
    shareBtn.textContent = enabled ? "Disable group sharing" : "Enable group sharing";
  }

  if (friendsList) {
    friendsList.innerHTML = "";
    if (!socialState.friends?.length) {
      friendsList.innerHTML = `<div class="friend-row"><div class="friend-counts">No friends yet.</div></div>`;
    } else {
      socialState.friends.forEach((f) => {
        const row = document.createElement("div");
        row.className = "friend-row";
        row.innerHTML = `<div class="friend-main">${f.display_name}</div><div class="friend-counts">${f.email}</div>`;
        friendsList.appendChild(row);
      });
    }
  }

  if (reqList) {
    reqList.innerHTML = "";
    if (!socialState.incoming_requests?.length) {
      reqList.innerHTML = `<div class="friend-row"><div class="friend-counts">No incoming requests.</div></div>`;
    } else {
      socialState.incoming_requests.forEach((r) => {
        const row = document.createElement("div");
        row.className = "friend-row";
        row.innerHTML = `
          <div class="friend-main">${r.display_name}</div>
          <div class="friend-counts">${r.email}</div>
          <div class="friend-actions">
            <button type="button" class="chip social-respond" data-request-id="${r.request_id}" data-action="accept">Accept</button>
            <button type="button" class="chip social-respond danger" data-request-id="${r.request_id}" data-action="reject">Reject</button>
          </div>
        `;
        reqList.appendChild(row);
      });
    }
  }
}

function renderSocialFeed(items) {
  const list = $("social-feed-list");
  if (!list) return;
  list.innerHTML = "";
  if (!items || !items.length) {
    list.innerHTML = `<div class="friend-row"><div class="friend-counts">No friend data shared yet.</div></div>`;
    return;
  }
  items.forEach((f) => {
    const bac = f.bac_now == null ? "-" : Number(f.bac_now).toFixed(3);
    const drinks = f.drink_count == null ? "-" : f.drink_count;
    const updated = f.updated_at || "n/a";
    const row = document.createElement("div");
    row.className = "friend-row";
    row.innerHTML = `
      <div class="friend-main">${f.display_name}</div>
      <div class="friend-counts">BAC ${bac} | Drinks ${drinks} | Updated ${updated}</div>
    `;
    list.appendChild(row);
  });
}

function renderGroupList() {
  const list = $("social-group-list");
  const label = $("social-active-group-label");
  if (!list) return;
  list.innerHTML = "";
  if (!socialGroups.length) {
    list.innerHTML = `<div class="friend-row"><div class="friend-counts">No groups yet. Create or join one.</div></div>`;
    if (label) label.textContent = "";
    return;
  }
  socialGroups.forEach((g) => {
    const row = document.createElement("div");
    row.className = "friend-row";
    row.innerHTML = `
      <div class="friend-main">${g.name}</div>
      <div class="friend-counts">Code ${g.invite_code} | Role ${g.role}</div>
      <div class="friend-actions">
        <button type="button" class="chip social-group-select" data-group-id="${g.id}">Open</button>
      </div>
    `;
    list.appendChild(row);
  });
  const active = socialGroups.find((g) => String(g.id) === String(activeGroupId));
  if (label) label.textContent = active ? `Active group: ${active.name}` : "Select a group to view members and alerts.";
}

function renderGroupSnapshot() {
  const membersList = $("social-members-list");
  const alertsList = $("social-alerts-list");
  if (!membersList || !alertsList) return;
  membersList.innerHTML = "";
  alertsList.innerHTML = "";

  if (!activeGroupSnapshot) {
    membersList.innerHTML = `<div class="friend-row"><div class="friend-counts">Select a group first.</div></div>`;
    alertsList.innerHTML = `<div class="friend-row"><div class="friend-counts">No alerts.</div></div>`;
    renderSocialStatus();
    return;
  }

  const me = activeGroupSnapshot.members.find((m) => m.user_id === currentUser?.id);
  const elevatedView = me && ["owner", "mod", "dd"].includes(me.role);
  const members = [...activeGroupSnapshot.members];
  if (elevatedView) {
    members.sort((a, b) => (b.bac_now || 0) - (a.bac_now || 0));
  }

  members.forEach((m) => {
    const bac = m.bac_now == null ? "hidden" : Number(m.bac_now).toFixed(3);
    const drinks = m.drink_count == null ? "hidden" : m.drink_count;
    const loc = m.location_note || "-";
    const row = document.createElement("div");
    row.className = "friend-row";
    row.innerHTML = `
      <div class="friend-main">${m.display_name} (${m.role})</div>
      <div class="friend-counts">BAC ${bac} | Drinks ${drinks} | Location ${loc}</div>
      <div class="friend-actions">
        <button type="button" class="chip social-check" data-target-user-id="${m.user_id}" data-kind="check">Check</button>
        <button type="button" class="chip social-check" data-target-user-id="${m.user_id}" data-kind="water">Water</button>
        <button type="button" class="chip social-check" data-target-user-id="${m.user_id}" data-kind="ride">Ride</button>
      </div>
    `;
    membersList.appendChild(row);
  });

  if (!activeGroupSnapshot.alerts.length) {
    alertsList.innerHTML = `<div class="friend-row"><div class="friend-counts">No alerts yet.</div></div>`;
  } else {
    const allAlerts = [...activeGroupSnapshot.alerts];
    const alertsToRender = showAllSocialAlerts ? allAlerts : allAlerts.slice(0, 3);
    alertsToRender.forEach((a) => {
      const row = document.createElement("div");
      row.className = "friend-row";
      row.innerHTML = `<div class="friend-main">${a.alert_type.toUpperCase()}</div><div class="friend-counts">${a.message} | ${a.created_at}</div>`;
      alertsList.appendChild(row);
    });
    if (!showAllSocialAlerts && allAlerts.length > 3) {
      const row = document.createElement("div");
      row.className = "friend-row";
      row.innerHTML = `<div class="friend-counts">${allAlerts.length - 3} more alerts hidden.</div>`;
      alertsList.appendChild(row);
    }
  }
  const toggleBtn = $("btn-social-toggle-alerts");
  if (toggleBtn) {
    toggleBtn.textContent = showAllSocialAlerts ? "Show fewer alerts" : "Show all alerts";
    toggleBtn.style.display = activeGroupSnapshot.alerts.length > 3 ? "inline-block" : "none";
  }
  renderSocialStatus();
  renderGuardianLinks();
  updateOnboardingStatus();
}

function renderGuardianLinks() {
  const list = $("social-guardian-list");
  if (!list) return;
  list.innerHTML = "";
  if (!activeGroupId) {
    list.innerHTML = `<div class="friend-row"><div class="friend-counts">Select a group first.</div></div>`;
    return;
  }
  if (!guardianLinks.length) {
    list.innerHTML = `<div class="friend-row"><div class="friend-counts">No guardian links yet.</div></div>`;
    return;
  }
  guardianLinks.forEach((g) => {
    const url = `${window.location.origin}/guardian/${g.token}`;
    const row = document.createElement("div");
    row.className = "friend-row";
    row.innerHTML = `
      <div class="friend-main">${g.label} ${g.is_active ? "" : "(revoked)"}</div>
      <div class="friend-counts">Alerts ${g.receive_alerts ? "ON" : "OFF"} | ${g.created_at}</div>
      <div class="friend-actions">
        <button type="button" class="chip guardian-copy" data-url="${url}">Copy link</button>
        <button type="button" class="chip guardian-alerts" data-link-id="${g.id}" data-enabled="${g.receive_alerts ? 1 : 0}">${g.receive_alerts ? "Mute alerts" : "Enable alerts"}</button>
        <button type="button" class="chip guardian-revoke danger" data-link-id="${g.id}">Revoke</button>
      </div>
    `;
    list.appendChild(row);
  });
}

async function loadGroupSnapshot(groupId) {
  if (!groupId) return;
  activeGroupId = String(groupId);
  const data = await fetchJSON(`${API.socialGroups}/${groupId}`);
  activeGroupSnapshot = data;
  const guardians = await fetchJSON(`${API.guardianBase}/${groupId}/guardian-links`);
  guardianLinks = guardians.items || [];
  renderGroupList();
  renderGroupSnapshot();
}

async function loadSocial() {
  if (!currentUser) return;
  try {
    socialState = await fetchJSON(API.socialStatus);
    renderSocialStatus();
    updateAccountShareStatus();
    const feed = await fetchJSON(API.socialFeed);
    renderSocialFeed(feed.items || []);
    const groups = await fetchJSON(API.socialGroups);
    socialGroups = groups.items || [];
    if ((!activeGroupId || !socialGroups.find((g) => String(g.id) === String(activeGroupId))) && socialGroups.length) {
      activeGroupId = String(socialGroups[0].id);
    }
    renderGroupList();
    if (activeGroupId) {
      await loadGroupSnapshot(activeGroupId);
    } else {
      activeGroupSnapshot = null;
      guardianLinks = [];
      renderGroupSnapshot();
    }
    updateOnboardingStatus();
  } catch (_) {
    socialState = { share_with_friends: false, friends: [], incoming_requests: [] };
    socialGroups = [];
    activeGroupId = null;
    activeGroupSnapshot = null;
    guardianLinks = [];
    renderSocialStatus();
    updateAccountShareStatus();
    renderSocialFeed([]);
    renderGroupList();
    renderGroupSnapshot();
    updateOnboardingStatus();
  }
}

async function saveAccountProfile() {
  if (!currentUser) return;
  const payload = {
    display_name: $("acct-display-name")?.value?.trim() || "",
    username: $("acct-username")?.value?.trim().toLowerCase() || "",
    gender: $("acct-gender")?.value || "",
    default_weight_lb: $("acct-weight")?.value || "",
  };
  const status = $("acct-status");
  try {
    const res = await fetchJSON(API.accountProfile, { method: "POST", body: JSON.stringify(payload) });
    currentUser = res.user || currentUser;
    setAuthStatus(`Signed in as ${currentUser.display_name || currentUser.email}`);
    populateAccountProfileForm();
    if (status) status.textContent = "Profile updated.";
    await refreshState();
  } catch (err) {
    if (status) status.textContent = err.message;
  }
}

async function toggleAccountSharePreference() {
  if (!currentUser) return;
  const next = !Boolean(socialState?.share_with_friends);
  await fetchJSON(API.socialShare, { method: "POST", body: JSON.stringify({ enabled: next }) });
  socialState.share_with_friends = next;
  updateAccountShareStatus();
  await loadAccountPrivacySummary();
}

async function addEmergencyContactFromForm() {
  if (!currentUser) return;
  const name = $("emergency-name")?.value?.trim() || "";
  const phone = $("emergency-phone")?.value?.trim() || "";
  const status = $("emergency-status");
  try {
    const data = await fetchJSON(API.accountEmergencyContacts, { method: "POST", body: JSON.stringify({ name, phone }) });
    emergencyContacts = [data.contact, ...emergencyContacts];
    renderEmergencyContacts();
    if ($("emergency-name")) $("emergency-name").value = "";
    if ($("emergency-phone")) $("emergency-phone").value = "";
    if (status) status.textContent = "Emergency contact added.";
  } catch (err) {
    if (status) status.textContent = err.message || "Could not add contact.";
  }
}

async function deleteEmergencyContact(contactId) {
  if (!currentUser) return;
  const status = $("emergency-status");
  try {
    await fetchJSON(`${API.accountEmergencyContacts}/${Number(contactId)}`, { method: "DELETE" });
    emergencyContacts = emergencyContacts.filter((c) => Number(c.id) !== Number(contactId));
    renderEmergencyContacts();
    if (status) status.textContent = "Emergency contact removed.";
  } catch (err) {
    if (status) status.textContent = err.message || "Could not remove contact.";
  }
}

async function deleteAccountFlow() {
  if (!currentUser) return;
  const password = $("acct-delete-password")?.value || "";
  const confirmText = $("acct-delete-confirm")?.value || "";
  const status = $("acct-delete-status");
  if (status) status.textContent = "";

  const ok = window.confirm("This will permanently delete your account and all data. Continue?");
  if (!ok) return;
  try {
    await fetchJSON(API.accountDelete, {
      method: "POST",
      body: JSON.stringify({ password, confirm_text: confirmText }),
    });
    if (status) status.textContent = "Account deleted.";
    window.location.href = "/login";
  } catch (err) {
    if (status) status.textContent = err.message || "Account delete failed.";
  }
}

async function toggleSocialShare() {
  if (!currentUser || !activeGroupId) return;
  const me = activeGroupSnapshot?.members?.find((m) => m.user_id === currentUser.id);
  const next = !Boolean(me?.share_enabled);
  if (next) {
    const ok = window.confirm("Share your BAC/drink summary with this group?");
    if (!ok) return;
  }
  await fetchJSON(`${API.socialGroups}/${activeGroupId}/share`, { method: "POST", body: JSON.stringify({ enabled: next }) });
  await loadSocial();
}

async function sendSocialFriendRequest() {
  const raw = $("social-friend-email")?.value?.trim() || "";
  const status = $("social-request-status");
  if (!raw) {
    if (status) status.textContent = "Enter an email or username first.";
    return;
  }
  const payload = raw.includes("@") ? { email: raw.toLowerCase() } : { username: raw.toLowerCase().replace(/^@/, "") };
  try {
    await fetchJSON(API.socialRequest, { method: "POST", body: JSON.stringify(payload) });
    if ($("social-friend-email")) $("social-friend-email").value = "";
    if (status) status.textContent = "Request sent.";
    await loadSocial();
  } catch (err) {
    if (status) status.textContent = err.message;
  }
}

async function lookupSocialUser() {
  const username = ($("social-lookup-username")?.value?.trim() || "").toLowerCase().replace(/^@/, "");
  const out = $("social-lookup-result");
  if (!username) {
    if (out) out.textContent = "Enter a username first.";
    return;
  }
  try {
    const found = await fetchJSON(`${API.socialLookup}?username=${encodeURIComponent(username)}`);
    if (out) out.textContent = `Found: ${found.user.display_name} (@${found.user.username}).`;
    if ($("social-friend-email")) $("social-friend-email").value = found.user.username;
  } catch (err) {
    if (out) out.textContent = err.message;
  }
}

async function respondSocialRequest(requestId, action) {
  await fetchJSON(API.socialRespond, {
    method: "POST",
    body: JSON.stringify({ request_id: requestId, action }),
  });
  await loadSocial();
}

async function createSocialGroup() {
  const name = $("social-group-name")?.value?.trim() || "";
  const status = $("social-request-status");
  if (name.length < 3) {
    if (status) status.textContent = "Group name should be at least 3 characters.";
    return;
  }
  await fetchJSON(API.socialGroupCreate, { method: "POST", body: JSON.stringify({ name }) });
  if ($("social-group-name")) $("social-group-name").value = "";
  if (status) status.textContent = "Group created.";
  await loadSocial();
}

async function joinSocialGroup() {
  const code = $("social-group-code")?.value?.trim() || "";
  const status = $("social-request-status");
  if (!code) {
    if (status) status.textContent = "Enter an invite code.";
    return;
  }
  await fetchJSON(API.socialGroupJoin, { method: "POST", body: JSON.stringify({ invite_code: code }) });
  if ($("social-group-code")) $("social-group-code").value = "";
  if (status) status.textContent = "Joined group.";
  await loadSocial();
}

async function updateGroupLocation() {
  if (!activeGroupId) return;
  const note = $("social-location-note")?.value?.trim() || "";
  await fetchJSON(`${API.socialGroups}/${activeGroupId}/location`, {
    method: "POST",
    body: JSON.stringify({ location_note: note }),
  });
  await loadSocial();
}

async function sendGroupCheck(targetUserId, kind) {
  if (!activeGroupId) return;
  await fetchJSON(`${API.socialGroups}/${activeGroupId}/check`, {
    method: "POST",
    body: JSON.stringify({ target_user_id: targetUserId, kind }),
  });
  await loadSocial();
}

async function createGuardianLink() {
  if (!activeGroupId) return;
  const label = $("social-guardian-label")?.value?.trim() || "Guardian";
  await fetchJSON(`${API.guardianBase}/${activeGroupId}/guardian-links`, {
    method: "POST",
    body: JSON.stringify({ label, receive_alerts: true }),
  });
  if ($("social-guardian-label")) $("social-guardian-label").value = "";
  await loadGroupSnapshot(activeGroupId);
}

async function setGuardianAlerts(linkId, enabled) {
  if (!activeGroupId) return;
  await fetchJSON(`${API.guardianBase}/${activeGroupId}/guardian-links/${linkId}/alerts`, {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
  await loadGroupSnapshot(activeGroupId);
}

async function revokeGuardian(linkId) {
  if (!activeGroupId) return;
  await fetchJSON(`${API.guardianBase}/${activeGroupId}/guardian-links/${linkId}/revoke`, {
    method: "POST",
  });
  await loadGroupSnapshot(activeGroupId);
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

async function authLogout() {
  await fetchJSON(API.authLogout, { method: "POST" });
  currentUser = null;
  window.location.href = "/login";
  renderMyFriendProfile();
}

function pullInviteCodeFromUrl() {
  try {
    const url = new URL(window.location.href);
    const invite = (url.searchParams.get("invite") || "").trim().toUpperCase();
    if (!invite) return;
    localStorage.setItem(STORAGE_PENDING_INVITE, invite);
    url.searchParams.delete("invite");
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  } catch (_) {}
}

function getPendingInviteCode() {
  try {
    return localStorage.getItem(STORAGE_PENDING_INVITE) || "";
  } catch (_) {
    return "";
  }
}

function clearPendingInviteCode() {
  try {
    localStorage.removeItem(STORAGE_PENDING_INVITE);
  } catch (_) {}
}

async function processPendingInviteCode() {
  if (!currentUser) return;
  const code = getPendingInviteCode();
  if (!code) return;
  const status = $("social-request-status");
  try {
    const data = await fetchJSON(API.socialInviteAccept, { method: "POST", body: JSON.stringify({ invite_code: code }) });
    if (status) status.textContent = data.message || "Friend added from invite link.";
    clearPendingInviteCode();
  } catch (err) {
    if (status) status.textContent = `Invite link error: ${err.message}`;
  }
}

async function copyMyInviteLink() {
  const status = $("social-request-status");
  if (!currentUser?.invite_code) {
    if (status) status.textContent = "No invite link available yet.";
    return;
  }
  const url = `${window.location.origin}/?invite=${encodeURIComponent(currentUser.invite_code)}`;
  try {
    await navigator.clipboard.writeText(url);
    if (status) status.textContent = "Invite link copied. Send it by text.";
  } catch (_) {
    if (status) status.textContent = url;
  }
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

function toYmd(dateObj) {
  const y = dateObj.getFullYear();
  const m = String(dateObj.getMonth() + 1).padStart(2, "0");
  const d = String(dateObj.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function toHm(dateObj) {
  const h = String(dateObj.getHours()).padStart(2, "0");
  const m = String(dateObj.getMinutes()).padStart(2, "0");
  return `${h}:${m}`;
}

function initializeTargetInputs() {
  const dateEl = $("target-date");
  const timeEl = $("target-time");
  if (!dateEl || !timeEl) return;

  const now = new Date();
  const storedDate = getStoredText(STORAGE_TARGET_DATE, "");
  const storedTime = getStoredText(STORAGE_TARGET_TIME, "");
  dateEl.value = storedDate || toYmd(now);
  timeEl.value = storedTime || "08:00";

  const onChange = () => {
    setStoredText(STORAGE_TARGET_DATE, dateEl.value || "");
    setStoredText(STORAGE_TARGET_TIME, timeEl.value || "");
    refreshState().catch(() => {});
  };

  dateEl.addEventListener("change", onChange);
  timeEl.addEventListener("change", onChange);

  $("btn-target-tonight")?.addEventListener("click", () => {
    const tonight = new Date();
    tonight.setHours(23, 0, 0, 0);
    dateEl.value = toYmd(tonight);
    timeEl.value = "23:00";
    onChange();
  });

  $("btn-target-tomorrow")?.addEventListener("click", () => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(8, 0, 0, 0);
    dateEl.value = toYmd(tomorrow);
    timeEl.value = "08:00";
    onChange();
  });
}

function getHoursUntilTargetFromInputs() {
  const dateVal = $("target-date")?.value || "";
  const timeVal = $("target-time")?.value || "";
  if (!dateVal || !timeVal) return null;
  const target = new Date(`${dateVal}T${timeVal}`);
  if (Number.isNaN(target.getTime())) return null;
  const now = new Date();
  return (target.getTime() - now.getTime()) / 36e5;
}

function updateTargetSummary() {
  const summary = $("target-summary");
  if (!summary) return;
  const hrs = getHoursUntilTargetFromInputs();
  if (hrs == null) {
    summary.textContent = "Set date and time to get planning advice.";
    return null;
  }
  if (hrs <= 0) {
    summary.textContent = "Target time is in the past. Pick a future time.";
    return null;
  }
  summary.textContent = `Target is in about ${formatHoursShort(hrs)}.`;
  return hrs;
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
  const pillEl = $("drive-pill");
  if (!statusEl || !msgEl || !actionEl) return;

  const advice = state.drive_advice;
  if (!advice) {
    statusEl.textContent = "No data yet";
    statusEl.className = "drive-status";
    msgEl.textContent = "Log drinks to see conservative guidance.";
    actionEl.textContent = "";
    if (pillEl) {
      pillEl.textContent = "No data";
      pillEl.className = "stat-value";
    }
    return;
  }

  statusEl.textContent = advice.title || "Drive guidance";
  statusEl.className = `drive-status ${advice.status || ""}`;
  msgEl.textContent = advice.message || "";
  actionEl.textContent = advice.action || "";
  if (pillEl) {
    if (advice.status === "do_not_drive") {
      pillEl.textContent = "Do not drive";
      pillEl.className = "stat-value risk-high";
    } else if (advice.status === "caution") {
      pillEl.textContent = "Use caution";
      pillEl.className = "stat-value risk-mid";
    } else {
      pillEl.textContent = "Lower risk";
      pillEl.className = "stat-value risk-low";
    }
  }
}

function updateRiskAlert(state) {
  const card = $("risk-alert");
  const msg = $("risk-alert-message");
  if (!card || !msg) return;
  const bac = Number(state?.bac_now || 0);
  if (!Number.isFinite(bac) || bac < 0.08) {
    card.style.display = "none";
    msg.textContent = "";
    return;
  }

  let text = "BAC is above 0.08. Do not drive. Hydrate and arrange a safe ride.";
  if (bac >= 0.12) {
    text = "High-risk BAC detected. Stay with trusted people, stop drinking, and consider emergency support now.";
  }
  if (bac >= 0.16) {
    text = "Critical BAC risk. Call emergency services now if symptoms worsen (vomiting, confusion, unresponsiveness).";
  }
  msg.textContent = text;
  card.style.display = "block";
}

function formatHoursShort(hours) {
  if (hours == null || !Number.isFinite(hours)) return "-";
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  if (h <= 0) return `${m}m`;
  return `${h}h ${m}m`;
}

function formatSoberAt(hoursFromNow) {
  if (hoursFromNow == null || !Number.isFinite(hoursFromNow)) return "-";
  const now = new Date();
  const at = new Date(now.getTime() + Math.max(0, hoursFromNow) * 36e5);
  const time = at.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const sameDay = now.toDateString() === at.toDateString();
  if (sameDay) return `Today ${time}`;
  const date = at.toLocaleDateString([], { month: "short", day: "numeric" });
  return `${date} ${time}`;
}

function renderSessionEvents(state) {
  const list = $("session-events-list");
  if (!list) return;
  const items = Array.isArray(state?.session_events) ? state.session_events : [];
  list.innerHTML = "";
  if (!items.length) {
    list.innerHTML = `<div class="friend-row"><div class="friend-counts">No drinks logged yet.</div></div>`;
    renderEventUndo();
    return;
  }
  items.forEach((ev) => {
    const row = document.createElement("div");
    row.className = "friend-row";
    row.innerHTML = `
      <div class="friend-main">Entry #${ev.index + 1}</div>
      <div class="friend-counts">~${Number(ev.standard_drinks || 0).toFixed(2)} drinks, ${Number(ev.hours_ago || 0).toFixed(2)}h ago</div>
      <div class="friend-add">
        <input type="number" min="0" max="24" step="0.25" class="session-event-hours" data-index="${ev.index}" value="${Number(ev.hours_ago || 0).toFixed(2)}" aria-label="Hours ago">
        <input type="number" min="0.25" max="20" step="0.25" class="session-event-count" data-index="${ev.index}" value="${Number(ev.standard_drinks || 1).toFixed(2)}" aria-label="Standard drinks">
      </div>
      <div class="friend-actions">
        <button type="button" class="chip session-event-save" data-index="${ev.index}">Save</button>
        <button type="button" class="chip danger session-event-delete" data-index="${ev.index}">Delete</button>
      </div>
    `;
    list.appendChild(row);
  });
  renderEventUndo();
}

function renderEventUndo() {
  const el = $("events-undo");
  if (!el) return;
  if (!lastDeletedSessionEvent || Date.now() > lastDeletedSessionEvent.expiresAt) {
    lastDeletedSessionEvent = null;
    el.innerHTML = "";
    return;
  }
  el.innerHTML = `Removed a drink entry. <button type="button" class="chip" id="btn-undo-event-delete">Undo</button>`;
}

async function saveSessionEvent(index) {
  const hoursEl = document.querySelector(`.session-event-hours[data-index="${index}"]`);
  const countEl = document.querySelector(`.session-event-count[data-index="${index}"]`);
  const hours_ago = parseFloat(hoursEl?.value || "");
  const standard_drinks = parseFloat(countEl?.value || "");
  if (!Number.isFinite(hours_ago) || !Number.isFinite(standard_drinks)) return;
  await fetchJSON(API.sessionEvents, {
    method: "PATCH",
    body: JSON.stringify({ index: Number(index), hours_ago, standard_drinks }),
  });
  await refreshState();
}

async function deleteSessionEvent(index) {
  const data = await fetchJSON(API.sessionEvents, {
    method: "PATCH",
    body: JSON.stringify({ index: Number(index), delete: true }),
  });
  if (data?.deleted_event) {
    lastDeletedSessionEvent = {
      event: data.deleted_event,
      index: data.deleted_index,
      expiresAt: Date.now() + 120000,
    };
  }
  renderEventUndo();
  window.setTimeout(() => renderEventUndo(), 121000);
  await refreshState();
}

async function undoDeleteSessionEvent() {
  if (!lastDeletedSessionEvent?.event) return;
  const payload = {
    index: Number(lastDeletedSessionEvent.index ?? 0),
    restore_event: {
      hours_ago: lastDeletedSessionEvent.event.hours_ago,
      standard_drinks: lastDeletedSessionEvent.event.standard_drinks,
      calories: lastDeletedSessionEvent.event.calories,
      carbs_g: lastDeletedSessionEvent.event.carbs_g,
      sugar_g: lastDeletedSessionEvent.event.sugar_g,
    },
  };
  await fetchJSON(API.sessionEvents, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  lastDeletedSessionEvent = null;
  renderEventUndo();
  await refreshState();
}

async function loadCampusPresets() {
  try {
    const data = await fetchJSON(API.campusPresets);
    campusPresets = data.items || [];
  } catch (_) {
    campusPresets = [];
  }
  const sel = $("campus-preset");
  if (!sel) return;
  sel.innerHTML = campusPresets
    .map((c) => `<option value="${c.id}">${c.name}</option>`)
    .join("");
}

function getSelectedCampus() {
  const sel = $("campus-preset");
  const id = sel?.value;
  return campusPresets.find((c) => c.id === id) || campusPresets[0] || null;
}

function setSosStatus(text) {
  const el = $("sos-status");
  if (el) el.textContent = text || "";
}

function getActiveGroupName() {
  const active = socialGroups.find((g) => String(g.id) === String(activeGroupId));
  return active?.name || "my group";
}

async function runSosAction(kind) {
  const campus = getSelectedCampus();
  if (!campus) {
    setSosStatus("Campus settings unavailable.");
    return;
  }

  if (kind === "ride") {
    if (campus.safe_ride_url) {
      window.open(campus.safe_ride_url, "_blank", "noopener");
      setSosStatus(`Opened ${campus.safe_ride_label}.`);
      return;
    }
    if (campus.non_emergency_phone) {
      window.location.href = `tel:${campus.non_emergency_phone}`;
      setSosStatus(`Calling ${campus.non_emergency_phone}...`);
      return;
    }
    setSosStatus("No campus ride contact configured.");
    return;
  }

  if (kind === "emergency") {
    const sure = window.confirm("Call 911 now?");
    if (!sure) {
      setSosStatus("911 call canceled.");
      return;
    }
    const finalSure = window.confirm("Final confirm: place emergency call to 911?");
    if (!finalSure) {
      setSosStatus("911 call canceled.");
      return;
    }
    window.location.href = "tel:911";
    setSosStatus("Calling emergency services...");
    return;
  }

  if (kind === "friend") {
    if (emergencyContacts.length) {
      const primary = emergencyContacts[0];
      window.location.href = `tel:${primary.phone}`;
      setSosStatus(`Calling ${primary.name}...`);
      return;
    }
    const firstFriend = (socialState.friends || [])[0];
    if (firstFriend?.email) {
      window.location.href = `mailto:${firstFriend.email}?subject=Safety check`;
      setSosStatus(`Opening message to ${firstFriend.display_name}.`);
      return;
    }
    setSosStatus("Add a friend first to use quick contact.");
    return;
  }

  if (kind === "location") {
    const groupName = getActiveGroupName();
    const bac = latestState?.bac_now != null ? Number(latestState.bac_now).toFixed(3) : "n/a";
    const text = `Safety update: BAC ${bac}. Group: ${groupName}.`;
    try {
      if (navigator.share) {
        await navigator.share({ title: "Safety update", text, url: window.location.href });
        setSosStatus("Safety update shared.");
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(`${text} ${window.location.href}`);
        setSosStatus("Safety update copied to clipboard.");
      } else {
        setSosStatus("Sharing not supported on this device.");
      }
    } catch (_) {
      setSosStatus("Sharing canceled.");
    }
    return;
  }

  if (kind === "campus") {
    if (campus.non_emergency_phone) {
      window.location.href = `tel:${campus.non_emergency_phone}`;
      setSosStatus(`Calling campus help at ${campus.non_emergency_phone}...`);
      return;
    }
    window.location.href = `tel:${campus.emergency_phone || "911"}`;
    setSosStatus("Calling emergency services...");
  }
}

async function revokeAllPrivacy() {
  await fetchJSON(API.socialPrivacyRevokeAll, { method: "POST" });
  const status = $("privacy-status");
  if (status) status.textContent = "All sharing and guardian links revoked.";
  await loadSocial();
  await loadAccountPrivacySummary();
}

async function loadSessionDebrief() {
  const box = $("debrief-content");
  if (!box) return;
  box.textContent = "Loading debrief...";
  try {
    const data = await fetchJSON(API.sessionDebrief);
    const suggestions = (data.suggestions || []).map((s) => `- ${s}`).join("\n");
    box.textContent = [
      `Peak BAC: ${Number(data.peak_bac || 0).toFixed(3)}`,
      `Minutes >= 0.08: ${data.minutes_over_legal_limit || 0}`,
      `Drinks: ${data.drink_count || 0}`,
      `Sober in: ${formatHoursShort(data.hours_until_sober_now || 0)}`,
      "",
      "Suggestions:",
      suggestions || "- Keep safe pacing and transportation planning.",
    ].join("\n");
  } catch (err) {
    box.textContent = err.message || "Debrief unavailable.";
  }
}

function updateOnboardingStatus() {
  const el = $("onboarding-status");
  if (!el) return;
  if (!currentUser) {
    el.textContent = "1) Create account 2) Create or join a group 3) Enable sharing when ready.";
    return;
  }
  const hasGroup = socialGroups.length > 0;
  const hasFriends = (socialState.friends || []).length > 0;
  const hasGuardian = guardianLinks.length > 0;
  const steps = [
    hasGroup ? "Group set up" : "Create or join a safety group",
    hasFriends ? "Friend network ready" : "Add at least one friend",
    hasGuardian ? "Guardian link ready" : "Create one guardian link",
  ];
  el.textContent = steps.join(" | ");
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

  const hints = $("chart-timeline-hints");
  const paceEl = $("chart-pace-metric");
  const pace = state?.chart_data?.pace_drinks_per_hour;
  if (paceEl) paceEl.textContent = `Pace: ${Number(pace || 0).toFixed(2)} drinks/hr (last 3h)`;
  const eta = state?.chart_data?.eta || {};
  if (hints) {
    const legal = eta.below_legal_hours == null ? "Below 0.08: now/already low" : `Below 0.08 in ~${formatHoursShort(eta.below_legal_hours)}`;
    const sober = eta.sober_hours == null ? "Sober ETA unavailable" : `Sober at ~${formatSoberAt(eta.sober_hours)}`;
    hints.textContent = `${legal} | ${sober}`;
  }
}

function updatePacePrediction(state) {
  const el = $("pace-prediction");
  if (!el) return;
  const p = state.pace_prediction;
  if (!p) {
    el.textContent = "Log drinks to get predictive pacing advice.";
    return;
  }
  el.textContent = `If you have one more drink now, estimated BAC in 30m: ${Number(p.bac_in_30m_if_one_more_now || 0).toFixed(3)}. ${p.recommendation || ""}`;
}

function getChartCurveByMode(state) {
  const base = Array.isArray(state?.curve) ? state.curve : [];
  if (!base.length) return [];
  if (chartMode === "last6") return base.filter((p) => (p.t ?? 999) >= -6);
  if (chartMode === "untilSober") {
    let cutoff = state?.hours_until_sober_from_now ?? 24;
    cutoff = Math.max(0, Math.min(48, cutoff));
    return base.filter((p) => (p.t ?? -999) <= cutoff);
  }
  return base;
}

function bandLabel(bac) {
  if (bac >= 0.1) return "Very high";
  if (bac >= 0.08) return "Over legal limit";
  if (bac >= 0.05) return "Elevated";
  if (bac >= 0.02) return "Low";
  return "Minimal";
}

function renderChart(state) {
  const curve = getChartCurveByMode(state);
  if (!curve.length) {
    if (bacChart) {
      bacChart.data.datasets = [];
      bacChart.update("none");
    }
    return;
  }
  const basePoints = curve.map((d) => ({ x: d.t, y: d.bac }));
  const pacePoints = (state.chart_data?.pace_curve || []).map((p) => ({ x: p.t, y: p.bac }));
  const markers = (state.chart_data?.event_markers || []).map((p) => ({ x: p.t, y: p.bac }));
  const xMin = Math.min(...basePoints.map((p) => p.x), -6);
  const xMax = Math.max(
    ...basePoints.map((p) => p.x),
    ...(pacePoints.length ? pacePoints.map((p) => p.x) : [0]),
    12
  );

  const datasets = [
    {
      label: "Current BAC",
      data: basePoints,
      borderColor: "#38bdf8",
      backgroundColor: "rgba(56, 189, 248, 0.08)",
      pointRadius: 0,
      fill: true,
      tension: 0.2,
      borderWidth: 2.2,
    },
    {
      label: "0.08 legal limit",
      data: [{ x: xMin, y: 0.08 }, { x: xMax, y: 0.08 }],
      borderColor: "#ef4444",
      borderDash: [6, 4],
      pointRadius: 0,
      fill: false,
      tension: 0,
      borderWidth: 2,
    },
    {
      type: "scatter",
      label: "Drink events",
      data: markers,
      backgroundColor: "rgba(147,197,253,0.8)",
      borderColor: "rgba(15,23,42,0.6)",
      pointRadius: 3,
      pointHoverRadius: 4,
    },
  ];

  if (chartPaceEnabled && pacePoints.length) {
    datasets.push({
      label: "Pace projection",
      data: pacePoints,
      borderColor: "rgba(251,191,36,0.95)",
      borderDash: [5, 4],
      pointRadius: 0,
      fill: false,
      tension: 0.2,
      borderWidth: 1.8,
    });
  }
  datasets.push({
    label: "Now marker",
    data: [{ x: 0, y: 0 }, { x: 0, y: 0.22 }],
    borderColor: "rgba(255,255,255,0.55)",
    borderDash: [2, 4],
    pointRadius: 0,
    fill: false,
    tension: 0,
    borderWidth: 1.2,
  });

  const ctx = document.getElementById("bac-chart")?.getContext("2d");
  if (!ctx) return;
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    parsing: false,
    scales: {
      x: {
        type: "linear",
        min: xMin,
        max: xMax,
        title: { display: true, text: "Hours (0 = now)" },
        grid: { color: "rgba(255,255,255,0.06)" },
        ticks: { color: "#94a3b8" },
      },
      y: {
        min: 0,
        max: 0.18,
        title: { display: true, text: "BAC (%)" },
        grid: { color: "rgba(255,255,255,0.06)" },
        ticks: { color: "#94a3b8" },
      },
    },
    plugins: {
      legend: { labels: { color: "#f1f5f9" } },
      tooltip: {
        callbacks: {
          label: (ctxTip) => {
            const y = Number(ctxTip.parsed.y || 0);
            const x = Number(ctxTip.parsed.x || 0);
            const advice = y >= 0.08 ? "Do not drive" : y >= 0.05 ? "Caution" : "Lower risk";
            return `${ctxTip.dataset.label}: BAC ${y.toFixed(3)} at ${x.toFixed(2)}h | ${bandLabel(y)} | ${advice}`;
          },
        },
      },
    },
  };

  if (bacChart) {
    bacChart.data.datasets = datasets;
    bacChart.options = options;
    bacChart.update("none");
  } else {
    bacChart = new Chart(ctx, { type: "line", data: { datasets }, options });
  }
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
  renderHistorySummary(filtered);

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

function renderHistorySummary(items) {
  const totalEl = $("hist-total-sessions");
  const avgEl = $("hist-avg-drinks");
  const maxEl = $("hist-max-drinks");
  if (!totalEl || !avgEl || !maxEl) return;
  const total = Array.isArray(items) ? items.length : 0;
  if (!total) {
    totalEl.textContent = "0";
    avgEl.textContent = "0.0";
    maxEl.textContent = "0";
    return;
  }
  const drinks = items.map((x) => Number(x.drink_count || 0));
  const sum = drinks.reduce((a, b) => a + b, 0);
  const avg = sum / total;
  const max = Math.max(...drinks);
  totalEl.textContent = String(total);
  avgEl.textContent = avg.toFixed(1);
  maxEl.textContent = String(max);
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
    switchTab("current");
  } catch (err) {
    setSessionStatus(`Load failed: ${err.message}`);
  }
}

function exportSavedSessionsCsv() {
  const input = $("session-date");
  const params = new URLSearchParams();
  const selectedDate = input?.value?.trim();
  if (selectedDate) params.set("date", selectedDate);
  const query = params.toString();
  window.location.href = query ? `${API.sessionExport}?${query}` : API.sessionExport;
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
  const lastId = getLastDrink();

  catalogById = {};
  (flat || []).forEach((d) => (catalogById[d.id] = d));
  catalogByCategory = by_category || {};
  renderCatalogOptions(lastId);
  refreshQuickAdd();
}

function normalizeSearchText(text) {
  return String(text || "").trim().toLowerCase();
}

function renderCatalogOptions(preferredId = null) {
  const sel = $("drink-catalog");
  if (!sel) return;
  const q = normalizeSearchText($("drink-search")?.value || "");
  const order = ["beer", "seltzer", "wine", "liquor", "cocktail", "other"];
  sel.innerHTML = "";
  let optionCount = 0;
  let preferredFound = false;
  let firstOption = null;

  for (const cat of order) {
    if (selectedDrinkCategory !== "all" && selectedDrinkCategory !== cat) continue;
    const items = Array.isArray(catalogByCategory[cat]) ? catalogByCategory[cat] : [];
    const matches = items.filter((d) => {
      if (!q) return true;
      const row = `${d.name || ""} ${d.brand || ""} ${cat}`.toLowerCase();
      return row.includes(q);
    });
    if (!matches.length) continue;

    const optgroup = document.createElement("optgroup");
    optgroup.label = cat.charAt(0).toUpperCase() + cat.slice(1);
    matches.sort((a, b) => String(a.name).localeCompare(String(b.name)));
    for (const d of matches) {
      const opt = document.createElement("option");
      opt.value = d.id;
      const brand = d.brand ? ` - ${d.brand}` : "";
      opt.textContent = `${d.name}${brand}`;
      optgroup.appendChild(opt);
      optionCount += 1;
      if (!firstOption) firstOption = opt;
      if (preferredId && d.id === preferredId) {
        opt.selected = true;
        preferredFound = true;
      }
    }
    sel.appendChild(optgroup);
  }

  if (!optionCount) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "No drinks found. Try a different search.";
    opt.disabled = true;
    opt.selected = true;
    sel.appendChild(opt);
    return;
  }
  if (!preferredFound && firstOption) firstOption.selected = true;
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
  const hoursTarget = updateTargetSummary();
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
  latestState = state;

  if (!state.configured) {
    if (!attemptedAutoSetup && currentUser?.default_weight_lb && typeof currentUser?.is_male === "boolean") {
      attemptedAutoSetup = true;
      try {
        await fetchJSON(API.setup, {
          method: "POST",
          body: JSON.stringify({
            weight_lb: currentUser.default_weight_lb,
            is_male: currentUser.is_male,
          }),
        });
        await refreshState();
        return;
      } catch (_) {
        // Fall back to manual setup UI if account defaults cannot be applied.
      }
    }
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
  if (soberEl) soberEl.textContent = state.configured ? formatSoberAt(state.hours_until_sober_from_now) : "-";

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
  updateRiskAlert(state);
  updateChartInsights(state);
  updatePacePrediction(state);
  renderSessionEvents(state);

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
    renderChart(state);
  } else if (bacChart) {
    bacChart.data.datasets = [];
    bacChart.update("none");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {});
  }

  await loadCatalog();
  pullInviteCodeFromUrl();
  initTabs();
  initializeTargetInputs();
  loadFriends();
  renderFriends();
  setupShareButton();
  await loadCampusPresets();
  await refreshAuth();

  $("btn-logout")?.addEventListener("click", async () => {
    try {
      await authLogout();
    } catch (err) {
      setAuthStatus(`Logout failed: ${err.message}`);
    }
  });
  $("btn-acct-save")?.addEventListener("click", async () => {
    await saveAccountProfile();
  });
  $("btn-acct-share-toggle")?.addEventListener("click", async () => {
    try {
      await toggleAccountSharePreference();
    } catch (err) {
      const s = $("acct-share-status");
      if (s) s.textContent = err.message;
    }
  });
  $("btn-emergency-add")?.addEventListener("click", async () => {
    await addEmergencyContactFromForm();
  });
  $("btn-account-delete")?.addEventListener("click", async () => {
    await deleteAccountFlow();
  });
  $("emergency-list")?.addEventListener("click", async (e) => {
    const callBtn = e.target.closest(".emergency-call");
    if (callBtn) {
      const phone = callBtn.dataset.phone;
      if (phone) window.location.href = `tel:${phone}`;
      return;
    }
    const delBtn = e.target.closest(".emergency-delete");
    if (!delBtn) return;
    const ok = window.confirm("Remove this emergency contact?");
    if (!ok) return;
    await deleteEmergencyContact(delBtn.dataset.id);
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
  $("drink-search")?.addEventListener("input", () => {
    renderCatalogOptions($("drink-catalog")?.value || getLastDrink());
  });
  $("drink-filter-chips")?.addEventListener("click", (e) => {
    const btn = e.target.closest(".drink-filter");
    if (!btn) return;
    selectedDrinkCategory = btn.dataset.category || "all";
    document.querySelectorAll(".drink-filter").forEach((x) => x.classList.remove("active"));
    btn.classList.add("active");
    renderCatalogOptions($("drink-catalog")?.value || getLastDrink());
  });

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
  $("btn-session-export")?.addEventListener("click", exportSavedSessionsCsv);
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

  $("btn-group-share-toggle")?.addEventListener("click", async () => {
    try {
      await toggleSocialShare();
    } catch (err) {
      const s = $("social-request-status");
      if (s) s.textContent = err.message;
    }
  });
  $("btn-social-create-group")?.addEventListener("click", async () => {
    try {
      await createSocialGroup();
    } catch (err) {
      const s = $("social-request-status");
      if (s) s.textContent = err.message;
    }
  });
  $("btn-social-join-group")?.addEventListener("click", async () => {
    try {
      await joinSocialGroup();
    } catch (err) {
      const s = $("social-request-status");
      if (s) s.textContent = err.message;
    }
  });
  $("btn-social-location")?.addEventListener("click", async () => {
    try {
      await updateGroupLocation();
    } catch (err) {
      const s = $("social-request-status");
      if (s) s.textContent = err.message;
    }
  });
  $("btn-social-add-friend")?.addEventListener("click", async () => {
    await sendSocialFriendRequest();
  });
  $("btn-social-lookup-user")?.addEventListener("click", async () => {
    await lookupSocialUser();
  });
  $("btn-copy-invite-link")?.addEventListener("click", async () => {
    await copyMyInviteLink();
  });
  $("btn-privacy-revoke-all")?.addEventListener("click", async () => {
    try {
      const ok = window.confirm("Revoke all sharing and guardian links now?");
      if (!ok) return;
      await revokeAllPrivacy();
    } catch (err) {
      const s = $("privacy-status");
      if (s) s.textContent = err.message;
    }
  });
  $("btn-sos-ride")?.addEventListener("click", () => runSosAction("ride"));
  $("btn-sos-911")?.addEventListener("click", () => runSosAction("emergency"));
  $("btn-sos-call-friend")?.addEventListener("click", () => runSosAction("friend"));
  $("btn-sos-share-location")?.addEventListener("click", () => runSosAction("location"));
  $("btn-sos-campus-help")?.addEventListener("click", () => runSosAction("campus"));
  $("btn-drive-ride")?.addEventListener("click", () => runSosAction("ride"));
  $("btn-drive-911")?.addEventListener("click", () => runSosAction("emergency"));
  $("btn-drive-share")?.addEventListener("click", () => runSosAction("location"));
  $("btn-emergency-911")?.addEventListener("click", () => runSosAction("emergency"));
  $("btn-risk-ride")?.addEventListener("click", () => runSosAction("ride"));
  $("btn-session-debrief")?.addEventListener("click", async () => {
    await loadSessionDebrief();
  });
  $("social-requests-list")?.addEventListener("click", async (e) => {
    const target = e.target.closest(".social-respond");
    if (!target) return;
    try {
      await respondSocialRequest(target.dataset.requestId, target.dataset.action);
    } catch (err) {
      const s = $("social-request-status");
      if (s) s.textContent = err.message;
    }
  });
  $("social-group-list")?.addEventListener("click", async (e) => {
    const target = e.target.closest(".social-group-select");
    if (!target) return;
    try {
      await loadGroupSnapshot(target.dataset.groupId);
    } catch (err) {
      const s = $("social-request-status");
      if (s) s.textContent = err.message;
    }
  });
  $("social-members-list")?.addEventListener("click", async (e) => {
    const target = e.target.closest(".social-check");
    if (!target) return;
    try {
      await sendGroupCheck(target.dataset.targetUserId, target.dataset.kind);
    } catch (err) {
      const s = $("social-request-status");
      if (s) s.textContent = err.message;
    }
  });
  $("btn-social-create-guardian")?.addEventListener("click", async () => {
    try {
      await createGuardianLink();
    } catch (err) {
      const s = $("social-request-status");
      if (s) s.textContent = err.message;
    }
  });
  $("social-guardian-list")?.addEventListener("click", async (e) => {
    const copy = e.target.closest(".guardian-copy");
    if (copy) {
      try {
        await navigator.clipboard.writeText(copy.dataset.url || "");
      } catch (_) {}
      return;
    }
    const alerts = e.target.closest(".guardian-alerts");
    if (alerts) {
      try {
        const enabled = alerts.dataset.enabled !== "1";
        await setGuardianAlerts(alerts.dataset.linkId, enabled);
      } catch (err) {
        const s = $("social-request-status");
        if (s) s.textContent = err.message;
      }
      return;
    }
    const revoke = e.target.closest(".guardian-revoke");
    if (revoke) {
      try {
        await revokeGuardian(revoke.dataset.linkId);
      } catch (err) {
        const s = $("social-request-status");
        if (s) s.textContent = err.message;
      }
    }
  });
  $("btn-social-toggle-alerts")?.addEventListener("click", () => {
    showAllSocialAlerts = !showAllSocialAlerts;
    renderGroupSnapshot();
  });
  document.querySelectorAll(".chart-mode").forEach((btn) => {
    btn.addEventListener("click", async () => {
      document.querySelectorAll(".chart-mode").forEach((x) => x.classList.remove("active"));
      btn.classList.add("active");
      chartMode = btn.dataset.mode || "full";
      if (latestState) renderChart(latestState);
    });
  });
  $("btn-chart-pace")?.addEventListener("click", () => {
    chartPaceEnabled = !chartPaceEnabled;
    $("btn-chart-pace").classList.toggle("active", chartPaceEnabled);
    $("btn-chart-pace").textContent = chartPaceEnabled ? "Hide pace projection" : "Show pace projection";
    if (latestState) renderChart(latestState);
  });
  $("session-events-list")?.addEventListener("click", async (e) => {
    const saveBtn = e.target.closest(".session-event-save");
    if (saveBtn) {
      try {
        await saveSessionEvent(saveBtn.dataset.index);
      } catch (err) {
        setSessionStatus(`Update failed: ${err.message}`);
      }
      return;
    }
    const delBtn = e.target.closest(".session-event-delete");
    if (delBtn) {
      const ok = window.confirm("Delete this drink entry?");
      if (!ok) return;
      try {
        await deleteSessionEvent(delBtn.dataset.index);
      } catch (err) {
        setSessionStatus(`Delete failed: ${err.message}`);
      }
    }
  });
  $("events-undo")?.addEventListener("click", async (e) => {
    const btn = e.target.closest("#btn-undo-event-delete");
    if (!btn) return;
    try {
      await undoDeleteSessionEvent();
      setSessionStatus("Drink entry restored.");
    } catch (err) {
      setSessionStatus(`Undo failed: ${err.message}`);
    }
  });

  // Keep current session state fresh so auto-save and expiry rules run even when user is idle.
  window.setInterval(() => {
    if (!currentUser) return;
    refreshState().catch(() => {});
  }, 60 * 1000);
});

const API = {
  authMe: "/api/auth/me",
  authRegister: "/api/auth/register",
  authLogin: "/api/auth/login",
};

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

function setStatus(text) {
  const el = $("login-status");
  if (el) el.textContent = text || "";
}

function setAuthMode(mode) {
  const isRegister = mode === "register";
  $("auth-login-view").style.display = isRegister ? "none" : "block";
  $("auth-register-view").style.display = isRegister ? "block" : "none";
  $("btn-mode-login").classList.toggle("active", !isRegister);
  $("btn-mode-register").classList.toggle("active", isRegister);
  setStatus(isRegister ? "Create an account to start tracking." : "Log in to your existing account.");
}

function redirectToApp() {
  const invite = String(window.__INVITE__ || "").trim();
  if (invite) {
    window.location.href = `/?invite=${encodeURIComponent(invite)}&tab=current`;
    return;
  }
  window.location.href = "/?tab=current";
}

async function login() {
  const email = $("auth-login-email")?.value?.trim() || "";
  const password = $("auth-login-password")?.value?.trim() || "";
  await fetchJSON(API.authLogin, { method: "POST", body: JSON.stringify({ email, password }) });
  redirectToApp();
}

async function register() {
  const payload = {
    display_name: $("auth-register-name")?.value?.trim() || "",
    username: $("auth-register-username")?.value?.trim().toLowerCase() || "",
    email: $("auth-register-email")?.value?.trim() || "",
    password: $("auth-register-password")?.value?.trim() || "",
    confirm_password: $("auth-register-password-confirm")?.value?.trim() || "",
    gender: $("auth-register-gender")?.value || "",
    default_weight_lb: $("auth-register-weight")?.value || "",
  };
  if (payload.password !== payload.confirm_password) {
    setStatus("Passwords do not match.");
    return;
  }
  await fetchJSON(API.authRegister, { method: "POST", body: JSON.stringify(payload) });
  redirectToApp();
}

document.addEventListener("DOMContentLoaded", async () => {
  setAuthMode("login");
  try {
    const me = await fetchJSON(API.authMe);
    if (me.authenticated) {
      redirectToApp();
      return;
    }
  } catch (_) {}

  $("btn-mode-login")?.addEventListener("click", () => setAuthMode("login"));
  $("btn-mode-register")?.addEventListener("click", () => setAuthMode("register"));
  $("btn-login")?.addEventListener("click", async () => {
    try {
      await login();
    } catch (err) {
      setStatus(err.message);
    }
  });
  $("btn-register")?.addEventListener("click", async () => {
    try {
      await register();
    } catch (err) {
      setStatus(err.message);
    }
  });
  $("auth-login-password")?.addEventListener("keydown", async (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    try {
      await login();
    } catch (err) {
      setStatus(err.message);
    }
  });
});

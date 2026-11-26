import { apiRequest } from "./api.js";

const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const joinForm = document.getElementById("quick-join-form");
const statusEl = document.getElementById("auth-status");

if (joinForm) {
  joinForm.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const code = document.getElementById("join-code-input").value.trim().toUpperCase();
    if (code) {
      window.location.href = `/play/${encodeURIComponent(code)}`;
    }
  });
}

if (loginForm) {
  loginForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    const totpCode = document.getElementById("login-totp").value.trim() || null;
    try {
      await apiRequest("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password, totp_code: totpCode }),
      });
      window.location.href = "/dashboard";
    } catch (err) {
      statusEl.textContent = err.message;
    }
  });
}

if (registerForm) {
  registerForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      await apiRequest("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email: document.getElementById("reg-email").value.trim(),
          password: document.getElementById("reg-password").value,
          display_name: document.getElementById("reg-name").value.trim(),
          locale: "ru",
          consent_privacy: document.getElementById("consent-privacy").checked,
          consent_terms: document.getElementById("consent-terms").checked,
          consent_disclaimer: document.getElementById("consent-disclaimer").checked,
          consent_version: "1.0",
        }),
      });
      window.location.href = "/dashboard";
    } catch (err) {
      statusEl.textContent = err.message;
    }
  });
}

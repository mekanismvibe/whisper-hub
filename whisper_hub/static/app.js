/* Whisper Hub dashboard — vanilla JS, no build step. */
(() => {
  "use strict";

  /* ---------------------------------------------------------------- icons */

  const SVG = (inner) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;

  const ICONS = {
    mic: SVG('<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><path d="M12 19v3"/>'),
    stop: SVG('<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/>'),
    search: SVG('<circle cx="11" cy="11" r="7.5"/><path d="m21 21-4.3-4.3"/>'),
    copy: SVG('<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'),
    check: SVG('<path d="M20 6 9 17l-5-5"/>'),
    x: SVG('<path d="M18 6 6 18"/><path d="m6 6 12 12"/>'),
    plus: SVG('<path d="M12 5v14"/><path d="M5 12h14"/>'),
    chevron: SVG('<path d="m9 18 6-6-6-6"/>'),
    phone: SVG('<rect x="6" y="2" width="12" height="20" rx="2.5"/><path d="M11 18h2"/>'),
    tablet: SVG('<rect x="4" y="2" width="16" height="20" rx="2.5"/><path d="M11 18h2"/>'),
    portable: SVG('<path d="M4 16V5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v11"/><path d="M2 16h20"/><path d="M2 16v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2"/>'),
    monitor: SVG('<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>'),
    globe: SVG('<circle cx="12" cy="12" r="9.5"/><path d="M2.5 12h19"/><path d="M12 2.5a15 15 0 0 1 4 9.5 15 15 0 0 1-4 9.5 15 15 0 0 1-4-9.5 15 15 0 0 1 4-9.5Z"/>'),
    terminal: SVG('<polyline points="4 17 10 11 4 5"/><path d="M12 19h8"/>'),
    key: SVG('<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/>'),
    qr: SVG('<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3h-3z"/><path d="M21 14v3"/><path d="M14 21h7"/>'),
    edit: SVG('<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>'),
    trash: SVG('<path d="M3 6h18"/><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M10 11v6"/><path d="M14 11v6"/>'),
    refresh: SVG('<path d="M3 12a9 9 0 0 1 15.3-6.4L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15.3 6.4L3 16"/><path d="M3 21v-5h5"/>'),
    sun: SVG('<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.9 4.9 1.4 1.4"/><path d="m17.7 17.7 1.4 1.4"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m4.9 19.1 1.4-1.4"/><path d="m17.7 6.3 1.4-1.4"/>'),
    moon: SVG('<path d="M21 12.8A8.5 8.5 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/>'),
    auto: SVG('<rect x="2" y="4" width="20" height="14" rx="2"/><path d="M8 22h8"/><path d="M12 18v4"/>'),
    logout: SVG('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><path d="M21 12H9"/>'),
    devices: SVG('<rect x="2" y="4" width="14" height="11" rx="2"/><path d="M6 20h6"/><rect x="17" y="9" width="5" height="11" rx="1.5"/>'),
    shield: SVG('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>'),
    clock: SVG('<circle cx="12" cy="12" r="9.5"/><polyline points="12 7 12 12 15 14"/>'),
    sparkles: SVG('<path d="m12 3 2.1 5.9L20 11l-5.9 2.1L12 19l-2.1-5.9L4 11l5.9-2.1Z"/><path d="M19 3v4"/><path d="M21 5h-4"/>'),
    upload: SVG('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><path d="M12 3v12"/>'),
    alert: SVG('<circle cx="12" cy="12" r="9.5"/><path d="M12 7.5v5"/><path d="M12 16.5h.01"/>'),
    lock: SVG('<rect x="3" y="10" width="18" height="11" rx="2"/><path d="M7 10V7a5 5 0 0 1 10 0v3"/>'),
    arrow: SVG('<path d="M7 17 17 7"/><path d="M7 7h10v10"/>'),
    history: SVG('<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/>'),
    inbox: SVG('<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5h13l3.5 7v5a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-5Z"/>'),
    wifi: SVG('<path d="M5 12.5a10 10 0 0 1 14 0"/><path d="M8.5 16a5 5 0 0 1 7 0"/><path d="M12 19.5h.01"/>'),
    headphones: SVG('<path d="M3 14v-2a9 9 0 0 1 18 0v2"/><rect x="2" y="14" width="5" height="7" rx="2"/><rect x="17" y="14" width="5" height="7" rx="2"/>'),
  };

  function icon(name, extraClass = "") {
    const span = document.createElement("span");
    span.className = "icon" + (extraClass ? " " + extraClass : "");
    span.innerHTML = ICONS[name] || ICONS.sparkles;
    return span;
  }

  function hydrateIcons(root = document) {
    root.querySelectorAll("[data-icon]").forEach((node) => {
      node.innerHTML = ICONS[node.dataset.icon] || "";
    });
  }

  const DEVICE_ICONS = {
    iphone: "phone",
    ipad: "tablet",
    mac: "portable",
    windows: "monitor",
    linux: "terminal",
    android: "phone",
    web: "globe",
    other: "devices",
  };

  const KIND_LABELS = {
    iphone: "iPhone",
    ipad: "iPad",
    mac: "Mac",
    windows: "Windows",
    linux: "Linux",
    android: "Android",
    web: "Web browser",
    other: "Other device",
  };

  /* ---------------------------------------------------------------- dom helpers */

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  function append(parent, ...children) {
    for (const child of children.flat(Infinity)) {
      if (child === null || child === undefined || child === false) continue;
      parent.append(child.nodeType ? child : document.createTextNode(String(child)));
    }
    return parent;
  }

  function h(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key === "html") node.innerHTML = value; // trusted: static icons / server QR SVG
      else if (key === "dataset") Object.assign(node.dataset, value);
      else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
      else if (value === true) node.setAttribute(key, "");
      else node.setAttribute(key, value);
    }
    append(node, ...children);
    return node;
  }

  function replace(parent, ...children) {
    parent.replaceChildren();
    append(parent, ...children);
  }

  const state = {
    authenticated: false,
    view: "overview",
    devices: [],
    stats: null,
    setup: null,
    recent: [],
    recentFilter: "all",
    history: { items: [], cursor: null, q: "", deviceId: "", loading: false, loaded: false, seq: 0, rendered: 0 },
    pair: null,
    record: null,
    refreshTimer: null,
    pairTimer: null,
    searchTimer: null,
    modalCleanup: null,
    lastFocus: null,
    settings: null,
    modelStatus: null,
    modelTimer: null,
    wizard: null,
  };

  /* ---------------------------------------------------------------- api / toast / copy */

  async function api(path, { method = "GET", body, form } = {}) {
    const options = { method, credentials: "same-origin", headers: { Accept: "application/json" } };
    if (form) options.body = form;
    else if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    let response;
    try {
      response = await fetch(path, options);
    } catch (error) {
      throw new Error("Network error. Is the server still running?");
    }
    const type = response.headers.get("content-type") || "";
    let payload = null;
    if (type.includes("application/json")) {
      payload = await response.json().catch(() => null);
    } else {
      payload = await response.text();
    }
    if (!response.ok) {
      if (response.status === 401 && state.authenticated) {
        showLogin("Your session expired. Sign in again.");
      }
      const message =
        (payload && payload.error && payload.error.message) ||
        (typeof payload === "string" && payload) ||
        `Request failed (${response.status}).`;
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  function toast(message, tone = "success") {
    const region = $("#toast-region");
    const node = h(
      "div",
      { class: `toast ${tone}`, role: "status" },
      icon(tone === "error" ? "alert" : "check"),
      h("span", { text: message })
    );
    region.append(node);
    setTimeout(() => {
      node.classList.add("leaving");
      setTimeout(() => node.remove(), 220);
    }, 2800);
  }

  async function copyText(text, message = "Copied") {
    if (window.isSecureContext && navigator.clipboard && navigator.clipboard.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        toast(message);
        return;
      } catch (error) {
        /* fall through to the legacy path */
      }
    }
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.setAttribute("aria-hidden", "true");
    area.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
    document.body.append(area);
    area.select();
    area.setSelectionRange(0, text.length);
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (error) {
      ok = false;
    }
    area.remove();
    if (ok) toast(message);
    else toast("Copy failed — select the text manually.", "error");
  }

  /* ---------------------------------------------------------------- time / language */

  function parseDate(value) {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  // One Intl formatter per shape, built once. Constructing a formatter inside
  // toLocaleString per row is a measurable cost on long histories.
  const ABS_TIME_FORMAT = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
  const CLOCK_FORMAT = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });
  const SHORT_DATE_FORMAT = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
  const SHORT_DATE_YEAR_FORMAT = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" });
  const WEEKDAY_FORMAT = new Intl.DateTimeFormat(undefined, { weekday: "long" });
  const LONG_DATE_FORMAT = new Intl.DateTimeFormat(undefined, { month: "long", day: "numeric", year: "numeric" });

  function absoluteTime(value) {
    const date = parseDate(value);
    if (!date) return value || "—";
    return ABS_TIME_FORMAT.format(date);
  }

  function clockTime(value) {
    const date = parseDate(value);
    if (!date) return "";
    return CLOCK_FORMAT.format(date);
  }

  function relativeTime(value) {
    const date = parseDate(value);
    if (!date) return "never";
    const seconds = Math.round((Date.now() - date.getTime()) / 1000);
    if (seconds < 45) return "just now";
    if (seconds < 90) return "1 min ago";
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `${minutes} min ago`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `${hours} hr ago`;
    const days = Math.round(hours / 24);
    if (days === 1) return "yesterday";
    if (days < 7) return `${days} days ago`;
    const format = date.getFullYear() === new Date().getFullYear() ? SHORT_DATE_FORMAT : SHORT_DATE_YEAR_FORMAT;
    return format.format(date);
  }

  function dayKey(value) {
    const date = parseDate(value) || new Date();
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  }

  function dayLabel(value) {
    const date = parseDate(value);
    if (!date) return "Unknown day";
    const today = new Date();
    const startToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const startDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const days = Math.round((startToday - startDay) / 86400000);
    if (days === 0) return "Today";
    if (days === 1) return "Yesterday";
    if (days > 1 && days < 7) return WEEKDAY_FORMAT.format(date);
    return LONG_DATE_FORMAT.format(date);
  }

  let languageNames = null;
  try {
    languageNames = new Intl.DisplayNames(["en"], { type: "language" });
  } catch (error) {
    languageNames = null;
  }

  function languageLabel(code) {
    if (!code) return "Unknown";
    let name = code;
    if (languageNames) {
      try {
        name = languageNames.of(code) || code;
      } catch (error) {
        name = code;
      }
    }
    return name.charAt(0).toUpperCase() + name.slice(1);
  }

  function languageSummary(item) {
    const name = languageLabel(item.detected_language);
    return item.task === "translate" ? `${name} → English` : name;
  }

  function formatDuration(seconds) {
    if (seconds === null || seconds === undefined) return "—";
    return seconds < 10 ? `${seconds.toFixed(1)} s` : `${Math.round(seconds)} s`;
  }

  function formatMs(ms) {
    if (ms === null || ms === undefined) return "—";
    return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`;
  }

  /* ---------------------------------------------------------------- theme */

  const THEMES = ["auto", "light", "dark"];

  function applyTheme() {
    const stored = localStorage.getItem("whub-theme") || "auto";
    const theme = THEMES.includes(stored) ? stored : "auto";
    if (theme === "auto") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
    const button = $("#theme-button");
    if (button) {
      button.innerHTML = "";
      button.append(icon(theme === "dark" ? "moon" : theme === "light" ? "sun" : "auto"));
      button.title = `Theme: ${theme}`;
      button.setAttribute("aria-label", `Theme: ${theme}. Switch theme`);
    }
  }

  function cycleTheme() {
    const current = localStorage.getItem("whub-theme") || "auto";
    const next = THEMES[(THEMES.indexOf(current) + 1) % THEMES.length];
    if (next === "auto") localStorage.removeItem("whub-theme");
    else localStorage.setItem("whub-theme", next);
    applyTheme();
  }

  /* ---------------------------------------------------------------- overlays */

  function lockScroll() {
    const open = !$("#modal-root").hidden || !$("#entry-overlay").hidden;
    document.body.style.overflow = open ? "hidden" : "";
  }

  function showOverlay(selector) {
    state.lastFocus = document.activeElement;
    $(selector).hidden = false;
    lockScroll();
  }

  function setModalContent({ title, body, footer = [], className = "" }) {
    $("#modal-title").textContent = title;
    replace($("#modal-body"), body);
    replace($("#modal-foot"), footer);
    $("#modal-card").className = "modal" + (className ? " " + className : "");
  }

  function openModal(options) {
    state.modalCleanup = options.onClose || null;
    setModalContent(options);
    showOverlay("#modal-root");
    setTimeout(() => {
      const target = $("#modal-body").querySelector("input, select, button, textarea") || $(".modal-head .icon-btn");
      if (target) target.focus({ preventScroll: true });
    }, 30);
  }

  function closeModal() {
    const overlay = $("#modal-root");
    if (overlay.hidden) return;
    const cleanup = state.modalCleanup;
    state.modalCleanup = null;
    state.pair = null;
    if (state.pairTimer) {
      clearInterval(state.pairTimer);
      state.pairTimer = null;
    }
    overlay.hidden = true;
    lockScroll();
    if (cleanup) cleanup();
    if (state.lastFocus && state.lastFocus.focus) state.lastFocus.focus({ preventScroll: true });
  }

  function closeEntry() {
    const overlay = $("#entry-overlay");
    if (overlay.hidden) return;
    overlay.hidden = true;
    lockScroll();
  }

  function closeEverything() {
    closeModal();
    closeEntry();
  }

  /* ---------------------------------------------------------------- boot / auth */

  async function init() {
    hydrateIcons();
    applyTheme();
    bindStaticEvents();
    const onSetupPath = location.pathname.replace(/\/+$/, "") === "/setup";
    const token = onSetupPath ? new URLSearchParams(location.search).get("token") || "" : "";
    let setup = null;
    try {
      const query = token ? `?token=${encodeURIComponent(token)}` : "";
      setup = await fetch(`/api/setup/status${query}`, { credentials: "same-origin" }).then((response) => response.json());
    } catch (error) {
      showLogin("Could not reach the server. Check that it is running.");
      return;
    }
    if (setup && setup.setup_required) {
      showWizard(token, Boolean(setup.token_valid));
      return;
    }
    if (onSetupPath) history.replaceState(null, "", "/" + location.hash);
    // /api/setup/status already reports the session; asking /api/session again
    // adds a second serial round trip to every dashboard load.
    if (setup && setup.authenticated) {
      state.authenticated = true;
      await enterApp();
    } else {
      showLogin();
    }
  }

  function showLogin(message = "") {
    state.authenticated = false;
    if (state.refreshTimer) {
      clearInterval(state.refreshTimer);
      state.refreshTimer = null;
    }
    closeEverything();
    $("#setup-view").hidden = true;
    $("#app-shell").hidden = true;
    $("#login-view").hidden = false;
    $("#login-error").hidden = !message;
    $("#login-error").textContent = message;
    setTimeout(() => $("#login-password").focus(), 30);
  }

  async function enterApp() {
    state.authenticated = true;
    $("#setup-view").hidden = true;
    $("#login-view").hidden = true;
    $("#app-shell").hidden = false;
    state.history.loaded = false;
    await showView(routeName(), { scroll: false });
    // Overview already fetched stats (which include model_status); only ask for
    // the status separately when booting straight into another view.
    syncModelStatusFromStats();
    if (!state.refreshTimer) {
      state.refreshTimer = setInterval(() => {
        if (!document.hidden) refreshLive();
      }, 10000);
    }
  }

  async function login(event) {
    event.preventDefault();
    const input = $("#login-password");
    const submit = $("#login-submit");
    const error = $("#login-error");
    error.hidden = true;
    submit.disabled = true;
    submit.textContent = "Signing in…";
    try {
      await api("/api/login", { method: "POST", body: { password: input.value } });
      input.value = "";
      await enterApp();
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
      input.select();
    } finally {
      submit.disabled = false;
      submit.textContent = "Sign in";
    }
  }

  async function logout() {
    try {
      await api("/api/logout", { method: "POST" });
    } catch (error) {
      /* the cookie is cleared server-side even if the request races */
    }
    state.devices = [];
    state.stats = null;
    state.recent = [];
    state.settings = null;
    state.modelStatus = null;
    state.history = { items: [], cursor: null, q: "", deviceId: "", loading: false, loaded: false, seq: 0, rendered: 0 };
    if (state.modelTimer) {
      clearTimeout(state.modelTimer);
      state.modelTimer = null;
    }
    showLogin();
  }

  /* ---------------------------------------------------------------- routing */

  const ROUTES = ["overview", "history", "devices", "setup", "settings"];

  function routeName() {
    const name = (location.hash || "").replace(/^#\/?/, "").split("?")[0];
    return ROUTES.includes(name) ? name : "overview";
  }

  function navigate(name, options = {}) {
    if (routeName() === name && location.hash) {
      showView(name, options);
      return;
    }
    location.hash = `#/${name}`;
  }

  async function showView(name, { scroll = true } = {}) {
    state.view = name;
    $$(".view").forEach((view) => {
      view.hidden = view.dataset.view !== name;
    });
    $$(".tabs a").forEach((tab) => {
      const active = tab.dataset.tab === name;
      tab.classList.toggle("active", active);
      if (active) tab.setAttribute("aria-current", "page");
      else tab.removeAttribute("aria-current");
    });
    if (scroll) window.scrollTo({ top: 0, behavior: "instant" });
    if (name === "overview") await loadOverview();
    if (name === "devices") {
      await loadDevices();
      renderDeviceCards($("#devices-grid"), "devices");
    }
    if (name === "history") {
      if (!state.devices.length) {
        try {
          await loadDevices();
        } catch (error) {
          /* the list can load without the filter options */
        }
      }
      syncDeviceSelect();
      // The list DOM is kept while another view is shown; rebuilding it here
      // made every return to History re-render the whole loaded list.
      if (!state.history.loaded) await loadHistory(true);
    }
    if (name === "setup") {
      await loadSetup();
    }
    if (name === "settings") {
      await loadSettings();
    }
  }

  /* ---------------------------------------------------------------- data loading */

  async function loadDevices() {
    const payload = await api("/api/admin/devices");
    state.devices = payload.devices;
    syncDeviceSelect();
    return state.devices;
  }

  // Every Recent fetch takes a ticket; only the newest one for the current filter may paint.
  let recentSeq = 0;
  const renderKeys = { recent: "", cards: "", stats: "", select: null };

  function recentQuery() {
    const query = new URLSearchParams({ limit: "20" });
    if (state.recentFilter !== "all") query.set("device_id", state.recentFilter);
    return query;
  }

  function recentFilterIsStale() {
    // The filtered device was deleted: fall back to "All" instead of an empty list.
    if (state.recentFilter === "all") return false;
    if (state.devices.some((device) => String(device.id) === String(state.recentFilter))) return false;
    state.recentFilter = "all";
    return true;
  }

  function paintOverview({ force = false } = {}) {
    renderStats(force);
    renderFirstDeviceCta();
    const cardsKey = JSON.stringify(state.devices);
    if (force || cardsKey !== renderKeys.cards) {
      renderKeys.cards = cardsKey;
      renderDeviceCards($("#device-grid"), "overview");
      renderRecentChips();
    }
    const recentKey = state.recentFilter + JSON.stringify(state.recent.map((item) => [item.id, item.text]));
    // Unchanged lists are left alone so the 10 s refresh does not steal focus or selection.
    if (force || recentKey !== renderKeys.recent) {
      renderKeys.recent = recentKey;
      renderRecent();
    }
  }

  async function loadOverview() {
    const seq = ++recentSeq;
    const filter = state.recentFilter;
    try {
      const [stats, devices, recent] = await Promise.all([
        api("/api/admin/stats"),
        api("/api/admin/devices"),
        api(`/api/admin/transcriptions?${recentQuery()}`),
      ]);
      state.stats = stats;
      state.devices = devices.devices;
      syncDeviceSelect();
      if (recentFilterIsStale()) return loadOverview();
      if (seq === recentSeq && filter === state.recentFilter) state.recent = recent.items;
      paintOverview({ force: true });
    } catch (error) {
      if (error.status !== 401) toast(error.message, "error");
    }
  }

  async function loadRecent() {
    const seq = ++recentSeq;
    const filter = state.recentFilter;
    try {
      const recent = await api(`/api/admin/transcriptions?${recentQuery()}`);
      if (seq !== recentSeq || filter !== state.recentFilter) return;
      state.recent = recent.items;
      renderKeys.recent = "";
      paintOverview();
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function refreshLive() {
    if (!state.authenticated) return;
    const seq = ++recentSeq;
    const filter = state.recentFilter;
    const onOverview = state.view === "overview";
    try {
      // The Recent payload is only rendered on Overview. Fetching it on every
      // other view cost ~11 KB per tick for data that was thrown away.
      const [stats, devices, recent] = await Promise.all([
        api("/api/admin/stats"),
        api("/api/admin/devices"),
        onOverview ? api(`/api/admin/transcriptions?${recentQuery()}`) : Promise.resolve(null),
      ]);
      state.stats = stats;
      state.devices = devices.devices;
      syncDeviceSelect();
      // /api/admin/stats already carries model_status; a second status request
      // on every tick was redundant.
      syncModelStatusFromStats();
      const staleFilter = recentFilterIsStale();
      if (onOverview) {
        if (staleFilter) return loadOverview();
        if (seq === recentSeq && filter === state.recentFilter) state.recent = recent.items;
        paintOverview();
      }
      if (state.view === "devices") renderDeviceCards($("#devices-grid"), "devices");
      if (state.pair) {
        const device = state.devices.find((item) => item.id === state.pair.deviceId);
        if (device && device.status === "active" && !state.pair.revealed) state.pair.linked = true;
        updatePairStatus();
      }
    } catch (error) {
      /* live refresh is best effort */
    }
  }

  async function refreshAfterMutation() {
    try {
      const payload = await api("/api/admin/devices");
      state.devices = payload.devices;
      syncDeviceSelect();
    } catch (error) {
      /* ignore */
    }
    if (state.view === "overview") {
      await loadOverview();
    } else if (state.view === "history") {
      await loadHistory(true);
    } else if (state.view === "devices") {
      renderDeviceCards($("#devices-grid"), "devices");
    }
  }

  /* ---------------------------------------------------------------- overview */

  function statTile({ iconName, value, label, sub, accent = false }) {
    return h(
      "div",
      { class: "stat-tile" + (accent ? " accent" : "") },
      h("span", { class: "stat-icon" }, icon(iconName)),
      h(
        "div",
        { style: "min-width:0" },
        h("div", { class: "stat-value", text: value }),
        h("div", { class: "stat-label", text: label }),
        h("div", { class: "stat-sub", text: sub, title: sub })
      )
    );
  }

  function renderStats(force = false) {
    const strip = $("#stat-strip");
    const stats = state.stats;
    if (!stats) {
      renderKeys.stats = "";
      replace(
        strip,
        ...Array.from({ length: 4 }, () =>
          h("div", { class: "stat-tile" }, h("div", { class: "skeleton", style: "width:100%;height:42px" }))
        )
      );
      return;
    }
    const modelShort = String(stats.model || "—");
    const lastValue = stats.last_transcription_at ? relativeTime(stats.last_transcription_at) : "—";
    const lastSub = stats.last_transcription_at ? absoluteTime(stats.last_transcription_at) : "No transcriptions yet";
    // The 10 s tick usually returns identical numbers; rebuilding the tiles
    // replaced 24 nodes and forced a layout for nothing. The relative label is
    // part of the key so "just now" still ages on its own.
    const statsKey = JSON.stringify([
      stats.transcriptions_total,
      stats.transcriptions_today,
      stats.devices_active,
      stats.devices_pending,
      stats.devices_total,
      modelShort,
      Boolean(stats.models_loaded),
      stats.device,
      lastValue,
      lastSub,
    ]);
    if (!force && statsKey === renderKeys.stats) return;
    renderKeys.stats = statsKey;
    strip.replaceChildren(
      statTile({
        iconName: "headphones",
        value: String(stats.transcriptions_total ?? 0),
        label: "Transcriptions",
        sub: `${stats.transcriptions_today ?? 0} today`,
        accent: true,
      }),
      statTile({
        iconName: "devices",
        value: `${stats.devices_active ?? 0}`,
        label: "Devices linked",
        sub: stats.devices_pending ? `${stats.devices_pending} waiting to pair` : `${stats.devices_total ?? 0} total`,
      }),
      statTile({
        iconName: "sparkles",
        value: modelShort.length > 16 ? modelShort.slice(0, 15) + "…" : modelShort,
        label: "Model",
        sub: `${stats.models_loaded ? "Loaded" : "Idle"} · ${String(stats.device || "cpu").toUpperCase()}`,
      }),
      statTile({
        iconName: "clock",
        value: lastValue,
        label: "Last activity",
        sub: lastSub,
      })
    );
  }

  function statusLabel(device) {
    if (device.deleted) return "Deleted";
    if (device.status === "active") return "Linked";
    if (device.status === "revoked") return "Revoked";
    return "Not linked";
  }

  function statusClass(device) {
    if (device.deleted) return "deleted";
    return device.status;
  }

  function deviceKindLabel(kind) {
    return KIND_LABELS[kind] || "Device";
  }

  function createDeviceCard(device, mode) {
    const card = h("article", {
      class: `device-card is-${statusClass(device)}`,
    });
    const metaParts = [deviceKindLabel(device.kind)];
    if (device.builtin) metaParts.push("built in");
    else if (device.deleted) metaParts.push("deleted");
    else if (device.status === "pending") metaParts.push("awaiting pairing");

    const top = h(
      "div",
      { class: "device-top" },
      h("span", { class: "device-icon" }, icon(DEVICE_ICONS[device.kind] || "devices")),
      h(
        "div",
        { class: "device-id" },
        h("h3", { text: device.display_name }),
        h("p", {
          text: metaParts.join(" · "),
          title: device.created_at ? `Added ${absoluteTime(device.created_at)}` : "",
        })
      ),
      h("span", { class: `pill ${statusClass(device)}`, text: statusLabel(device) })
    );
    card.append(top);

    const preview = (device.last_text_preview || "").trim();
    card.append(h("p", { class: "device-preview" + (preview ? "" : " is-empty"), text: preview || "No transcriptions yet." }));

    const last = device.last_transcription_at
      ? h("span", { text: relativeTime(device.last_transcription_at), title: absoluteTime(device.last_transcription_at) })
      : h("span", { text: "never" });
    card.append(
      h(
        "div",
        { class: "device-meta" },
        h(
          "span",
          {},
          h("strong", { text: String(device.transcription_count ?? 0) }),
          (device.transcription_count ?? 0) === 1 ? " transcript" : " transcripts"
        ),
        last
      )
    );

    const actions = h("div", { class: "device-actions" });
    const historyButton = h("button", { class: "btn btn-quiet", type: "button" }, icon("history"), "History");
    historyButton.addEventListener("click", () => {
      state.history.deviceId = String(device.id);
      state.history.q = "";
      state.history.loaded = false;
      $("#history-search").value = "";
      $("#history-clear").hidden = true;
      syncDeviceSelect();
      navigate("history");
    });
    actions.append(historyButton);

    if (mode === "devices" && !device.builtin && !device.deleted) {
      if (device.status !== "active") {
        actions.append(
          h(
            "button",
            { class: "btn btn-primary btn-sm", type: "button", onclick: () => pairDevice(device) },
            icon("qr"),
            device.status === "revoked" ? "Re-pair" : "Pair"
          )
        );
      } else {
        actions.append(
          h(
            "button",
            { class: "btn btn-secondary btn-sm", type: "button", onclick: () => pairDevice(device) },
            icon("refresh"),
            "Re-pair"
          )
        );
      }
      actions.append(
        h("button", { class: "btn btn-secondary btn-sm", type: "button", onclick: () => editDevice(device) }, icon("edit"), "Edit")
      );
      if (device.status === "active") {
        actions.append(
          h("button", { class: "btn btn-quiet btn-sm", type: "button", onclick: () => revokeDevice(device) }, "Revoke")
        );
      }
      actions.append(
        h(
          "button",
          { class: "btn btn-quiet btn-sm danger-text", type: "button", onclick: () => deleteDevice(device) },
          icon("trash"),
          "Delete"
        )
      );
    } else if (mode === "overview" && device.status === "pending" && !device.builtin) {
      actions.append(
        h("button", { class: "btn btn-quiet btn-sm", type: "button", onclick: () => pairDevice(device) }, icon("qr"), "Pair")
      );
    }

    if (device.builtin) {
      card.append(h("div", { class: "device-foot" }, h("span", { class: "device-key", text: "This browser · always available" })));
    } else {
      const keyText = device.key_prefix
        ? device.key_prefix + "…"
        : device.deleted
          ? "key destroyed"
          : "no key yet";
      const seenText = device.last_seen_at
        ? `seen ${relativeTime(device.last_seen_at)}`
        : device.deleted
          ? ""
          : device.status === "pending"
            ? "waiting for pairing"
            : device.status === "revoked"
              ? "key revoked"
              : "no requests yet";
      card.append(
        h(
          "div",
          { class: "device-foot" },
          h("span", { class: "device-key", text: keyText }),
          h("span", { class: "device-key", text: seenText, title: device.last_seen_at ? absoluteTime(device.last_seen_at) : "" })
        )
      );
    }
    card.append(actions);
    return card;
  }

  function renderDeviceCards(container, mode) {
    if (!container) return;
    if (!state.devices.length) {
      container.replaceChildren(
        emptyState({
          iconName: "devices",
          title: "No devices yet",
          message: "Add a device to get a pairing QR code and a key.",
          action: { label: "Add device", onClick: openAddDevice },
        })
      );
      return;
    }
    const sorted = [...state.devices].sort((a, b) => Number(a.builtin) - Number(b.builtin) || a.id - b.id);
    container.replaceChildren(...sorted.map((device) => createDeviceCard(device, mode)));
  }

  function renderRecentChips() {
    const chips = $("#recent-chips");
    const total = state.devices.reduce((sum, device) => sum + (device.transcription_count || 0), 0);
    const options = [{ id: "all", label: "All", count: total }, ...state.devices.map((device) => ({ id: String(device.id), label: device.display_name, count: device.transcription_count || 0 }))];
    chips.replaceChildren(
      ...options.map((option) =>
        h(
          "button",
          {
            class: "chip" + (String(state.recentFilter) === option.id ? " active" : ""),
            type: "button",
            role: "tab",
            "aria-selected": String(state.recentFilter) === option.id,
            onclick: () => {
              state.recentFilter = option.id;
              renderRecentChips();
              loadRecent();
            },
          },
          option.label,
          h("span", { class: "chip-count", text: String(option.count) })
        )
      )
    );
  }

  function entryRow(item, { grouped = false } = {}) {
    const row = h("article", {
      class: "entry",
      tabindex: "0",
      role: "button",
      "aria-label": "Open transcription",
    });
    row.append(
      h(
        "div",
        { class: "entry-time", title: absoluteTime(item.created_at) },
        h("strong", { text: grouped ? clockTime(item.created_at) : relativeTime(item.created_at) }),
        h("span", { text: grouped ? formatDuration(item.audio_duration_s) : clockTime(item.created_at) })
      ),
      h("span", { class: "entry-dot" + (item.task === "translate" ? " translate" : "") }),
      h(
        "div",
        { class: "entry-body" },
        h("p", { class: "entry-text", text: item.text }),
        h(
          "div",
          { class: "entry-meta" },
          h("span", { text: item.device_name || "Deleted device" }),
          h("span", { class: "sep", text: "·" }),
          h("span", { class: "lang", text: languageSummary(item) })
        )
      )
    );
    const copy = h(
      "button",
      { class: "icon-btn entry-copy", type: "button", "aria-label": "Copy transcription", title: "Copy" },
      icon("copy")
    );
    copy.addEventListener("click", (event) => {
      event.stopPropagation();
      copyText(item.text);
    });
    row.append(copy);
    row.addEventListener("click", (event) => {
      if (event.target.closest("button, a")) return;
      openEntry(item.id);
    });
    row.addEventListener("keydown", (event) => {
      if (event.target.closest("button, a")) return;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openEntry(item.id);
      }
    });
    return row;
  }

  function emptyState({ iconName, title, message, action = null }) {
    const node = h(
      "div",
      { class: "empty" },
      h("span", { class: "empty-icon" }, icon(iconName)),
      h("h3", { text: title }),
      h("p", { text: message })
    );
    if (action) {
      node.append(h("button", { class: "btn btn-secondary btn-sm", type: "button", onclick: action.onClick }, action.label));
    }
    return node;
  }

  function renderRecent() {
    const list = $("#recent-list");
    const count = $("#recent-count");
    if (!state.recent.length) {
      count.textContent = "";
      list.replaceChildren(
        emptyState({
          iconName: "inbox",
          title: "Nothing here yet",
          message: "Dictate from a paired device and the text will appear here within seconds.",
          action: { label: "Add a device", onClick: openAddDevice },
        })
      );
      return;
    }
    count.textContent = `${state.recent.length} most recent`;
    list.replaceChildren(...state.recent.map(entryRow));
  }

  /* ---------------------------------------------------------------- history */

  function syncDeviceSelect() {
    const select = $("#history-device");
    if (!select) return;
    const current = state.history.deviceId;
    // Rebuilding the <select> every 10 s closed an open dropdown and replaced
    // its options plus the visible value even when the device list was unchanged.
    const selectKey = current + "|" + state.devices.map((device) => `${device.id}:${device.display_name}`).join("|");
    if (selectKey === renderKeys.select) {
      select.value = current;
      return;
    }
    renderKeys.select = selectKey;
    const options = [new Option("All devices", "")];
    for (const device of state.devices) options.push(new Option(device.display_name, String(device.id)));
    select.replaceChildren(...options);
    select.value = current;
    if (select.value !== current) {
      // The filtered device is gone: show all devices, and reload so the list matches.
      select.value = "";
      state.history.deviceId = "";
      renderKeys.select = null;
      if (state.view === "history") loadHistory(true);
    }
  }

  async function loadHistory(reset = false) {
    const history = state.history;
    if (history.loading && !reset) return;
    if (reset) {
      history.seq += 1;
      history.cursor = null;
    }
    const seq = history.seq;
    const query = new URLSearchParams({ limit: "50" });
    if (history.q) query.set("q", history.q);
    if (history.deviceId) query.set("device_id", history.deviceId);
    if (!reset && history.cursor) query.set("before", history.cursor);
    history.loading = true;
    $("#history-list").classList.add("is-loading");
    try {
      const payload = await api(`/api/admin/transcriptions?${query}`);
      if (seq !== history.seq) return;
      const beforeCount = history.items.length;
      history.items = reset ? payload.items : history.items.concat(payload.items);
      history.cursor = payload.next_cursor;
      history.loaded = true;
      renderHistory({ append: !reset && beforeCount > 0 });
    } catch (error) {
      if (seq === history.seq && error.status !== 401) toast(error.message, "error");
    } finally {
      if (seq === history.seq) {
        history.loading = false;
        $("#history-list").classList.remove("is-loading");
      }
    }
  }

  function renderHistory({ append = false } = {}) {
    const list = $("#history-list");
    const meta = $("#history-meta");
    const loadMore = $("#load-more");
    const history = state.history;
    const filters = [];
    if (history.q) filters.push(`“${history.q}”`);
    if (history.deviceId) {
      const device = state.devices.find((item) => String(item.id) === history.deviceId);
      if (device) filters.push(device.display_name);
    }
    if (!history.items.length) {
      meta.textContent = filters.length ? `No matches for ${filters.join(" · ")}` : "";
      list.replaceChildren(
        emptyState({
          iconName: history.q ? "search" : "inbox",
          title: history.q ? "No matching transcripts" : "Your history is empty",
          message: history.q
            ? "Try fewer words, or clear the device filter."
            : "Every transcription from every device lands here as text.",
          action: history.q
            ? {
                label: "Clear search",
                onClick: () => {
                  $("#history-search").value = "";
                  $("#history-clear").hidden = true;
                  history.q = "";
                  loadHistory(true);
                },
              }
            : null,
        })
      );
      history.rendered = 0;
      loadMore.hidden = true;
      return;
    }

    meta.textContent = `${history.items.length} transcript${history.items.length === 1 ? "" : "s"}${filters.length ? " · " + filters.join(" · ") : ""}`;
    if (append && history.rendered > 0 && list.childElementCount) {
      appendHistoryItems(list, history.items.slice(history.rendered));
      history.rendered = history.items.length;
      loadMore.hidden = !history.cursor;
      return;
    }
    const groups = new Map();
    for (const item of history.items) {
      const key = dayKey(item.created_at);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(item);
    }
    list.replaceChildren(
      ...Array.from(groups.entries()).map(([key, items]) =>
        h(
          "section",
          { class: "day-group", dataset: { day: key, count: String(items.length) } },
          h(
            "h3",
            { class: "day-head" },
            h("span", { text: dayLabel(items[0].created_at) }),
            h("span", { class: "day-count", text: `${items.length} note${items.length === 1 ? "" : "s"}` })
          ),
          ...items.map((item) => entryRow(item, { grouped: true }))
        )
      )
    );
    history.rendered = history.items.length;
    loadMore.hidden = !history.cursor;
  }

  // Load more only ever appends older entries, so keep the existing rows and
  // update the last day group instead of rebuilding the whole list.
  function appendHistoryItems(list, items) {
    let group = list.lastElementChild;
    let pending = [];
    const flush = () => {
      if (!pending.length) return;
      const total = Number(group.dataset.count || 0) + pending.length;
      group.dataset.count = String(total);
      group.append(...pending);
      group.querySelector(".day-count").textContent = `${total} note${total === 1 ? "" : "s"}`;
      pending = [];
    };
    for (const item of items) {
      const key = dayKey(item.created_at);
      if (!group || group.dataset.day !== key) {
        flush();
        group = h(
          "section",
          { class: "day-group", dataset: { day: key, count: "0" } },
          h("h3", { class: "day-head" }, h("span", { text: dayLabel(item.created_at) }), h("span", { class: "day-count" }))
        );
        list.append(group);
      }
      pending.push(entryRow(item, { grouped: true }));
    }
    flush();
  }

  /* ---------------------------------------------------------------- entry detail */

  let entrySeq = 0;

  async function openEntry(id) {
    const seq = ++entrySeq;
    const overlay = $("#entry-overlay");
    overlay.hidden = false;
    lockScroll();
    $("#entry-title").textContent = `Entry #${id}`;
    const known =
      state.history.items.find((item) => String(item.id) === String(id)) ||
      state.recent.find((item) => String(item.id) === String(id));
    if (known) {
      // The list already holds every field the drawer shows; opening it should
      // not wait for another round trip.
      renderEntry(known);
      setTimeout(() => $(".drawer-head .icon-btn").focus({ preventScroll: true }), 30);
      return;
    }
    replace($("#entry-body"), h("div", { class: "skeleton", style: "height:120px;margin-bottom:18px" }), h("div", { class: "skeleton", style: "height:220px" }));
    setTimeout(() => $(".drawer-head .icon-btn").focus({ preventScroll: true }), 30);
    try {
      const item = await api(`/api/admin/transcriptions/${id}`);
      // A later open (or close + reopen) supersedes this response.
      if (overlay.hidden || seq !== entrySeq) return;
      renderEntry(item);
    } catch (error) {
      if (overlay.hidden || seq !== entrySeq) return;
      replace($("#entry-body"), emptyState({ iconName: "alert", title: "Could not load this entry", message: error.message }));
    }
  }

  function renderEntry(item) {
    $("#entry-title").textContent = `Entry #${item.id}`;
    const meta = [
      ["Device", item.device_name || "Deleted device"],
      ["Captured", absoluteTime(item.created_at)],
      ["Detected", `${languageLabel(item.detected_language)} (${item.detected_language || "?"})`],
      ["Task", item.task === "translate" ? "Translate to English" : "Transcribe"],
      ["Audio duration", formatDuration(item.audio_duration_s)],
      ["Processing", formatMs(item.processing_ms)],
      ["Model", item.model || "—"],
      ["Endpoint", item.endpoint || "—"],
    ];
    if (item.language_probability !== null && item.language_probability !== undefined) {
      meta.push(["Language confidence", `${Math.round(item.language_probability * 100)}%`]);
    }
    const copy = h("button", { class: "btn btn-primary", type: "button" }, icon("copy"), "Copy text");
    copy.addEventListener("click", () => copyText(item.text));
    const remove = h("button", { class: "btn btn-danger", type: "button" }, icon("trash"), "Delete");
    remove.addEventListener("click", async () => {
      const result = await confirmAction({
        title: "Delete this transcription?",
        message: "The text is removed from the shared history. This cannot be undone.",
        confirmLabel: "Delete",
        danger: true,
      });
      if (!result) return;
      try {
        await api(`/api/admin/transcriptions/${item.id}`, { method: "DELETE" });
        closeEntry();
        toast("Transcription deleted");
        refreshAfterMutation();
      } catch (error) {
        toast(error.message, "error");
      }
    });
    replace(
      $("#entry-body"),
      h("p", { class: "entry-full", text: item.text }),
      h(
        "dl",
        { class: "detail-meta" },
        ...meta.map(([label, value]) => h("div", {}, h("dt", { text: label }), h("dd", { text: value })))
      ),
      h("div", { class: "detail-actions" }, copy, remove)
    );
  }

  /* ---------------------------------------------------------------- devices: actions */

  async function pairDevice(device) {
    try {
      const payload = await api(`/api/admin/devices/${device.id}/pair`, { method: "POST" });
      state.devices = state.devices.map((item) => (item.id === device.id ? { ...item, ...payload.device } : item));
      openPairing(payload.device, payload.pairing);
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function revokeDevice(device) {
    const result = await confirmAction({
      title: `Revoke ${device.display_name}?`,
      message: "Its key stops working immediately. History is kept and the device can be paired again later.",
      confirmLabel: "Revoke key",
      danger: true,
    });
    if (!result) return;
    try {
      await api(`/api/admin/devices/${device.id}/revoke`, { method: "POST" });
      toast("Device revoked");
      refreshAfterMutation();
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function deleteDevice(device) {
    const result = await confirmAction({
      title: `Delete ${device.display_name}?`,
      message: "The device disappears from the overview. By default its transcriptions stay in history as “Deleted device”.",
      confirmLabel: "Delete device",
      danger: true,
      checkbox: { label: "Also delete all transcriptions from this device", checked: false },
    });
    if (!result) return;
    try {
      const query = result.checked ? "?delete_history=true" : "?delete_history=false";
      await api(`/api/admin/devices/${device.id}${query}`, { method: "DELETE" });
      toast(result.checked ? "Device and its history deleted" : "Device deleted; history kept");
      refreshAfterMutation();
    } catch (error) {
      toast(error.message, "error");
    }
  }

  function openAddDevice() {
    const nameInput = h("input", { id: "device-name", type: "text", maxlength: "80", placeholder: "e.g. Alice’s iPhone", required: "required", autocomplete: "off" });
    const kindOptions = ["iphone", "ipad", "mac", "windows", "linux", "android", "web", "other"];
    const kindGrid = h("div", { class: "kind-grid", role: "radiogroup", "aria-label": "Device kind" });
    kindOptions.forEach((kind, index) => {
      const radio = h("input", { type: "radio", name: "device-kind", value: kind, checked: kind === "iphone" ? true : null });
      kindGrid.append(
        h("label", { class: "kind-option" }, radio, h("span", {}, icon(DEVICE_ICONS[kind]), KIND_LABELS[kind]))
      );
    });
    const form = h(
      "form",
      { id: "add-device-form" },
      h("div", { class: "field" }, h("label", { for: "device-name", text: "Name" }), nameInput),
      h("div", { class: "field" }, h("span", { class: "field-label", text: "Kind" }), kindGrid)
    );
    const cancel = h("button", { class: "btn btn-secondary", type: "button" }, "Cancel");
    cancel.addEventListener("click", closeModal);
    const add = h("button", { class: "btn btn-primary", type: "submit", form: "add-device-form" }, icon("plus"), "Add device");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const kind = (form.querySelector('input[name="device-kind"]:checked') || {}).value || "other";
      const name = nameInput.value.trim();
      if (!name) {
        nameInput.focus();
        return;
      }
      add.disabled = true;
      try {
        const payload = await api("/api/admin/devices", { method: "POST", body: { name, kind } });
        closeModal();
        toast("Device created");
        await loadDevices();
        if (state.view === "overview") renderDeviceCards($("#device-grid"), "overview");
        if (state.view === "devices") renderDeviceCards($("#devices-grid"), "devices");
        openPairing(payload.device, payload.pairing);
      } catch (error) {
        toast(error.message, "error");
      } finally {
        add.disabled = false;
      }
    });
    openModal({ title: "Add a device", body: form, footer: [cancel, add] });
    setTimeout(() => nameInput.focus(), 30);
  }

  function editDevice(device) {
    const nameInput = h("input", { id: "edit-device-name", type: "text", maxlength: "80", value: device.name, required: "required" });
    const select = h(
      "select",
      { id: "edit-device-kind" },
      ...Object.entries(KIND_LABELS)
        .filter(([kind]) => kind !== "web" || device.kind === "web")
        .map(([kind, label]) => new Option(label, kind, false, device.kind === kind))
    );
    const form = h(
      "form",
      { id: "edit-device-form" },
      h("div", { class: "field" }, h("label", { for: "edit-device-name", text: "Name" }), nameInput),
      h("div", { class: "field" }, h("label", { for: "edit-device-kind", text: "Kind" }), select)
    );
    const cancel = h("button", { class: "btn btn-secondary", type: "button" }, "Cancel");
    cancel.addEventListener("click", closeModal);
    const save = h("button", { class: "btn btn-primary", type: "submit", form: "edit-device-form" }, "Save changes");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      save.disabled = true;
      try {
        await api(`/api/admin/devices/${device.id}`, { method: "PATCH", body: { name: nameInput.value.trim(), kind: select.value } });
        closeModal();
        toast("Device updated");
        refreshAfterMutation();
      } catch (error) {
        toast(error.message, "error");
      } finally {
        save.disabled = false;
      }
    });
    openModal({ title: "Edit device", body: form, footer: [cancel, save] });
  }

  function confirmAction({ title, message, confirmLabel = "Confirm", danger = false, checkbox = null }) {
    return new Promise((resolve) => {
      let settled = false;
      const finish = (value) => {
        if (settled) return;
        settled = true;
        resolve(value);
      };
      let checkboxNode = null;
      let checked = false;
      const body = [h("p", { class: "modal-intro", text: message })];
      if (checkbox) {
        const input = h("input", { type: "checkbox", checked: checkbox.checked ? true : null });
        checked = Boolean(checkbox.checked);
        input.addEventListener("change", () => {
          checked = input.checked;
        });
        checkboxNode = h("label", { class: "checkbox" }, input, h("span", { text: checkbox.label }));
        body.push(checkboxNode);
      }
      const cancel = h("button", { class: "btn btn-secondary", type: "button" }, "Cancel");
      cancel.addEventListener("click", () => closeModal());
      const confirm = h("button", { class: `btn ${danger ? "btn-danger" : "btn-primary"}`, type: "button" }, confirmLabel);
      confirm.addEventListener("click", () => {
        finish({ checked });
        closeModal();
      });
      openModal({ title, body, footer: [cancel, confirm], onClose: () => finish(null) });
      setTimeout(() => confirm.focus({ preventScroll: true }), 40);
    });
  }

  /* ---------------------------------------------------------------- pairing modal */

  function openPairing(device, pairing) {
    state.pair = {
      deviceId: device.id,
      device,
      pairing,
      revealed: null,
      linked: device.status === "active",
    };
    setModalContent(pairModalContent());
    $("#modal-card").className = "modal modal-qr";
    showOverlay("#modal-root");
    if (state.pairTimer) clearInterval(state.pairTimer);
    state.pairTimer = setInterval(async () => {
      if (!state.pair) return;
      try {
        const payload = await api("/api/admin/devices");
        state.devices = payload.devices;
        const current = state.devices.find((item) => item.id === state.pair.deviceId);
        if (current) {
          state.pair.device = current;
          if (current.status === "active") state.pair.linked = true;
        }
        updatePairStatus();
        updatePairActions();
      } catch (error) {
        /* keep waiting */
      }
    }, 3000);
    state.modalCleanup = () => {
      if (state.pairTimer) {
        clearInterval(state.pairTimer);
        state.pairTimer = null;
      }
      state.pair = null;
    };
  }

  function pairModalContent() {
    const pair = state.pair;
    const device = pair.device;
    const base = window.location.origin;
    const qr = h("div", { class: "qr-card", html: pair.pairing.qr_svg });
    const urlBox = h("div", { class: "copy-box" }, h("code", { text: pair.pairing.url }), h("button", { class: "icon-btn", type: "button", "aria-label": "Copy pairing link", onclick: () => copyText(pair.pairing.url, "Pairing link copied") }, icon("copy")));
    const status = h("div", { class: "pair-status", id: "pair-status" });
    const actions = h("div", { class: "pair-actions", id: "pair-actions" });
    const reveal = h("div", { id: "pair-reveal" });
    const body = [
      h("p", { class: "modal-intro", text: `Scan this code with ${device.display_name}, or open the link on the device you are pairing. Codes last 15 minutes and work once.` }),
      h("div", { class: "qr-wrap" }, qr),
      urlBox,
      status,
      actions,
      reveal,
    ];
    const close = h("button", { class: "btn btn-secondary", type: "button" }, "Close");
    close.addEventListener("click", closeModal);
    const content = { title: `Pair ${device.display_name}`, body, footer: [close], className: "modal-qr" };
    setTimeout(() => {
      updatePairStatus();
      updatePairActions();
    }, 0);
    return content;
  }

  function updatePairStatus() {
    const status = $("#pair-status");
    if (!status || !state.pair) return;
    const pair = state.pair;
    if (pair.revealed) {
      status.className = "pair-status linked";
      status.replaceChildren(icon("check"), h("span", { text: "Device linked. The key is shown below — copy it now." }));
    } else if (pair.linked || pair.device.status === "active") {
      status.className = "pair-status linked";
      status.replaceChildren(icon("check"), h("span", { text: "Device linked. The key was shown on the device; re-pair to show a key here." }));
    } else {
      status.className = "pair-status";
      status.replaceChildren(h("span", { class: "spinner" }), h("span", { text: "Waiting for the device to scan…" }));
    }
  }

  function updatePairActions() {
    const actions = $("#pair-actions");
    if (!actions || !state.pair) return;
    const pair = state.pair;
    actions.replaceChildren();
    const claim = h("button", { class: "btn btn-primary", type: "button" }, icon("key"), "I’m on this device — show key here");
    claim.disabled = Boolean(pair.revealed);
    claim.addEventListener("click", claimPairing);
    const open = h("a", { class: "btn btn-secondary", href: `/pair/${encodeURIComponent(pair.pairing.code)}`, target: "_blank", rel: "noopener noreferrer" }, icon("arrow"), "Open pairing page");
    actions.append(claim, open);
  }

  async function claimPairing() {
    if (!state.pair) return;
    const button = $("#pair-actions button");
    if (button) button.disabled = true;
    try {
      const payload = await api(`/pair/${encodeURIComponent(state.pair.pairing.code)}?format=json`, { method: "POST" });
      state.pair.revealed = payload;
      state.pair.linked = true;
      toast("Device linked");
      updatePairStatus();
      updatePairActions();
      const reveal = $("#pair-reveal");
      if (reveal) replace(reveal, revealPanel(payload));
      refreshAfterMutation();
    } catch (error) {
      toast(error.message, "error");
      if (button) button.disabled = false;
    }
  }

  function stepList(steps) {
    return h(
      "ol",
      { class: "steps" },
      ...steps.map((step) => h("li", {}, richFragment(step)))
    );
  }

  function richFragment(text) {
    const fragment = document.createDocumentFragment();
    const pattern = /(`[^`]+`|\*\*[^*]+\*\*)/g;
    let lastIndex = 0;
    let match;
    while ((match = pattern.exec(text)) !== null) {
      if (match.index > lastIndex) fragment.append(text.slice(lastIndex, match.index));
      const token = match[0];
      if (token.startsWith("`")) fragment.append(h("code", { text: token.slice(1, -1) }));
      else fragment.append(h("strong", { text: token.slice(2, -2) }));
      lastIndex = match.index + token.length;
    }
    if (lastIndex < text.length) fragment.append(text.slice(lastIndex));
    return fragment;
  }

  function revealPanel(payload) {
    const setup = payload.setup;
    const keyBox = h(
      "div",
      { class: "copy-box secret" },
      h("code", { text: payload.api_key }),
      h("button", { class: "btn btn-quiet", type: "button", onclick: () => copyText(payload.api_key, "API key copied") }, "Copy")
    );
    const panel = h(
      "div",
      { class: "reveal" },
      h("h3", { text: "API key — shown once" }),
      keyBox,
      h("p", { class: "reveal-note", text: "This key will not be shown again. The setup page on the paired device walks through the client steps." }),
      h("details", { class: "guide", style: "margin-top:12px" }, h("summary", {}, h("h3", { text: setup.guide.title }), h("span", { class: "chev" }, icon("chevron"))), h("div", { class: "guide-body" }, stepList(setup.guide.steps)))
    );
    return panel;
  }

  /* ---------------------------------------------------------------- record modal */

  function recordSupported() {
    return Boolean(window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  }

  function openRecordModal() {
    if (window.isSecureContext && !recordSupported()) {
      toast("This browser cannot record audio.", "error");
    }
    const record = {
      status: "idle",
      cancelled: false,
      chunks: [],
      stream: null,
      recorder: null,
      timer: null,
      startedAt: 0,
      levelRaf: null,
      audioContext: null,
      result: null,
      error: "",
      refs: {},
    };
    state.record = record;
    const wrapper = h("div", {});
    const supported = recordSupported();
    if (!supported) {
      wrapper.append(
        h(
          "div",
          { class: "insecure-note", style: "margin-bottom:16px" },
          icon("lock"),
          h(
            "div",
            {},
            h("strong", { text: "Recording needs HTTPS or localhost" }),
            h(
              "span",
              {
                text: window.isSecureContext
                  ? "This browser does not expose MediaRecorder. Upload an audio file instead."
                  : "Browsers block the microphone on plain-HTTP LAN addresses. Open the dashboard through its HTTPS URL, or upload an audio file below.",
              }
            )
          )
        )
      );
    }
    const button = h("button", { class: "record-button", type: "button", "aria-label": "Start recording", disabled: supported ? null : true }, icon("mic"));
    const timer = h("div", { class: "record-time", text: "00:00" });
    const levels = h("div", { class: "levels", "aria-hidden": "true" }, ...Array.from({ length: 7 }, () => h("i")));
    const hint = h("p", { class: "record-hint", text: supported ? "Tap the microphone, speak, then tap again to stop." : "Upload a recording to transcribe it." });
    const stage = h("div", { class: "record-stage" }, button, timer, levels, hint);
    const fileInput = h("input", { type: "file", accept: "audio/*", id: "record-file" });
    const fileRow = h(
      "div",
      { class: "upload-row" },
      icon("upload"),
      h("label", { class: "file-label", for: "record-file" }, "Upload an audio file", fileInput)
    );
    const result = h("div", { id: "record-result", class: "record-result" });
    wrapper.append(stage, fileRow, result);
    record.refs = { button, timer, levels, hint, result, fileRow };
    button.addEventListener("click", () => {
      if (record.status === "recording") stopRecording();
      else if (record.status === "idle" || record.status === "done" || record.status === "error") beginRecording();
    });
    fileInput.addEventListener("change", () => {
      const file = fileInput.files && fileInput.files[0];
      if (file) sendRecording(file, file.type || "audio/webm");
      fileInput.value = "";
    });
    const close = h("button", { class: "btn btn-secondary", type: "button" }, "Close");
    close.addEventListener("click", closeModal);
    openModal({
      title: "Record a note",
      body: wrapper,
      footer: [close],
      onClose: () => cleanupRecording(true),
    });
    updateRecordUI();
  }

  function pickMimeType() {
    const types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
    if (window.MediaRecorder && MediaRecorder.isTypeSupported) {
      return types.find((type) => MediaRecorder.isTypeSupported(type)) || "";
    }
    return "";
  }

  async function beginRecording() {
    const record = state.record;
    if (!record || !recordSupported()) return;
    record.status = "starting";
    record.result = null;
    record.error = "";
    record.cancelled = false;
    updateRecordUI();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      if (record.cancelled) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      record.stream = stream;
      const mime = pickMimeType();
      record.recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      record.chunks = [];
      record.recorder.addEventListener("dataavailable", (event) => {
        if (event.data && event.data.size) record.chunks.push(event.data);
      });
      record.recorder.addEventListener("stop", () => {
        const type = (record.recorder && record.recorder.mimeType) || mime || "audio/webm";
        const blob = new Blob(record.chunks, { type });
        stopStream(record);
        if (!record.cancelled) sendRecording(blob, type);
      });
      record.recorder.start(250);
      record.status = "recording";
      record.startedAt = Date.now();
      record.timer = setInterval(() => {
        const elapsed = Math.floor((Date.now() - record.startedAt) / 1000);
        record.refs.timer.textContent = `${String(Math.floor(elapsed / 60)).padStart(2, "0")}:${String(elapsed % 60).padStart(2, "0")}`;
      }, 250);
      startLevels(record, stream);
      updateRecordUI();
    } catch (error) {
      record.status = "error";
      record.error = error && error.name === "NotAllowedError" ? "Microphone permission was denied." : "Could not start the microphone.";
      updateRecordUI();
    }
  }

  function startLevels(record, stream) {
    try {
      record.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const source = record.audioContext.createMediaStreamSource(stream);
      const analyser = record.audioContext.createAnalyser();
      analyser.fftSize = 128;
      analyser.smoothingTimeConstant = 0.75;
      source.connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);
      const bars = Array.from(record.refs.levels.children);
      const tick = () => {
        if (!state.record || state.record !== record || record.status !== "recording") return;
        analyser.getByteFrequencyData(data);
        bars.forEach((bar, index) => {
          const value = data[Math.min(data.length - 1, Math.floor((index / bars.length) * data.length))] / 255;
          bar.style.height = `${5 + value * 20}px`;
          bar.style.opacity = String(0.35 + value * 0.65);
        });
        record.levelRaf = requestAnimationFrame(tick);
      };
      tick();
    } catch (error) {
      /* levels are decorative */
    }
  }

  function stopStream(record) {
    if (record.timer) {
      clearInterval(record.timer);
      record.timer = null;
    }
    if (record.levelRaf) {
      cancelAnimationFrame(record.levelRaf);
      record.levelRaf = null;
    }
    if (record.stream) {
      record.stream.getTracks().forEach((track) => track.stop());
      record.stream = null;
    }
    if (record.audioContext) {
      record.audioContext.close().catch(() => {});
      record.audioContext = null;
    }
    if (record.refs && record.refs.levels) {
      Array.from(record.refs.levels.children).forEach((bar) => {
        bar.style.height = "5px";
        bar.style.opacity = "0.35";
      });
    }
  }

  function stopRecording() {
    const record = state.record;
    if (!record || !record.recorder) return;
    record.status = "sending";
    updateRecordUI();
    try {
      record.recorder.stop();
    } catch (error) {
      record.status = "error";
      record.error = "Could not stop the recording.";
      updateRecordUI();
    }
  }

  function cleanupRecording(cancelled) {
    const record = state.record;
    if (!record) return;
    record.cancelled = Boolean(cancelled);
    if (record.recorder && record.recorder.state !== "inactive") {
      try {
        record.recorder.stop();
      } catch (error) {
        /* already stopped */
      }
    }
    stopStream(record);
    state.record = null;
  }

  async function sendRecording(blob, mime) {
    const record = state.record;
    if (!record || record.cancelled) return;
    record.status = "sending";
    record.result = null;
    updateRecordUI();
    const extension = String(mime).includes("mp4") ? "m4a" : String(mime).includes("ogg") ? "ogg" : String(mime).includes("wav") ? "wav" : "webm";
    const form = new FormData();
    form.append("file", blob, `recording.${extension}`);
    try {
      const payload = await api("/api/admin/web-transcribe", { method: "POST", form });
      record.result = payload;
      record.status = "done";
      toast(payload.text ? "Transcription ready" : "No speech detected");
      refreshAfterMutation();
    } catch (error) {
      record.status = "error";
      record.error = error.message;
    }
    updateRecordUI();
  }

  function updateRecordUI() {
    const record = state.record;
    if (!record) return;
    const { button, timer, levels, hint, result, fileRow } = record.refs;
    if (!button) return;
    button.classList.toggle("recording", record.status === "recording");
    const supported = recordSupported();
    button.disabled = !supported || record.status === "sending" || record.status === "starting";
    button.replaceChildren(icon(record.status === "recording" ? "stop" : "mic"));
    button.setAttribute("aria-label", record.status === "recording" ? "Stop recording" : "Start recording");
    levels.style.visibility = record.status === "recording" ? "visible" : "hidden";
    if (record.status === "idle") timer.textContent = "00:00";
    fileRow.style.display = record.status === "recording" || record.status === "sending" ? "none" : "";
    if (record.status === "recording") hint.textContent = "Recording… tap to stop.";
    else if (record.status === "starting") hint.textContent = "Opening the microphone…";
    else if (record.status === "sending") hint.textContent = "Transcribing…";
    else if (record.status === "done") hint.textContent = "Done. Record again or upload a file.";
    else if (record.status === "error") hint.textContent = "Something went wrong. Try again.";
    else hint.textContent = supported ? "Tap the microphone, speak, then tap again to stop." : "Upload a recording to transcribe it.";

    replace(result);
    if (record.status === "sending") {
      result.append(h("div", { class: "pair-status", style: "margin-top:14px" }, h("span", { class: "spinner" }), h("span", { text: "Sending audio to Whisper Hub…" })));
    } else if (record.status === "error") {
      result.append(h("div", { class: "insecure-note" }, icon("alert"), h("div", {}, h("strong", { text: "Could not transcribe" }), h("span", { text: record.error }))));
    } else if (record.result) {
      const item = record.result;
      const copy = h("button", { class: "btn btn-secondary btn-sm", type: "button" }, icon("copy"), "Copy");
      copy.addEventListener("click", () => copyText(item.text));
      result.append(
        h("p", { class: "eyebrow", text: item.text ? "Result" : "No speech" }),
        h("div", { class: "record-result-text", text: item.text || "Whisper heard no speech in that recording." }),
        h(
          "div",
          { class: "record-result-meta" },
          h("span", { text: `${languageSummary(item)} · ${formatDuration(item.duration)} · ${formatMs(item.processing_ms)}` }),
          copy
        )
      );
    }
  }

  /* ---------------------------------------------------------------- setup */

  async function loadSetup() {
    try {
      state.setup = await api("/api/admin/setup");
      renderSetup();
    } catch (error) {
      if (error.status !== 401) toast(error.message, "error");
    }
  }

  function renderSetup() {
    const setup = state.setup;
    if (!setup) return;
    $("#setup-api-base").textContent = setup.api_base;
    $("#setup-endpoint").textContent = setup.endpoint;
    $("#setup-model").textContent = setup.model;
    $("#setup-server-model").textContent = setup.server_model || "—";
    $("#setup-url-note").textContent = setup.https_url
      ? `Recommended: ${setup.base_url} (HTTPS). The LAN address ${setup.lan_url} also works for most clients; browser recording needs HTTPS.`
      : `LAN address: ${setup.base_url}. Plain HTTP works for most clients; browser recording needs HTTPS or localhost.`;
    replace(
      $("#setup-endpoints"),
      ...setup.endpoints.map((endpoint) =>
        h(
          "li",
          {},
          h("span", { class: "method", text: endpoint.method }),
          h("div", {}, h("code", { text: endpoint.path }), h("div", { text: endpoint.description }))
        )
      )
    );
    $("#setup-curl").textContent = setup.curl;
    $("#setup-sdk").textContent = setup.sdk_snippet;
    replace(
      $("#guide-list"),
      ...setup.kinds.map((guide, index) => {
        const details = h(
          "details",
          { class: "guide" },
          h(
            "summary",
            {},
            icon(DEVICE_ICONS[guide.kind] || "devices"),
            h("h3", { text: guide.title }),
            h("span", { class: "client", text: guide.client }),
            h("span", { class: "chev" }, icon("chevron"))
          ),
          h(
            "div",
            { class: "guide-body" },
            stepList(guide.steps),
            ...guide.alternatives.map((alternative) =>
              h(
                "details",
                { class: "details", style: "margin-top:12px" },
                h("summary", { text: alternative.title }),
                stepList(alternative.steps)
              )
            )
          )
        );
        if (index === 0) details.open = true;
        return details;
      })
    );
  }

  /* ---------------------------------------------------------------- setup wizard */

  // Measured on the reference GPU at 16 kHz: small + Parakeet, English-only vs hybrid.
  const NON_ENGLISH_NOTE =
    "Measured with small + Parakeet: about 290 MB extra VRAM, 170 MB extra RAM and 0.5 s extra startup. " +
    "An English clip takes about 80 ms longer (135 ms vs 56 ms).";

  const WIZARD_STEPS = ["Password", "Hardware", "Models", "Address", "Finish"];

  function showWizard(token, tokenValid) {
    state.authenticated = false;
    $("#app-shell").hidden = true;
    $("#login-view").hidden = true;
    $("#setup-view").hidden = false;
    state.wizard = {
      token,
      tokenValid,
      step: 1,
      hardware: null,
      passwordSet: false,
      model: "base",
      translateModel: "",
      engine: "whisper",
      nonEnglish: false,
      locked: {},
      publicUrl: location.origin,
      httpsUrl: "",
    };
    if (!tokenValid) {
      renderWizardSteps(1);
      replace(
        $("#wizard-body"),
        h(
          "div",
          { class: "wizard-block" },
          h("h2", { text: "Setup token required" }),
          h("p", {
            text: "Open the setup URL printed in the server log. The same one-time token is in the server's data directory as setup_token (or run `docker logs` for the container).",
          }),
          h("p", { class: "muted", text: "If this instance was just started, copy the URL exactly, including ?token=." }),
          h("button", { class: "btn btn-secondary", type: "button", onclick: () => location.reload() }, "Reload this page")
        )
      );
      return;
    }
    renderWizardStep();
  }

  function renderWizardSteps(current) {
    replace(
      $("#wizard-steps"),
      ...WIZARD_STEPS.map((label, index) =>
        h(
          "li",
          { class: index + 1 === current ? "current" : index + 1 < current ? "done" : "" },
          h("span", { class: "wizard-index", text: String(index + 1) }),
          h("span", { text: label })
        )
      )
    );
  }

  function wizardError(message = "") {
    const node = $("#wizard-error");
    node.textContent = message;
    node.hidden = !message;
  }

  function wizardNav(actions) {
    return h("div", { class: "wizard-actions" }, ...actions);
  }

  function wizardButton(label, onClick, { primary = false, back = false } = {}) {
    const button = h(
      "button",
      { class: `btn ${primary ? "btn-primary" : "btn-secondary"}`, type: "button" },
      back ? icon("arrow") : null,
      label
    );
    button.addEventListener("click", onClick);
    return button;
  }

  function renderWizardStep() {
    const wizard = state.wizard;
    if (!wizard) return;
    wizardError();
    renderWizardSteps(wizard.step);
    const body = $("#wizard-body");
    if (wizard.step === 1) renderWizardPassword(body);
    else if (wizard.step === 2) renderWizardHardware(body);
    else if (wizard.step === 3) renderWizardModels(body);
    else if (wizard.step === 4) renderWizardAddress(body);
    else renderWizardFinish(body);
  }

  function renderWizardPassword(body) {
    const password = h("input", { id: "wizard-password", type: "password", autocomplete: "new-password", minlength: "8", required: "required" });
    const confirm = h("input", { id: "wizard-confirm", type: "password", autocomplete: "new-password", minlength: "8", required: "required" });
    const form = h(
      "form",
      { class: "wizard-block", id: "wizard-password-form" },
      h("h2", { text: "Choose the dashboard password" }),
      h("p", { class: "muted", text: "This password protects the dashboard and settings. It is stored as a scrypt hash." }),
      h("div", { class: "field" }, h("label", { for: "wizard-password", text: "Password" }), password),
      h("div", { class: "field" }, h("label", { for: "wizard-confirm", text: "Confirm password" }), confirm)
    );
    const submit = h("button", { class: "btn btn-primary", type: "submit", form: "wizard-password-form" }, "Continue");
    form.append(wizardNav([submit]));
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      wizardError();
      if (password.value.length < 8) {
        wizardError("Use at least 8 characters.");
        password.focus();
        return;
      }
      if (password.value !== confirm.value) {
        wizardError("The passwords do not match.");
        confirm.focus();
        return;
      }
      submit.disabled = true;
      submit.textContent = "Saving…";
      try {
        await api("/api/setup/password", {
          method: "POST",
          body: { token: state.wizard.token, password: password.value, confirm: confirm.value },
        });
        state.wizard.passwordSet = true;
        state.wizard.step = 2;
        renderWizardStep();
      } catch (error) {
        wizardError(error.message);
      } finally {
        submit.disabled = false;
        submit.textContent = "Continue";
      }
    });
    replace(body, form);
    setTimeout(() => password.focus(), 30);
  }

  async function renderWizardHardware(body) {
    const wizard = state.wizard;
    if (!wizard.hardware) {
      replace(body, h("div", { class: "wizard-block" }, h("h2", { text: "Checking this machine…" }), h("div", { class: "skeleton", style: "height:120px" })));
      try {
        const payload = await api(`/api/setup/hardware?token=${encodeURIComponent(wizard.token)}`);
        wizard.hardware = payload.hardware;
        wizard.catalog = payload.catalog;
        // Env-pinned values win over the hardware recommendation (the server ignores them anyway).
        const pinned = payload.values || {};
        wizard.locked = payload.locked || {};
        wizard.model = pinned.model || payload.hardware.recommended_model;
        wizard.translateModel = "translate_model" in pinned ? pinned.translate_model || "" : payload.hardware.recommended_translate_model;
        if (pinned.english_engine) wizard.engine = pinned.english_engine;
        if ("non_english" in pinned) wizard.nonEnglish = Boolean(pinned.non_english);
        if (pinned.public_url) wizard.publicUrl = pinned.public_url;
        if (pinned.https_url) wizard.httpsUrl = pinned.https_url;
      } catch (error) {
        replace(
          body,
          h("div", { class: "wizard-block" }, h("h2", { text: "Could not read the hardware" }), h("p", { class: "form-error", text: error.message }), wizardNav([wizardButton("Try again", () => renderWizardStep())]))
        );
        return;
      }
    }
    const hardware = wizard.hardware;
    const gpuLines = hardware.gpus.length
      ? hardware.gpus.map((gpu) => `${gpu.name}${gpu.vram_gb ? ` · ${gpu.vram_gb} GB VRAM` : ""}`)
      : ["No CUDA GPU detected"];
    replace(
      body,
      h(
        "div",
        { class: "wizard-block" },
        h("h2", { text: "What this machine can do" }),
        h(
          "dl",
          { class: "detail-meta wizard-meta" },
          h("div", {}, h("dt", { text: "GPU" }), h("dd", { text: gpuLines.join(", ") })),
          h("div", {}, h("dt", { text: "CPU cores" }), h("dd", { text: String(hardware.cpu_cores) })),
          h("div", {}, h("dt", { text: "RAM" }), h("dd", { text: hardware.ram_gb ? `${hardware.ram_gb} GB` : "Unknown" })),
          h("div", {}, h("dt", { text: "Parakeet engine" }), h("dd", { text: hardware.moondream ? "Available" : "Not installed" }))
        ),
        h(
          "div",
          { class: "callout" },
          h("strong", { text: `Recommended main model: ${hardware.recommended_model}` }),
          h("span", {
            text: hardware.has_cuda
              ? "A GPU is available, so a larger model is practical. You can pick a different one in the next step."
              : "CPU-only machines work best with a small model. You can pick a different one in the next step.",
          })
        ),
        wizardNav([
          wizardButton("Back", () => {
            state.wizard.step = 1;
            renderWizardStep();
          }, { back: true }),
          wizardButton("Continue", () => {
            state.wizard.step = 3;
            renderWizardStep();
          }, { primary: true }),
        ])
      )
    );
  }

  function translatableModels(catalog) {
    return (catalog || []).filter((model) => model.can_translate);
  }

  function renderWizardModels(body) {
    const wizard = state.wizard;
    const hardware = wizard.hardware;
    const catalog = wizard.catalog || [];
    const mainModels = wizard.nonEnglish
      ? catalog
      : [...catalog].sort((a, b) => Number(b.id.endsWith(".en")) - Number(a.id.endsWith(".en")));
    const mainSelect = h(
      "select",
      { id: "wizard-model" },
      ...mainModels.map((model) => new Option(`${model.label} · about ${model.download_mb} MB download`, model.id, false, model.id === wizard.model))
    );
    const translationSelect = h("select", { id: "wizard-translate-model" });
    const nonEnglish = h("input", {
      id: "wizard-non-english",
      type: "checkbox",
      checked: wizard.nonEnglish ? true : null,
    });
    const engineSelect = h(
      "select",
      { id: "wizard-engine" },
      new Option("Whisper (built in)", "whisper", false, wizard.engine === "whisper"),
      ...(hardware.moondream ? [new Option("Parakeet Ultra (optional, faster English)", "parakeet", false, wizard.engine === "parakeet")] : [])
    );
    const modelNote = h("p", { class: "field-note" });
    const translationNote = h("p", { class: "field-note" });
    const parakeetNote = h("p", { class: "field-note disclosure", hidden: wizard.engine !== "parakeet" });

    function syncModels() {
      const main = catalog.find((model) => model.id === mainSelect.value) || {};
      modelNote.textContent = [main.note, main.can_translate ? "" : "This model cannot translate."].filter(Boolean).join(" ");
      const options = [];
      if (main.can_translate) options.push(new Option("Same as the main model", "", false, wizard.translateModel === ""));
      for (const model of translatableModels(catalog)) options.push(new Option(model.label, model.id, false, model.id === wizard.translateModel));
      translationSelect.replaceChildren(...options);
      if (!main.can_translate && (wizard.translateModel === "" || !options.some((option) => option.value === wizard.translateModel))) {
        wizard.translateModel = wizard.hardware.recommended_translate_model || "medium";
      }
      translationSelect.value = wizard.translateModel;
      if (translationSelect.value !== wizard.translateModel) translationSelect.value = options.length ? options[0].value : "";
      translationNote.textContent = main.can_translate
        ? "Optional. Keep “Same as the main model” unless you want a stronger translator."
        : "Required: the main model cannot translate non-English audio.";
    }
    const translateField = h(
      "div",
      { class: "field" },
      h("label", { for: "wizard-translate-model", text: "Translation model" }),
      translationSelect,
      translationNote
    );
    const nonEnglishField = h(
      "div",
      { class: "field" },
      h("label", { for: "wizard-non-english", text: "Non-English speech (detect language and translate to English)" }),
      nonEnglish,
      h("p", { class: "field-note", text: NON_ENGLISH_NOTE }),
      "non_english" in wizard.locked
        ? h("p", { class: "field-note env-lock", text: `set by ${wizard.locked.non_english}` })
        : null
    );
    if ("non_english" in wizard.locked) nonEnglish.disabled = true;

    function syncEnglishOnly() {
      wizard.nonEnglish = nonEnglish.checked;
      translateField.hidden = !nonEnglish.checked;
      if (nonEnglish.checked) syncModels();
    }
    mainSelect.addEventListener("change", () => {
      wizard.model = mainSelect.value;
      syncModels();
    });
    translationSelect.addEventListener("change", () => {
      wizard.translateModel = translationSelect.value;
    });
    nonEnglish.addEventListener("change", syncEnglishOnly);
    engineSelect.addEventListener("change", () => {
      wizard.engine = engineSelect.value;
      parakeetNote.hidden = wizard.engine !== "parakeet";
    });
    syncModels();
    syncEnglishOnly();

    if (!hardware.moondream) {
      parakeetNote.hidden = true;
    }
    parakeetNote.textContent =
      "Parakeet Ultra uses a proprietary runtime (M87 Labs licence) and sends usage telemetry (hostname, GPU, request counts; never audio or transcript text) to api.moondream.ai. Enable it only if that is acceptable.";

    replace(
      body,
      h(
        "div",
        { class: "wizard-block" },
        h("h2", { text: "Pick the models" }),
        h("p", { class: "muted", text: "You can change all of this later in Settings. English-only speech is the default; enabling non-English speech adds language detection and translation." }),
        h("div", { class: "field" }, h("label", { for: "wizard-model", text: "Main model" }), mainSelect, modelNote),
        nonEnglishField,
        translateField,
        h("div", { class: "field" }, h("label", { for: "wizard-engine", text: "English engine" }), engineSelect, parakeetNote),
        wizardNav([
          wizardButton("Back", () => {
            state.wizard.step = 2;
            renderWizardStep();
          }, { back: true }),
          wizardButton("Continue", () => {
            state.wizard.model = mainSelect.value;
            state.wizard.translateModel = translationSelect.value;
            state.wizard.engine = engineSelect.value;
            state.wizard.step = 4;
            renderWizardStep();
          }, { primary: true }),
        ])
      )
    );
  }

  function renderWizardAddress(body) {
    const wizard = state.wizard;
    const publicUrl = h("input", { id: "wizard-public-url", type: "url", value: wizard.publicUrl, placeholder: "http://hub.example.lan:8765", required: "required" });
    const httpsUrl = h("input", { id: "wizard-https-url", type: "url", value: wizard.httpsUrl, placeholder: "https://whisper.example.com" });
    replace(
      body,
      h(
        "form",
        { class: "wizard-block", id: "wizard-address-form" },
        h("h2", { text: "How devices reach this hub" }),
        h("p", { class: "muted", text: "The public URL is put into pairing links and the client guides. The HTTPS URL is optional; use it when a reverse proxy terminates TLS. Browser recording needs HTTPS or localhost." }),
        h("div", { class: "field" }, h("label", { for: "wizard-public-url", text: "Public URL" }), publicUrl),
        h("div", { class: "field" }, h("label", { for: "wizard-https-url", text: "HTTPS URL (optional)" }), httpsUrl),
        wizardNav([
          wizardButton("Back", () => {
            state.wizard.step = 3;
            renderWizardStep();
          }, { back: true }),
          h("button", { class: "btn btn-primary", type: "submit", form: "wizard-address-form" }, "Continue"),
        ])
      )
    );
    $("#wizard-address-form").addEventListener("submit", (event) => {
      event.preventDefault();
      wizardError();
      try {
        const value = new URL(publicUrl.value);
        if (!["http:", "https:"].includes(value.protocol)) throw new Error();
      } catch (error) {
        wizardError("Enter a full http:// or https:// public URL.");
        return;
      }
      if (httpsUrl.value.trim()) {
        try {
          const value = new URL(httpsUrl.value);
          if (!["http:", "https:"].includes(value.protocol)) throw new Error();
        } catch (error) {
          wizardError("Enter a full http:// or https:// HTTPS URL, or leave it empty.");
          return;
        }
      }
      state.wizard.publicUrl = publicUrl.value.trim();
      state.wizard.httpsUrl = httpsUrl.value.trim();
      state.wizard.step = 5;
      renderWizardStep();
    });
  }

  function renderWizardFinish(body) {
    const wizard = state.wizard;
    const main = (wizard.catalog || []).find((model) => model.id === wizard.model);
    const translate = (wizard.catalog || []).find((model) => model.id === wizard.translateModel);
    const finish = h("button", { class: "btn btn-primary", type: "button" }, "Finish setup");
    finish.addEventListener("click", async () => {
      finish.disabled = true;
      finish.textContent = "Starting models…";
      wizardError();
      try {
        await api("/api/setup/finish", {
          method: "POST",
          body: {
            token: wizard.token,
            model: wizard.model,
            translate_model: wizard.translateModel,
            english_engine: wizard.engine,
            non_english: wizard.nonEnglish,
            public_url: wizard.publicUrl,
            https_url: wizard.httpsUrl,
          },
        });
        location.assign("/");
      } catch (error) {
        wizardError(error.message);
        finish.disabled = false;
        finish.textContent = "Finish setup";
      }
    });
    replace(
      body,
      h(
        "div",
        { class: "wizard-block" },
        h("h2", { text: "Ready to start" }),
        h(
          "dl",
          { class: "detail-meta wizard-meta" },
          h("div", {}, h("dt", { text: "Main model" }), h("dd", { text: main ? main.label : wizard.model })),
          h("div", {}, h("dt", { text: "Non-English speech" }), h("dd", { text: wizard.nonEnglish ? "Enabled" : "Off (English-only)" })),
          h("div", {}, h("dt", { text: "Translation model" }), h("dd", { text: wizard.nonEnglish ? (translate ? translate.label : wizard.translateModel || "Same as main") : "Not used" })),
          h("div", {}, h("dt", { text: "English engine" }), h("dd", { text: wizard.engine === "parakeet" ? "Parakeet Ultra" : "Whisper" })),
          h("div", {}, h("dt", { text: "Public URL" }), h("dd", { text: wizard.publicUrl })),
          h("div", {}, h("dt", { text: "HTTPS URL" }), h("dd", { text: wizard.httpsUrl || "Not set" }))
        ),
        h("p", { class: "muted", text: "Finishing signs you in and starts the model download in the background. The dashboard shows its progress." }),
        wizardNav([
          wizardButton("Back", () => {
            state.wizard.step = 4;
            renderWizardStep();
          }, { back: true }),
          finish,
        ])
      )
    );
  }

  /* ---------------------------------------------------------------- settings */

  const SETTING_GROUPS = [
    {
      title: "Models",
      fields: [
        { name: "model", label: "Main model", type: "model", note: "Used for English transcription. English-only .en models are listed first while non-English speech is off." },
        { name: "non_english", label: "Non-English speech (detect language and translate to English)", type: "checkbox", note: NON_ENGLISH_NOTE },
        { name: "translate_model", label: "Translation model", type: "translate", note: "Used for non-English audio. Must be able to translate." },
        { name: "english_engine", label: "English engine", type: "select", options: ["whisper", "parakeet"], note: "Parakeet is optional and needs the parakeet extra." },
      ],
    },
    {
      title: "Inference",
      fields: [
        { name: "device", label: "Device", type: "select", options: ["auto", "cpu", "cuda"] },
        { name: "compute_type", label: "Compute type", type: "select", options: ["auto", "int8", "int8_float16", "int8_float32", "float16", "float32"] },
        { name: "beam_size", label: "Beam size", type: "number", min: 1, max: 10 },
        { name: "translate_beam_size", label: "Translation beam size", type: "number", min: 1, max: 10, note: "Used only when translating non-English audio." },
        { name: "cpu_threads", label: "CPU threads (0 = auto)", type: "number", min: 0 },
        { name: "max_concurrency", label: "Max concurrent requests", type: "number", min: 1, max: 32 },
        { name: "model_idle_unload_seconds", label: "Idle unload (seconds, 0 = never)", type: "number", min: 0, step: 1 },
        { name: "max_upload_mb", label: "Max upload (MB)", type: "number", min: 1, max: 4096 },
        { name: "lang_confidence", label: "Language confidence threshold", type: "number", min: 0, max: 1, step: 0.05 },
        { name: "honor_client_language", label: "Honor the language sent by clients", type: "checkbox" },
      ],
    },
    {
      title: "Address",
      fields: [
        { name: "public_url", label: "Public URL", type: "url", note: "Used in pairing links and guides. Leave empty to use the request host." },
        { name: "https_url", label: "HTTPS URL", type: "url", note: "Optional reverse-proxy URL recommended to clients." },
      ],
    },
  ];

  async function loadSettings() {
    try {
      state.settings = await api("/api/admin/settings");
      renderSettings();
    } catch (error) {
      if (error.status !== 401) toast(error.message, "error");
    }
  }

  function renderSettings() {
    const settings = state.settings;
    if (!settings) return;
    const values = settings.values;
    const locked = settings.locked || {};
    const catalog = settings.catalog || [];
    const refs = new Map();
    const containers = [];
    for (const group of SETTING_GROUPS) {
      const fields = h("div", { class: "settings-fields" });
      for (const field of group.fields) {
        const id = `setting-${field.name}`;
        const isLocked = Boolean(locked[field.name]);
        let input;
        if (field.type === "model") {
          input = h("select", { id });
          // English-only checkpoints are the better default when nothing is translated;
          // multilingual models stay selectable.
          const models = values.non_english
            ? catalog
            : [...catalog].sort((a, b) => Number(b.id.endsWith(".en")) - Number(a.id.endsWith(".en")));
          const options = models.map((model) => new Option(`${model.label} (${model.download_mb} MB)`, model.id));
          if (!catalog.some((model) => model.id === values[field.name])) options.unshift(new Option(String(values[field.name]), values[field.name]));
          input.append(...options);
          input.value = values[field.name];
        } else if (field.type === "translate") {
          input = h("select", { id });
        } else if (field.type === "select") {
          let options = [...field.options];
          if (field.name === "english_engine" && !settings.parakeet_available && values[field.name] !== "parakeet") {
            options = options.filter((option) => option !== "parakeet");
          }
          if (!options.includes(values[field.name])) options.push(String(values[field.name]));
          input = h("select", { id }, ...options.map((option) => new Option(option, option)));
          input.value = values[field.name];
        } else if (field.type === "checkbox") {
          input = h("input", { id, type: "checkbox", checked: Boolean(values[field.name]) ? true : null });
        } else {
          input = h("input", {
            id,
            type: field.type === "number" ? "number" : "url",
            value: values[field.name] === "" ? "" : String(values[field.name]),
            min: field.min,
            max: field.max,
            step: field.step,
            placeholder: field.type === "url" ? "https://…" : "",
          });
        }
        input.dataset.setting = field.name;
        if (isLocked) {
          input.disabled = true;
          input.setAttribute("aria-describedby", `${id}-locked`);
        }
        const wrap = h(
          "div",
          { class: "field" },
          h("label", { for: id, text: field.label }),
          input,
          field.note ? h("p", { class: "field-note", text: field.note }) : null,
          isLocked ? h("p", { class: "field-note env-lock", id: `${id}-locked`, text: `set by ${locked[field.name]}` }) : null
        );
        fields.append(wrap);
        refs.set(field.name, { input, type: field.type, field, wrap });
      }
      const panel = h(
        "section",
        { class: "settings-group" },
        h("h3", { text: group.title }),
        fields
      );
      containers.push(panel);
    }

    function syncTranslation() {
      const mainValue = refs.get("model").input.value;
      const main = catalog.find((model) => model.id === mainValue);
      const translateInput = refs.get("translate_model").input;
      if (translateInput.disabled) {
        const lockedValue = values.translate_model || "";
        translateInput.replaceChildren(
          new Option(lockedValue || "Same as the main model", lockedValue)
        );
        translateInput.value = lockedValue;
        return;
      }
      const current = values.translate_model;
      const options = [];
      if (!main || main.can_translate) options.push(new Option("Same as the main model", ""));
      for (const model of catalog.filter((entry) => entry.can_translate)) {
        options.push(new Option(model.label, model.id));
      }
      translateInput.replaceChildren(...options);
      let desired = translateInput.dataset.chosen ?? current ?? "";
      if (main && !main.can_translate && !desired) desired = "medium";
      if (!options.some((option) => option.value === desired)) desired = options.length ? options[0].value : "";
      translateInput.value = desired;
      translateInput.dataset.chosen = desired;
    }
    const modelInput = refs.get("model").input;
    modelInput.addEventListener("change", () => {
      refs.get("translate_model").input.dataset.chosen = "";
      syncTranslation();
    });
    refs.get("translate_model").input.addEventListener("change", (event) => {
      event.target.dataset.chosen = event.target.value;
    });
    syncTranslation();

    const nonEnglishOnlyFields = [
      "translate_model",
      "translate_beam_size",
      "lang_confidence",
      "honor_client_language",
    ];
    function syncNonEnglish() {
      const enabled = refs.get("non_english").input.checked;
      for (const name of nonEnglishOnlyFields) {
        const ref = refs.get(name);
        if (ref) ref.wrap.hidden = !enabled;
      }
      if (enabled) syncTranslation();
    }
    refs.get("non_english").input.addEventListener("change", syncNonEnglish);
    syncNonEnglish();

    replace($("#settings-fields"), ...containers);
    $("#settings-save-note").textContent = "";
    $("#settings-save").disabled = false;

    const envPassword = settings.password_from_env;
    $("#password-env-note").hidden = !envPassword;
    for (const id of ["#current-password", "#new-password", "#confirm-password", "#password-save"]) {
      $(id).disabled = Boolean(envPassword);
    }
    $("#server-meta").replaceChildren(
      h("div", {}, h("dt", { text: "Version" }), h("dd", { text: settings.server.version })),
      h("div", {}, h("dt", { text: "Listen" }), h("dd", { text: `${settings.server.host}:${settings.server.port}` })),
      h("div", {}, h("dt", { text: "Data directory" }), h("dd", { text: settings.server.data_dir })),
      h("div", {}, h("dt", { text: "Config source" }), h("dd", { text: Object.keys(locked).length ? `Environment overrides ${Object.values(locked).join(", ")}` : "Web UI" }))
    );
    renderModelStatus(settings.model_status);
  }

  async function saveSettings(event) {
    event.preventDefault();
    const settings = state.settings;
    if (!settings) return;
    const button = $("#settings-save");
    const note = $("#settings-save-note");
    const payload = {};
    $$("#settings-fields [data-setting]").forEach((input) => {
      if (input.disabled) return;
      const field = input.dataset.setting;
      if (input.type === "checkbox") payload[field] = input.checked;
      else if (["beam_size", "translate_beam_size", "cpu_threads", "max_concurrency", "max_upload_mb", "model_idle_unload_seconds", "lang_confidence"].includes(field)) {
        // An emptied number box means "leave unchanged", not 0 (0 disables some features).
        if (input.value.trim() !== "") payload[field] = Number(input.value);
      }
      else payload[field] = input.value.trim();
    });
    button.disabled = true;
    note.textContent = "Saving…";
    try {
      const response = await api("/api/admin/settings", { method: "POST", body: payload });
      state.settings = response;
      renderSettings();
      note.textContent = response.reload_requested ? "Saved. The new model is loading in the background." : "Saved.";
      toast(response.reload_requested ? "Settings saved; model loading" : "Settings saved");
      if (response.reload_requested) pollModelStatus();
      refreshAfterMutation();
    } catch (error) {
      note.textContent = "";
      toast(error.message, "error");
      button.disabled = false;
    }
  }

  function statusLabelFor(stateName) {
    return { ready: "Ready", idle: "Idle", downloading: "Downloading", loading: "Loading", error: "Error" }[stateName] || "Unknown";
  }

  function renderModelStatus(status) {
    if (!status) return;
    state.modelStatus = status;
    const chip = $("#model-status");
    if (chip) {
      chip.className = `model-chip ${status.state || "idle"}`;
      const text = chip.querySelector(".model-status-text");
      if (text) {
        const model = status.model || "Model";
        text.textContent = status.state === "error" ? "Model error" : status.state === "ready" ? `${model} · ${String(status.device || "cpu").toUpperCase()}` : `${statusLabelFor(status.state)} ${model}…`;
      }
      chip.title = status.message || `Model: ${status.state}`;
    }
    const badge = $("#settings-model-badge");
    if (badge) {
      badge.className = `model-badge ${status.state || "idle"}`;
      badge.textContent = `${statusLabelFor(status.state)}${status.device ? ` · ${String(status.device).toUpperCase()}` : ""}`;
    }
    const title = $("#status-title");
    if (title) {
      title.textContent = statusLabelFor(status.state);
      $("#status-message").textContent = status.message || "";
      $("#status-led").className = `status-led ${status.state || "idle"}`;
      const wrap = $("#status-progress-wrap");
      const bar = $("#status-progress");
      if (status.progress !== null && status.progress !== undefined && status.state !== "ready") {
        wrap.hidden = false;
        bar.style.width = `${Math.max(0, Math.min(100, status.progress))}%`;
      } else {
        wrap.hidden = true;
      }
      replace(
        $("#status-meta"),
        h("div", {}, h("dt", { text: "Main model" }), h("dd", { text: status.model || "—" })),
        h("div", {}, h("dt", { text: "Translation" }), h("dd", { text: status.non_english === false ? "Off (English-only)" : status.translate_model || status.model || "—" })),
        h("div", {}, h("dt", { text: "Device" }), h("dd", { text: status.device || "—" })),
        h("div", {}, h("dt", { text: "Compute" }), h("dd", { text: status.compute_type || "—" })),
        h("div", {}, h("dt", { text: "Loaded" }), h("dd", { text: (status.loaded_models || []).join(", ") || "None" }))
      );
    }
  }

  function renderModelStatusFromStats() {
    if (state.stats && state.stats.model_status) renderModelStatus(state.stats.model_status);
  }

  function syncModelStatusFromStats() {
    // The stats payload carries model_status; only older backends need the
    // dedicated endpoint.
    if (state.stats && state.stats.model_status) renderModelStatusFromStats();
    else refreshModelStatus();
  }

  async function refreshModelStatus() {
    if (!state.authenticated) return;
    try {
      const status = await api("/api/admin/model-status");
      renderModelStatus(status);
    } catch (error) {
      /* status is best effort */
    }
  }

  function pollModelStatus() {
    if (state.modelTimer) clearTimeout(state.modelTimer);
    const tick = async () => {
      if (!state.authenticated) return;
      await refreshModelStatus();
      const current = state.modelStatus && state.modelStatus.state;
      if (current === "downloading" || current === "loading") {
        state.modelTimer = setTimeout(tick, 2000);
      } else {
        state.modelTimer = null;
      }
    };
    state.modelTimer = setTimeout(tick, 500);
  }

  function renderFirstDeviceCta() {
    const cta = $("#first-device-cta");
    if (!cta) return;
    const realDevices = state.devices.filter((device) => !device.builtin && !device.deleted);
    cta.hidden = realDevices.length > 0;
  }

  async function changePassword(event) {
    event.preventDefault();
    const error = $("#password-error");
    error.hidden = true;
    const current = $("#current-password").value;
    const next = $("#new-password").value;
    const confirm = $("#confirm-password").value;
    if (next.length < 8) {
      error.textContent = "Use at least 8 characters.";
      error.hidden = false;
      return;
    }
    if (next !== confirm) {
      error.textContent = "The passwords do not match.";
      error.hidden = false;
      return;
    }
    try {
      await api("/api/admin/password", {
        method: "POST",
        body: { current_password: current, new_password: next, confirm },
      });
      $("#password-form").reset();
      toast("Password changed");
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
    }
  }

  async function signOutAll() {
    const confirmed = await confirmAction({
      title: "Sign out all sessions?",
      message: "The session secret is rotated. Every dashboard session, including this one, must sign in again.",
      confirmLabel: "Sign out all",
      danger: true,
    });
    if (!confirmed) return;
    try {
      await api("/api/admin/logout-all", { method: "POST" });
    } catch (error) {
      /* the current cookie is already invalid when rotation succeeds */
    }
    showLogin("All sessions were signed out. Sign in again.");
  }

  function deleteAllHistory() {
    const input = h("input", { id: "delete-confirm", type: "text", autocomplete: "off", placeholder: "DELETE" });
    const confirmButton = h("button", { class: "btn btn-danger", type: "button", disabled: true }, "Delete all history");
    input.addEventListener("input", () => {
      confirmButton.disabled = input.value !== "DELETE";
    });
    confirmButton.addEventListener("click", async () => {
      if (input.value !== "DELETE") return;
      confirmButton.disabled = true;
      try {
        const response = await api("/api/admin/history?confirm=DELETE", { method: "DELETE" });
        closeModal();
        toast(`${response.deleted} transcript${response.deleted === 1 ? "" : "s"} deleted`);
        state.history.loaded = false;
        refreshAfterMutation();
      } catch (error) {
        toast(error.message, "error");
        confirmButton.disabled = false;
      }
    });
    const cancel = h("button", { class: "btn btn-secondary", type: "button" }, "Cancel");
    cancel.addEventListener("click", closeModal);
    openModal({
      title: "Delete all history",
      body: h(
        "div",
        {},
        h("p", { text: "This removes every transcript from every device. Devices and keys stay linked. This cannot be undone." }),
        h("div", { class: "field" }, h("label", { for: "delete-confirm", text: "Type DELETE to confirm" }), input)
      ),
      footer: [cancel, confirmButton],
    });
    setTimeout(() => input.focus(), 30);
  }

  /* ---------------------------------------------------------------- static events */

  function bindStaticEvents() {
    $("#login-form").addEventListener("submit", login);
    $("#logout-button").addEventListener("click", logout);
    $("#theme-button").addEventListener("click", cycleTheme);
    $("#record-button").addEventListener("click", openRecordModal);
    $("#model-status").addEventListener("click", () => {
      if (state.authenticated) navigate("settings");
    });
    $("#settings-form").addEventListener("submit", saveSettings);
    $("#password-form").addEventListener("submit", changePassword);
    $("#logout-all").addEventListener("click", signOutAll);
    $("#delete-history").addEventListener("click", deleteAllHistory);
    $("#load-more").addEventListener("click", () => loadHistory(false));
    $("#copy-curl").addEventListener("click", () => state.setup && copyText(state.setup.curl, "curl command copied"));
    $("#copy-sdk").addEventListener("click", () => state.setup && copyText(state.setup.sdk_snippet, "SDK example copied"));

    $("#history-search").addEventListener("input", (event) => {
      const value = event.target.value.trim();
      state.history.q = value;
      $("#history-clear").hidden = !event.target.value;
      clearTimeout(state.searchTimer);
      state.searchTimer = setTimeout(() => loadHistory(true), 200);
    });
    $("#history-clear").addEventListener("click", () => {
      $("#history-search").value = "";
      $("#history-clear").hidden = true;
      state.history.q = "";
      loadHistory(true);
      $("#history-search").focus();
    });
    $("#history-device").addEventListener("change", (event) => {
      state.history.deviceId = event.target.value;
      loadHistory(true);
    });

    document.addEventListener("click", (event) => {
      const copy = event.target.closest("[data-copy], [data-copy-target]");
      if (copy) {
        event.preventDefault();
        const value = copy.dataset.copy !== undefined ? copy.dataset.copy : (document.getElementById(copy.dataset.copyTarget) || {}).textContent || "";
        if (value) copyText(value);
        return;
      }
      const target = event.target.closest("[data-close]");
      if (target) {
        if (target.dataset.close === "modal-root") closeModal();
        else if (target.dataset.close === "entry-overlay") closeEntry();
        return;
      }
      if (event.target.id === "modal-root") closeModal();
      if (event.target.id === "entry-overlay") closeEntry();
      const action = event.target.closest('[data-action="add-device"]');
      if (action) openAddDevice();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeEverything();
    });

    window.addEventListener("hashchange", () => {
      if (state.authenticated) showView(routeName(), { scroll: true });
    });

    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && state.authenticated) refreshLive();
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();

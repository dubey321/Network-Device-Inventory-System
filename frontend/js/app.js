/* Rackline — frontend application logic
   Talks to the Flask REST API at /api/* (same origin). */

const API = "/api";

const state = {
  devices: [],
  locations: [],
  stats: null,
  filters: { q: "", type: "", status: "", location_id: "" },
  editingDeviceId: null,
  editingLocationId: null,
};

const DEVICE_TYPES = ["router", "switch", "firewall", "access_point", "server",
                       "load_balancer", "printer", "ups", "other"];
const STATUSES = ["active", "maintenance", "offline", "decommissioned"];
const IP_TYPES = ["management", "primary", "secondary", "vlan"];

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function prettify(str) {
  return (str || "").replace(/_/g, " ");
}

// -------------------------------------------------------------- API calls

async function apiRequest(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let body = null;
  try { body = await res.json(); } catch (_) { /* no body */ }
  if (!res.ok) {
    const message = (body && body.error) || `Request failed (${res.status})`;
    throw new Error(message);
  }
  return body;
}

const Api = {
  health: () => apiRequest("/health"),
  stats: () => apiRequest("/stats"),
  listDevices: (params) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v));
    return apiRequest(`/devices?${qs.toString()}`);
  },
  getDevice: (id) => apiRequest(`/devices/${id}`),
  createDevice: (data) => apiRequest("/devices", { method: "POST", body: JSON.stringify(data) }),
  updateDevice: (id, data) => apiRequest(`/devices/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteDevice: (id) => apiRequest(`/devices/${id}`, { method: "DELETE" }),
  addIp: (deviceId, data) => apiRequest(`/devices/${deviceId}/ips`, { method: "POST", body: JSON.stringify(data) }),
  deleteIp: (ipId) => apiRequest(`/ips/${ipId}`, { method: "DELETE" }),
  listLocations: () => apiRequest("/locations"),
  createLocation: (data) => apiRequest("/locations", { method: "POST", body: JSON.stringify(data) }),
  updateLocation: (id, data) => apiRequest(`/locations/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteLocation: (id) => apiRequest(`/locations/${id}`, { method: "DELETE" }),
};

// ---------------------------------------------------------------- toasts

function toast(message, isError = false) {
  const rail = $("#toast-rail");
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " error" : "");
  el.textContent = message;
  rail.appendChild(el);
  setTimeout(() => el.remove(), 3600);
}

// ------------------------------------------------------------ navigation

function setView(view) {
  $$(".view").forEach((v) => (v.hidden = true));
  $(`#view-${view}`).hidden = false;
  $$(".rail-port").forEach((btn) => btn.classList.toggle("active", btn.dataset.view === view));
  if (view === "devices") loadDevices();
  if (view === "dashboard") loadStats();
  if (view === "locations") loadLocations();
}

$$(".rail-port").forEach((btn) => btn.addEventListener("click", () => setView(btn.dataset.view)));

// --------------------------------------------------------------- health

async function checkHealth() {
  const indicator = $("#api-indicator");
  try {
    await Api.health();
    indicator.classList.add("ok");
    indicator.classList.remove("down");
    indicator.innerHTML = '<span class="dot"></span> connected';
  } catch (e) {
    indicator.classList.add("down");
    indicator.classList.remove("ok");
    indicator.innerHTML = '<span class="dot"></span> unreachable';
  }
}

// ------------------------------------------------------------- dashboard

async function loadStats() {
  try {
    state.stats = await Api.stats();
    renderStatusStrip();
    renderDashboard();
  } catch (e) {
    toast("Could not load stats: " + e.message, true);
  }
}

function renderStatusStrip() {
  const s = state.stats;
  if (!s) return;
  const byStatus = Object.fromEntries(s.by_status.map((x) => [x.status, x.count]));
  $("#stat-total").textContent = s.total_devices;
  $("#stat-active").textContent = byStatus.active || 0;
  $("#stat-maintenance").textContent = byStatus.maintenance || 0;
  $("#stat-offline").textContent = byStatus.offline || 0;
  $("#stat-locations").textContent = s.total_locations;

  const offlineChip = document.querySelector('.strip-chip[data-stat="offline"]');
  offlineChip.classList.toggle("has-fault", (byStatus.offline || 0) > 0);
}

function renderBarChart(container, rows, labelKey, countKey) {
  const max = Math.max(1, ...rows.map((r) => r[countKey]));
  container.innerHTML = rows.length
    ? rows.map((r) => `
        <div class="bar-row">
          <div class="bar-row-label">${prettify(r[labelKey])}</div>
          <div class="bar-track"><div class="bar-fill" style="width:${(r[countKey] / max) * 100}%"></div></div>
          <div class="bar-row-count">${r[countKey]}</div>
        </div>`).join("")
    : `<p class="attention-empty">Nothing recorded yet.</p>`;
}

function renderDashboard() {
  const s = state.stats;
  renderBarChart($("#chart-type"), s.by_type, "device_type", "count");
  renderBarChart($("#chart-location"), s.by_location, "location", "count");

  // "needs attention": devices not in active status, pulled from full list
  Api.listDevices({}).then((devices) => {
    const flagged = devices.filter((d) => d.status !== "active");
    const list = $("#attention-list");
    list.innerHTML = flagged.length
      ? flagged.map((d) => `
          <div class="attention-row">
            <span class="led-dot status-${d.status}" style="background:var(--${statusColorVar(d.status)})"></span>
            <span class="a-host">${escapeHtml(d.hostname)}</span>
            <span class="a-note">${prettify(d.status)}${d.location_name ? " · " + escapeHtml(d.location_name) : ""}</span>
          </div>`).join("")
      : `<p class="attention-empty">Everything is active. Nice patch panel.</p>`;
  });
}

function statusColorVar(status) {
  return { active: "uplink", maintenance: "amber", offline: "fault", decommissioned: "decom" }[status] || "decom";
}

// --------------------------------------------------------------- devices

function populateFilterOptions() {
  const typeSel = $("#filter-type");
  const statusSel = $("#filter-status");
  const locSel = $("#filter-location");

  DEVICE_TYPES.forEach((t) => typeSel.add(new Option(prettify(t), t)));
  STATUSES.forEach((s) => statusSel.add(new Option(prettify(s), s)));

  const fDeviceType = $("#f-device_type");
  const fStatus = $("#f-status");
  DEVICE_TYPES.forEach((t) => fDeviceType.add(new Option(prettify(t), t)));
  STATUSES.forEach((s) => fStatus.add(new Option(prettify(s), s)));
}

function refreshLocationSelects() {
  const locSel = $("#filter-location");
  const fLoc = $("#f-location_id");
  [locSel, fLoc].forEach((sel) => {
    const keepFirst = sel.options[0];
    sel.innerHTML = "";
    sel.add(keepFirst);
  });
  state.locations.forEach((loc) => {
    locSel.add(new Option(loc.name, loc.id));
    fLoc.add(new Option(loc.name, loc.id));
  });
}

async function loadDevices() {
  try {
    const devices = await Api.listDevices(state.filters);
    state.devices = devices;
    renderDeviceTable();
  } catch (e) {
    toast("Could not load devices: " + e.message, true);
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function renderDeviceTable() {
  const tbody = $("#device-tbody");
  const devices = state.devices;
  $("#devices-empty").hidden = devices.length !== 0;

  tbody.innerHTML = devices.map((d) => {
    const ips = d.ip_addresses || [];
    const ipCell = ips.length
      ? ips.map((ip, i) => `<span class="${i === 0 ? "ip-primary" : ""}">${escapeHtml(ip.ip_address)}</span>`).join(", ")
      : "—";
    return `
      <tr data-id="${d.id}">
        <td class="col-led"><span class="row-led status-${d.status}"></span></td>
        <td class="hostname-cell">${escapeHtml(d.hostname)}</td>
        <td><span class="type-pill">${prettify(d.device_type)}</span></td>
        <td>${escapeHtml([d.manufacturer, d.model].filter(Boolean).join(" · ") || "—")}</td>
        <td class="mono-cell">${ipCell}</td>
        <td>${escapeHtml(d.location_name || "—")}</td>
        <td><span class="status-cell status-${d.status}"><span class="status-dot"></span>${prettify(d.status)}</span></td>
        <td class="col-actions"><button class="row-delete-btn" data-action="delete" data-id="${d.id}" title="Delete device">🗑</button></td>
      </tr>`;
  }).join("");

  tbody.querySelectorAll("tr").forEach((row) => {
    row.addEventListener("click", (e) => {
      if (e.target.closest("[data-action='delete']")) return;
      openDeviceModal(Number(row.dataset.id));
    });
  });
  tbody.querySelectorAll("[data-action='delete']").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const id = Number(btn.dataset.id);
      const device = state.devices.find((d) => d.id === id);
      if (!confirm(`Delete "${device.hostname}"? This can't be undone.`)) return;
      try {
        await Api.deleteDevice(id);
        toast(`Deleted ${device.hostname}`);
        loadDevices();
        loadStats();
      } catch (err) {
        toast("Delete failed: " + err.message, true);
      }
    });
  });
}

let searchDebounce;
$("#search-input").addEventListener("input", (e) => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    state.filters.q = e.target.value.trim();
    loadDevices();
  }, 250);
});
$("#filter-type").addEventListener("change", (e) => { state.filters.type = e.target.value; loadDevices(); });
$("#filter-status").addEventListener("change", (e) => { state.filters.status = e.target.value; loadDevices(); });
$("#filter-location").addEventListener("change", (e) => { state.filters.location_id = e.target.value; loadDevices(); });

// --------------------------------------------------------- device modal

function ipRowTemplate(ip = {}) {
  const row = document.createElement("div");
  row.className = "ip-row";
  row.innerHTML = `
    <input type="text" class="ip-address" placeholder="10.0.0.1" value="${escapeHtml(ip.ip_address || "")}" />
    <select class="ip-type">${IP_TYPES.map((t) => `<option value="${t}" ${t === (ip.ip_type || "management") ? "selected" : ""}>${prettify(t)}</option>`).join("")}</select>
    <button type="button" class="ip-row-remove" title="Remove">✕</button>
  `;
  row.dataset.ipId = ip.id || "";
  row.querySelector(".ip-row-remove").addEventListener("click", () => row.remove());
  return row;
}

$("#btn-add-ip-row").addEventListener("click", () => {
  $("#ip-rows").appendChild(ipRowTemplate());
});

function openDeviceModal(deviceId = null) {
  state.editingDeviceId = deviceId;
  $("#device-form").reset();
  $("#device-form-error").hidden = true;
  $("#ip-rows").innerHTML = "";

  if (deviceId) {
    const device = state.devices.find((d) => d.id === deviceId);
    $("#device-modal-title").textContent = `Edit ${device.hostname}`;
    $("#device-id").value = device.id;
    $("#f-hostname").value = device.hostname;
    $("#f-device_type").value = device.device_type;
    $("#f-status").value = device.status;
    $("#f-location_id").value = device.location_id || "";
    $("#f-manufacturer").value = device.manufacturer || "";
    $("#f-model").value = device.model || "";
    $("#f-serial_number").value = device.serial_number || "";
    $("#f-mac_address").value = device.mac_address || "";
    $("#f-os_version").value = device.os_version || "";
    $("#f-purchase_date").value = device.purchase_date || "";
    $("#f-warranty_expiry").value = device.warranty_expiry || "";
    $("#f-notes").value = device.notes || "";
    (device.ip_addresses || []).forEach((ip) => $("#ip-rows").appendChild(ipRowTemplate(ip)));
    $("#btn-delete-device").hidden = false;
  } else {
    $("#device-modal-title").textContent = "Add device";
    $("#device-id").value = "";
    $("#f-status").value = "active";
    $("#btn-delete-device").hidden = true;
  }

  $("#device-modal-backdrop").hidden = false;
}

function closeDeviceModal() {
  $("#device-modal-backdrop").hidden = true;
  state.editingDeviceId = null;
}

$("#btn-add-device").addEventListener("click", () => openDeviceModal(null));
$("#device-modal-close").addEventListener("click", closeDeviceModal);
$("#btn-cancel-device").addEventListener("click", closeDeviceModal);
$("#device-modal-backdrop").addEventListener("click", (e) => { if (e.target.id === "device-modal-backdrop") closeDeviceModal(); });

$("#btn-delete-device").addEventListener("click", async () => {
  const id = state.editingDeviceId;
  const device = state.devices.find((d) => d.id === id);
  if (!confirm(`Delete "${device.hostname}"? This can't be undone.`)) return;
  try {
    await Api.deleteDevice(id);
    toast(`Deleted ${device.hostname}`);
    closeDeviceModal();
    loadDevices();
    loadStats();
  } catch (err) {
    toast("Delete failed: " + err.message, true);
  }
});

$("#device-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = $("#device-form-error");
  errorEl.hidden = true;

  const payload = {
    hostname: $("#f-hostname").value.trim(),
    device_type: $("#f-device_type").value,
    status: $("#f-status").value,
    location_id: $("#f-location_id").value || null,
    manufacturer: $("#f-manufacturer").value.trim() || null,
    model: $("#f-model").value.trim() || null,
    serial_number: $("#f-serial_number").value.trim() || null,
    mac_address: $("#f-mac_address").value.trim() || null,
    os_version: $("#f-os_version").value.trim() || null,
    purchase_date: $("#f-purchase_date").value || null,
    warranty_expiry: $("#f-warranty_expiry").value || null,
    notes: $("#f-notes").value.trim() || null,
  };

  const ipRows = $$("#ip-rows .ip-row");
  const newIps = [];
  for (const row of ipRows) {
    const ip_address = row.querySelector(".ip-address").value.trim();
    const ip_type = row.querySelector(".ip-type").value;
    const existingIpId = row.dataset.ipId;
    if (!ip_address) continue;
    if (!existingIpId) newIps.push({ ip_address, ip_type });
  }

  try {
    let device;
    if (state.editingDeviceId) {
      device = await Api.updateDevice(state.editingDeviceId, payload);
      for (const ip of newIps) {
        await Api.addIp(device.id, ip);
      }
      toast(`Saved ${device.hostname}`);
    } else {
      payload.ip_addresses = newIps;
      device = await Api.createDevice(payload);
      toast(`Added ${device.hostname}`);
    }
    closeDeviceModal();
    loadDevices();
    loadStats();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  }
});

// ------------------------------------------------------------ locations

async function loadLocations() {
  try {
    state.locations = await Api.listLocations();
    refreshLocationSelects();
    renderLocationGrid();
  } catch (e) {
    toast("Could not load locations: " + e.message, true);
  }
}

function renderLocationGrid() {
  const grid = $("#location-grid");
  grid.innerHTML = state.locations.map((loc) => {
    const meta = [loc.site, loc.building, loc.room].filter(Boolean).join(" · ");
    return `
      <div class="location-card" data-id="${loc.id}">
        <h3>${escapeHtml(loc.name)}</h3>
        <p class="loc-meta">${escapeHtml(meta || "No address details on file")}</p>
        <div class="loc-count">${loc.device_count}</div>
        <div class="loc-count-label">device${loc.device_count === 1 ? "" : "s"}</div>
      </div>`;
  }).join("") || `<p class="attention-empty">No locations yet — add your first one.</p>`;

  grid.querySelectorAll(".location-card").forEach((card) => {
    card.addEventListener("click", () => openLocationModal(Number(card.dataset.id)));
  });
}

function openLocationModal(locationId = null) {
  state.editingLocationId = locationId;
  $("#location-form").reset();
  $("#location-form-error").hidden = true;

  if (locationId) {
    const loc = state.locations.find((l) => l.id === locationId);
    $("#location-modal-title").textContent = `Edit ${loc.name}`;
    $("#loc-id").value = loc.id;
    $("#loc-name").value = loc.name;
    $("#loc-site").value = loc.site || "";
    $("#loc-building").value = loc.building || "";
    $("#loc-floor").value = loc.floor || "";
    $("#loc-room").value = loc.room || "";
    $("#loc-notes").value = loc.notes || "";
    $("#btn-delete-location").hidden = false;
  } else {
    $("#location-modal-title").textContent = "Add location";
    $("#loc-id").value = "";
    $("#btn-delete-location").hidden = true;
  }
  $("#location-modal-backdrop").hidden = false;
}

function closeLocationModal() {
  $("#location-modal-backdrop").hidden = true;
  state.editingLocationId = null;
}

$("#btn-add-location").addEventListener("click", () => openLocationModal(null));
$("#location-modal-close").addEventListener("click", closeLocationModal);
$("#btn-cancel-location").addEventListener("click", closeLocationModal);
$("#location-modal-backdrop").addEventListener("click", (e) => { if (e.target.id === "location-modal-backdrop") closeLocationModal(); });

$("#btn-delete-location").addEventListener("click", async () => {
  const id = state.editingLocationId;
  const loc = state.locations.find((l) => l.id === id);
  if (!confirm(`Delete location "${loc.name}"? Devices there will become unassigned.`)) return;
  try {
    await Api.deleteLocation(id);
    toast(`Deleted ${loc.name}`);
    closeLocationModal();
    loadLocations();
    loadStats();
  } catch (err) {
    toast("Delete failed: " + err.message, true);
  }
});

$("#location-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = $("#location-form-error");
  errorEl.hidden = true;
  const payload = {
    name: $("#loc-name").value.trim(),
    site: $("#loc-site").value.trim() || null,
    building: $("#loc-building").value.trim() || null,
    floor: $("#loc-floor").value.trim() || null,
    room: $("#loc-room").value.trim() || null,
    notes: $("#loc-notes").value.trim() || null,
  };
  try {
    if (state.editingLocationId) {
      const loc = await Api.updateLocation(state.editingLocationId, payload);
      toast(`Saved ${loc.name}`);
    } else {
      const loc = await Api.createLocation(payload);
      toast(`Added ${loc.name}`);
    }
    closeLocationModal();
    loadLocations();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  }
});

// ------------------------------------------------------------------ init

async function init() {
  populateFilterOptions();
  await checkHealth();
  await loadLocations();
  await loadStats();
  await loadDevices();
  setView("dashboard");
}

init();

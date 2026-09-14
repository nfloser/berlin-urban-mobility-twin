import { escapeHtml, freshnessLabel, isInsideBerlin, statusTone } from "./lib.mjs";

const MAX_TRANSIT_MARKERS = 2500;
const map = L.map("map", { preferCanvas: true }).setView([52.52, 13.405], 11);
L.control.zoom({ position: "topright" }).addTo(map);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

const transitLayer = L.layerGroup().addTo(map);
const detectorLayer = L.layerGroup().addTo(map);
const disruptionLayer = L.layerGroup().addTo(map);
L.control.layers(null, {
  "Transit stops": transitLayer,
  "Traffic detectors": detectorLayer,
  "Published disruptions": disruptionLayer,
}, { position: "topright", collapsed: false }).addTo(map);

const elements = {
  badge: document.querySelector("#system-badge"),
  counts: document.querySelector("#counts"),
  refreshTime: document.querySelector("#refresh-time"),
  warnings: document.querySelector("#warnings"),
  sources: document.querySelector("#sources"),
  reload: document.querySelector("#reload"),
  mapNote: document.querySelector("#map-note"),
};

async function api(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
  return response.json();
}

function setBadge(value) {
  elements.badge.textContent = value === "ok" ? "Operational" : "Degraded";
  elements.badge.className = `badge ${statusTone(value)}`;
}

function metric(value, label) {
  return `<div class="metric"><strong>${Number(value ?? 0).toLocaleString()}</strong><span>${escapeHtml(label)}</span></div>`;
}

function renderCounts(status) {
  const entities = status.entity_counts ?? {};
  const observations = status.observation_counts ?? {};
  elements.counts.innerHTML = [
    metric(entities.stops, "scheduled stops"),
    metric(entities.detectors, "detectors"),
    metric(observations.transit, "realtime records"),
    metric(observations.disruptions, "published disruptions"),
  ].join("");
}

function renderWarnings(snapshot, status) {
  const warnings = [...(snapshot.warnings ?? [])];
  for (const [source, message] of Object.entries(status.source_errors ?? {})) {
    const text = `source ${source} failed: ${message}`;
    if (!warnings.includes(text)) warnings.push(text);
  }
  if (!warnings.length) {
    elements.warnings.innerHTML = '<div class="message good">No source warnings in the current server state.</div>';
    return;
  }
  elements.warnings.innerHTML = warnings
    .map((warning) => `<div class="message warn">${escapeHtml(warning)}</div>`)
    .join("");
}

function renderSources(sources, status) {
  const statuses = status.source_status ?? {};
  elements.sources.innerHTML = sources.map((source) => {
    const freshness = statuses[source.source_id];
    const tone = status.source_errors?.[source.source_id] ? "bad" : statusTone(freshness);
    const label = status.source_errors?.[source.source_id] ? "Error" : freshnessLabel(freshness);
    return `<article class="source">
      <div class="source-top">
        <strong>${escapeHtml(source.dataset_title)}</strong>
        <span class="badge ${tone}">${escapeHtml(label)}</span>
      </div>
      <p>${escapeHtml(source.provider)} · ${escapeHtml(source.licence)}</p>
      <p>${escapeHtml(source.update_frequency ?? "Update frequency not specified")}</p>
    </article>`;
  }).join("");
}

function stopPopup(stop) {
  return `<div class="popup-title">${escapeHtml(stop.name)}</div>
    <div class="popup-meta">Stop ${escapeHtml(stop.stop_id)}<br>Scheduled GTFS location</div>`;
}

function detectorPopup(detector) {
  const provenance = detector.provenance;
  const source = provenance ? `${provenance.dataset_title} · ${provenance.licence}` : "Detector metadata";
  return `<div class="popup-title">${escapeHtml(detector.location_description || detector.detector_id)}</div>
    <div class="popup-meta">${escapeHtml(detector.road || "Road not supplied")} · ${escapeHtml(detector.direction || "Direction not supplied")}<br>${escapeHtml(source)}</div>`;
}

function disruptionPopup(disruption) {
  const qualityWarnings = disruption.quality?.warnings ?? [];
  const validity = [disruption.valid_from, disruption.valid_until].filter(Boolean).join(" → ") || "Validity not supplied";
  return `<div class="popup-title">${escapeHtml(disruption.category)}</div>
    <div class="popup-meta">${escapeHtml(disruption.description || "No description supplied")}<br>${escapeHtml(validity)}<br>Source: ${escapeHtml(disruption.provenance?.dataset_title || "published disruption feed")}${qualityWarnings.length ? `<br>Quality: ${escapeHtml(qualityWarnings.join("; "))}` : ""}</div>`;
}

function renderMap(stops, detectors, disruptions) {
  transitLayer.clearLayers();
  detectorLayer.clearLayers();
  disruptionLayer.clearLayers();

  const berlinStops = stops.filter((stop) => isInsideBerlin(stop.latitude, stop.longitude));
  const visibleStops = berlinStops.slice(0, MAX_TRANSIT_MARKERS);
  for (const stop of visibleStops) {
    L.circleMarker([stop.latitude, stop.longitude], {
      radius: 2.6, weight: 0, fillColor: "#54b6ff", fillOpacity: 0.72,
    }).bindPopup(stopPopup(stop)).addTo(transitLayer);
  }

  for (const detector of detectors) {
    L.circleMarker([detector.latitude, detector.longitude], {
      radius: 4.3, weight: 1, color: "#f6b544", fillColor: "#f6b544", fillOpacity: 0.82,
    }).bindPopup(detectorPopup(detector)).addTo(detectorLayer);
  }

  for (const disruption of disruptions) {
    if (!disruption.geometry) continue;
    L.geoJSON(disruption.geometry, {
      style: { color: "#ff657a", weight: 4, opacity: 0.82, fillOpacity: 0.16 },
      pointToLayer: (_, latlng) => L.circleMarker(latlng, {
        radius: 6, color: "#ff657a", fillColor: "#ff657a", fillOpacity: 0.8,
      }),
      onEachFeature: (_, layer) => layer.bindPopup(disruptionPopup(disruption)),
    }).addTo(disruptionLayer);
  }

  const notes = [];
  if (!stops.length) notes.push("GTFS stop data is not loaded.");
  if (!detectors.length) notes.push("Detector locations are not loaded.");
  if (!disruptions.length) notes.push("No disruptions are present in the current server state.");
  if (berlinStops.length > visibleStops.length) {
    notes.push(`Rendering ${visibleStops.length.toLocaleString()} of ${berlinStops.length.toLocaleString()} Berlin stops for browser performance; the API exposes all loaded stops.`);
  }
  elements.mapNote.textContent = notes.length ? notes.join(" ") : "All displayed mobility layers come from the current API state; no synthetic production data is rendered.";
}

async function load() {
  elements.reload.disabled = true;
  elements.refreshTime.textContent = "Loading API state…";
  try {
    const [status, sources, snapshot, stops, detectors, disruptions] = await Promise.all([
      api("/api/v1/status"),
      api("/api/v1/sources"),
      api("/api/v1/mobility/snapshot"),
      api("/api/v1/transit/stops"),
      api("/api/v1/traffic/detectors"),
      api("/api/v1/disruptions"),
    ]);
    setBadge(status.status);
    renderCounts(status);
    renderWarnings(snapshot, status);
    renderSources(sources, status);
    renderMap(stops, detectors, disruptions);
    elements.refreshTime.textContent = `API state read ${new Date().toLocaleString()}. Snapshot timestamp: ${new Date(snapshot.timestamp).toLocaleString()}.`;
  } catch (error) {
    setBadge("degraded");
    elements.warnings.innerHTML = `<div class="message warn">${escapeHtml(error.message)}</div>`;
    elements.refreshTime.textContent = "The API state could not be loaded.";
    elements.mapNote.textContent = "No fallback or synthetic mobility data has been substituted.";
  } finally {
    elements.reload.disabled = false;
  }
}

elements.reload.addEventListener("click", load);
load();

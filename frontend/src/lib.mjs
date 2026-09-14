export const BERLIN_BOUNDS = {
  south: 52.3383,
  west: 13.0884,
  north: 52.6755,
  east: 13.7611,
};

export function isInsideBerlin(latitude, longitude) {
  return (
    latitude >= BERLIN_BOUNDS.south &&
    latitude <= BERLIN_BOUNDS.north &&
    longitude >= BERLIN_BOUNDS.west &&
    longitude <= BERLIN_BOUNDS.east
  );
}

export function freshnessLabel(value) {
  const labels = {
    fresh: "Fresh",
    stale: "Stale",
    expired: "Expired",
    unknown: "Unknown freshness",
  };
  return labels[value] ?? "Not loaded";
}

export function statusTone(value) {
  if (value === "fresh" || value === "ok") return "good";
  if (value === "stale" || value === "unknown" || value === "degraded") return "warn";
  if (value === "expired" || value === "error") return "bad";
  return "neutral";
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

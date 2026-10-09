// R50 — Formattazione data coerente con Admin → Impostazioni → Generali.
// La configurazione generale viene memorizzata da AppLayout in localStorage.
function configuredFormat() {
  try {
    const raw = window.localStorage.getItem("elios_general_settings");
    const cfg = raw ? JSON.parse(raw) : {};
    return cfg?.date_format || "DD/MM/YYYY";
  } catch {
    return "DD/MM/YYYY";
  }
}

function formatParts(y, m, d) {
  const fmt = configuredFormat();
  if (fmt === "YYYY-MM-DD") return `${y}-${m}-${d}`;
  if (fmt === "MM/DD/YYYY") return `${m}/${d}/${y}`;
  return `${d}/${m}/${y}`;
}

export function formatDateIT(iso) {
  if (!iso) return "";
  try {
    if (iso instanceof Date) {
      const d = iso;
      return formatParts(
        String(d.getFullYear()),
        String(d.getMonth() + 1).padStart(2, "0"),
        String(d.getDate()).padStart(2, "0"),
      );
    }
    const s = String(iso).trim();
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
    if (m) return formatParts(m[1], m[2], m[3]);
    const d = new Date(s);
    if (Number.isNaN(d.getTime())) return s;
    return formatParts(
      String(d.getFullYear()),
      String(d.getMonth() + 1).padStart(2, "0"),
      String(d.getDate()).padStart(2, "0"),
    );
  } catch {
    return String(iso || "");
  }
}

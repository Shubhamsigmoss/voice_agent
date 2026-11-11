const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const num = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const compact = new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 });

export function formatValue(value, fmt) {
  if (value === null || value === undefined || value === "") return "—";
  switch (fmt) {
    case "money":
      return inr.format(Number(value));
    case "int":
      return num.format(Number(value));
    case "percent":
      return `${Number(value).toFixed(1)}%`;
    case "change": {
      const n = Number(value);
      return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
    }
    case "date":
      return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", weekday: "short" });
    case "datetime":
      return new Date(value).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    default:
      return String(value);
  }
}

const MONTH = { day: "numeric", month: "short" };

/** "2026-09-01".."2026-09-10" -> "1–10 Sep 2026"; single day -> "Thu, 10 Sep 2026" */
export function formatPeriod(period) {
  if (!period?.from) return "";
  const f = new Date(`${period.from}T00:00:00`);
  const t = new Date(`${period.to || period.from}T00:00:00`);
  if (isNaN(f) || isNaN(t)) return `${period.from} to ${period.to}`;
  const year = t.getFullYear();
  if (+f === +t) return f.toLocaleDateString("en-IN", { weekday: "short", ...MONTH, year: "numeric" });
  if (f.getMonth() === t.getMonth() && f.getFullYear() === t.getFullYear())
    return `${f.getDate()}–${t.getDate()} ${t.toLocaleDateString("en-IN", { month: "short" })} ${year}`;
  return `${f.toLocaleDateString("en-IN", MONTH)} – ${t.toLocaleDateString("en-IN", MONTH)} ${year}`;
}

/** Replaces ISO dates inside labels, e.g. "Best day (2026-09-06)" -> "Best day (6 Sep)" */
export function friendlyLabel(label) {
  return String(label ?? "").replace(/\d{4}-\d{2}-\d{2}/g, (d) => shortDate(d));
}

/** "A: 2026-09-10" style period labels from compare_sales -> "10 Sep" */
export function friendlyText(v) {
  return typeof v === "string" ? friendlyLabel(v.replace(/^[AB]: /, "")).replace(/ to /, " – ") : v;
}

export function axisMoney(v) {
  return `₹${compact.format(v)}`;
}

export function shortDate(v) {
  const d = new Date(`${v}T00:00:00`);
  return isNaN(d) ? v : d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

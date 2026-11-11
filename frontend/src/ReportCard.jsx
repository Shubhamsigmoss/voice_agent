import { useId, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { axisMoney, formatPeriod, formatValue, friendlyLabel, friendlyText, shortDate } from "./format.js";

const AXIS = { fontSize: 12, fill: "var(--muted)" };

function colFormat(report, key) {
  return report.columns?.find((c) => c.key === key)?.format || "text";
}

function colLabel(report, key) {
  return report.columns?.find((c) => c.key === key)?.label || key;
}

function CategoryTick({ x, y, payload }) {
  const full = String(payload?.value ?? "");
  return (
    <text x={x} y={y} dy={4} textAnchor="end" fontSize={12} fill="var(--muted)">
      <title>{full}</title>
      {truncate(full, 20)}
    </text>
  );
}

/** compare_sales rows are labelled "A: <date>" / "B: <date>"; give the summary labels real dates. */
function periodNames(report) {
  const names = {};
  for (const r of report.rows || []) {
    const m = typeof r.Period === "string" && r.Period.match(/^([AB]): (.*)$/);
    if (m) names[m[1]] = friendlyText(m[2]);
  }
  return names;
}

function kpiLabel(label, names) {
  let l = friendlyLabel(label);
  if (names.A && names.B) {
    l = l.replace(/^Change \(A vs B\)$/, `Change vs ${names.B}`).replace(/^Bills change$/, `Bills vs ${names.B}`);
    l = l.replace(/ ([AB])$/, (_, k) => `, ${names[k]}`);
  }
  return l;
}

function truncate(s, n = 24) {
  const t = String(s ?? "");
  return t.length > n ? `${t.slice(0, n - 1)}…` : t;
}

/** Share of a total, as labelled bars. Used instead of a pie: every slice gets its name, value and %. */
function ShareList({ report, rows, x, y }) {
  const fmt = colFormat(report, y);
  const total = rows.reduce((s, r) => s + Number(r[y] || 0), 0) || 1;
  const sorted = [...rows].sort((a, b) => Number(b[y] || 0) - Number(a[y] || 0));
  const max = Number(sorted[0]?.[y] || 1);
  return (
    <ul className="share" aria-label={`${colLabel(report, y)} by ${colLabel(report, x)}`}>
      {sorted.map((r) => {
        const v = Number(r[y] || 0);
        return (
          <li key={r[x]}>
            <span className="share-name">{friendlyText(r[x])}</span>
            <span className="share-bar" aria-hidden>
              <span style={{ width: `${Math.max(0.6, (v / max) * 100)}%` }} />
            </span>
            <span className="share-val">{formatValue(v, fmt)}</span>
            <span className="share-pct">{((v / total) * 100).toFixed(1)}%</span>
          </li>
        );
      })}
    </ul>
  );
}

function Chart({ report }) {
  const { chart } = report;
  let rows = report.chart_rows ? report.rows?.slice(0, report.chart_rows) : report.rows;
  if (!chart || !rows?.length) return null;
  if (rows.every((r) => typeof r.Period === "string" && /^[AB]: /.test(r.Period))) rows = [...rows].reverse();
  const x = chart.x;
  const y = chart.y[0];
  const yFmt = colFormat(report, y);
  const xFmt = colFormat(report, x);
  const tickX = xFmt === "date" ? shortDate : (v) => truncate(friendlyText(v), 14);
  const tickY = yFmt === "money" ? axisMoney : undefined;
  const tip = (v) => [formatValue(v, yFmt), colLabel(report, y)];
  const labelFmt = xFmt === "date" ? (l) => formatValue(l, "date") : (l) => friendlyText(l);
  const tooltip = (
    <Tooltip
      formatter={tip}
      labelFormatter={labelFmt}
      cursor={{ fill: "var(--hover)" }}
      contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, color: "var(--ink)" }}
    />
  );

  if (chart.type === "pie") return <ShareList report={report} rows={rows} x={x} y={y} />;

  if (chart.type === "line") {
    return (
      <div className="chart">
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey={x} tickFormatter={tickX} tick={AXIS} tickLine={false} axisLine={false} minTickGap={18} />
            <YAxis tickFormatter={tickY} tick={AXIS} tickLine={false} axisLine={false} width={58} />
            {tooltip}
            <Line type="monotone" dataKey={y} stroke="var(--leaf)" strokeWidth={2.5} dot={rows.length <= 31 ? { r: 3, fill: "var(--leaf)" } : false} activeDot={{ r: 5 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  const horizontal = chart.type === "hbar";
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={horizontal ? Math.max(160, rows.length * 34) : 240}>
        <BarChart data={rows} layout={horizontal ? "vertical" : "horizontal"} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--line)" horizontal={!horizontal} vertical={horizontal} />
          {horizontal ? (
            <>
              <XAxis type="number" tickFormatter={tickY} tick={AXIS} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey={x} width={150} tick={<CategoryTick />} tickLine={false} axisLine={false} interval={0} />
            </>
          ) : (
            <>
              <XAxis dataKey={x} tickFormatter={tickX} tick={AXIS} tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis tickFormatter={tickY} tick={AXIS} tickLine={false} axisLine={false} width={58} />
            </>
          )}
          {tooltip}
          <Bar dataKey={y} fill="var(--leaf)" radius={horizontal ? [0, 3, 3, 0] : [3, 3, 0, 0]} maxBarSize={horizontal ? 20 : 48} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function Table({ report }) {
  return (
    <div className="table-wrap" tabIndex={0} aria-label={`${report.title} table`}>
      <table>
        <thead>
          <tr>
            {report.columns.map((c) => (
              <th key={c.key} className={c.format !== "text" ? "num" : ""} scope="col">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {report.rows.map((r, i) => (
            <tr key={i}>
              {report.columns.map((c) => (
                <td key={c.key} className={c.format !== "text" ? "num" : ""}>
                  {c.format === "text" ? friendlyText(r[c.key]) : formatValue(r[c.key], c.format)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ReportCard({ report }) {
  const hasChart = !!report.chart && report.rows?.length > 0;
  const hasTable = report.rows?.length > 0 && report.columns?.length > 0;
  const [view, setView] = useState(hasChart ? "chart" : "table");
  const id = useId();
  const summary = report.summary || [];
  const leadIdx = Math.max(0, summary.findIndex((k) => k.format === "money"));
  const lead = summary[leadIdx];
  const rest = summary.filter((_, i) => i !== leadIdx);
  const names = periodNames(report);
  const context = [formatPeriod(report.period), report.outlet].filter(Boolean).join(", ");

  return (
    <section className="report" aria-labelledby={`${id}-t`}>
      <header className="report-head">
        <div>
          <h3 id={`${id}-t`}>{report.title}</h3>
          {context && <p className="report-context">{context}</p>}
        </div>
        {hasChart && hasTable && (
          <div className="seg" role="group" aria-label="View">
            <button aria-pressed={view === "chart"} onClick={() => setView("chart")}>
              Chart
            </button>
            <button aria-pressed={view === "table"} onClick={() => setView("table")}>
              Table
            </button>
          </div>
        )}
      </header>

      {lead && (
        <div className="figures">
          <div className="lead">
            <span className="lead-label">{kpiLabel(lead.label, names)}</span>
            <span className={`lead-value ${lead.format === "change" ? (lead.value < 0 ? "down" : "up") : ""}`}>
              {formatValue(lead.value, lead.format)}
            </span>
          </div>
          {rest.length > 0 && (
            <dl className="stats">
              {rest.map((k) => (
                <div key={k.label}>
                  <dt>{kpiLabel(k.label, names)}</dt>
                  <dd className={k.format === "change" ? (k.value < 0 ? "down" : k.value > 0 ? "up" : "") : ""}>
                    {formatValue(k.value, k.format)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      )}

      {view === "chart" && hasChart && <Chart report={report} />}
      {view === "table" && hasTable && <Table report={report} />}
      {report.note && <p className="report-note">{report.note}</p>}
    </section>
  );
}

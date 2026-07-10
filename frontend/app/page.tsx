import { Activity, AlertTriangle, BarChart3, RefreshCw, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { getScreenerRows } from "@/lib/api";
import type { ScreenerRow } from "@/types/crypto";

export default async function DashboardPage() {
  let rows: ScreenerRow[] = [];
  let error: string | null = null;
  try {
    rows = await getScreenerRows();
  } catch (exc) {
    error = exc instanceof Error ? exc.message : "Unable to load screener data";
  }

  const buyCount = rows.filter((row) => row.rating === "BUY").length;
  const watchCount = rows.filter((row) => row.rating === "WATCH").length;
  const avoidCount = rows.filter((row) => row.rating === "AVOID").length;
  const partialCount = rows.filter((row) => row.data_quality_status !== "complete").length;

  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <div className="brand">
          <BarChart3 aria-hidden="true" />
          <div>
            <strong>Crypto Quant</strong>
            <span>Research desk</span>
          </div>
        </div>
        <nav className="nav-list" aria-label="Dashboard pages">
          {["Market Overview", "Quant Screener", "Coin Detail", "AI Analyst Report", "Watchlist", "Settings"].map(
            (item) => (
              <a href="#" key={item} className={item === "Quant Screener" ? "active" : ""}>
                {item}
              </a>
            )
          )}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Quantitative research classification only</p>
            <h1>Stage 2 Crypto Screener</h1>
          </div>
          <div className="status-pill">
            <RefreshCw aria-hidden="true" />
            <span>{rows.length ? "Stored data loaded" : "Awaiting first scan"}</span>
          </div>
        </header>

        {error ? (
          <div className="notice" role="alert">
            <AlertTriangle aria-hidden="true" />
            <span>{error}</span>
          </div>
        ) : null}

        <section className="metric-grid" aria-label="Market overview">
          <Metric label="Scanned" value={rows.length.toString()} icon={<Activity aria-hidden="true" />} />
          <Metric label="BUY" value={buyCount.toString()} tone="buy" icon={<ShieldCheck aria-hidden="true" />} />
          <Metric label="WATCH" value={watchCount.toString()} tone="watch" icon={<Activity aria-hidden="true" />} />
          <Metric label="AVOID" value={avoidCount.toString()} tone="avoid" icon={<AlertTriangle aria-hidden="true" />} />
          <Metric label="Partial data" value={partialCount.toString()} icon={<AlertTriangle aria-hidden="true" />} />
        </section>

        <section className="table-section">
          <div className="section-header">
            <h2>Quant Screener</h2>
            <span>{new Date().toLocaleString()}</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Coin</th>
                  <th>Price</th>
                  <th>24h</th>
                  <th>7d</th>
                  <th>Market cap</th>
                  <th>Volume</th>
                  <th>Stage</th>
                  <th>Score</th>
                  <th>Rating</th>
                  <th>Data</th>
                </tr>
              </thead>
              <tbody>
                {rows.length ? (
                  rows.map((row) => (
                    <tr key={row.cmc_id}>
                      <td>{row.rank ?? "-"}</td>
                      <td>
                        <strong>{row.symbol}</strong>
                        <span>{row.name}</span>
                      </td>
                      <td>{formatCurrency(row.price)}</td>
                      <td className={changeClass(row.percent_change_24h)}>{formatPct(row.percent_change_24h)}</td>
                      <td className={changeClass(row.percent_change_7d)}>{formatPct(row.percent_change_7d)}</td>
                      <td>{formatCompact(row.market_cap)}</td>
                      <td>{formatCompact(row.volume_24h)}</td>
                      <td>{row.stage}</td>
                      <td>{row.display_score.toFixed(1)}</td>
                      <td>
                        <span className={`rating ${row.rating.toLowerCase()}`}>{row.rating}</span>
                      </td>
                      <td>{row.data_quality_status}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={11} className="empty-row">
                      No crypto scan data has been stored yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </section>
    </main>
  );
}

function Metric({
  label,
  value,
  icon,
  tone
}: {
  label: string;
  value: string;
  icon: ReactNode;
  tone?: "buy" | "watch" | "avoid";
}) {
  return (
    <div className={`metric ${tone ?? ""}`}>
      <div className="metric-icon">{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatCurrency(value: number | null): string {
  if (value === null) return "-";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumSignificantDigits: 6 }).format(value);
}

function formatCompact(value: number | null): string {
  if (value === null) return "-";
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function formatPct(value: number | null): string {
  if (value === null) return "-";
  return `${value.toFixed(2)}%`;
}

function changeClass(value: number | null): string {
  if (value === null) return "";
  return value >= 0 ? "positive" : "negative";
}

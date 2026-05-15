import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { getMarketMetrics, getFredSeries, refreshFred } from "../services/api";

const CATEGORY_ORDER = ["credit", "prices", "inventory", "rates", "economy", "distress", "safety"];
const CATEGORY_LABELS = {
  credit: "Credit & Delinquency",
  prices: "Home Prices",
  inventory: "Housing Supply",
  rates: "Interest Rates",
  economy: "Economy",
  distress: "Vacant Buildings",
  safety: "Crime",
};
const CATEGORY_COLORS = {
  credit: "#ef4444",
  prices: "#3b82f6",
  inventory: "#8b5cf6",
  rates: "#10b981",
  economy: "#f59e0b",
  distress: "#dc2626",
  safety: "#7c2d12",
};
const GEO_LABELS = {
  national: "US",
  illinois: "IL",
  chicago_msa: "Chicago MSA",
  chicago: "Chicago",
};
const GEO_COLORS = {
  national: "bg-gray-100 text-gray-700",
  illinois: "bg-blue-100 text-blue-700",
  chicago_msa: "bg-red-100 text-red-700",
  chicago: "bg-orange-100 text-orange-700",
};

function categoryOf(seriesId, knownSeries) {
  const s = knownSeries.find((k) => k.series_id === seriesId);
  return s?.category || "other";
}

function fmt(v, unit) {
  if (v == null) return "—";
  const n = Number(v);
  if (unit === "percent") return `${n.toFixed(2)}%`;
  if (unit === "usd") return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  if (unit === "count") return n.toLocaleString();
  if (unit === "months") return `${n.toFixed(1)} mo`;
  if (unit === "index") return n.toFixed(1);
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export default function MarketMetricsPage() {
  const [data, setData] = useState(null);
  const [seriesData, setSeriesData] = useState({});
  const [seriesMeta, setSeriesMeta] = useState([]);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [expandedSeries, setExpandedSeries] = useState(new Set());

  useEffect(() => {
    loadAll();
  }, []);

  async function loadAll() {
    try {
      const [summary, meta] = await Promise.all([
        getMarketMetrics(),
        fetch("/api/v1/market-metrics/fred-series", {
          headers: { Authorization: `Bearer ${localStorage.getItem("cpt_token")}` },
        }).then((r) => r.json()),
      ]);
      setData(summary);
      setSeriesMeta(meta);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  }

  async function loadChart(seriesId) {
    if (seriesData[seriesId]) return; // already loaded
    try {
      const d = await getFredSeries(seriesId);
      setSeriesData((prev) => ({ ...prev, [seriesId]: d }));
    } catch {
      // ignore
    }
  }

  function toggleExpand(seriesId) {
    setExpandedSeries((prev) => {
      const next = new Set(prev);
      if (next.has(seriesId)) {
        next.delete(seriesId);
      } else {
        next.add(seriesId);
        loadChart(seriesId);
      }
      return next;
    });
  }

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await refreshFred();
      setTimeout(loadAll, 6000);
    } catch (e) {
      setError(e.response?.data?.detail || "Refresh failed");
    } finally {
      setTimeout(() => setRefreshing(false), 6500);
    }
  }

  if (error)
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 rounded p-4 text-sm">{error}</div>
    );
  if (!data) return <div className="text-center py-20 text-gray-400">Loading metrics…</div>;

  const macroEmpty = data.macro.series.every((s) => s.value == null);
  const t = data.tracked;
  const totals = t.totals;
  const rates = t.rates;

  // Group macro series by category, preserving order
  const grouped = {};
  for (const series of data.macro.series) {
    const cat = categoryOf(series.series_id, seriesMeta);
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push({
      ...series,
      geography: seriesMeta.find((m) => m.series_id === series.series_id)?.geography || series.geography || "national",
    });
  }

  // Chicago portal series come pre-categorized
  if (data.chicago) {
    for (const series of data.chicago.series) {
      const cat = series.category || "distress";
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push({
        ...series,
        geography: series.geography || "chicago",
      });
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-bold text-gray-800">Market Metrics</h2>
        <p className="text-sm text-gray-500">
          Macro indicators from the Federal Reserve + tracked-area counts from our local data.
        </p>
      </div>

      {/* TIER 1 — Macro FRED */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="font-semibold text-gray-800">Macro indicators</h3>
            <p className="text-xs text-gray-500">Source: {data.macro.source}</p>
          </div>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-100 disabled:opacity-50"
          >
            {refreshing ? "Refreshing…" : "Refresh FRED"}
          </button>
        </div>

        {macroEmpty && (
          <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 rounded p-3 text-sm mb-3">
            No FRED data yet. Add <code className="bg-yellow-100 px-1 rounded">FRED_API_KEY</code> to{" "}
            <code className="bg-yellow-100 px-1 rounded">backend/.env</code>, restart the backend, then click{" "}
            <strong>Refresh FRED</strong>.
          </div>
        )}

        <div className="space-y-5">
          {CATEGORY_ORDER.map((cat) => {
            const items = grouped[cat] || [];
            if (items.length === 0) return null;
            return (
              <div key={cat}>
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ background: CATEGORY_COLORS[cat] }}
                  />
                  <h4 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                    {CATEGORY_LABELS[cat] || cat}
                  </h4>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                  {items.map((s) => {
                    const isExpanded = expandedSeries.has(s.series_id);
                    const series = seriesData[s.series_id];
                    return (
                      <div
                        key={s.series_id}
                        className={`bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden ${
                          isExpanded ? "lg:col-span-2 xl:col-span-2" : ""
                        }`}
                      >
                        <button
                          onClick={() => toggleExpand(s.series_id)}
                          className="w-full text-left p-4 hover:bg-gray-50 transition-colors"
                        >
                          <div className="flex items-start justify-between gap-2 mb-1">
                            <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide line-clamp-2 flex-1">
                              {s.name}
                            </div>
                            <span
                              className={`text-xs px-1.5 py-0.5 rounded font-medium ${GEO_COLORS[s.geography]}`}
                            >
                              {GEO_LABELS[s.geography] || s.geography}
                            </span>
                          </div>
                          <div className="text-2xl font-bold text-gray-800">{fmt(s.value, s.unit)}</div>
                          <div className="text-xs text-gray-400 mt-1">
                            {s.as_of ? `as of ${s.as_of}` : "no data yet"}
                            {s.frequency && <span className="ml-1">· {s.frequency}</span>}
                            <span className="ml-1 font-mono">· {s.series_id}</span>
                          </div>
                          <div className="text-xs text-blue-500 mt-1">
                            {isExpanded ? "▲ hide chart" : "▼ show chart"}
                          </div>
                        </button>

                        {isExpanded && (
                          <div className="border-t border-gray-100 p-3">
                            {series ? (
                              <ResponsiveContainer width="100%" height={180}>
                                <LineChart data={series.observations}>
                                  <CartesianGrid strokeDasharray="3 3" />
                                  <XAxis
                                    dataKey="date"
                                    tick={{ fontSize: 9 }}
                                    interval={Math.floor(series.observations.length / 6)}
                                  />
                                  <YAxis tick={{ fontSize: 9 }} width={50} />
                                  <Tooltip />
                                  <Line
                                    type="monotone"
                                    dataKey="value"
                                    stroke={CATEGORY_COLORS[cat]}
                                    strokeWidth={2}
                                    dot={false}
                                  />
                                </LineChart>
                              </ResponsiveContainer>
                            ) : (
                              <div className="text-center py-8 text-gray-400 text-xs">Loading chart…</div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* TIER 2 — Tracked-area counts */}
      <section>
        <h3 className="font-semibold text-gray-800 mb-3">Tracked-area counts</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          <Stat title="Tracked properties" value={totals.tracked_properties} />
          <Stat title="Active foreclosures" value={totals.active_foreclosures} color="red" />
          <Stat title="Starts (30d)" value={totals.foreclosure_starts_30d} color="orange" />
          <Stat title="Completed (90d)" value={totals.foreclosures_completed_90d} color="yellow" />
          <Stat title="REO inventory" value={totals.reo_inventory} color="purple" />
          <Stat title="REO disposed (90d)" value={totals.reo_disposed_90d} color="green" />
          <Stat title="Tax distress (active)" value={totals.active_tax_distress} color="orange" />
          <Stat title="Total completed (all time)" value={totals.total_completed_foreclosures} color="gray" />
          <Stat title="Total filings (all time)" value={totals.total_foreclosure_filings} color="gray" />
          <Stat title="Starts (365d)" value={totals.foreclosure_starts_365d} color="orange" />
        </div>
      </section>

      {/* TIER 3 — Tracked-sample rates */}
      <section>
        <h3 className="font-semibold text-gray-800 mb-1">Tracked-sample rates</h3>
        <p className="text-xs text-gray-500 mb-3 italic">{t.denominator_caveat}</p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <Stat title="Foreclosure rate" value={`${rates.foreclosure_rate_per_1000_tracked} / 1000`} sub="active / tracked properties" color="red" />
          <Stat title="Start rate (30d)" value={`${rates.foreclosure_start_rate_30d_per_1000_tracked} / 1000`} sub="new starts / tracked properties" color="orange" />
          <Stat title="Completion rate" value={`${rates.foreclosure_completion_rate_pct}%`} sub="completed / total filings" color="yellow" />
          <Stat title="REO inventory" value={`${rates.reo_per_1000_tracked} / 1000`} sub="active REO / tracked properties" color="purple" />
          <Stat title="REO disposition (90d)" value={`${rates.reo_disposition_rate_90d_pct}%`} sub="disposed / (active + disposed)" color="green" />
        </div>
      </section>

      {/* Per-city breakdown */}
      <section>
        <h3 className="font-semibold text-gray-800 mb-3">By city — counts + listing metrics</h3>
        <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
          <table className="min-w-full bg-white text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-2 text-xs font-semibold text-gray-600 uppercase">City</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600 uppercase">Properties</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600 uppercase">Foreclosures</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600 uppercase">REO</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600 uppercase">Active listings</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600 uppercase">Median list</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600 uppercase">Avg DOM</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600 uppercase">% with drops</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(t.by_city).map(([city, m]) => (
                <tr key={city} className="border-b border-gray-100">
                  <td className="px-4 py-2 font-medium">{city}</td>
                  <td className="px-4 py-2 text-right">{m.tracked_properties.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right text-red-700">{m.active_foreclosures}</td>
                  <td className="px-4 py-2 text-right text-purple-700">{m.reo_inventory}</td>
                  <td className="px-4 py-2 text-right">{m.active_listings ?? "—"}</td>
                  <td className="px-4 py-2 text-right">
                    {m.median_list_price ? `$${Number(m.median_list_price).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : "—"}
                  </td>
                  <td className="px-4 py-2 text-right">{m.avg_days_on_market ?? "—"}</td>
                  <td className="px-4 py-2 text-right text-orange-700">
                    {m.pct_listings_with_drops != null ? `${m.pct_listings_with_drops}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data.chicago && (
          <p className="text-xs text-gray-400 mt-2 italic">
            Vacant Buildings + Crime metrics above are for Chicago city only. {data.chicago.note}
          </p>
        )}
      </section>

      <p className="text-xs text-gray-400 text-center">Reported as of {t.as_of}</p>
    </div>
  );
}

function Stat({ title, value, sub, color = "blue" }) {
  const colors = {
    blue: "border-blue-500 bg-blue-50",
    red: "border-red-500 bg-red-50",
    orange: "border-orange-500 bg-orange-50",
    yellow: "border-yellow-500 bg-yellow-50",
    green: "border-green-500 bg-green-50",
    purple: "border-purple-500 bg-purple-50",
    gray: "border-gray-400 bg-gray-50",
  };
  return (
    <div className={`rounded-lg border-l-4 p-3 shadow-sm ${colors[color]}`}>
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{title}</p>
      <p className="text-lg font-bold text-gray-800 mt-0.5">{value ?? "—"}</p>
      {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
    </div>
  );
}

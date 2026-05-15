import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { getMarketMetrics, getFredSeries, refreshFred } from "../services/api";

const fmt = (v, unit) => {
  if (v == null) return "—";
  if (unit === "percent") return `${Number(v).toFixed(2)}%`;
  if (unit === "count") return Number(v).toLocaleString();
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
};

export default function MarketMetricsPage() {
  const [data, setData] = useState(null);
  const [seriesData, setSeriesData] = useState({});
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadAll();
  }, []);

  async function loadAll() {
    try {
      const summary = await getMarketMetrics();
      setData(summary);
      // Try to fetch time series for each FRED series with data
      const seriesPromises = summary.macro.series
        .filter((s) => s.as_of)
        .map((s) =>
          getFredSeries(s.series_id)
            .then((d) => [s.series_id, d])
            .catch(() => [s.series_id, null])
        );
      const entries = await Promise.all(seriesPromises);
      setSeriesData(Object.fromEntries(entries.filter(([, v]) => v)));
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  }

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await refreshFred();
      // Give the background task a moment to write rows before reloading
      setTimeout(loadAll, 4000);
    } catch (e) {
      setError(e.response?.data?.detail || "Refresh failed");
    } finally {
      setTimeout(() => setRefreshing(false), 4500);
    }
  }

  if (error)
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 rounded p-4 text-sm">
        {error}
      </div>
    );
  if (!data)
    return <div className="text-center py-20 text-gray-400">Loading metrics…</div>;

  const macroEmpty = data.macro.series.every((s) => s.value == null);
  const t = data.tracked;
  const totals = t.totals;
  const rates = t.rates;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-bold text-gray-800">Market Metrics</h2>
        <p className="text-sm text-gray-500">
          Macro indicators from the Federal Reserve + tracked-area counts from our local data.
        </p>
      </div>

      {/* ----- TIER 1: Macro FRED ----- */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="font-semibold text-gray-800">Macro indicators (US national)</h3>
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
            No FRED data yet. Add your <code className="bg-yellow-100 px-1 rounded">FRED_API_KEY</code> to
            <code className="bg-yellow-100 px-1 rounded ml-1">backend/.env</code>, restart the backend,
            then click <strong>Refresh FRED</strong>.
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {data.macro.series.map((s) => (
            <div key={s.series_id} className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide line-clamp-2 min-h-[2rem]">
                {s.name}
              </div>
              <div className="text-2xl font-bold text-gray-800 mt-1">{fmt(s.value, s.unit)}</div>
              <div className="text-xs text-gray-400 mt-1">
                {s.as_of ? `as of ${s.as_of}` : "no data yet"}
                {s.frequency && <span className="ml-1">· {s.frequency}</span>}
              </div>
              <div className="text-xs text-gray-400 mt-0.5 font-mono">{s.series_id}</div>
            </div>
          ))}
        </div>

        {Object.entries(seriesData).map(([sid, series]) => (
          <div key={sid} className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm mt-4">
            <h4 className="text-sm font-semibold text-gray-700 mb-2">
              {series.name} <span className="text-xs text-gray-400 font-mono">({sid})</span>
            </h4>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={series.observations}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} interval={Math.floor(series.observations.length / 8)} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ))}
      </section>

      {/* ----- TIER 2: Tracked-area counts ----- */}
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

      {/* ----- TIER 3: Tracked-sample rates (with caveat) ----- */}
      <section>
        <h3 className="font-semibold text-gray-800 mb-1">Tracked-sample rates</h3>
        <p className="text-xs text-gray-500 mb-3 italic">{t.denominator_caveat}</p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <Stat
            title="Foreclosure rate"
            value={`${rates.foreclosure_rate_per_1000_tracked} / 1000`}
            sub="active / tracked properties"
            color="red"
          />
          <Stat
            title="Start rate (30d)"
            value={`${rates.foreclosure_start_rate_30d_per_1000_tracked} / 1000`}
            sub="new starts / tracked properties"
            color="orange"
          />
          <Stat
            title="Completion rate"
            value={`${rates.foreclosure_completion_rate_pct}%`}
            sub="completed / total filings"
            color="yellow"
          />
          <Stat
            title="REO inventory"
            value={`${rates.reo_per_1000_tracked} / 1000`}
            sub="active REO / tracked properties"
            color="purple"
          />
          <Stat
            title="REO disposition (90d)"
            value={`${rates.reo_disposition_rate_90d_pct}%`}
            sub="disposed / (active + disposed)"
            color="green"
          />
        </div>
      </section>

      {/* ----- Per-city breakdown ----- */}
      <section>
        <h3 className="font-semibold text-gray-800 mb-3">By city</h3>
        <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
          <table className="min-w-full bg-white text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-2 text-xs font-semibold text-gray-600 uppercase">City</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600 uppercase">Properties</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600 uppercase">Active foreclosures</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600 uppercase">REO inventory</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(t.by_city).map(([city, m]) => (
                <tr key={city} className="border-b border-gray-100">
                  <td className="px-4 py-2 font-medium">{city}</td>
                  <td className="px-4 py-2 text-right">{m.tracked_properties.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right text-red-700">{m.active_foreclosures}</td>
                  <td className="px-4 py-2 text-right text-purple-700">{m.reo_inventory}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <p className="text-xs text-gray-400 text-center">
        Reported as of {t.as_of}
      </p>
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

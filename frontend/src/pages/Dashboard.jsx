import { useEffect, useState } from "react";
import { getStats } from "../services/api";
import StatCard from "../components/StatCard";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

const fmt = (n) => (n != null ? Number(n).toLocaleString() : "—");
const fmtUSD = (n) => (n != null ? `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : "—");

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch(() => setError("Could not load stats. Is the API running?"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-20 text-gray-400">Loading dashboard…</div>;
  if (error) return <div className="text-center py-20 text-red-500">{error}</div>;

  const cities = Object.keys(stats);
  const totals = cities.reduce(
    (acc, city) => {
      acc.properties += stats[city].total_properties;
      acc.foreclosures += stats[city].foreclosures;
      acc.evictions += stats[city].evictions;
      acc.seizures += stats[city].bank_seizures;
      return acc;
    },
    { properties: 0, foreclosures: 0, evictions: 0, seizures: 0 }
  );

  const chartData = cities.map((city) => ({
    city,
    Foreclosures: stats[city].foreclosures,
    Evictions: stats[city].evictions,
    "Bank Seizures": stats[city].bank_seizures,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-800">Overview</h2>
        <p className="text-sm text-gray-500">Across all tracked municipalities</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="Total Properties" value={fmt(totals.properties)} color="blue" />
        <StatCard title="Foreclosures" value={fmt(totals.foreclosures)} color="red" />
        <StatCard title="Evictions" value={fmt(totals.evictions)} color="yellow" />
        <StatCard title="Bank Seizures" value={fmt(totals.seizures)} color="purple" />
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
        <h3 className="font-semibold text-gray-700 mb-4">Events by City</h3>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={chartData}>
            <XAxis dataKey="city" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="Foreclosures" fill="#ef4444" radius={[3, 3, 0, 0]} />
            <Bar dataKey="Evictions" fill="#f59e0b" radius={[3, 3, 0, 0]} />
            <Bar dataKey="Bank Seizures" fill="#8b5cf6" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {cities.map((city) => (
          <div key={city} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <h3 className="font-semibold text-gray-800 mb-3">{city}</h3>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="text-gray-500">Properties</div>
              <div className="font-medium">{fmt(stats[city].total_properties)}</div>
              <div className="text-gray-500">Avg Market Value</div>
              <div className="font-medium">{fmtUSD(stats[city].avg_market_value)}</div>
              <div className="text-gray-500">Foreclosures</div>
              <div className="font-medium text-red-600">{fmt(stats[city].foreclosures)}</div>
              <div className="text-gray-500">Evictions</div>
              <div className="font-medium text-yellow-600">{fmt(stats[city].evictions)}</div>
              <div className="text-gray-500">Bank Seizures</div>
              <div className="font-medium text-purple-600">{fmt(stats[city].bank_seizures)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

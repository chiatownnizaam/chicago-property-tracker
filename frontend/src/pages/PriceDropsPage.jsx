import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getPriceDrops } from "../services/api";

const CITIES = ["", "Chicago", "Lincolnwood", "Sauganash", "Skokie", "Evanston"];
const SOURCES = ["", "redfin", "realtor", "zillow", "trulia"];

const fmtUSD = (n) =>
  n != null ? `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : "—";

const fmtPct = (n) => (n != null ? `${Number(n).toFixed(1)}%` : "—");

export default function PriceDropsPage() {
  const [drops, setDrops] = useState([]);
  const [filters, setFilters] = useState({ city: "", source: "", days: 60, min_drop_pct: "" });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = { days: filters.days };
    if (filters.city) params.city = filters.city;
    if (filters.source) params.source = filters.source;
    if (filters.min_drop_pct) params.min_drop_pct = filters.min_drop_pct;
    getPriceDrops(params)
      .then(setDrops)
      .finally(() => setLoading(false));
  }, [filters]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-gray-800">Price Drops</h2>
        <p className="text-sm text-gray-500">
          Active listings where the asking price has been reduced. Sourced from Redfin and Realtor.com.
        </p>
      </div>

      <div className="flex flex-wrap gap-3 bg-white p-3 rounded-lg shadow-sm border border-gray-200">
        <select
          className="border border-gray-300 rounded px-2 py-1.5 text-sm"
          value={filters.city}
          onChange={(e) => setFilters({ ...filters, city: e.target.value })}
        >
          {CITIES.map((c) => (
            <option key={c} value={c}>{c || "All Cities"}</option>
          ))}
        </select>
        <select
          className="border border-gray-300 rounded px-2 py-1.5 text-sm"
          value={filters.source}
          onChange={(e) => setFilters({ ...filters, source: e.target.value })}
        >
          {SOURCES.map((s) => (
            <option key={s} value={s}>{s ? s.charAt(0).toUpperCase() + s.slice(1) : "All Sources"}</option>
          ))}
        </select>
        <select
          className="border border-gray-300 rounded px-2 py-1.5 text-sm"
          value={filters.days}
          onChange={(e) => setFilters({ ...filters, days: Number(e.target.value) })}
        >
          {[7, 14, 30, 60, 90, 180, 365].map((d) => (
            <option key={d} value={d}>Last {d} days</option>
          ))}
        </select>
        <input
          type="number"
          placeholder="Min drop %"
          className="border border-gray-300 rounded px-2 py-1.5 text-sm w-28"
          value={filters.min_drop_pct}
          onChange={(e) => setFilters({ ...filters, min_drop_pct: e.target.value })}
        />
        <button
          className="ml-auto text-sm text-gray-500 hover:text-gray-800 underline"
          onClick={() => setFilters({ city: "", source: "", days: 60, min_drop_pct: "" })}
        >
          Clear filters
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">Loading price drops…</div>
      ) : drops.length === 0 ? (
        <div className="text-center py-12 text-gray-400 bg-white rounded-lg border border-gray-200">
          No price drops found for the selected filters.
        </div>
      ) : (
        <>
          <p className="text-xs text-gray-500">{drops.length} listings with price drops</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {drops.map((d) => (
              <Link
                to={`/properties/${d.property_id}`}
                key={d.listing_id}
                className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden hover:shadow-md hover:border-blue-300 transition-all"
              >
                {d.photo_url && (
                  <div className="h-40 bg-gray-200 overflow-hidden">
                    <img src={d.photo_url} alt={d.address} className="w-full h-full object-cover" />
                  </div>
                )}
                <div className="p-4 space-y-2">
                  <div className="flex justify-between items-start">
                    <div className="font-semibold text-gray-800">{d.address}</div>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      d.source === "redfin" ? "bg-red-100 text-red-700" : "bg-blue-100 text-blue-700"
                    }`}>{d.source}</span>
                  </div>
                  <div className="text-sm text-gray-500">{d.city}, IL</div>

                  <div className="border-t border-gray-100 pt-2">
                    <div className="flex justify-between items-baseline">
                      <span className="text-2xl font-bold text-gray-800">{fmtUSD(d.current_price)}</span>
                      <span className="text-sm text-gray-400 line-through">{fmtUSD(d.original_price)}</span>
                    </div>
                    <div className="flex justify-between text-sm mt-1">
                      <span className="text-red-600 font-semibold">
                        ↓ {fmtUSD(d.total_drop_amount)} ({fmtPct(d.total_drop_pct)})
                      </span>
                      <span className="text-gray-500">{d.total_drops} drop{d.total_drops !== 1 ? "s" : ""}</span>
                    </div>
                  </div>

                  <div className="flex justify-between text-xs text-gray-500 pt-1">
                    <span>{d.days_on_market != null ? `${d.days_on_market} days on market` : ""}</span>
                    <span>{d.latest_drop_date ? `Last drop: ${d.latest_drop_date}` : ""}</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

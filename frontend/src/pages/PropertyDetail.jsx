import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { MapContainer, TileLayer, CircleMarker } from "react-leaflet";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { getPropertyHistory } from "../services/api";

const fmtUSD = (n) =>
  n != null ? `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : "—";

const TYPE_COLORS = {
  sale: "bg-green-100 text-green-700 border-green-200",
  foreclosure: "bg-red-100 text-red-700 border-red-200",
  eviction: "bg-yellow-100 text-yellow-700 border-yellow-200",
  bank_seizure: "bg-purple-100 text-purple-700 border-purple-200",
  listing: "bg-blue-100 text-blue-700 border-blue-200",
};

const TYPE_ICONS = {
  sale: "$",
  foreclosure: "⚖",
  eviction: "📋",
  bank_seizure: "🔒",
  listing: "🏷",
};

export default function PropertyDetail() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    getPropertyHistory(id)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="text-center py-20 text-gray-400">Loading property…</div>;
  if (error) return <div className="text-center py-20 text-red-500">Error: {error}</div>;
  if (!data) return null;

  const { property: prop, timeline, listings } = data;
  const salesHistory = timeline
    .filter((e) => e.type === "sale")
    .map((e) => ({ date: e.date, price: e.amount }))
    .reverse();

  const activeListing = listings.find((l) => l.price_drops_count > 0) || listings[0];

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 text-sm">
        <Link to="/" className="text-blue-600 hover:underline">← Back</Link>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
        <div className="flex flex-wrap justify-between gap-3">
          <div>
            <h2 className="text-2xl font-bold text-gray-800">{prop.address}</h2>
            <p className="text-sm text-gray-500">
              {prop.city}, {prop.state} {prop.zip_code} {prop.neighborhood && `· ${prop.neighborhood}`}
            </p>
            {prop.pin && <p className="text-xs text-gray-400 mt-1">PIN: {prop.pin}</p>}
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-500 uppercase">Market Value</div>
            <div className="text-2xl font-bold text-gray-800">{fmtUSD(prop.market_value)}</div>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 text-sm">
          <div><span className="text-gray-500">Type:</span> <strong>{prop.property_type || "—"}</strong></div>
          <div><span className="text-gray-500">Built:</span> <strong>{prop.year_built || "—"}</strong></div>
          <div><span className="text-gray-500">Sqft:</span> <strong>{prop.square_footage?.toLocaleString() || "—"}</strong></div>
          <div><span className="text-gray-500">Beds/Baths:</span> <strong>{prop.bedrooms || "—"} / {prop.bathrooms || "—"}</strong></div>
        </div>
      </div>

      {activeListing && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-semibold text-gray-800">Active Listing on {activeListing.source}</h3>
            {activeListing.url && (
              <a href={activeListing.url} target="_blank" rel="noopener noreferrer"
                 className="text-sm text-blue-600 hover:underline">View original →</a>
            )}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm mb-4">
            <div>
              <div className="text-gray-500 text-xs">Current Price</div>
              <div className="text-xl font-bold text-gray-800">{fmtUSD(activeListing.current_price)}</div>
            </div>
            <div>
              <div className="text-gray-500 text-xs">Original Price</div>
              <div className="text-lg text-gray-500 line-through">{fmtUSD(activeListing.original_price)}</div>
            </div>
            <div>
              <div className="text-gray-500 text-xs">Total Drop</div>
              <div className="text-lg font-semibold text-red-600">
                {fmtUSD(activeListing.total_price_drop_amount)} ({(activeListing.total_price_drop_pct || 0).toFixed(1)}%)
              </div>
            </div>
            <div>
              <div className="text-gray-500 text-xs">Days On Market</div>
              <div className="text-lg font-semibold text-gray-800">{activeListing.days_on_market || "—"}</div>
            </div>
          </div>

          {activeListing.price_history && activeListing.price_history.length > 1 && (
            <>
              <h4 className="text-sm font-semibold text-gray-700 mb-2">Price History</h4>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={[...activeListing.price_history].reverse()}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                  <Tooltip formatter={(v) => fmtUSD(v)} />
                  <Line type="stepAfter" dataKey="price" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
          <h3 className="font-semibold text-gray-800 mb-3">Sales Price History</h3>
          {salesHistory.length === 0 ? (
            <div className="text-center text-gray-400 py-10 text-sm">No recorded sales.</div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={salesHistory}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                <Tooltip formatter={(v) => fmtUSD(v)} />
                <Line type="monotone" dataKey="price" stroke="#10b981" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {prop.latitude && prop.longitude && (
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
            <h3 className="font-semibold text-gray-800 mb-3">Location</h3>
            <div style={{ height: 220 }} className="rounded overflow-hidden">
              <MapContainer center={[prop.latitude, prop.longitude]} zoom={15} style={{ height: "100%", width: "100%" }}>
                <TileLayer
                  attribution='&copy; OpenStreetMap'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                <CircleMarker
                  center={[prop.latitude, prop.longitude]}
                  radius={8}
                  pathOptions={{ color: "#3b82f6", fillColor: "#3b82f6", fillOpacity: 0.8 }}
                />
              </MapContainer>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
        <h3 className="font-semibold text-gray-800 mb-3">Full Event Timeline</h3>
        {timeline.length === 0 ? (
          <div className="text-center text-gray-400 py-10 text-sm">No events recorded.</div>
        ) : (
          <div className="space-y-3">
            {timeline.map((event, i) => (
              <div key={i} className={`border-l-4 p-3 rounded ${TYPE_COLORS[event.type] || "bg-gray-50 border-gray-300"}`}>
                <div className="flex justify-between items-start">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wide opacity-70">
                      {TYPE_ICONS[event.type] || "•"} {event.type.replace(/_/g, " ")}
                    </div>
                    <div className="font-medium mt-0.5">{event.title}</div>
                  </div>
                  <div className="text-sm font-mono text-gray-600">{event.date}</div>
                </div>
                {event.details && (
                  <div className="mt-2 text-xs grid grid-cols-2 gap-x-3 gap-y-1 opacity-80">
                    {Object.entries(event.details).map(([k, v]) =>
                      v != null && v !== "" ? (
                        <div key={k}>
                          <span className="font-semibold">{k.replace(/_/g, " ")}:</span> {String(v)}
                        </div>
                      ) : null
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

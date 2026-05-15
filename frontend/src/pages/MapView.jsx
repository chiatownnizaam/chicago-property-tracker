import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import { getProperties } from "../services/api";

const LAYER_COLORS = {
  foreclosure: "#ef4444",
  eviction: "#f59e0b",
  bank_seizure: "#8b5cf6",
  normal: "#3b82f6",
};

function markerColor(prop) {
  if (prop.has_bank_seizure) return LAYER_COLORS.bank_seizure;
  if (prop.has_foreclosure) return LAYER_COLORS.foreclosure;
  if (prop.has_eviction) return LAYER_COLORS.eviction;
  return LAYER_COLORS.normal;
}

const CHICAGO_CENTER = [41.8827, -87.6233];

export default function MapView() {
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [city, setCity] = useState("");
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    setLoading(true);
    const params = { limit: 500 };
    if (city) params.city = city;
    if (filter === "foreclosure") params.has_foreclosure = true;
    if (filter === "eviction") params.has_eviction = true;
    if (filter === "bank_seizure") params.has_bank_seizure = true;
    getProperties(params)
      .then(setProperties)
      .finally(() => setLoading(false));
  }, [city, filter]);

  const mappable = properties.filter((p) => p.latitude && p.longitude);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3 bg-white p-3 rounded-lg shadow-sm border border-gray-200 items-center">
        <select
          className="border border-gray-300 rounded px-2 py-1.5 text-sm"
          value={city}
          onChange={(e) => setCity(e.target.value)}
        >
          {["", "Chicago", "Lincolnwood", "Sauganash", "Skokie", "Evanston"].map((c) => (
            <option key={c} value={c}>{c || "All Cities"}</option>
          ))}
        </select>
        <select
          className="border border-gray-300 rounded px-2 py-1.5 text-sm"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">All Properties</option>
          <option value="foreclosure">Foreclosures Only</option>
          <option value="eviction">Evictions Only</option>
          <option value="bank_seizure">Bank Seizures Only</option>
        </select>
        <div className="flex gap-3 ml-auto text-xs text-gray-600 items-center">
          {Object.entries(LAYER_COLORS).map(([k, color]) => (
            <span key={k} className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded-full" style={{ background: color }} />
              {k.replace("_", " ")}
            </span>
          ))}
        </div>
      </div>

      {loading && <div className="text-center py-4 text-gray-400 text-sm">Loading properties…</div>}

      <div className="rounded-lg overflow-hidden shadow-sm border border-gray-200" style={{ height: "580px" }}>
        <MapContainer center={CHICAGO_CENTER} zoom={12} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {mappable.map((prop) => (
            <CircleMarker
              key={prop.id}
              center={[prop.latitude, prop.longitude]}
              radius={6}
              pathOptions={{ color: markerColor(prop), fillColor: markerColor(prop), fillOpacity: 0.8 }}
            >
              <Popup>
                <div className="text-sm space-y-1">
                  <p className="font-semibold">{prop.address}</p>
                  <p className="text-gray-600">{prop.city}, IL</p>
                  {prop.last_sale_price && (
                    <p>Last Sale: <strong>${Number(prop.last_sale_price).toLocaleString()}</strong></p>
                  )}
                  {prop.last_sale_date && <p className="text-gray-500">{prop.last_sale_date}</p>}
                  <div className="flex gap-2 pt-1 flex-wrap">
                    {prop.has_foreclosure && <span className="bg-red-100 text-red-700 px-1.5 py-0.5 rounded text-xs">Foreclosure</span>}
                    {prop.has_eviction && <span className="bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded text-xs">Eviction</span>}
                    {prop.has_bank_seizure && <span className="bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded text-xs">Bank Seizure</span>}
                  </div>
                  <Link to={`/properties/${prop.id}`} className="block pt-1 text-blue-600 font-medium hover:underline">
                    View details →
                  </Link>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
      <p className="text-xs text-gray-400 text-right">{mappable.length} properties with coordinates shown</p>
    </div>
  );
}

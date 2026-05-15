import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { MapContainer, TileLayer, CircleMarker } from "react-leaflet";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from "recharts";
import { getPropertyHistory, getComps, getMarketMetrics } from "../services/api";
import { computeAffordability, fmtMoney } from "../services/affordability";

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

function FloodBadge({ zone, subtype }) {
  // High-risk = A* or V* zones (Special Flood Hazard Area)
  const isHighRisk = /^A/.test(zone) || /^V/.test(zone);
  const isModerate = zone === "X" && subtype && subtype.toUpperCase().includes("0.2");
  const cls = isHighRisk
    ? "bg-red-100 text-red-800 border border-red-200"
    : isModerate
    ? "bg-yellow-100 text-yellow-800 border border-yellow-200"
    : zone === "UNMAPPED"
    ? "bg-gray-100 text-gray-600 border border-gray-200"
    : "bg-green-100 text-green-800 border border-green-200";
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`} title={subtype || zone}>
      Zone {zone}{subtype ? ` — ${subtype}` : ""}
    </span>
  );
}

export default function PropertyDetail() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [comps, setComps] = useState(null);
  const [radius, setRadius] = useState(1.0);
  const [months, setMonths] = useState(12);
  const [mortgageRate, setMortgageRate] = useState(null);

  useEffect(() => {
    setLoading(true);
    getPropertyHistory(id)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!data?.property?.id) return;
    if (!data.property.latitude || !data.property.longitude) {
      setComps({ count: 0, comps: [] });
      return;
    }
    getComps(data.property.id, { radius_miles: radius, months }).then(setComps).catch(() => setComps(null));
  }, [data?.property?.id, radius, months]);

  useEffect(() => {
    getMarketMetrics().then((m) => {
      const mort = m.macro?.series?.find((s) => s.series_id === "MORTGAGE30US");
      if (mort?.value) setMortgageRate(Number(mort.value));
    }).catch(() => {});
  }, []);

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

        {(prop.flood_zone || prop.walk_score != null || prop.school_district) && (
          <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            {prop.flood_zone && (
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Flood:</span>
                <FloodBadge zone={prop.flood_zone} subtype={prop.flood_zone_subtype} />
              </div>
            )}
            {prop.walk_score != null && (
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Walk Score:</span>
                <span className="font-semibold text-gray-800">{Number(prop.walk_score).toFixed(1)}</span>
                <span className="text-xs text-gray-400">/ 100</span>
              </div>
            )}
            {prop.school_district && (
              <div className="flex items-center gap-2 text-gray-700">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">School:</span>
                <span className="truncate text-xs">{prop.school_district}</span>
              </div>
            )}
          </div>
        )}

        {prop.parcel_data && Object.keys(prop.parcel_data).length > 0 && (
          <details className="mt-3 text-xs">
            <summary className="cursor-pointer text-blue-600 hover:underline">More from Cook County Assessor</summary>
            <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-1 text-gray-600">
              {Object.entries(prop.parcel_data).map(([k, v]) =>
                v != null && v !== "" ? (
                  <div key={k} className="flex gap-2">
                    <span className="font-semibold capitalize">{k.replace(/_/g, " ")}:</span>
                    <span>{String(v)}</span>
                  </div>
                ) : null
              )}
            </div>
          </details>
        )}
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

      {/* AFFORDABILITY */}
      <AffordabilityCard
        price={activeListing?.current_price || prop.market_value}
        rate={mortgageRate}
      />

      {/* CLIMATE RISK */}
      <ClimateRiskCard prop={prop} />

      {/* COMPARABLE SALES */}
      <CompsCard
        comps={comps}
        radius={radius}
        setRadius={setRadius}
        months={months}
        setMonths={setMonths}
        subject={prop}
      />

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

// ============== AFFORDABILITY ==============

function AffordabilityCard({ price, rate }) {
  if (!price || rate == null) return null;
  const calc = computeAffordability(Number(price), rate);
  if (!calc) return null;
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
      <div className="flex justify-between items-baseline mb-3">
        <h3 className="font-semibold text-gray-800">Affordability calculator</h3>
        <span className="text-xs text-gray-500">
          Using 30Y rate {rate.toFixed(2)}% · 20% down · 30y term
        </span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Money label="Monthly P&amp;I" value={calc.monthly_pi} />
        <Money label="Property tax" value={calc.monthly_tax} hint="2.0%/yr Cook County" />
        <Money label="Insurance" value={calc.monthly_insurance} hint="0.5%/yr" />
        <Money label="Total monthly (PITI)" value={calc.monthly_piti} bold />
      </div>
      <div className="border-t border-gray-100 mt-4 pt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <div>
          <span className="text-gray-500">Loan amount: </span>
          <strong>{fmtMoney(calc.loan_amount)}</strong>
        </div>
        <div>
          <span className="text-gray-500">Down payment: </span>
          <strong>{fmtMoney(calc.down_payment)}</strong>
        </div>
        <div>
          <span className="text-gray-500">Income to qualify: </span>
          <strong className="text-green-700">{fmtMoney(calc.income_required_annual)}</strong>
          <span className="text-xs text-gray-400 ml-1">/yr · 28% DTI</span>
        </div>
      </div>
    </div>
  );
}

function Money({ label, value, hint, bold }) {
  return (
    <div>
      <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
      <div className={`mt-0.5 ${bold ? "text-xl font-bold text-gray-900" : "text-lg font-semibold text-gray-800"}`}>
        {fmtMoney(value)}
      </div>
      {hint && <div className="text-xs text-gray-400 mt-0.5">{hint}</div>}
    </div>
  );
}

// ============== CLIMATE RISK ==============

function ClimateRiskCard({ prop }) {
  const pd = prop.parcel_data || {};
  const fsFactor = pd.first_street_flood_factor != null ? Number(pd.first_street_flood_factor) : null;
  const sfha = pd.fema_sfha === true || /^A|^V/.test(prop.flood_zone || "");
  const dnl = pd.airport_noise_dnl != null ? Number(pd.airport_noise_dnl) : null;
  const ohareNoise = !!pd.ohare_noise_contour;

  if (!prop.flood_zone && fsFactor == null && dnl == null && pd.fema_sfha == null) return null;

  const radar = [
    { dim: "FEMA Flood", score: sfha ? 8 : prop.flood_zone === "X" ? 2 : prop.flood_zone === "UNMAPPED" ? 0 : 4 },
    { dim: "First Street", score: fsFactor != null ? Math.min(10, fsFactor) : 0 },
    { dim: "Airport Noise", score: dnl != null ? Math.max(0, Math.min(10, (dnl - 55) / 2)) : ohareNoise ? 5 : 0 },
    { dim: "Heat", score: 4 },
    { dim: "Storm/Wind", score: 5 },
  ];

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
      <div className="flex justify-between items-baseline mb-3">
        <h3 className="font-semibold text-gray-800">Climate risk profile</h3>
        <span className="text-xs text-gray-500">0 = minimal · 10 = severe</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
        <ResponsiveContainer width="100%" height={240}>
          <RadarChart data={radar}>
            <PolarGrid />
            <PolarAngleAxis dataKey="dim" tick={{ fontSize: 11 }} />
            <PolarRadiusAxis angle={90} domain={[0, 10]} tick={{ fontSize: 10 }} />
            <Radar name="Risk" dataKey="score" stroke="#dc2626" fill="#dc2626" fillOpacity={0.3} />
          </RadarChart>
        </ResponsiveContainer>
        <div className="space-y-2 text-sm">
          <RiskRow
            label="FEMA flood zone"
            value={prop.flood_zone || "—"}
            sub={prop.flood_zone_subtype}
            risk={sfha ? "high" : prop.flood_zone === "X" ? "low" : "moderate"}
          />
          {fsFactor != null && (
            <RiskRow
              label="First Street flood factor"
              value={`${fsFactor} / 10`}
              sub={pd.first_street_flood_direction || ""}
              risk={fsFactor >= 7 ? "high" : fsFactor >= 4 ? "moderate" : "low"}
            />
          )}
          {dnl != null && (
            <RiskRow
              label="Airport noise (DNL)"
              value={`${dnl} dB`}
              sub={ohareNoise ? "Within O'Hare contour" : ""}
              risk={dnl >= 65 ? "high" : dnl >= 55 ? "moderate" : "low"}
            />
          )}
          <p className="text-xs text-gray-400 pt-1 italic">
            FEMA zone is authoritative; First Street factor and airport noise come from
            the Cook County Assessor enrichment. Heat and storm scores are
            Chicago-metro baselines.
          </p>
        </div>
      </div>
    </div>
  );
}

function RiskRow({ label, value, sub, risk }) {
  const color =
    risk === "high" ? "bg-red-100 text-red-800" :
    risk === "moderate" ? "bg-yellow-100 text-yellow-800" :
    "bg-green-100 text-green-800";
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-gray-100 pb-1.5">
      <div>
        <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
        {sub && <div className="text-xs text-gray-400">{sub}</div>}
      </div>
      <span className={`px-2 py-0.5 rounded text-xs font-semibold ${color}`}>{value}</span>
    </div>
  );
}

// ============== COMPS ==============

function CompsCard({ comps, radius, setRadius, months, setMonths, subject }) {
  if (!subject?.latitude || !subject?.longitude) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
        <h3 className="font-semibold text-gray-800 mb-2">Comparable sales</h3>
        <p className="text-sm text-gray-500">This property has no coordinates — comparable-sales lookup requires lat/lon.</p>
      </div>
    );
  }
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <h3 className="font-semibold text-gray-800">Comparable sales</h3>
        <div className="flex flex-wrap gap-2 items-center text-xs">
          <label className="text-gray-500">Radius</label>
          <select
            value={radius}
            onChange={(e) => setRadius(Number(e.target.value))}
            className="border border-gray-300 rounded px-2 py-1"
          >
            {[0.25, 0.5, 1.0, 2.0, 5.0].map((r) => (
              <option key={r} value={r}>{r} mi</option>
            ))}
          </select>
          <label className="text-gray-500 ml-2">Window</label>
          <select
            value={months}
            onChange={(e) => setMonths(Number(e.target.value))}
            className="border border-gray-300 rounded px-2 py-1"
          >
            {[3, 6, 12, 24, 36].map((m) => (
              <option key={m} value={m}>last {m}mo</option>
            ))}
          </select>
        </div>
      </div>

      {!comps ? (
        <p className="text-sm text-gray-400 text-center py-6">Loading comps…</p>
      ) : comps.count === 0 ? (
        <p className="text-sm text-gray-400 text-center py-6">No comparable sales in this radius and window.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3 text-sm">
            <Money label="Median" value={comps.median_price} bold />
            <Money label="Mean" value={comps.mean_price} />
            <Money label="Range (low)" value={comps.min_price} />
            <Money label="Range (high)" value={comps.max_price} />
          </div>
          {comps.median_price_per_sqft && (
            <p className="text-xs text-gray-500 mb-3">
              Median price/sqft: <strong>${comps.median_price_per_sqft.toFixed(0)}</strong>
              <span className="ml-1">· {comps.count} sales</span>
            </p>
          )}
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full bg-white text-xs">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-3 py-2 text-gray-600 uppercase font-semibold">Address</th>
                  <th className="text-right px-3 py-2 text-gray-600 uppercase font-semibold">Distance</th>
                  <th className="text-right px-3 py-2 text-gray-600 uppercase font-semibold">Sold</th>
                  <th className="text-right px-3 py-2 text-gray-600 uppercase font-semibold">Price</th>
                  <th className="text-right px-3 py-2 text-gray-600 uppercase font-semibold">$/sqft</th>
                  <th className="text-right px-3 py-2 text-gray-600 uppercase font-semibold">Beds</th>
                  <th className="text-right px-3 py-2 text-gray-600 uppercase font-semibold">Baths</th>
                  <th className="text-right px-3 py-2 text-gray-600 uppercase font-semibold">Sqft</th>
                </tr>
              </thead>
              <tbody>
                {comps.comps.map((c) => (
                  <tr key={`${c.property_id}-${c.sale_date}`} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-3 py-2">
                      <Link to={`/properties/${c.property_id}`} className="text-blue-600 hover:underline">
                        {c.address}
                      </Link>
                      <div className="text-gray-400 text-xs">{c.city}</div>
                    </td>
                    <td className="px-3 py-2 text-right">{c.distance_miles.toFixed(2)} mi</td>
                    <td className="px-3 py-2 text-right text-gray-500">{c.sale_date}</td>
                    <td className="px-3 py-2 text-right font-mono font-semibold">{fmtMoney(c.sale_price)}</td>
                    <td className="px-3 py-2 text-right">{c.price_per_sqft ? `$${c.price_per_sqft.toFixed(0)}` : "—"}</td>
                    <td className="px-3 py-2 text-right">{c.bedrooms ?? "—"}</td>
                    <td className="px-3 py-2 text-right">{c.bathrooms ?? "—"}</td>
                    <td className="px-3 py-2 text-right">{c.square_footage ? c.square_footage.toLocaleString() : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

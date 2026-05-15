import { Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import MapView from "./pages/MapView";
import ForeclosuresPage from "./pages/ForeclosuresPage";
import EvictionsPage from "./pages/EvictionsPage";
import BankSeizuresPage from "./pages/BankSeizuresPage";
import SalesPage from "./pages/SalesPage";
import PriceDropsPage from "./pages/PriceDropsPage";
import PropertyDetail from "./pages/PropertyDetail";

const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/map", label: "Map" },
  { to: "/price-drops", label: "Price Drops" },
  { to: "/foreclosures", label: "Foreclosures" },
  { to: "/evictions", label: "Evictions" },
  { to: "/bank-seizures", label: "Bank Seizures" },
  { to: "/sales", label: "Sales" },
];

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-chicago-blue text-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Chicago Property Tracker</h1>
            <p className="text-xs text-blue-200">Chicago · Lincolnwood · Sauganash · Skokie · Evanston, IL</p>
          </div>
          <nav className="flex gap-1">
            {NAV.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-white text-chicago-blue"
                      : "text-blue-100 hover:bg-blue-800"
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/map" element={<MapView />} />
          <Route path="/price-drops" element={<PriceDropsPage />} />
          <Route path="/foreclosures" element={<ForeclosuresPage />} />
          <Route path="/evictions" element={<EvictionsPage />} />
          <Route path="/bank-seizures" element={<BankSeizuresPage />} />
          <Route path="/sales" element={<SalesPage />} />
          <Route path="/properties/:id" element={<PropertyDetail />} />
        </Routes>
      </main>

      <footer className="bg-gray-800 text-gray-400 text-xs text-center py-3">
        Data sources: Cook County Assessor · Cook County Circuit Court · Chicago Data Portal · Cook County Treasurer
      </footer>
    </div>
  );
}

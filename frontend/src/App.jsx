import { Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import MapView from "./pages/MapView";
import ForeclosuresPage from "./pages/ForeclosuresPage";
import EvictionsPage from "./pages/EvictionsPage";
import BankSeizuresPage from "./pages/BankSeizuresPage";
import SalesPage from "./pages/SalesPage";
import PriceDropsPage from "./pages/PriceDropsPage";
import MarketMetricsPage from "./pages/MarketMetricsPage";
import PropertyDetail from "./pages/PropertyDetail";
import LoginPage from "./pages/LoginPage";
import SetupTOTPPage from "./pages/SetupTOTPPage";
import RequireAuth from "./components/RequireAuth";
import { useAuth } from "./contexts/AuthContext";

const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/map", label: "Map" },
  { to: "/price-drops", label: "Price Drops" },
  { to: "/market-metrics", label: "Market Metrics" },
  { to: "/foreclosures", label: "Foreclosures" },
  { to: "/evictions", label: "Evictions" },
  { to: "/bank-seizures", label: "Bank Seizures" },
  { to: "/sales", label: "Sales" },
];

function MainLayout({ children }) {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-chicago-blue text-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Chicago Property Tracker</h1>
            <p className="text-xs text-blue-200">Chicago · Lincolnwood · Sauganash · Skokie · Evanston, IL</p>
          </div>
          <nav className="flex gap-1 items-center">
            {NAV.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                    isActive ? "bg-white text-chicago-blue" : "text-blue-100 hover:bg-blue-800"
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
            {user && (
              <button
                onClick={logout}
                className="ml-4 px-3 py-1.5 text-sm text-blue-100 hover:text-white border border-blue-700 hover:border-white rounded transition-colors"
                title={`Signed in as ${user.username}`}
              >
                Sign out
              </button>
            )}
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">{children}</main>

      <footer className="bg-gray-800 text-gray-400 text-xs text-center py-3">
        Data sources: Cook County Assessor · Cook County Treasurer · Chicago Data Portal · Redfin · Realtor.com
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/setup-totp" element={<SetupTOTPPage />} />

      <Route
        path="/*"
        element={
          <RequireAuth>
            <MainLayout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/map" element={<MapView />} />
                <Route path="/price-drops" element={<PriceDropsPage />} />
                <Route path="/market-metrics" element={<MarketMetricsPage />} />
                <Route path="/foreclosures" element={<ForeclosuresPage />} />
                <Route path="/evictions" element={<EvictionsPage />} />
                <Route path="/bank-seizures" element={<BankSeizuresPage />} />
                <Route path="/sales" element={<SalesPage />} />
                <Route path="/properties/:id" element={<PropertyDetail />} />
              </Routes>
            </MainLayout>
          </RequireAuth>
        }
      />
    </Routes>
  );
}

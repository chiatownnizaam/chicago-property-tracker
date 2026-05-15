import { useEffect, useState } from "react";
import { getEvictions } from "../services/api";
import FilterBar from "../components/FilterBar";
import DataTable from "../components/DataTable";
import PropertyCell from "../components/PropertyCell";

const STATUS_COLORS = {
  filed: "bg-blue-100 text-blue-700",
  served: "bg-indigo-100 text-indigo-700",
  judgment_for_plaintiff: "bg-red-100 text-red-700",
  judgment_for_defendant: "bg-green-100 text-green-700",
  dismissed: "bg-gray-100 text-gray-700",
  executed: "bg-orange-100 text-orange-700",
};

const COLUMNS = [
  { key: "property", label: "Property", render: (_, row) => <PropertyCell property={row.property} /> },
  { key: "case_number", label: "Case #" },
  { key: "status", label: "Status", render: (v) => (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[v] || ""}`}>
      {v?.replace(/_/g, " ")}
    </span>
  )},
  { key: "filing_date", label: "Filed" },
  { key: "plaintiff", label: "Landlord" },
  { key: "defendant", label: "Tenant" },
  { key: "eviction_reason", label: "Reason" },
  { key: "monthly_rent", label: "Monthly Rent", render: (v) =>
    v ? `$${Number(v).toLocaleString()}` : "—"
  },
  { key: "amount_owed", label: "Amount Owed", render: (v) =>
    v ? `$${Number(v).toLocaleString()}` : "—"
  },
];

export default function EvictionsPage() {
  const [data, setData] = useState([]);
  const [filters, setFilters] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = {};
    if (filters.city) params.city = filters.city;
    if (filters.date_from) params.date_from = filters.date_from;
    if (filters.date_to) params.date_to = filters.date_to;
    getEvictions({ ...params, limit: 200 })
      .then(setData)
      .finally(() => setLoading(false));
  }, [filters]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-gray-800">Evictions</h2>
        <p className="text-sm text-gray-500">Cook County Circuit Court eviction filings</p>
      </div>
      <FilterBar filters={filters} onChange={setFilters} />
      {loading ? (
        <div className="text-center py-12 text-gray-400">Loading…</div>
      ) : (
        <>
          <p className="text-xs text-gray-500">{data.length} records</p>
          <DataTable columns={COLUMNS} rows={data} emptyMessage="No eviction records found." />
        </>
      )}
    </div>
  );
}

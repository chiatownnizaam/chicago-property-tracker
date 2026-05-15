import { useEffect, useState } from "react";
import { getBankSeizures } from "../services/api";
import FilterBar from "../components/FilterBar";
import DataTable from "../components/DataTable";
import PropertyCell from "../components/PropertyCell";

const TYPE_COLORS = {
  tax_lien: "bg-red-100 text-red-700",
  tax_sale: "bg-orange-100 text-orange-700",
  reo: "bg-purple-100 text-purple-700",
  hud: "bg-blue-100 text-blue-700",
  fdic: "bg-indigo-100 text-indigo-700",
  city_owned: "bg-gray-100 text-gray-700",
  county_owned: "bg-yellow-100 text-yellow-700",
};

const COLUMNS = [
  { key: "property", label: "Property", render: (_, row) => <PropertyCell property={row.property} /> },
  { key: "seizure_type", label: "Type", render: (v) => (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLORS[v] || ""}`}>
      {v?.replace(/_/g, " ").toUpperCase()}
    </span>
  )},
  { key: "seizure_date", label: "Seizure Date" },
  { key: "seizing_entity", label: "Seizing Entity" },
  { key: "tax_delinquency_amount", label: "Tax Delinquency", render: (v) =>
    v ? `$${Number(v).toLocaleString()}` : "—"
  },
  { key: "lien_amount", label: "Lien Amount", render: (v) =>
    v ? `$${Number(v).toLocaleString()}` : "—"
  },
  { key: "is_active", label: "Active", render: (v) => (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${v ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"}`}>
      {v ? "Yes" : "Released"}
    </span>
  )},
  { key: "document_number", label: "Document #" },
];

export default function BankSeizuresPage() {
  const [data, setData] = useState([]);
  const [filters, setFilters] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = {};
    if (filters.city) params.city = filters.city;
    if (filters.date_from) params.date_from = filters.date_from;
    if (filters.date_to) params.date_to = filters.date_to;
    getBankSeizures({ ...params, limit: 200 })
      .then(setData)
      .finally(() => setLoading(false));
  }, [filters]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-gray-800">Bank & Government Seizures</h2>
        <p className="text-sm text-gray-500">Tax liens, REO properties, HUD/FDIC seizures</p>
      </div>
      <FilterBar filters={filters} onChange={setFilters} />
      {loading ? (
        <div className="text-center py-12 text-gray-400">Loading…</div>
      ) : (
        <>
          <p className="text-xs text-gray-500">{data.length} records</p>
          <DataTable columns={COLUMNS} rows={data} emptyMessage="No seizure records found." />
        </>
      )}
    </div>
  );
}

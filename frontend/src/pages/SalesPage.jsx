import { useEffect, useState } from "react";
import { getSales } from "../services/api";
import FilterBar from "../components/FilterBar";
import DataTable from "../components/DataTable";
import PropertyCell from "../components/PropertyCell";

const COLUMNS = [
  { key: "property", label: "Property", render: (_, row) => <PropertyCell property={row.property} /> },
  { key: "sale_date", label: "Sale Date" },
  { key: "sale_price", label: "Sale Price", render: (v) =>
    v ? `$${Number(v).toLocaleString()}` : "—"
  },
  { key: "price_per_sqft", label: "$/sqft", render: (v) =>
    v ? `$${Number(v).toFixed(0)}` : "—"
  },
  { key: "buyer_name", label: "Buyer" },
  { key: "seller_name", label: "Seller" },
  { key: "deed_type", label: "Deed Type" },
  { key: "document_number", label: "Document #" },
  { key: "source", label: "Source" },
];

export default function SalesPage() {
  const [data, setData] = useState([]);
  const [filters, setFilters] = useState({});
  const [loading, setLoading] = useState(true);
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");

  useEffect(() => {
    setLoading(true);
    const params = {};
    if (filters.city) params.city = filters.city;
    if (filters.date_from) params.date_from = filters.date_from;
    if (filters.date_to) params.date_to = filters.date_to;
    if (minPrice) params.min_price = minPrice;
    if (maxPrice) params.max_price = maxPrice;
    getSales({ ...params, limit: 200 })
      .then(setData)
      .finally(() => setLoading(false));
  }, [filters, minPrice, maxPrice]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-gray-800">Property Sales</h2>
        <p className="text-sm text-gray-500">Cook County Recorder of Deeds</p>
      </div>
      <FilterBar filters={filters} onChange={setFilters} />
      <div className="flex gap-3 -mt-2">
        <input
          type="number"
          placeholder="Min price"
          className="border border-gray-300 rounded px-2 py-1.5 text-sm w-36"
          value={minPrice}
          onChange={(e) => setMinPrice(e.target.value)}
        />
        <input
          type="number"
          placeholder="Max price"
          className="border border-gray-300 rounded px-2 py-1.5 text-sm w-36"
          value={maxPrice}
          onChange={(e) => setMaxPrice(e.target.value)}
        />
      </div>
      {loading ? (
        <div className="text-center py-12 text-gray-400">Loading…</div>
      ) : (
        <>
          <p className="text-xs text-gray-500">{data.length} records</p>
          <DataTable columns={COLUMNS} rows={data} emptyMessage="No sales records found." />
        </>
      )}
    </div>
  );
}

const CITIES = ["", "Chicago", "Lincolnwood", "Sauganash", "Skokie", "Evanston"];

export default function FilterBar({ filters, onChange }) {
  return (
    <div className="flex flex-wrap gap-3 mb-4 bg-white p-3 rounded-lg shadow-sm border border-gray-200">
      <select
        className="border border-gray-300 rounded px-2 py-1.5 text-sm"
        value={filters.city || ""}
        onChange={(e) => onChange({ ...filters, city: e.target.value })}
      >
        {CITIES.map((c) => (
          <option key={c} value={c}>
            {c || "All Cities"}
          </option>
        ))}
      </select>

      <input
        type="date"
        className="border border-gray-300 rounded px-2 py-1.5 text-sm"
        value={filters.date_from || ""}
        onChange={(e) => onChange({ ...filters, date_from: e.target.value })}
        placeholder="From date"
      />
      <input
        type="date"
        className="border border-gray-300 rounded px-2 py-1.5 text-sm"
        value={filters.date_to || ""}
        onChange={(e) => onChange({ ...filters, date_to: e.target.value })}
        placeholder="To date"
      />

      <button
        className="ml-auto text-sm text-gray-500 hover:text-gray-800 underline"
        onClick={() => onChange({})}
      >
        Clear filters
      </button>
    </div>
  );
}

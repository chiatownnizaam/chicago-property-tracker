export default function DataTable({ columns, rows, emptyMessage = "No records found." }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="text-center text-gray-400 py-12 bg-white rounded-lg border border-gray-200">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
      <table className="min-w-full bg-white text-sm">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            {columns.map((col) => (
              <th
                key={col.key}
                className="px-4 py-2.5 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={row.id ?? i}
              className={`border-b border-gray-100 hover:bg-gray-50 transition-colors ${
                i % 2 === 0 ? "" : "bg-gray-50/40"
              }`}
            >
              {columns.map((col) => (
                <td key={col.key} className="px-4 py-2.5 text-gray-700">
                  {col.render ? col.render(row[col.key], row) : row[col.key] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

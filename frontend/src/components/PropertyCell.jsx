import { Link } from "react-router-dom";

export default function PropertyCell({ property }) {
  if (!property) return <span className="text-gray-400">—</span>;
  return (
    <Link
      to={`/properties/${property.id}`}
      className="block hover:text-blue-700"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="font-medium text-blue-600 hover:underline leading-tight">
        {property.address}
      </div>
      <div className="text-xs text-gray-500 leading-tight">
        {property.city}{property.zip_code ? `, ${property.zip_code}` : ""}
      </div>
    </Link>
  );
}

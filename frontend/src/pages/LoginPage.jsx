import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login, saveToken } from "../services/auth";
import { useAuth } from "../contexts/AuthContext";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const { refreshUser } = useAuth();

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await login(username, password, totpCode || undefined);
      saveToken(res.access_token);

      if (res.requires_totp_setup) {
        navigate("/setup-totp");
      } else {
        await refreshUser();
        navigate("/");
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-900 to-slate-900 p-4">
      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-lg shadow-xl p-7 w-full max-w-sm space-y-4"
      >
        <div>
          <h1 className="text-xl font-bold text-gray-800">Chicago Property Tracker</h1>
          <p className="text-xs text-gray-500 mt-1">Sign in with username, password, and MS Authenticator code.</p>
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">Username</label>
          <input
            type="text"
            autoFocus
            autoComplete="username"
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">Password</label>
          <input
            type="password"
            autoComplete="current-password"
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">
            MS Authenticator code <span className="text-gray-400 font-normal">(skip on first login)</span>
          </label>
          <input
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            placeholder="000000"
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm font-mono tracking-widest focus:outline-none focus:border-blue-500"
            value={totpCode}
            onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ""))}
          />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-xs rounded px-3 py-2">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full bg-blue-600 text-white font-semibold py-2 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>

        <p className="text-xs text-gray-400 text-center mt-4">
          Open MS Authenticator → enter the 6-digit code shown for this account.
        </p>
      </form>
    </div>
  );
}

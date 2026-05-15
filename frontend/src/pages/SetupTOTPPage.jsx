import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { setupTotp, confirmTotp, saveToken } from "../services/auth";
import { useAuth } from "../contexts/AuthContext";

export default function SetupTOTPPage() {
  const [setup, setSetup] = useState(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const { refreshUser } = useAuth();

  useEffect(() => {
    setupTotp()
      .then(setSetup)
      .catch((e) => setError(e.response?.data?.detail || "Failed to generate QR"));
  }, []);

  async function handleConfirm(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await confirmTotp(code);
      saveToken(res.access_token);
      await refreshUser();
      navigate("/");
    } catch (err) {
      setError(err.response?.data?.detail || "Invalid code");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-900 to-slate-900 p-4">
      <div className="bg-white rounded-lg shadow-xl p-7 w-full max-w-md space-y-5">
        <div>
          <h1 className="text-xl font-bold text-gray-800">Set up MS Authenticator</h1>
          <p className="text-xs text-gray-500 mt-1">
            One-time setup. Scan the QR code with the MS Authenticator app, then enter the 6-digit code it shows.
          </p>
        </div>

        {!setup && !error && (
          <div className="text-center py-8 text-gray-400 text-sm">Generating QR code…</div>
        )}

        {setup && (
          <>
            <div className="flex justify-center">
              <img
                src={setup.qr_code_data_url}
                alt="Scan with MS Authenticator"
                className="border-2 border-gray-200 rounded"
                width={220}
                height={220}
              />
            </div>

            <details className="text-xs text-gray-500">
              <summary className="cursor-pointer hover:text-gray-700">Can't scan? Enter the secret manually</summary>
              <code className="block bg-gray-100 p-2 mt-2 rounded font-mono text-xs break-all select-all">
                {setup.secret}
              </code>
            </details>

            <form onSubmit={handleConfirm} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">
                  Enter the 6-digit code from the app
                </label>
                <input
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  placeholder="000000"
                  autoFocus
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm font-mono tracking-widest text-center focus:outline-none focus:border-blue-500"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  required
                />
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-xs rounded px-3 py-2">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={busy || code.length !== 6}
                className="w-full bg-blue-600 text-white font-semibold py-2 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {busy ? "Confirming…" : "Confirm and sign in"}
              </button>
            </form>
          </>
        )}

        {error && !setup && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-xs rounded px-3 py-2">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}

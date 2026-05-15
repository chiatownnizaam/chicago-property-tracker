import axios from "axios";

const TOKEN_KEY = "cpt_token";

export const api = axios.create({ baseURL: "/api/v1" });
export const authApi = axios.create({ baseURL: "/auth" });

// Attach token to every request
[api, authApi].forEach((client) => {
  client.interceptors.request.use((config) => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  });
});

// On 401, clear token and bounce to /login
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      if (!window.location.pathname.startsWith("/login") &&
          !window.location.pathname.startsWith("/setup-totp")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

export const saveToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

export const login = (username, password, totp_code) =>
  authApi.post("/login", { username, password, totp_code }).then((r) => r.data);

export const setupTotp = () =>
  authApi.post("/setup-totp").then((r) => r.data);

export const confirmTotp = (totp_code) =>
  authApi.post("/confirm-totp", { totp_code }).then((r) => r.data);

export const getMe = () => authApi.get("/me").then((r) => r.data);

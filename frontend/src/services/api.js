import axios from "axios";

const api = axios.create({ baseURL: "/api/v1" });

export const getProperties = (params = {}) =>
  api.get("/properties", { params }).then((r) => r.data);

export const getProperty = (id) =>
  api.get(`/properties/${id}`).then((r) => r.data);

export const getStats = () =>
  api.get("/properties/stats").then((r) => r.data);

export const getForeclosures = (params = {}) =>
  api.get("/foreclosures", { params }).then((r) => r.data);

export const getEvictions = (params = {}) =>
  api.get("/evictions", { params }).then((r) => r.data);

export const getBankSeizures = (params = {}) =>
  api.get("/bank-seizures", { params }).then((r) => r.data);

export const getSales = (params = {}) =>
  api.get("/sales", { params }).then((r) => r.data);

export const getPropertyHistory = (id) =>
  api.get(`/properties/${id}/history`).then((r) => r.data);

export const getListings = (params = {}) =>
  api.get("/listings", { params }).then((r) => r.data);

export const getPriceDrops = (params = {}) =>
  api.get("/listings/price-drops", { params }).then((r) => r.data);

export const getListing = (id) =>
  api.get(`/listings/${id}`).then((r) => r.data);

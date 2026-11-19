/**
 * Credence API client utilities and base URL configuration.
 * Automatically adapts between relative URLs (same-origin / proxy)
 * and external backend URLs via VITE_API_BASE_URL.
 */

export const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');

export function apiUrl(endpoint) {
  const clean = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${API_BASE}${clean}`;
}

export function getAuthHeaders() {
  const token = localStorage.getItem('credence_token');
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

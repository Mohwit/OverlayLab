import type { DiffDTO, FileContentDTO, FileEntryDTO, GraphDTO, HealthPreflightDTO, LayerFilesDTO, LayerInfoDTO } from './types';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  preflight: () => request<HealthPreflightDTO>('/health/preflight'),
  getGraph: () => request<GraphDTO>('/graph'),
  createSession: (name?: string) => request('/session/create', { method: 'POST', body: JSON.stringify({ name: name ?? null }) }),
  createNode: (session_id: string, from_node_id?: string) =>
    request('/node/create', { method: 'POST', body: JSON.stringify({ session_id, from_node_id: from_node_id ?? null }) }),
  branchSession: (node_id: string, name?: string) =>
    request(`/session/branch/${node_id}`, { method: 'POST', body: JSON.stringify({ name: name ?? null }) }),
  revertNode: (node_id: string, session_id: string) =>
    request(`/node/revert/${node_id}`, { method: 'POST', body: JSON.stringify({ session_id }) }),
  listFiles: async (node_id: string) => (await request<{ node_id: string; files: FileEntryDTO[] }>(`/node/${node_id}/files`)).files,
  readFileContent: async (node_id: string, path: string) =>
    (await request<FileContentDTO>(`/node/${node_id}/file?path=${encodeURIComponent(path)}`)).content,
  getLayerFiles: async (node_id: string, layer: 'merged' | 'upper' | 'lower', index?: number) => {
    const params = new URLSearchParams({ layer });
    if (index !== undefined) {
      params.set('index', String(index));
    }
    return (await request<LayerFilesDTO>(`/node/${node_id}/layer-files?${params.toString()}`)).files;
  },
  writeFile: (node_id: string, path: string, content: string, mode: 'overwrite' | 'append') =>
    request(`/node/${node_id}/file`, { method: 'POST', body: JSON.stringify({ path, content, mode }) }),
  deleteFile: (node_id: string, path: string) =>
    request(`/node/${node_id}/file`, { method: 'DELETE', body: JSON.stringify({ path }) }),
  getLayers: (node_id: string) => request<LayerInfoDTO>(`/node/${node_id}/layers`),
  getDiff: (from_node_id: string, to_node_id: string) =>
    request<DiffDTO>(`/diff?from_node_id=${encodeURIComponent(from_node_id)}&to_node_id=${encodeURIComponent(to_node_id)}`),
};

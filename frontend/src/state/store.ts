import { create } from 'zustand';

import { api } from './api';
import type { DiffDTO, FileEntryDTO, GraphDTO, HealthPreflightDTO, LayerInfoDTO } from './types';

interface AppState {
  graph: GraphDTO;
  preflight: HealthPreflightDTO | null;
  selectedNodeId: string | null;
  files: FileEntryDTO[];
  layerInfo: LayerInfoDTO | null;
  diff: DiffDTO | null;
  loading: boolean;
  error: string | null;
  fetchGraph: () => Promise<void>;
  selectNode: (nodeId: string) => Promise<void>;
  createSession: () => Promise<void>;
  createNode: (nodeId: string) => Promise<void>;
  branchSession: (nodeId: string) => Promise<void>;
  revertToNode: (nodeId: string) => Promise<void>;
  writeFile: (path: string, content: string, mode: 'overwrite' | 'append') => Promise<void>;
  deleteFile: (path: string) => Promise<void>;
  readSelectedFileContent: (path: string) => Promise<string>;
  getLayerFilesForSelectedNode: (layer: 'merged' | 'upper' | 'lower', index?: number) => Promise<FileEntryDTO[]>;
  loadDiffAgainstActive: (nodeId: string) => Promise<void>;
}

const emptyGraph: GraphDTO = { sessions: [], nodes: [], edges: [] };

export const useAppStore = create<AppState>((set, get) => ({
  graph: emptyGraph,
  preflight: null,
  selectedNodeId: null,
  files: [],
  layerInfo: null,
  diff: null,
  loading: false,
  error: null,

  fetchGraph: async () => {
    set({ loading: true, error: null });
    try {
      const preflight = await api.preflight();
      set({ preflight });
      if (!preflight.linux || !preflight.overlay_supported || !preflight.mount_capable) {
        set({ loading: false, error: preflight.message });
        return;
      }
      const graph = await api.getGraph();
      set((state) => ({
        graph,
        loading: false,
        selectedNodeId: state.selectedNodeId ?? graph.nodes[0]?.node_id ?? null,
      }));
      const selected = get().selectedNodeId;
      if (selected) {
        await get().selectNode(selected);
      }
    } catch (err) {
      set({ loading: false, error: String(err) });
    }
  },

  selectNode: async (nodeId: string) => {
    try {
      const [files, layerInfo] = await Promise.all([api.listFiles(nodeId), api.getLayers(nodeId)]);
      set({ selectedNodeId: nodeId, files, layerInfo, error: null });
    } catch (err) {
      set({ error: String(err) });
    }
  },

  createSession: async () => {
    try {
      await api.createSession();
      await get().fetchGraph();
    } catch (err) {
      set({ error: String(err) });
    }
  },

  createNode: async (nodeId: string) => {
    const node = get().graph.nodes.find((n) => n.node_id === nodeId);
    if (!node) {
      return;
    }
    try {
      await api.createNode(node.session_id, nodeId);
      await get().fetchGraph();
    } catch (err) {
      set({ error: String(err) });
    }
  },

  branchSession: async (nodeId: string) => {
    try {
      await api.branchSession(nodeId);
      await get().fetchGraph();
    } catch (err) {
      set({ error: String(err) });
    }
  },

  revertToNode: async (nodeId: string) => {
    const node = get().graph.nodes.find((n) => n.node_id === nodeId);
    if (!node) {
      return;
    }
    try {
      await api.revertNode(nodeId, node.session_id);
      await get().fetchGraph();
      await get().selectNode(nodeId);
    } catch (err) {
      set({ error: String(err) });
    }
  },

  writeFile: async (path: string, content: string, mode: 'overwrite' | 'append') => {
    const nodeId = get().selectedNodeId;
    if (!nodeId) {
      return;
    }
    try {
      await api.writeFile(nodeId, path, content, mode);
      await get().selectNode(nodeId);
    } catch (err) {
      set({ error: String(err) });
    }
  },

  deleteFile: async (path: string) => {
    const nodeId = get().selectedNodeId;
    if (!nodeId) {
      return;
    }
    try {
      await api.deleteFile(nodeId, path);
      await get().selectNode(nodeId);
    } catch (err) {
      set({ error: String(err) });
    }
  },

  readSelectedFileContent: async (path: string) => {
    const nodeId = get().selectedNodeId;
    if (!nodeId) {
      return '';
    }
    try {
      return await api.readFileContent(nodeId, path);
    } catch (err) {
      set({ error: String(err) });
      return '';
    }
  },

  getLayerFilesForSelectedNode: async (layer: 'merged' | 'upper' | 'lower', index?: number) => {
    const nodeId = get().selectedNodeId;
    if (!nodeId) {
      return [];
    }
    try {
      return await api.getLayerFiles(nodeId, layer, index);
    } catch (err) {
      set({ error: String(err) });
      return [];
    }
  },

  loadDiffAgainstActive: async (nodeId: string) => {
    const node = get().graph.nodes.find((n) => n.node_id === nodeId);
    if (!node) {
      return;
    }
    const activeNode = get().graph.sessions.find((s) => s.session_id === node.session_id)?.active_node_id;
    if (!activeNode) {
      return;
    }
    try {
      const diff = await api.getDiff(activeNode, nodeId);
      set({ diff });
    } catch (err) {
      set({ error: String(err) });
    }
  },
}));

import { useEffect, useMemo, useState } from 'react';

import OverlayLearningCue from './OverlayLearningCue';
import type { FileEntryDTO, LayerInfoDTO, NodeDTO } from '../state/types';

interface Props {
  layerInfo: LayerInfoDTO | null;
  nodes: NodeDTO[];
  onSelectNode: (nodeId: string) => void | Promise<void>;
  onHoverNodeChange: (nodeId: string | null) => void;
  refreshToken: string;
  onLoadLayerFiles: (layer: 'merged' | 'upper' | 'lower', index?: number) => Promise<FileEntryDTO[]>;
}

function PathChip({
  label,
  value,
  tooltip,
  onHover,
  linkedNodeId,
  onSelectNode,
  onHoverNodeChange,
}: {
  label: string;
  value: string;
  tooltip: string | null;
  onHover: () => void;
  linkedNodeId: string | null;
  onSelectNode: (nodeId: string) => void | Promise<void>;
  onHoverNodeChange: (nodeId: string | null) => void;
}) {
  const isLinked = Boolean(linkedNodeId);

  return (
    <button
      type="button"
      className={[
        'relative w-full rounded-xl border p-2 text-left transition',
        isLinked
          ? 'border-sky-200 bg-sky-50/50 hover:border-sky-400 hover:bg-sky-50'
          : 'border-slate-200 bg-white hover:border-slate-300',
      ].join(' ')}
      onMouseEnter={() => {
        onHover();
        onHoverNodeChange(linkedNodeId);
      }}
      onClick={() => {
        if (linkedNodeId) {
          void onSelectNode(linkedNodeId);
        }
      }}
      title={linkedNodeId ? `Select linked node ${linkedNodeId}` : 'No node mapped for this path'}
    >
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="flex items-center justify-between gap-2">
        <div className="break-all font-mono text-[11px] text-slate-700">{value}</div>
        {linkedNodeId && (
          <span className="shrink-0 rounded bg-blue-100 px-1.5 py-0.5 text-[9px] font-medium text-blue-700">
            node {linkedNodeId.replace(/^node_/, '').slice(0, 6)}
          </span>
        )}
      </div>
      {tooltip && (
        <div className="pointer-events-none absolute left-0 top-full z-10 mt-1 max-h-44 w-full overflow-auto rounded-xl border border-slate-300 bg-white p-2 text-[11px] text-slate-700 shadow-xl">
          <pre className="whitespace-pre-wrap font-mono">{tooltip}</pre>
        </div>
      )}
    </button>
  );
}

function normalizePath(path: string): string {
  const trimmed = path.trim();
  if (trimmed.length > 1 && trimmed.endsWith('/')) {
    return trimmed.slice(0, -1);
  }
  return trimmed;
}

function parseHoverKey(key: string): { layer: 'merged' | 'upper' | 'lower'; index?: number } | null {
  if (key === 'merged') {
    return { layer: 'merged' };
  }
  if (key === 'upper') {
    return { layer: 'upper' };
  }
  if (key.startsWith('lower-')) {
    const raw = key.replace('lower-', '');
    const idx = Number.parseInt(raw, 10);
    if (!Number.isNaN(idx) && idx >= 0) {
      return { layer: 'lower', index: idx };
    }
  }
  return null;
}

export default function LayerInspector({
  layerInfo,
  nodes,
  onSelectNode,
  onHoverNodeChange,
  refreshToken,
  onLoadLayerFiles,
}: Props) {
  const [hoverKey, setHoverKey] = useState<string | null>(null);
  const [cache, setCache] = useState<Record<string, FileEntryDTO[]>>({});

  useEffect(() => {
    setHoverKey(null);
    setCache({});
    onHoverNodeChange(null);
  }, [layerInfo?.node_id, onHoverNodeChange]);

  // Invalidate cached layer previews whenever selected node file content changes.
  // This keeps "upperdir" hover previews accurate immediately after Save/Delete.
  useEffect(() => {
    setCache({});
  }, [refreshToken, layerInfo?.node_id]);

  const tooltip = useMemo(() => {
    if (!hoverKey) {
      return null;
    }
    const entries = cache[hoverKey];
    if (!entries) {
      return 'Loading files...';
    }
    if (entries.length === 0) {
      return 'No files in this layer path.';
    }
    return entries
      .slice(0, 20)
      .map((entry) => `${entry.type === 'dir' ? '[dir]' : '[file]'} ${entry.path}`)
      .join('\n');
  }, [cache, hoverKey]);

  const pathToNodeId = useMemo(() => {
    const map = new Map<string, string>();
    for (const node of nodes) {
      map.set(normalizePath(node.merged), node.node_id);
      map.set(normalizePath(node.upperdir), node.node_id);
      map.set(normalizePath(node.workdir), node.node_id);
    }
    return map;
  }, [nodes]);

  const nodeIdForPath = (path: string) => pathToNodeId.get(normalizePath(path)) ?? null;

  if (!layerInfo) {
    return <section className="rounded-2xl border border-slate-200 bg-white p-4 text-xs text-slate-500 shadow-sm">Select a node to inspect layers.</section>;
  }

  const loadKey = async (key: string, layer: 'merged' | 'upper' | 'lower', index?: number) => {
    setHoverKey(key);
    if (cache[key]) {
      return;
    }
    const files = await onLoadLayerFiles(layer, index);
    setCache((prev) => ({ ...prev, [key]: files }));
  };

  useEffect(() => {
    if (!hoverKey) {
      return;
    }
    const spec = parseHoverKey(hoverKey);
    if (!spec) {
      return;
    }
    let cancelled = false;
    void (async () => {
      const files = await onLoadLayerFiles(spec.layer, spec.index);
      if (!cancelled) {
        setCache((prev) => ({ ...prev, [hoverKey]: files }));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [hoverKey, refreshToken, onLoadLayerFiles]);

  return (
    <section
      className="space-y-2 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
      onMouseLeave={() => {
        setHoverKey(null);
        onHoverNodeChange(null);
      }}
    >
      <div className="flex items-center gap-1.5">
        <h3 className="text-sm font-semibold tracking-tight text-slate-800">Overlay Layer Inspector</h3>
        <OverlayLearningCue topic="layers" compact />
      </div>
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-2 text-[11px] text-slate-600">
        <div className="mb-1 flex items-center gap-2">
          <span className="rounded bg-slate-900 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-white">Read</span>
          <span>`merged` checks `upperdir` first, then each `lowerdir` in order.</span>
        </div>
        <div className="mb-1 flex items-center gap-2">
          <span className="rounded bg-emerald-700 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-white">Write</span>
          <span>All file edits go to `upperdir` (copy-on-write).</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded bg-indigo-700 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-white">Branch</span>
          <span>New branches reuse parent layers through `lowerdir` entries.</span>
        </div>
      </div>
      <p className="text-[11px] text-slate-500">Hover a linked path to highlight its node; click to select it.</p>
      <PathChip
        label="merged"
        value={layerInfo.merged}
        linkedNodeId={nodeIdForPath(layerInfo.merged)}
        tooltip={hoverKey === 'merged' ? tooltip : null}
        onHover={() => void loadKey('merged', 'merged')}
        onSelectNode={onSelectNode}
        onHoverNodeChange={onHoverNodeChange}
      />
      <PathChip
        label="upperdir"
        value={layerInfo.upperdir}
        linkedNodeId={nodeIdForPath(layerInfo.upperdir)}
        tooltip={hoverKey === 'upper' ? tooltip : null}
        onHover={() => void loadKey('upper', 'upper')}
        onSelectNode={onSelectNode}
        onHoverNodeChange={onHoverNodeChange}
      />
      <PathChip
        label="workdir"
        value={layerInfo.workdir}
        linkedNodeId={nodeIdForPath(layerInfo.workdir)}
        tooltip={null}
        onHover={() => setHoverKey(null)}
        onSelectNode={onSelectNode}
        onHoverNodeChange={onHoverNodeChange}
      />
      {layerInfo.lowerdirs.map((lower, idx) => (
        <PathChip
          key={lower}
          label={`lowerdir ${idx + 1}`}
          value={lower}
          linkedNodeId={nodeIdForPath(lower)}
          tooltip={hoverKey === `lower-${idx}` ? tooltip : null}
          onHover={() => void loadKey(`lower-${idx}`, 'lower', idx)}
          onSelectNode={onSelectNode}
          onHoverNodeChange={onHoverNodeChange}
        />
      ))}
    </section>
  );
}

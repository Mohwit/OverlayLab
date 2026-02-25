import { useEffect, useMemo, useState } from 'react';

import type { FileEntryDTO, LayerInfoDTO } from '../state/types';

interface Props {
  layerInfo: LayerInfoDTO | null;
  onLoadLayerFiles: (layer: 'merged' | 'upper' | 'lower', index?: number) => Promise<FileEntryDTO[]>;
}

function PathChip({
  label,
  value,
  tooltip,
  onHover,
}: {
  label: string;
  value: string;
  tooltip: string | null;
  onHover: () => void;
}) {
  return (
    <div className="relative rounded border border-slate-200 bg-slate-50 p-2" onMouseEnter={onHover}>
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="break-all font-mono text-[11px] text-slate-700">{value}</div>
      {tooltip && (
        <div className="pointer-events-none absolute left-0 top-full z-10 mt-1 max-h-44 w-full overflow-auto rounded border border-slate-300 bg-white p-2 text-[11px] text-slate-700 shadow-lg">
          <pre className="whitespace-pre-wrap font-mono">{tooltip}</pre>
        </div>
      )}
    </div>
  );
}

export default function LayerInspector({ layerInfo, onLoadLayerFiles }: Props) {
  const [hoverKey, setHoverKey] = useState<string | null>(null);
  const [cache, setCache] = useState<Record<string, FileEntryDTO[]>>({});

  useEffect(() => {
    setHoverKey(null);
    setCache({});
  }, [layerInfo?.node_id]);

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

  if (!layerInfo) {
    return <section className="rounded-xl border border-slate-200 bg-white p-4 text-xs text-slate-500">Select a node to inspect layers.</section>;
  }

  const loadKey = async (key: string, layer: 'merged' | 'upper' | 'lower', index?: number) => {
    setHoverKey(key);
    if (cache[key]) {
      return;
    }
    const files = await onLoadLayerFiles(layer, index);
    setCache((prev) => ({ ...prev, [key]: files }));
  };

  return (
    <section className="space-y-2 rounded-xl border border-slate-200 bg-white p-4" onMouseLeave={() => setHoverKey(null)}>
      <h3 className="text-sm font-semibold text-slate-700">Overlay Layer Inspector</h3>
      <PathChip label="merged" value={layerInfo.merged} tooltip={hoverKey === 'merged' ? tooltip : null} onHover={() => void loadKey('merged', 'merged')} />
      <PathChip label="upperdir" value={layerInfo.upperdir} tooltip={hoverKey === 'upper' ? tooltip : null} onHover={() => void loadKey('upper', 'upper')} />
      <PathChip label="workdir" value={layerInfo.workdir} tooltip={null} onHover={() => setHoverKey(null)} />
      {layerInfo.lowerdirs.map((lower, idx) => (
        <PathChip
          key={lower}
          label={`lowerdir ${idx + 1}`}
          value={lower}
          tooltip={hoverKey === `lower-${idx}` ? tooltip : null}
          onHover={() => void loadKey(`lower-${idx}`, 'lower', idx)}
        />
      ))}
    </section>
  );
}

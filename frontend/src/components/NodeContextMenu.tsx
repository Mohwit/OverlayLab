import type { MouseEvent } from 'react';

interface Props {
  x: number;
  y: number;
  nodeId: string;
  onCreateNode: (nodeId: string) => void;
  onBranch: (nodeId: string) => void;
  onRevert: (nodeId: string) => void;
  onInspectLayers: (nodeId: string) => void;
  onDiff: (nodeId: string) => void;
  onClose: () => void;
}

function MenuButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      className="w-full rounded-md px-3 py-2 text-left text-sm hover:bg-slate-100"
      onClick={onClick}
    >
      {label}
    </button>
  );
}

export default function NodeContextMenu(props: Props) {
  const stop = (e: MouseEvent) => e.stopPropagation();
  return (
    <div
      className="absolute z-50 min-w-56 rounded-lg border border-slate-200 bg-white p-2 shadow-xl"
      style={{ left: props.x, top: props.y }}
      onClick={stop}
    >
      <MenuButton label="Create Interaction Node" onClick={() => { props.onCreateNode(props.nodeId); props.onClose(); }} />
      <MenuButton label="Branch Session Here" onClick={() => { props.onBranch(props.nodeId); props.onClose(); }} />
      <MenuButton label="Revert Session Here" onClick={() => { props.onRevert(props.nodeId); props.onClose(); }} />
      <MenuButton label="Inspect Layers" onClick={() => { props.onInspectLayers(props.nodeId); props.onClose(); }} />
      <MenuButton label="Diff From Active" onClick={() => { props.onDiff(props.nodeId); props.onClose(); }} />
    </div>
  );
}

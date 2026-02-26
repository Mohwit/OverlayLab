import { useEffect, useMemo, useState } from 'react';

import DiffViewer from './components/DiffViewer';
import FilePanel from './components/FilePanel';
import GraphCanvas from './components/GraphCanvas';
import LayerInspector from './components/LayerInspector';
import OverlayLearningCue from './components/OverlayLearningCue';
import { useAppStore } from './state/store';

export default function App() {
  const [hoveredInspectorNodeId, setHoveredInspectorNodeId] = useState<string | null>(null);

  const {
    graph,
    preflight,
    selectedNodeId,
    files,
    layerInfo,
    diff,
    loading,
    error,
    fetchGraph,
    selectNode,
    resetLab,
    createNode,
    branchSession,
    revertToNode,
    writeFile,
    deleteFile,
    readSelectedFileContent,
    getLayerFilesForSelectedNode,
    loadDiffAgainstActive,
  } = useAppStore();

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  const layerRefreshToken = useMemo(
    () => files.map((file) => `${file.path}:${file.size}:${file.mtime}`).join('|'),
    [files],
  );

  const handleReset = () => {
    const confirmed = window.confirm(
      'Reset everything? This will delete all sessions, nodes, and file data.',
    );
    if (!confirmed) {
      return;
    }
    resetLab();
  };

  return (
    <main className="h-screen bg-slate-100 p-4 text-slate-900">
      <div className="mb-3 flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
        <div className="flex items-center gap-2">
          <h1 className="text-sm font-semibold tracking-tight text-slate-800">Recall-FS Session Graph Lab</h1>
          <OverlayLearningCue topic="overview" buttonText="Layer Guide" />
        </div>
        <div className="flex items-center gap-2">
          <button
            className="rounded-lg border border-rose-200 bg-white px-3 py-1.5 text-xs font-medium text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:border-rose-100 disabled:text-rose-300"
            onClick={handleReset}
            disabled={loading}
          >
            Reset
          </button>
        </div>
      </div>
      {preflight && !preflight.ready && (
        <div className="mb-3 rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-2 text-xs text-amber-800">
          Preflight check failed: {preflight.message}
        </div>
      )}
      {error && <div className="mb-3 rounded-xl border border-rose-200 bg-rose-50/70 px-3 py-2 text-xs text-rose-700">{error}</div>}
      <div className="grid h-[calc(100vh-96px)] grid-cols-[2fr_1fr] gap-3">
        <section className="min-h-0 rounded-2xl border border-slate-200 bg-white shadow-sm">
          <GraphCanvas
            graph={graph}
            selectedNodeId={selectedNodeId}
            hoveredNodeId={hoveredInspectorNodeId}
            onSelectNode={selectNode}
            onCreateNode={createNode}
            onBranch={branchSession}
            onRevert={revertToNode}
            onDiff={loadDiffAgainstActive}
          />
        </section>
        <aside className="min-h-0 space-y-3 overflow-auto pr-1">
          <LayerInspector
            layerInfo={layerInfo}
            nodes={graph.nodes}
            onSelectNode={selectNode}
            onHoverNodeChange={setHoveredInspectorNodeId}
            refreshToken={layerRefreshToken}
            onLoadLayerFiles={getLayerFilesForSelectedNode}
          />
          <FilePanel files={files} onWrite={writeFile} onDelete={deleteFile} onReadContent={readSelectedFileContent} />
          <DiffViewer diff={diff} />
        </aside>
      </div>
    </main>
  );
}

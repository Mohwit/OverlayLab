import { useEffect } from 'react';

import DiffViewer from './components/DiffViewer';
import FilePanel from './components/FilePanel';
import GraphCanvas from './components/GraphCanvas';
import LayerInspector from './components/LayerInspector';
import { useAppStore } from './state/store';

export default function App() {
  const {
    graph,
    preflight,
    selectedNodeId,
    files,
    layerInfo,
    diff,
    error,
    fetchGraph,
    selectNode,
    createSession,
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

  return (
    <main className="h-screen bg-gradient-to-br from-slate-100 to-slate-200 p-3 text-ink">
      <div className="mb-2 flex items-center justify-between rounded-xl border border-slate-300 bg-white px-3 py-2">
        <h1 className="text-sm font-semibold">OverlayFS Session Graph Lab</h1>
        <button
          className="rounded bg-slate-900 px-3 py-1 text-xs text-white disabled:cursor-not-allowed disabled:bg-slate-400"
          onClick={() => createSession()}
          disabled={!!preflight && (!preflight.linux || !preflight.overlay_supported || !preflight.mount_capable)}
        >
          New Session
        </button>
      </div>
      {preflight && (!preflight.linux || !preflight.overlay_supported || !preflight.mount_capable) && (
        <div className="mb-2 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          OverlayFS preflight failed: {preflight.message}
        </div>
      )}
      {error && <div className="mb-2 rounded border border-rose-300 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div>}
      <div className="grid h-[calc(100vh-72px)] grid-cols-[2fr_1fr] gap-3">
        <section className="min-h-0 rounded-xl border border-slate-300 bg-canvas">
          <GraphCanvas
            graph={graph}
            selectedNodeId={selectedNodeId}
            onSelectNode={selectNode}
            onCreateNode={createNode}
            onBranch={branchSession}
            onRevert={revertToNode}
            onDiff={loadDiffAgainstActive}
          />
        </section>
        <aside className="min-h-0 space-y-3 overflow-auto">
          <LayerInspector layerInfo={layerInfo} onLoadLayerFiles={getLayerFilesForSelectedNode} />
          <FilePanel files={files} onWrite={writeFile} onDelete={deleteFile} onReadContent={readSelectedFileContent} />
          <DiffViewer diff={diff} />
        </aside>
      </div>
    </main>
  );
}

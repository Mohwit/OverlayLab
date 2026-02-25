import type { DiffDTO } from '../state/types';

interface Props {
  diff: DiffDTO | null;
}

export default function DiffViewer({ diff }: Props) {
  if (!diff) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-4 text-xs text-slate-500">
        Use node menu {"->"} Diff From Active.
      </section>
    );
  }

  return (
    <section className="space-y-2 rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-slate-700">Diff Viewer</h3>
      <p className="text-xs text-slate-500">
        {diff.from_node_id} {"->"} {diff.to_node_id}
      </p>
      <div className="max-h-56 space-y-3 overflow-auto">
        {diff.files.length === 0 && <div className="text-xs text-slate-500">No text changes.</div>}
        {diff.files.map((file) => (
          <article key={file.path} className="rounded border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-200 px-2 py-1 text-xs">
              <span>{file.path}</span>
              <span className="uppercase text-slate-500">{file.status}</span>
            </div>
            <pre className="overflow-auto bg-slate-950 p-2 text-[11px] text-slate-50">{file.diff}</pre>
          </article>
        ))}
      </div>
    </section>
  );
}

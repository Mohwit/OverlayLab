import { useMemo, useState } from 'react';

import type { FileEntryDTO } from '../state/types';

interface Props {
  files: FileEntryDTO[];
  onWrite: (path: string, content: string, mode: 'overwrite' | 'append') => void;
  onDelete: (path: string) => void;
  onReadContent: (path: string) => Promise<string>;
}

function isEditable(path: string): boolean {
  return path.endsWith('.txt') || path.endsWith('.md');
}

export default function FilePanel({ files, onWrite, onDelete, onReadContent }: Props) {
  const [path, setPath] = useState('notes.md');
  const [content, setContent] = useState('');
  const [loadingPath, setLoadingPath] = useState<string | null>(null);

  const fileList = useMemo(() => files.filter((f) => f.type === 'file'), [files]);

  return (
    <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-slate-700">Files (merged view)</h3>
      <p className="text-xs text-slate-500">Edits trigger copy-on-write: only this node upperdir records changes.</p>
      <div className="grid gap-2">
        <input className="rounded border border-slate-300 px-2 py-1 text-sm" value={path} onChange={(e) => setPath(e.target.value)} placeholder="file.md" />
        <textarea
          className="min-h-24 rounded border border-slate-300 px-2 py-1 text-sm"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="File content"
        />
        <div className="flex gap-2">
          <button className="rounded bg-slate-900 px-3 py-1 text-xs text-white" onClick={() => onWrite(path, content, 'overwrite')}>Save</button>
          <button className="rounded bg-slate-700 px-3 py-1 text-xs text-white" onClick={() => onWrite(path, content, 'append')}>Append</button>
          <button className="rounded bg-rose-700 px-3 py-1 text-xs text-white" onClick={() => onDelete(path)}>Delete</button>
        </div>
      </div>
      <ul className="max-h-44 overflow-auto rounded border border-slate-200 text-xs">
        {fileList.map((file) => (
          <li key={file.path} className="flex items-center justify-between border-b border-slate-100 px-2 py-1">
            <button
              className="truncate text-left hover:underline disabled:cursor-not-allowed disabled:text-slate-400"
              disabled={!isEditable(file.path) || loadingPath === file.path}
              onClick={async () => {
                setPath(file.path);
                if (!isEditable(file.path)) {
                  return;
                }
                setLoadingPath(file.path);
                const text = await onReadContent(file.path);
                setContent(text);
                setLoadingPath(null);
              }}
              title={isEditable(file.path) ? 'Load content for editing' : 'Only .txt and .md are editable'}
            >
              {loadingPath === file.path ? `Loading ${file.path}...` : file.path}
            </button>
            <span className="text-slate-400">{file.size}b</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

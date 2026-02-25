import { useMemo, useRef, useState } from 'react';

import OverlayLearningCue from './OverlayLearningCue';
import type { FileEntryDTO } from '../state/types';

interface Props {
  files: FileEntryDTO[];
  onWrite: (path: string, content: string, mode: 'overwrite' | 'append') => Promise<void>;
  onDelete: (path: string) => Promise<void>;
  onReadContent: (path: string) => Promise<string>;
}

function isEditable(path: string): boolean {
  return path.endsWith('.txt') || path.endsWith('.md');
}

export default function FilePanel({ files, onWrite, onDelete, onReadContent }: Props) {
  const [path, setPath] = useState('notes.md');
  const [content, setContent] = useState('');
  const [loadingPath, setLoadingPath] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<'save' | 'delete' | null>(null);
  const [localHint, setLocalHint] = useState<string>('Select a file from below or type a new path.');
  const [baseline, setBaseline] = useState<{ path: string; content: string }>({ path: 'notes.md', content: '' });
  const pathInputRef = useRef<HTMLInputElement | null>(null);

  const fileList = useMemo(
    () => files.filter((f) => f.type === 'file').sort((a, b) => a.path.localeCompare(b.path)),
    [files],
  );
  const trimmedPath = path.trim();
  const selectedFile = fileList.find((file) => file.path === trimmedPath);
  const normalizedBaselinePath = baseline.path.trim();
  const isDirty = trimmedPath !== normalizedBaselinePath || content !== baseline.content;
  const canSubmit = trimmedPath.length > 0 && busyAction === null;
  const canSave = canSubmit && isDirty;
  const canDelete = canSubmit && Boolean(selectedFile);

  const loadFile = async (file: FileEntryDTO) => {
    setPath(file.path);
    if (!isEditable(file.path)) {
      setContent('');
      setBaseline({ path: file.path, content: '' });
      setLocalHint('Selected file is not text-editable here. Use a .txt or .md file.');
      return;
    }

    setLoadingPath(file.path);
    setLocalHint(`Loading ${file.path}...`);
    try {
      const text = await onReadContent(file.path);
      setContent(text);
      setBaseline({ path: file.path, content: text });
      setLocalHint(`Editing ${file.path}`);
    } finally {
      setLoadingPath(null);
    }
  };

  const saveFile = async () => {
    if (!canSave) {
      return;
    }
    setBusyAction('save');
    setLocalHint(`Saving ${trimmedPath}...`);
    try {
      await onWrite(trimmedPath, content, 'overwrite');
      setPath(trimmedPath);
      setBaseline({ path: trimmedPath, content });
      setLocalHint(`Saved ${trimmedPath}`);
    } finally {
      setBusyAction(null);
    }
  };

  const deleteFile = async () => {
    if (!canDelete) {
      return;
    }
    const confirmed = window.confirm(`Delete "${trimmedPath}" from this node?`);
    if (!confirmed) {
      return;
    }

    setBusyAction('delete');
    setLocalHint(`Deleting ${trimmedPath}...`);
    try {
      await onDelete(trimmedPath);
      if (selectedFile) {
        setContent('');
      }
      setBaseline({ path: trimmedPath, content: '' });
      setLocalHint(`Deleted ${trimmedPath}`);
    } finally {
      setBusyAction(null);
    }
  };

  const startNewFile = () => {
    setPath('');
    setContent('');
    setBaseline({ path: '', content: '' });
    setLoadingPath(null);
    setLocalHint('Creating a new file. Add a path and content, then click Save.');
    requestAnimationFrame(() => {
      pathInputRef.current?.focus();
    });
  };

  const revertChanges = () => {
    setPath(baseline.path);
    setContent(baseline.content);
    setLocalHint('Reverted unsaved changes.');
  };

  return (
    <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-1.5">
            <h3 className="text-sm font-semibold tracking-tight text-slate-800">File Editor</h3>
            <OverlayLearningCue topic="readwrite" compact />
          </div>
          <p className="text-[11px] text-slate-500">Merged view for the selected node</p>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={[
              'rounded px-2 py-0.5 text-[11px] font-medium',
              isDirty ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700',
            ].join(' ')}
          >
            {isDirty ? 'Unsaved' : 'Saved'}
          </span>
          <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">{fileList.length} files</span>
        </div>
      </div>
      <div className="grid gap-2 rounded-xl border border-slate-200 bg-slate-50/80 p-3">
        <div className="flex items-center justify-between">
          <label className="text-[11px] font-medium uppercase tracking-wide text-slate-500">File path</label>
          <button
            className="h-5 w-5 rounded-md border border-slate-300 bg-white text-sm font-semibold leading-none text-slate-700 hover:border-slate-400 hover:text-slate-900"
            onClick={startNewFile}
            title="New file"
            aria-label="Create new file"
            type="button"
          >
            +
          </button>
        </div>
        <input
          ref={pathInputRef}
          className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="notes.md"
        />
        <textarea
          className="min-h-28 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
              event.preventDefault();
              void saveFile();
            }
          }}
          placeholder="Write content here"
        />
        <div className="flex items-center gap-2">
          <button
            className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            onClick={() => void saveFile()}
            disabled={!canSave}
          >
            {busyAction === 'save' ? 'Saving...' : isDirty ? 'Save' : 'Saved'}
          </button>
          <button
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-slate-400 hover:text-slate-900 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
            onClick={revertChanges}
            disabled={!isDirty || busyAction !== null}
          >
            Revert
          </button>
          <button
            className="rounded-lg border border-rose-200 bg-white px-3 py-1.5 text-xs font-medium text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:border-rose-100 disabled:text-rose-300"
            onClick={() => void deleteFile()}
            disabled={!canDelete}
          >
            {busyAction === 'delete' ? 'Deleting...' : 'Delete'}
          </button>
          <span className="text-[11px] text-slate-500">Tip: Ctrl/Cmd + S to save</span>
        </div>
        <div className="text-[11px] text-slate-500">{localHint}</div>
      </div>
      <ul className="max-h-48 overflow-auto rounded-xl border border-slate-200 bg-white text-xs">
        {fileList.map((file) => {
          const selected = trimmedPath === file.path;
          const previewable = isEditable(file.path);
          return (
            <li
              key={file.path}
              className={[
                'flex items-center justify-between border-b border-slate-100 px-2 py-1.5',
                selected ? 'bg-slate-100' : 'hover:bg-slate-50',
              ].join(' ')}
            >
              <button
                className="truncate text-left text-slate-700 hover:underline"
                disabled={loadingPath === file.path || busyAction !== null}
                onClick={() => void loadFile(file)}
                title={previewable ? 'Load content for editing' : 'Select path (preview disabled for non-text file)'}
              >
                {loadingPath === file.path ? `Loading ${file.path}...` : file.path}
              </button>
              <span className="flex items-center gap-2 text-slate-400">
                {!previewable && <span className="rounded bg-slate-200 px-1 py-0.5 text-[9px] text-slate-600">binary</span>}
                <span>{file.size}b</span>
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

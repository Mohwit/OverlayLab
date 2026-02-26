import { useEffect, useMemo, useState } from 'react';

type TopicId = 'overview' | 'layers' | 'readwrite' | 'branching' | 'operations';

interface Props {
  topic?: TopicId;
  buttonText?: string;
  compact?: boolean;
}

const TOPIC_LABEL: Record<TopicId, string> = {
  overview: 'Overview',
  layers: 'Layers',
  readwrite: 'Read / Write',
  branching: 'Branching',
  operations: 'Ops / Limits',
};

const TOPIC_ORDER: TopicId[] = ['overview', 'layers', 'readwrite', 'branching', 'operations'];

function TopicContent({ topic }: { topic: TopicId }) {
  if (topic === 'overview') {
    return (
      <div className="space-y-3 text-xs text-slate-700">
        <p>
          Recall-FS uses copy-on-write layering to give each node its own writable layer, backed by a SQLite database.
          The concept is inspired by OverlayFS, but runs on any platform.
        </p>
        <div className="rounded border border-slate-200 bg-slate-50 p-3 font-mono text-[11px]">
          lower layers + upper layer -&gt; merged view
        </div>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            `merged`: the combined view the app reads/writes.
          </li>
          <li>
            `upper`: writable layer for current node.
          </li>
          <li>
            `lower`: inherited read-only history from ancestor nodes.
          </li>
        </ul>
      </div>
    );
  }

  if (topic === 'layers') {
    return (
      <div className="space-y-3 text-xs text-slate-700">
        <p>Each selected node has virtual layer references stored in SQLite:</p>
        <div className="rounded border border-slate-200 bg-slate-50 p-3 font-mono text-[11px]">
          node:&lt;node_id&gt;/upper<br />
          node:&lt;node_id&gt;/merged
        </div>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Lower layers 1..N are ordered. Earlier entries have higher read priority.
          </li>
          <li>
            The final fallback is the shared `base` layer.
          </li>
          <li>
            In the inspector, linked paths map back to graph nodes; `base` is not a node.
          </li>
        </ul>
      </div>
    );
  }

  if (topic === 'readwrite') {
    return (
      <div className="space-y-3 text-xs text-slate-700">
        <p>Lookup and write behavior in the copy-on-write layer system:</p>
        <div className="rounded border border-slate-200 bg-slate-50 p-3 font-mono text-[11px]">
          Read path lookup: upper -&gt; lower1 -&gt; lower2 -&gt; ... -&gt; base
          <br />
          Write path target: upper only
        </div>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Editing a file that exists in a lower layer triggers copy-on-write into the upper layer.
          </li>
          <li>
            Deleting lower-only files creates whiteout markers so they disappear from the merged view.
          </li>
          <li>
            File editor in this UI is focused on `.txt` and `.md` for safe readable edits.
          </li>
        </ul>
      </div>
    );
  }

  if (topic === 'branching') {
    return (
      <div className="space-y-3 text-xs text-slate-700">
        <p>How the graph maps to copy-on-write history:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Creating a node: new upper layer, inherited lower stack from parent node.
          </li>
          <li>
            Branching: creates a new session lane with a root node that reuses source node history as lower layers.
          </li>
          <li>
            Unchanged files are shared through the ancestry chain; only edits occupy new upper space.
          </li>
        </ul>
        <div className="rounded border border-slate-200 bg-slate-50 p-3 font-mono text-[11px]">
          node A (upper A)<br />
          node B lower: [A/upper, base]<br />
          node C lower: [B/upper, A/upper, base]
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3 text-xs text-slate-700">
      <p>Practical notes for this lab:</p>
      <ul className="list-disc space-y-1 pl-5">
        <li>All layer data is stored in a SQLite database -- works on any platform.</li>
        <li>No elevated privileges or special kernel modules are required.</li>
        <li>Reset deletes all session, node, and file data; base layer files remain.</li>
      </ul>
      <div className="rounded border border-slate-200 bg-slate-50 p-3 text-[11px]">
        Tip: Use Layer Inspector hover/click to understand how paths map to graph nodes.
      </div>
    </div>
  );
}

export default function OverlayLearningCue({ topic = 'overview', buttonText, compact = false }: Props) {
  const [open, setOpen] = useState(false);
  const [activeTopic, setActiveTopic] = useState<TopicId>(topic);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open]);

  const buttonClass = useMemo(() => {
    if (buttonText) {
      return [
        'rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700',
        'hover:border-slate-400 hover:text-slate-900',
      ].join(' ');
    }
    return [
      compact ? 'h-5 w-5 text-[10px]' : 'h-6 w-6 text-xs',
      'rounded-full border border-slate-300 bg-white font-semibold text-slate-700',
      'hover:border-slate-400 hover:text-slate-900',
    ].join(' ');
  }, [buttonText, compact]);

  return (
    <>
      <button
        type="button"
        className={buttonClass}
        onClick={() => {
          setActiveTopic(topic);
          setOpen(true);
        }}
        title="Copy-on-write layer guide"
        aria-label="Open copy-on-write layer guide"
      >
        {buttonText ?? 'i'}
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-900/35 p-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="max-h-[88vh] w-full max-w-3xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-800">Copy-on-Write Layer Guide</h3>
                <p className="text-[11px] text-slate-500">Concepts used directly in this lab UI and graph behavior</p>
              </div>
              <button
                type="button"
                className="rounded-lg border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:border-slate-400 hover:text-slate-900"
                onClick={() => setOpen(false)}
              >
                Close
              </button>
            </div>
            <div className="border-b border-slate-200 px-3 py-2">
              <div className="flex flex-wrap gap-1.5">
                {TOPIC_ORDER.map((item) => (
                  <button
                    key={item}
                    type="button"
                    className={[
                      'rounded-lg px-2 py-1 text-xs',
                      activeTopic === item
                        ? 'bg-slate-900 text-white'
                        : 'border border-slate-300 bg-white text-slate-700 hover:border-slate-400',
                    ].join(' ')}
                    onClick={() => setActiveTopic(item)}
                  >
                    {TOPIC_LABEL[item]}
                  </button>
                ))}
              </div>
            </div>
            <div className="max-h-[64vh] overflow-auto px-4 py-3">
              <TopicContent topic={activeTopic} />
            </div>
          </div>
        </div>
      )}
    </>
  );
}

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
          OverlayFS combines many directories into one logical filesystem view. In this lab, each node is an OverlayFS
          mount with its own writable layer.
        </p>
        <div className="rounded border border-slate-200 bg-slate-50 p-3 font-mono text-[11px]">
          lowerdir(s) + upperdir + workdir -&gt; merged
        </div>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            `merged`: what the app reads/writes.
          </li>
          <li>
            `upperdir`: writable layer for current node.
          </li>
          <li>
            `lowerdir`: inherited read-only history.
          </li>
          <li>
            `workdir`: kernel scratch area required by OverlayFS.
          </li>
        </ul>
      </div>
    );
  }

  if (topic === 'layers') {
    return (
      <div className="space-y-3 text-xs text-slate-700">
        <p>Each selected node has these real paths in this project:</p>
        <div className="rounded border border-slate-200 bg-slate-50 p-3 font-mono text-[11px]">
          overlay_lab/nodes/&lt;node_id&gt;/upper<br />
          overlay_lab/nodes/&lt;node_id&gt;/work<br />
          overlay_lab/nodes/&lt;node_id&gt;/merged
        </div>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            `lowerdir 1..N` is ordered. Earlier entries have higher read priority than later entries.
          </li>
          <li>
            The final fallback is usually `overlay_lab/base`.
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
        <p>Lookup and write behavior in OverlayFS:</p>
        <div className="rounded border border-slate-200 bg-slate-50 p-3 font-mono text-[11px]">
          Read path lookup: upper -&gt; lowerdir1 -&gt; lowerdir2 -&gt; ... -&gt; base
          <br />
          Write path target: upper only
        </div>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Editing a file that exists in a lower layer triggers copy-on-write (copy-up) into `upperdir`.
          </li>
          <li>
            Deleting lower-only files creates whiteouts in `upperdir` so they disappear in `merged`.
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
        <p>How this graph maps to OverlayFS history:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Creating an interaction node: new `upperdir`, inherited lower stack from current node.
          </li>
          <li>
            Branching: creates a new session lane with a root node that reuses source node history via `lowerdir`.
          </li>
          <li>
            Unchanged files are shared logically through lower layers; only edits occupy new upper space.
          </li>
        </ul>
        <div className="rounded border border-slate-200 bg-slate-50 p-3 font-mono text-[11px]">
          node A (upperA)<br />
          node B lower: [upperA, base]<br />
          node C lower: [upperB, upperA, base]
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3 text-xs text-slate-700">
      <p>Practical constraints in this lab:</p>
      <ul className="list-disc space-y-1 pl-5">
        <li>Linux kernel + OverlayFS support required.</li>
        <li>Mount operations need elevated privileges in this implementation.</li>
        <li>
          Common mount errors come from invalid lowerdir stacks, permission issues, or unavailable overlay module.
        </li>
        <li>Reset unmounts and deletes local node/session data; base files remain.</li>
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
        title="OverlayFS learning guide"
        aria-label="Open OverlayFS learning guide"
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
                <h3 className="text-sm font-semibold text-slate-800">OverlayFS Learning Guide</h3>
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

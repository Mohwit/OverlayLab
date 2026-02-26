import { memo, useMemo, useState } from 'react';
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeMouseHandler,
  type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import NodeContextMenu from './NodeContextMenu';
import OverlayLearningCue from './OverlayLearningCue';
import type { GraphDTO } from '../state/types';

interface Props {
  graph: GraphDTO;
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
  onCreateNode: (nodeId: string) => void;
  onBranch: (nodeId: string) => void;
  onRevert: (nodeId: string) => void;
  onDiff: (nodeId: string) => void;
}

interface GitNodeData {
  shortId: string;
  sessionLabel: string;
  color: string;
  active: boolean;
  selected: boolean;
  hovered: boolean;
  mountState: string;
}

const NODE_X_GAP = 230;
const NODE_Y_GAP = 96;
const LEFT_PADDING = 36;
const TOP_PADDING = 28;

const byCreatedAt = (a: { created_at: string; node_id: string }, b: { created_at: string; node_id: string }) =>
  a.created_at.localeCompare(b.created_at) || a.node_id.localeCompare(b.node_id);

const shortNodeId = (nodeId: string) => nodeId.replace(/^node_/, '').slice(0, 7);

const sessionSort = (a: { created_at: string; session_id: string }, b: { created_at: string; session_id: string }) =>
  a.created_at.localeCompare(b.created_at) || a.session_id.localeCompare(b.session_id);

const buildSessionLabelMap = (graph: GraphDTO): Map<string, string> => {
  const labelById = new Map<string, string>();
  const nodeById = new Map(graph.nodes.map((node) => [node.node_id, node]));
  let branchCounter = 1;
  let assignedStart = false;

  for (const session of [...graph.sessions].sort(sessionSort)) {
    const explicit = session.name?.trim();
    if (explicit) {
      labelById.set(session.session_id, explicit);
      if (explicit.toLowerCase() === 'start') {
        assignedStart = true;
      }
      continue;
    }

    const rootNode = nodeById.get(session.root_node_id);
    if (rootNode && !rootNode.parent_node_id && !assignedStart) {
      labelById.set(session.session_id, 'start');
      assignedStart = true;
      continue;
    }

    labelById.set(session.session_id, `branch-${branchCounter}`);
    branchCounter += 1;
  }

  return labelById;
};

const buildChildOrder = (
  parentSessionId: string | undefined,
  children: GraphDTO['nodes'],
): { primaryChildId: string | null; branchChildIds: string[] } => {
  const sameSession = children
    .filter((child) => child.session_id === parentSessionId)
    .sort(byCreatedAt);
  const branchChildren = children
    .filter((child) => child.session_id !== parentSessionId)
    .sort(byCreatedAt);

  // Keep the parent lane reserved for the original session only.
  // If there is no same-session continuation yet, branches start on new lanes.
  const primaryChild = sameSession.length > 0 ? sameSession[0].node_id : null;
  const secondarySameSession = sameSession.slice(1).map((child) => child.node_id);
  return {
    primaryChildId: primaryChild,
    branchChildIds: [...secondarySameSession, ...branchChildren.map((child) => child.node_id)],
  };
};

const GitNode = memo(({ data }: NodeProps) => {
  const payload = data as unknown as GitNodeData;
  const selectedStyle = payload.selected
    ? {
        borderColor: payload.color,
        backgroundColor: `${payload.color}2e`,
        boxShadow: `0 0 0 2px ${payload.color}52, 0 4px 12px rgba(15, 23, 42, 0.14)`,
      }
    : undefined;
  const hoveredStyle = !payload.selected && payload.hovered
    ? {
        borderColor: `${payload.color}b3`,
        backgroundColor: `${payload.color}10`,
        boxShadow: `0 0 0 1px ${payload.color}40`,
      }
    : undefined;
  const activeStyle = !payload.selected && payload.active
    ? {
        borderColor: `${payload.color}cc`,
        boxShadow: `0 0 0 1px ${payload.color}33`,
      }
    : undefined;
  return (
    <div
      className={[
        'min-w-[152px] rounded-xl border bg-white px-3 py-2 shadow-[0_1px_2px_rgba(15,23,42,0.08)]',
        payload.selected ? '' : 'border-slate-300',
      ].join(' ')}
      style={{ ...activeStyle, ...hoveredStyle, ...selectedStyle }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <div className="flex items-center gap-2">
        <span
          className="inline-block h-3 w-3 rounded-full border border-white shadow-sm"
          style={{ backgroundColor: payload.color }}
        />
        <span className="font-mono text-[11px] font-semibold tracking-tight text-slate-800">{shortNodeId(payload.shortId)}</span>
        {payload.active && <span className="rounded bg-slate-900 px-1.5 py-0.5 text-[9px] font-semibold text-white">HEAD</span>}
      </div>
      <div className="mt-1 flex items-center justify-between gap-2">
        <span className="max-w-[100px] truncate text-[10px] text-slate-500">{payload.sessionLabel}</span>
        <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[9px] font-medium text-emerald-700">
          available
        </span>
      </div>
    </div>
  );
});

GitNode.displayName = 'GitNode';

const nodeTypes = {
  gitNode: GitNode,
};

export default function GraphCanvas(props: Props) {
  const [menu, setMenu] = useState<{ x: number; y: number; nodeId: string } | null>(null);
  const sessionLabels = useMemo(
    () => buildSessionLabelMap(props.graph),
    [props.graph.nodes, props.graph.sessions],
  );

  const nodes = useMemo(() => {
    const nodeById = new Map(props.graph.nodes.map((n) => [n.node_id, n]));
    const sessionById = new Map(props.graph.sessions.map((s) => [s.session_id, s]));
    const childrenByParent = new Map<string, GraphDTO['nodes']>();

    for (const node of props.graph.nodes) {
      if (!node.parent_node_id) {
        continue;
      }
      const current = childrenByParent.get(node.parent_node_id) ?? [];
      current.push(node);
      childrenByParent.set(node.parent_node_id, current);
    }

    const childPlanByParent = new Map<string, { primaryChildId: string | null; branchChildIds: string[] }>();
    for (const [parentId, children] of childrenByParent) {
      const parent = nodeById.get(parentId);
      childPlanByParent.set(parentId, buildChildOrder(parent?.session_id, children));
    }

    const laneByNodeId = new Map<string, number>();
    const depthByNodeId = new Map<string, number>();
    let nextLane = 0;
    const takeNextLane = () => {
      const lane = nextLane;
      nextLane += 1;
      return lane;
    };

    const assignLane = (nodeId: string, lane: number, depth: number, visiting: Set<string>) => {
      if (laneByNodeId.has(nodeId) || visiting.has(nodeId)) {
        return;
      }

      visiting.add(nodeId);
      laneByNodeId.set(nodeId, lane);
      depthByNodeId.set(nodeId, depth);

      const childPlan = childPlanByParent.get(nodeId);
      if (childPlan?.primaryChildId) {
        assignLane(childPlan.primaryChildId, lane, depth + 1, visiting);
      }
      if (childPlan) {
        for (const childId of childPlan.branchChildIds) {
          assignLane(childId, takeNextLane(), depth + 1, visiting);
        }
      }

      visiting.delete(nodeId);
    };

    const roots = props.graph.nodes
      .filter((node) => !node.parent_node_id || !nodeById.has(node.parent_node_id))
      .sort(byCreatedAt);
    for (const root of roots) {
      assignLane(root.node_id, takeNextLane(), 0, new Set());
    }

    const remaining = [...props.graph.nodes].sort(byCreatedAt);
    for (const node of remaining) {
      if (laneByNodeId.has(node.node_id)) {
        continue;
      }
      assignLane(node.node_id, takeNextLane(), 0, new Set());
    }

    return props.graph.nodes.map((n) => {
      const session = sessionById.get(n.session_id);
      const active = session?.active_node_id === n.node_id;
      const selected = props.selectedNodeId === n.node_id;
      const hovered = props.hoveredNodeId === n.node_id;
      const lane = laneByNodeId.get(n.node_id) ?? 0;
      const depth = depthByNodeId.get(n.node_id) ?? 0;

      return {
        id: n.node_id,
        type: 'gitNode',
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        data: {
          shortId: n.node_id,
          sessionLabel: sessionLabels.get(n.session_id) ?? `branch-${n.session_id.replace(/^sess_/, '').slice(0, 4)}`,
          color: session?.color ?? '#334155',
          active,
          selected,
          hovered,
          mountState: n.mount_state,
        },
        draggable: false,
        selectable: true,
        position: {
          x: LEFT_PADDING + depth * NODE_X_GAP,
          y: TOP_PADDING + lane * NODE_Y_GAP,
        },
      };
    });
  }, [props.graph, props.selectedNodeId, props.hoveredNodeId, sessionLabels]);

  const edges = useMemo<Edge[]>(() => {
    const nodeById = new Map(props.graph.nodes.map((n) => [n.node_id, n]));
    const sessionById = new Map(props.graph.sessions.map((s) => [s.session_id, s]));

    return props.graph.edges.map((e) => ({
      id: `${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      type: 'smoothstep',
      sourceHandle: null,
      targetHandle: null,
      animated: false,
      style: {
        stroke: sessionById.get(nodeById.get(e.source)?.session_id ?? '')?.color ?? '#64748b',
        strokeWidth: 2.5,
      },
    }));
  }, [props.graph.edges, props.graph.nodes, props.graph.sessions]);

  const onNodeClick: NodeMouseHandler = (_, node) => {
    props.onSelectNode(node.id);
    setMenu(null);
  };

  const onNodeContextMenu: NodeMouseHandler = (event, node) => {
    event.preventDefault();
    props.onSelectNode(node.id);
    setMenu({ x: event.clientX, y: event.clientY, nodeId: node.id });
  };

  return (
    <div className="relative h-full w-full" onClick={() => setMenu(null)}>
      <div className="pointer-events-none absolute left-3 top-3 z-10 rounded-xl border border-slate-200 bg-white px-3 py-2 text-[10px] shadow-sm">
        <div className="mb-1 flex items-center gap-1.5 font-semibold uppercase tracking-wide text-slate-500">
          <span>Sessions</span>
          <span className="pointer-events-auto">
            <OverlayLearningCue topic="branching" compact />
          </span>
        </div>
        <div className="space-y-1">
          {props.graph.sessions.map((session) => (
            <div key={session.session_id} className="flex items-center gap-2 text-slate-700">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: session.color }} />
              <span className="max-w-[140px] truncate">{sessionLabels.get(session.session_id) ?? session.session_id}</span>
            </div>
          ))}
        </div>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        onNodeContextMenu={onNodeContextMenu}
        nodesDraggable={false}
        nodesConnectable={false}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.35}
        maxZoom={1.4}
      >
        <Background color="#dbe3ee" gap={20} size={1} />
        <Controls />
      </ReactFlow>
      {menu && (
        <NodeContextMenu
          x={menu.x}
          y={menu.y}
          nodeId={menu.nodeId}
          onCreateNode={props.onCreateNode}
          onBranch={props.onBranch}
          onRevert={props.onRevert}
          onInspectLayers={props.onSelectNode}
          onDiff={props.onDiff}
          onClose={() => setMenu(null)}
        />
      )}
    </div>
  );
}

import { useMemo, useState } from 'react';
import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node, type NodeMouseHandler } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import NodeContextMenu from './NodeContextMenu';
import type { GraphDTO } from '../state/types';

interface Props {
  graph: GraphDTO;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
  onCreateNode: (nodeId: string) => void;
  onBranch: (nodeId: string) => void;
  onRevert: (nodeId: string) => void;
  onDiff: (nodeId: string) => void;
}

const layout = (nodes: Node[]): Node[] => {
  return nodes.map((node, idx) => ({
    ...node,
    position: { x: (idx % 8) * 220, y: Math.floor(idx / 8) * 140 },
  }));
};

export default function GraphCanvas(props: Props) {
  const [menu, setMenu] = useState<{ x: number; y: number; nodeId: string } | null>(null);

  const nodes = useMemo(() => {
    const sessionById = new Map(props.graph.sessions.map((s) => [s.session_id, s]));
    const baseNodes: Node[] = props.graph.nodes.map((n) => {
      const session = sessionById.get(n.session_id);
      const active = session?.active_node_id === n.node_id;
      const selected = props.selectedNodeId === n.node_id;
      return {
        id: n.node_id,
        data: { label: n.node_id },
        style: {
          borderRadius: 999,
          border: `3px solid ${session?.color ?? '#334155'}`,
          background: selected ? '#e2e8f0' : '#ffffff',
          boxShadow: active ? `0 0 0 5px ${session?.color ?? '#334155'}33` : undefined,
          width: 54,
          height: 54,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 10,
        },
        position: { x: 0, y: 0 },
      };
    });
    return layout(baseNodes);
  }, [props.graph, props.selectedNodeId]);

  const edges = useMemo<Edge[]>(() => {
    return props.graph.edges.map((e) => ({
      id: `${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      markerEnd: { type: MarkerType.ArrowClosed },
      animated: false,
    }));
  }, [props.graph.edges]);

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
      <ReactFlow nodes={nodes} edges={edges} onNodeClick={onNodeClick} onNodeContextMenu={onNodeContextMenu} fitView>
        <Background />
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

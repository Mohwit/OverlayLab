export type MountState = 'mounted' | 'unmounted';

export interface NodeDTO {
  node_id: string;
  parent_node_id: string | null;
  session_id: string;
  lowerdirs: string[];
  upperdir: string;
  workdir: string;
  merged: string;
  mount_state: MountState;
  created_at: string;
}

export interface SessionDTO {
  session_id: string;
  name: string | null;
  root_node_id: string;
  active_node_id: string;
  created_at: string;
  color: string;
}

export interface EdgeDTO {
  source: string;
  target: string;
}

export interface GraphDTO {
  sessions: SessionDTO[];
  nodes: NodeDTO[];
  edges: EdgeDTO[];
}

export interface FileEntryDTO {
  path: string;
  type: 'file' | 'dir';
  size: number;
  mtime: number;
}

export interface FileContentDTO {
  node_id: string;
  path: string;
  content: string;
}

export interface LayerFilesDTO {
  node_id: string;
  layer: 'merged' | 'upper' | 'lower';
  index: number | null;
  files: FileEntryDTO[];
}

export interface LayerInfoDTO {
  node_id: string;
  parent_node_id: string | null;
  lowerdirs: string[];
  upperdir: string;
  workdir: string;
  merged: string;
  mount_state: MountState;
}

export interface DiffFileDTO {
  path: string;
  status: 'added' | 'removed' | 'modified' | 'unchanged';
  diff: string;
}

export interface DiffDTO {
  from_node_id: string;
  to_node_id: string;
  files: DiffFileDTO[];
}

export interface HealthPreflightDTO {
  ready: boolean;
  message: string;
}

export interface ResetResponseDTO {
  cleared_nodes: number;
  cleared_sessions: number;
  message: string;
}

# Turso AgentFS Research Notes
## Comprehensive Documentation on SQLite-Based Copy-on-Write Filesystem

---

## 1. Overview and Key Concepts

### What is AgentFS?
AgentFS is a filesystem abstraction explicitly designed for AI agents, built by Turso Database. It provides a SQLite-backed storage system that enables:
- **Auditability**: Every file operation, tool call, and state change is recorded and queryable
- **Reproducibility**: Complete state snapshots via simple file copying
- **Portability**: Entire agent runtime in a single SQLite database file
- **Isolation**: Copy-on-write semantics keep original data safe

### Core Philosophy
The entire agent runtime—files, state, and history—lives in a single SQLite database file (e.g., `.agentfs/my-agent.db`). This design makes agent state portable, queryable, and reproducible.

---

## 2. Copy-on-Write Architecture

### Two-Layer Overlay System

AgentFS implements copy-on-write through an overlay filesystem with two layers:

```
┌────────────────────────────────────┐
│    Merged View (what you see)      │
├────────────────────────────────────┤
│  Delta Layer (SQLite database)     │  ← All writes go here
├────────────────────────────────────┤
│  Base Layer (original directory)   │  ← Read-only
└────────────────────────────────────┘
```

### How File Operations Work

#### Reads
1. Check delta layer first
2. If not found, fall back to base layer
3. Base layer provides transparent read-through

#### Writes
1. **Existing files**: Copy entire file from base layer to delta layer (if not already copied), then modify
2. **New files**: Write directly to delta layer
3. **Base layer is never modified** - all changes isolated in delta

#### Deletes
1. Create a "whiteout" marker in delta layer
2. File appears deleted in merged view
3. Original file in base layer remains untouched

### Storage Efficiency
- Only stores actual changes
- Modified files require full copy after first write
- Deleted files only need small whiteout markers
- Unmodified files are never duplicated
- Example: 10GB project with 1MB of changes uses only ~1MB in delta layer

---

## 3. Database Schema

### Core Tables

#### `fs_inode` - File and Directory Metadata
```sql
CREATE TABLE fs_inode (
    ino INTEGER PRIMARY KEY,
    parent_ino INTEGER,
    name TEXT,
    mode INTEGER,
    size INTEGER,
    ...
    whiteout INTEGER DEFAULT 0
);
```

**Purpose**: Represents files and directories with POSIX-like inode structure
**Key fields**:
- `ino`: Inode number (primary key)
- `parent_ino`: Parent directory inode
- `name`: File/directory name
- `mode`: POSIX file mode/permissions
- `size`: File size
- `whiteout`: Flag indicating if file is deleted (whiteout marker)

#### `fs_block` - File Content Storage
```sql
CREATE TABLE fs_block (
    ino INTEGER,
    block_num INTEGER,
    data BLOB
);
```

**Purpose**: Stores actual file content as blocks
**Key fields**:
- `ino`: References the inode
- `block_num`: Block number within the file
- `data`: Binary data (BLOB)

#### `kv_store` - Key-Value Store
**Purpose**: Stores agent state and context as key-value pairs
**Features**: Supports JSON-serialized values for complex state

#### `tool_call` - Tool Call Audit Trail
**Purpose**: Records every tool invocation by the agent
**Tracked information**:
- Tool name
- Status (pending, success, error)
- Duration
- Timestamp
- Input parameters
- Output results

### Schema Design Principles
- **Single file storage**: Everything in one SQLite database
- **Queryable via SQL**: Complete visibility into agent operations
- **POSIX-like abstractions**: Familiar filesystem semantics
- **Audit trail**: Every operation is recorded

---

## 4. File Storage Implementation

### Inode-Based Storage
AgentFS uses a traditional filesystem-like structure:
- Files and directories represented as inodes
- Content stored in blocks (similar to Unix filesystems)
- Metadata separated from data

### Block Storage
- File content split into blocks
- Stored as BLOBs in SQLite
- Efficient for both small and large files

### Whiteout Mechanism
When a file is deleted:
```sql
-- Mark file as whiteout (deleted)
UPDATE fs_inode SET whiteout = 1 WHERE ino = ?;

-- Query to see deleted files
SELECT * FROM fs_inode WHERE whiteout = 1;
```

### File Operation Table

| Operation           | Behavior                                    |
| ------------------- | ------------------------------------------- |
| Read existing file  | Pass through to base layer if not in delta |
| Write existing file | Copy to delta, then write                   |
| Create new file     | Write directly to delta                     |
| Delete file         | Create whiteout marker in delta             |
| Rename file         | Delete old + create new                     |

---

## 5. Layers, Snapshots, and Sessions

### Layers

**Base Layer**:
- Original read-only directory on host filesystem
- Never modified by agent operations
- Provides source data for copy-on-write

**Delta Layer**:
- SQLite database storing all modifications
- Contains only changed/new/deleted files
- Portable and queryable

### Snapshots

**How it works**: Since everything is in a single SQLite file, snapshotting is trivial:
```bash
# Create snapshot
cp agent.db snapshot.db

# Restore snapshot
cp snapshot.db agent.db
```

**Use cases**:
- Reproduce exact execution states
- Test what-if scenarios
- Roll back mistakes
- Version control agent state

### Sessions

**Named sessions** enable multiple agents or terminals to share the same copy-on-write view:

```bash
# Start session with specific ID
agentfs run --session my-session /bin/bash

# Join existing session from another terminal
agentfs run --session my-session /bin/bash

# Check current session
echo $AGENTFS_SESSION
```

**Features**:
- Multiple participants see identical changes in real-time
- Session stored as `.agentfs/<session-id>.db`
- Enables multi-terminal collaboration
- Useful for iterative development workflows

**Session ID strategies**:
- Can match git branch names
- Can be UUIDs for unique isolation
- Can be feature/bug fix identifiers

---

## 6. Branching and Forking

### Forking
**Effortless forking** is a key feature:
- Copy entire filesystem by copying SQLite file
- Instant operation (no recursive directory copying)
- Each fork is completely isolated
- Ideal for subagents or parallel experiments

```bash
# Fork an agent filesystem
cp .agentfs/agent-a.db .agentfs/agent-b.db
```

### Parallel Experiments
Run multiple experiments on same codebase:

```bash
# Experiment A
agentfs run --session exp-a python3 approach_a.py

# Experiment B (same base, different changes)
agentfs run --session exp-b python3 approach_b.py

# Compare results
agentfs diff exp-a
agentfs diff exp-b
```

### Branching Workflow
1. Create base session with original code
2. Fork session for each experiment/branch
3. Let agents work independently
4. Compare results using `agentfs diff`
5. Merge successful changes back manually or programmatically

---

## 7. Tracking File Changes and Diffs

### Built-in Diff Command
```bash
# View changes from base layer
agentfs diff my-session

# Shows:
# - Modified files
# - New files
# - Deleted files (whiteouts)
```

### Timeline View
```bash
# View agent's action timeline
agentfs timeline my-agent

# Output shows:
# ID   TOOL                 STATUS       DURATION STARTED
# 4    execute_code         pending            -- 2024-01-05 09:44:20
# 3    api_call             error           300ms 2024-01-05 09:44:15
# 2    read_file            success          50ms 2024-01-05 09:44:10
# 1    web_search           success        1200ms 2024-01-05 09:43:45
```

### SQL Queryability
Since everything is in SQLite, you can query directly:

```sql
-- Find all modified files
SELECT * FROM fs_inode WHERE ino IN (
    SELECT DISTINCT ino FROM fs_block
);

-- Find all deleted files
SELECT * FROM fs_inode WHERE whiteout = 1;

-- Find all tool calls with errors
SELECT * FROM tool_call WHERE status = 'error';

-- Track state evolution
SELECT * FROM kv_store ORDER BY timestamp;
```

### Audit Capabilities
- Every file operation recorded
- Complete history queryable via SQL
- Debug issues by examining past operations
- Analyze agent behavior patterns
- Meet compliance requirements

---

## 8. SDK Architecture

### Three Main Components

1. **SDK** - TypeScript, Python, and Rust libraries
2. **CLI** - Command-line interface for filesystem management
3. **Specification** - SQLite schema definition (SPEC.md)

### SDK Interfaces

All SDKs provide three core abstractions:

#### 1. Filesystem Interface
POSIX-like file operations:
- `writeFile()` / `write_file()`
- `readFile()` / `read_file()`
- `readdir()` / `readdir()`
- `stat()` / `stat()`
- `deleteFile()` / `delete_file()`
- `mkdir()` / `mkdir()`

#### 2. Key-Value Store Interface
Agent state management:
- `set(key, value)` - Store JSON-serializable data
- `get(key)` - Retrieve data
- `list()` - List all keys
- `delete(key)` - Remove entry

#### 3. Tool Call Tracking Interface
Audit trail:
- `record()` - Record complete tool call
- `start()` - Begin tool call
- `success()` - Mark as successful
- `error()` - Mark as failed
- `getStats()` - Get statistics

### TypeScript/JavaScript SDK

**Installation**:
```bash
npm install agentfs-sdk
```

**Basic Usage**:
```typescript
import { AgentFS } from 'agentfs-sdk';

// Persistent storage with identifier
const agent = await AgentFS.open({ id: 'my-agent' });
// Creates: .agentfs/my-agent.db

// Or use ephemeral in-memory database
const ephemeralAgent = await AgentFS.open();

// Filesystem operations
await agent.fs.writeFile('/output/report.pdf', pdfBuffer);
const files = await agent.fs.readdir('/output');
const content = await agent.fs.readFile('/output/report.pdf');

// Key-value operations
await agent.kv.set('user:preferences', { theme: 'dark' });
const prefs = await agent.kv.get('user:preferences');

// Tool call tracking
await agent.tools.record(
  'web_search',
  Date.now() / 1000,
  Date.now() / 1000 + 1.5,
  { query: 'AI' },
  { results: [...] }
);
```

**Environment Support**: Works in both Node.js and browser (via WebAssembly)

### Python SDK

**Installation**:
```bash
pip install agentfs-sdk  # Requires Python ≥3.10
```

**Basic Usage**:
```python
from agentfs_sdk import AgentFS, AgentFSOptions

# Open agent filesystem
agent = await AgentFS.open(AgentFSOptions(id='my-agent'))

# File operations
await agent.fs.write_file('/data/output.txt', b'Hello')
content = await agent.fs.read_file('/data/output.txt')
files = await agent.fs.readdir('/data')

# KV operations
await agent.kv.set('config', {'setting': 'value'})
config = await agent.kv.get('config')

# Tool tracking
await agent.tools.start('api_call', {'endpoint': '/users'})
await agent.tools.success('api_call', {'status': 200})
```

### Rust SDK

**Installation**:
```toml
[dependencies]
agentfs-sdk = "0.x"
```

**Basic Usage**:
```rust
use agentfs_sdk::AgentFS;

// Initialize with SQLite backend
let agent = AgentFS::new().await?;

// File operations
agent.fs.write_file("/data/file.txt", b"content").await?;
let content = agent.fs.read_file("/data/file.txt").await?;

// KV operations
agent.kv.set("key", serde_json::json!({"value": 42})).await?;

// Tool tracking
agent.tools.start("process_data", params).await?;
agent.tools.success("process_data", result).await?;
```

**Features**:
- Backend-agnostic design (works with any AgentDB backend)
- Integration with Rig.rs agent framework
- High-performance native implementation

### Backend Architecture (AgentDB)

**Backend-agnostic design**: AgentFS can work with different backend types:
- SQL (primary implementation via SQLite/Turso)
- Key-Value stores
- Graph databases

**Primary Backend**: SQLite/Turso
- Single file storage
- ACID transactions
- Full SQL queryability
- Cloud sync support (Turso Cloud)

---

## 9. CLI and Mounting

### CLI Commands

#### Initialize
```bash
# Create new agent filesystem
agentfs init my-agent

# Create with base directory (overlay)
agentfs init my-overlay --base /path/to/project
```

#### Run (Sandboxed Execution)
```bash
# Run command with automatic overlay
cd /path/to/project
agentfs run /bin/bash

# Run with specific session
agentfs run --session my-session /bin/bash

# Join existing session
agentfs run --session <session-id> /bin/bash
```

#### Mount
```bash
# Mount agent filesystem to directory
agentfs mount my-agent ./mnt

# Now use standard tools
echo "hello" > ./mnt/hello.txt
cat ./mnt/hello.txt
```

#### Filesystem Operations
```bash
# List files
agentfs fs ls my-agent

# Read file
agentfs fs cat my-agent hello.txt

# Can also use database path directly
agentfs fs cat .agentfs/my-agent.db hello.txt
```

#### Diff and Timeline
```bash
# View changes from base
agentfs diff my-session

# View tool call timeline
agentfs timeline my-agent
```

### Mounting Implementation

#### Linux: FUSE (Filesystem in Userspace)
- Implements overlay using FUSE
- Kernel forwards filesystem operations to userspace process
- Combined with user namespaces and mount namespaces for sandboxing
- Process sees read-only filesystem except for working directory and allowed paths

**Sandbox implementation**:
1. Create new namespaces with `unshare()`
2. Bind-mount allowed writable paths (e.g., `~/.claude`, `~/.local`, `~/.npm`)
3. Remount everything else as read-only with `MS_RDONLY`
4. Bind-mount FUSE overlay onto working directory

#### macOS: NFS (Network File System)
- Uses native NFS support (no kernel extensions required)
- Starts localhost NFS server exposing overlay filesystem
- Mounts using built-in `/sbin/mount_nfs`
- Copy-on-write semantics identical to FUSE

**Sandbox implementation**:
- Uses `sandbox-exec` with dynamically generated Sandbox profile
- Profile allows all reads but restricts writes to NFS mountpoint and allowed paths
- Kernel-enforced sandboxing without special privileges

### Virtual Filesystems
`/proc`, `/sys`, `/dev`, and `/tmp` remain writable for system functionality

---

## 10. Use Cases and Examples

### Agentic Coding
```bash
# Clone repository
git clone git@github.com:user/project.git
cd project

# Start coding agent with overlay
agentfs run claude

# Agent makes changes - all isolated to session
# Original files remain untouched

# Review changes
agentfs diff <session-id>

# Apply or discard as needed
```

### Safe Refactoring
```bash
cd my-project
agentfs run --session refactor python3 refactor_agent.py

# Review what changed
agentfs diff refactor

# Happy? Apply changes manually or via script
# Not happy? Just delete the session
rm .agentfs/refactor.db
```

### Testing Destructive Operations
```bash
agentfs run --session test /bin/bash
$ rm -rf src/  # Yikes!
$ exit

# Original files are fine
ls src/  # Still there!

# Only the overlay was affected
agentfs fs ls test  # Shows the deletion
```

### Parallel Experiments
```bash
# Experiment A
agentfs run --session exp-a python3 approach_a.py

# Experiment B (same base, different changes)
agentfs run --session exp-b python3 approach_b.py

# Compare results
agentfs diff exp-a
agentfs diff exp-b
```

---

## 11. Key Technical Insights

### Why SQLite?
1. **Single file**: Entire filesystem in one portable file
2. **ACID transactions**: Data consistency guarantees
3. **SQL queryability**: Powerful audit and analysis capabilities
4. **Write-ahead log**: Enables snapshotting and time-travel
5. **Universal support**: Works everywhere (desktop, server, browser, edge)
6. **No dependencies**: Embedded database, no separate server

### Comparison with Alternatives

#### vs. Bubblewrap
- Bubblewrap provides isolation via Linux namespaces
- AgentFS adds persistence and queryability
- AgentFS state is portable across machines
- Both can be used together

#### vs. Docker Sandbox
- Complementary, not competing
- Docker answers "how do I run this safely?"
- AgentFS answers "what happened and what's the state?"
- Can use both: Docker for security, AgentFS for state management

#### vs. Git Worktrees
- Git worktrees provide multiple checkouts
- AgentFS provides filesystem-level isolation that can't be bypassed
- AgentFS works below git, handles untracked files
- AgentFS isolation is system-wide and enforced

### Why Filesystem Layer vs. Containers/VMs?
1. **Queryability**: SQLite tables enable SQL queries on filesystem state
2. **Snapshotting**: Write-ahead log captures every change
3. **Portability**: Works in serverless and browser environments
4. **Compatibility**: Works fine with containers/VMs via NFS or virtio-fuse

---

## 12. Advanced Features

### Cloud Sync
- Optional syncing to Turso Cloud
- Enables distributed agent state
- Multi-region replication
- Collaborative agent sessions

### Browser Support
- TypeScript SDK works in browser via WebAssembly
- Enables in-browser agent development
- Local-first with optional cloud sync

### MCP Server Integration
- Model Context Protocol support
- Enables LLM integration
- Structured tool calling

### NFS Server Access
- Expose agent filesystem via NFS
- Access from any NFS client
- Network-accessible agent state

---

## 13. Status and Availability

### Current Status
- **BETA software** - may contain bugs
- Active development with 56+ releases
- Use caution with production data
- Maintain backups

### Installation
```bash
# Install CLI
curl -fsSL https://agentfs.ai/install | bash

# Or download from GitHub releases
# https://github.com/tursodatabase/agentfs/releases
```

### Repository
- GitHub: https://github.com/tursodatabase/agentfs
- Stars: 2,306+
- Forks: 134+

### Language Composition
- Rust: 71.0% (core implementation)
- TypeScript: 13.2% (SDK)
- Python: 9.2% (SDK)
- C: 4.3% (native bindings)
- Shell: 2.1% (scripts)

---

## 14. Key Takeaways for Implementation

### Database Schema Design
1. **Inode table** stores file/directory metadata with whiteout support
2. **Block table** stores file content as BLOBs
3. **KV store** for agent state
4. **Tool call table** for audit trail
5. All in single SQLite file for portability

### Copy-on-Write Implementation
1. Two-layer overlay (base + delta)
2. Delta layer is SQLite database
3. Reads check delta first, fall back to base
4. Writes always go to delta
5. Deletes use whiteout markers

### Branching/Forking Strategy
1. Fork = copy SQLite file
2. Sessions enable shared state
3. Named sessions for organization
4. Diff command shows changes

### SDK Architecture
1. Three core interfaces: FS, KV, Tools
2. Backend-agnostic design
3. Multiple language support
4. Browser and server compatible

### Mounting Strategy
1. FUSE on Linux
2. NFS on macOS
3. Sandboxing for security
4. Virtual filesystems remain accessible

---

## 15. Resources

### Documentation
- Main docs: https://docs.turso.tech/agentfs/introduction
- Overlay guide: https://docs.turso.tech/agentfs/guides/overlay
- TypeScript SDK: https://docs.turso.tech/agentfs/sdk/typescript

### Blog Posts
- Introduction: https://turso.tech/blog/agentfs
- FUSE mounting: https://turso.tech/blog/agentfs-fuse
- Overlay filesystem: https://turso.tech/blog/agentfs-overlay

### Repository
- GitHub: https://github.com/tursodatabase/agentfs
- SPEC.md: Full schema specification
- MANUAL.md: Complete CLI documentation
- Examples: Integration examples with various frameworks

### Community
- Discord: Turso community
- GitHub Issues: Bug reports and feature requests

---

## Summary

Turso AgentFS provides a comprehensive SQLite-based filesystem abstraction for AI agents with:

✅ **Copy-on-write isolation** via two-layer overlay (base + delta)
✅ **Complete auditability** with SQL-queryable operations
✅ **Trivial snapshots** via file copying
✅ **Effortless forking** for parallel experiments
✅ **Named sessions** for shared state
✅ **Multi-language SDKs** (TypeScript, Python, Rust)
✅ **POSIX mounting** via FUSE/NFS
✅ **Single-file portability** for entire agent state
✅ **Whiteout mechanism** for tracking deletions
✅ **Tool call tracking** for observability

The core innovation is storing everything in a single SQLite database with a well-defined schema, enabling unprecedented portability, queryability, and reproducibility for agent state management.

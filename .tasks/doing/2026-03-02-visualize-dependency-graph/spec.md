# Spec: `visualize-dependency-graph` (`dot-tasks graph`)

## Summary
Add a new human-readable dependency graph command, `dot-tasks graph`, that visualizes task DAGs for active work (`todo` + `doing`) with two terminal visualization modes:
1. `tree` (default): root-to-dependency traversal view.
2. `layers`: topological layer view.

This is a new command (not a `view` mode), supports rich/plain terminal output only in v1 (no JSON/Mermaid), and includes concrete visualization examples in docs/spec output.

## Public Interfaces and Types

### CLI interface
Add a command in `src/dot_tasks/cli.py`:

```bash
dot-tasks graph [--mode tree|layers] [--include-done] [--nointeractive] [--tasks-root <path>]
```

Behavior:
1. Default scope: `todo` + `doing`.
2. `--include-done`: include completed tasks in graph rendering.
3. `--mode`:
   - `tree` (default)
   - `layers`
4. Rich output when TTY; plain output otherwise (same pattern as `view`/`list`).
5. Exit code `0` for empty graph with message `No tasks found.`

### Internal graph data model
Add graph snapshot types in `src/dot_tasks/models.py`:

```python
@dataclass(slots=True)
class DependencyGraphNode:
    task_id: str
    task_name: str
    status: str
    priority: str
    effort: str
    depends_on: list[str]      # scoped deps
    hidden_depends_on: list[str]  # deps excluded by scope (e.g., done when not included)

@dataclass(slots=True)
class DependencyGraph:
    nodes: dict[str, DependencyGraphNode]
    root_ids: list[str]        # nodes not referenced as a dependency by another scoped node
    source_ids: list[str]      # nodes with no scoped depends_on
    dependent_ids_by_node: dict[str, list[str]]  # reverse adjacency
```

### Service API
Add to `src/dot_tasks/service.py`:

1. `build_dependency_graph(*, include_done: bool = False) -> DependencyGraph`
2. Graph construction uses all active tasks, then applies render scope.
3. Reuses existing validation guarantees (acyclic, known dependency IDs).

### Render API
Add to `src/dot_tasks/render.py`:

1. `render_dependency_graph_tree_plain(graph: DependencyGraph) -> str`
2. `render_dependency_graph_tree_rich(graph: DependencyGraph)`
3. `render_dependency_graph_layers_plain(graph: DependencyGraph) -> str`
4. `render_dependency_graph_layers_rich(graph: DependencyGraph)`

## Rendering Spec

### Tree mode (`--mode tree`)
1. Roots are scoped nodes that are not dependencies of other scoped nodes.
2. Traverse each root depth-first following `task -> depends_on`.
3. Show shared-node marker when a node appears under multiple branches: `(shared)`.
4. For each node line show: `task_name (task_id) [status] [deps: ready|blocked(n)]`.
5. If filtered deps are hidden (e.g., done deps when `--include-done` absent), append `(+N hidden)`.

Example:

```text
Dependency Graph | mode=tree | scope=todo,doing
nodes=5 edges=4 roots=2

release-cli (t-1) [doing] [deps: blocked(1)]
├─ finalize-readme (t-3) [todo] [deps: ready]
└─ package-wheel (t-2) [todo] [deps: blocked(1)]
   └─ generate-changelog (t-4) [doing] [deps: ready]

publish-blog (t-5) [todo] [deps: blocked(1)]
└─ package-wheel (t-2) [todo] [deps: blocked(1)] (shared)
```

### Layers mode (`--mode layers`)
1. Build topological layers from scoped prerequisite sources.
2. `L0`: nodes with no scoped dependencies.
3. `L(n+1)`: nodes whose scoped dependencies are all in layers `<= n`.
4. Within each layer, sort by existing task ordering convention (`status`, `date_created` desc, `task_name`).
5. Show same per-node metadata line format.

Example:

```text
Dependency Graph | mode=layers | scope=todo,doing
nodes=5 edges=4 layers=3

L0 prerequisites
- generate-changelog (t-4) [doing] [deps: ready]
- finalize-readme (t-3) [todo] [deps: ready]

L1 depends on L0
- package-wheel (t-2) [todo] [deps: blocked(1)]

L2 depends on L1
- publish-blog (t-5) [todo] [deps: blocked(1)]
- release-cli (t-1) [doing] [deps: blocked(1)]
```

## Acceptance Criteria
1. `dot-tasks graph` exists and is documented.
2. Default output visualizes active (`todo` + `doing`) DAG in tree mode.
3. `--mode layers` provides layer-based DAG visualization.
4. `--include-done` extends graph scope to completed tasks.
5. Rich/plain rendering follows existing TTY behavior patterns.
6. Tests covering command behavior and render formatting are passing.

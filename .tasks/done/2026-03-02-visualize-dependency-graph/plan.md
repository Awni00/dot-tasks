## Plan
1. Add dependency graph dataclasses (`DependencyGraphNode`, `DependencyGraph`) to `src/dot_tasks/models.py`.
2. Implement `TaskService.build_dependency_graph(include_done=False)` in `src/dot_tasks/service.py`:
   - Build scoped graph for `todo` + `doing` by default.
   - Optionally include `completed` tasks with `include_done=True`.
   - Produce `nodes`, `root_ids`, `source_ids`, and reverse adjacency (`dependent_ids_by_node`) with deterministic ordering.
   - Track hidden dependencies excluded by scope in each node.
3. Add graph renderers in `src/dot_tasks/render.py`:
   - `render_dependency_graph_tree_plain` / `render_dependency_graph_tree_rich`
   - `render_dependency_graph_layers_plain` / `render_dependency_graph_layers_rich`
   - Tree mode: depth-first root traversal, shared-node marker, hidden dependency count.
   - Layers mode: topological depth layers (`L0`, `L1`, ...).
4. Add `graph` CLI command in `src/dot_tasks/cli.py`:
   - Signature: `dot-tasks graph [--mode tree|layers] [--include-done] [--nointeractive] [--tasks-root <path>]`
   - Default mode `tree`, default scope `todo` + `doing`.
   - Rich/plain dispatch based on TTY parity with existing commands.
   - Empty graph behavior: print `No tasks found.` and exit 0.
5. Update `README.md` command table to document `graph` usage.
6. Add tests:
   - CLI: default tree scope exclusion of done, layers mode switch, include-done behavior, rich/plain dispatch, empty graph output.
   - Render: shared-node marker, hidden dependency annotation, layers layout and formatting.
7. Validate with pytest and ensure all tests pass.

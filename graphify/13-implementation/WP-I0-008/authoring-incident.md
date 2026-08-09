# WP-I0-008 authoring incident

Before final evidence collection, `python -B -m py_compile` created the known package-local cache file `graphify/13-implementation/WP-I0-008/__pycache__/collect_evidence.cpython-311.pyc` (`py_compile` writes its requested output even with bytecode-import suppression enabled).

The exact file and its now-empty `__pycache__` directory were removed immediately. No file under `Codebase/`, no external output directory, and no dependency/fixture/credential/environment prerequisite was created or supplied. The final collector was then rerun with an AST parse check that performs no bytecode compilation. The cache path is absent from the final artifact scan and worktree.

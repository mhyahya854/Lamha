# WP-I0-006 prior failed-run incident

- Prior invocation starting SHA: `82dfd9e8e2b3a826d5728cc3b2290b3aedb3e50c`
- Incident: the prior invocation redirected `collect_evidence.py --self-test` stdout to `C:\Users\mhyah\AppData\Local\Temp\wp_i0_006_selftest.txt`.
- Classification: unauthorized external evidence scratch/test output in that prior invocation.
- Recovery: the exact scratch file was deleted and its absence verified. The prior invocation was marked NOT COMPLETE, was not staged, committed, pushed, certified, or transitioned, and then hard-stopped.
- This invocation: starts as a new bounded attempt, preserves this disclosure as history, streams validation output, and must independently prove that it creates no external workspace/copy/build/test/cache/generated/package-manager/temporary output.

## Post-transition operational incident

After terminal transition commit `96529caf6fddac93057fea9e10482219d508d590` was pushed, a read-only plan-validator check was run without `PYTHONDONTWRITEBYTECODE=1`. Python briefly created these untracked cache files outside the already-closed WP-I0-006 execution boundary:

- `graphify/tools/__pycache__/certification_gates.cpython-311.pyc`
- `graphify/tools/__pycache__/write_guard.cpython-311.pyc`

The cache directory was detected immediately and removed with a path-scoped `git clean`. It is absent, `HEAD == origin/main`, and the worktree is clean at the recovery boundary. This validator run is not WP-I0-006 exit-gate evidence and does not retroactively alter the independently reviewed, committed, and transitioned package invocation. Any later Python validation must set `PYTHONDONTWRITEBYTECODE=1`.

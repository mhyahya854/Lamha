# WP-I0-006 prior failed-run incident

- Prior invocation starting SHA: `82dfd9e8e2b3a826d5728cc3b2290b3aedb3e50c`
- Incident: the prior invocation redirected `collect_evidence.py --self-test` stdout to `C:\Users\mhyah\AppData\Local\Temp\wp_i0_006_selftest.txt`.
- Classification: unauthorized external evidence scratch/test output in that prior invocation.
- Recovery: the exact scratch file was deleted and its absence verified. The prior invocation was marked NOT COMPLETE, was not staged, committed, pushed, certified, or transitioned, and then hard-stopped.
- This invocation: starts as a new bounded attempt, preserves this disclosure as history, streams validation output, and must independently prove that it creates no external workspace/copy/build/test/cache/generated/package-manager/temporary output.

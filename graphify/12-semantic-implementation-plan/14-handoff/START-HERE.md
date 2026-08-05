# Start here — I0 only

The planning repair is complete only when the validator and external integrity report both pass. The first safe package is `WP-I0-001` (read-only repository provenance and integrity baseline). Execute that packet alone; do not start a later package automatically. Create no archive, backup, repository copy, application mutation, or Git mutation.

```powershell
python .\11-model-packets\plan_cli.py prompt WP-I0-001
```

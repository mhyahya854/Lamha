from __future__ import annotations
import csv, hashlib, json, re, sqlite3, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
required=[
'00-READ-ME-FIRST.md','01-PLANNING-GAP-AUDIT.md','02-DECISION-REGISTER.md','03-RELEASE-SCOPE.md',
'04-WORK-BREAKDOWN-STRUCTURE.md','05-TARGET-DATA-MODEL.md','06-SQLITE-INDEX-SPEC.md','07-TAURI-IPC-CONTRACT.md',
'08-FILESYSTEM-TRANSACTION-SPEC.md','09-SECURITY-PRIVACY-THREAT-MODEL.md','10-UX-ROUTE-SCREEN-MATRIX.md',
'11-AI-WORKER-MODEL-PACKAGING.md','12-TEST-AND-FIXTURE-MATRIX.md','13-PERFORMANCE-BUDGETS.md',
'14-CROSS-PLATFORM-PACKAGING-LICENSE.md','15-GIT-CI-CODE-QUALITY.md','16-UPSTREAM-IMMICH-FORK-STRATEGY.md',
'17-CODEX-EXECUTION-PROMPT.md','18-DEFINITION-OF-READY-DONE.md','19-RISK-REGISTER-EXPANDED.md','20-OPEN-DECISIONS.md',
'21-REQUIREMENT-MAPPING-CORRECTIONS.md','22-PHASE-0-EXECUTION-CHECKLIST.md','23-LEGACY-CUTOVER-INVENTORY.md',
'24-FINAL-IMPLEMENTATION-READY-HANDOFF.md','REQUIREMENTS_EXECUTION.csv','sqlite/001_initial.sql',
'contracts/ipc-command-catalog-v1.json','contracts/ipc-envelope-v1.schema.json','contracts/ai-protocol-v1.schema.json',
'components/COMPONENT_MANIFEST_TEMPLATE.csv','PLAN_MANIFEST_SHA256.csv']
errors=[]
for rel in required:
 p=HERE/rel
 if not p.is_file() or p.stat().st_size==0: errors.append(f'missing/empty: {rel}')

# Requirements
p=HERE/'REQUIREMENTS_EXECUTION.csv'
if p.is_file():
 rows=list(csv.DictReader(p.open(encoding='utf-8',newline='')))
 ids=[r['RequirementID'] for r in rows]
 if len(rows)!=2083: errors.append(f'requirement row count {len(rows)} != 2083')
 if len(ids)!=len(set(ids)): errors.append('duplicate requirement IDs')
 phases={int(r['ExecutionPrimaryPhase']) for r in rows}
 if phases!=set(range(17)): errors.append(f'phase coverage {sorted(phases)}')
 if any(r['PlanningDecisionState']!='LOCKED' for r in rows): errors.append('non-locked planning decision row')
 for r in rows:
  m=re.search(r'Phase\s+(\d+)\s+[—-]',r['SourceHeading'])
  if m and r['ExecutionPrimaryPhase']!=m.group(1):
   errors.append(f'exact phase mismatch {r["RequirementID"]}')
   break

# JSON
for p in list((HERE/'schemas').glob('*.json'))+list((HERE/'contracts').glob('*.json')):
 try: json.loads(p.read_text(encoding='utf-8'))
 except Exception as e: errors.append(f'invalid JSON {p.name}: {e}')
if len(list((HERE/'schemas').glob('*.json')))<10: errors.append('too few schema files')

# SQL executes and key tables exist.
try:
 con=sqlite3.connect(':memory:')
 con.executescript((HERE/'sqlite/001_initial.sql').read_text(encoding='utf-8'))
 tables={r[0] for r in con.execute("select name from sqlite_master where type='table'")}
 for name in ['asset_index','event_index','review_queue','job_state','map_node_index','relationship_index']:
  if name not in tables: errors.append(f'missing SQL table {name}')
except Exception as e: errors.append(f'SQL invalid: {e}')

# Manifest validates every listed file.
try:
 for r in csv.DictReader((HERE/'PLAN_MANIFEST_SHA256.csv').open(encoding='utf-8',newline='')):
  # Paths are relative to graphify, so strip prefix.
  rel=r['Path'].split('11-implementation-ready-plan/',1)[-1]
  p=HERE/rel
  if not p.is_file(): errors.append(f'manifest missing {rel}'); continue
  if str(p.stat().st_size)!=r['Bytes']: errors.append(f'manifest size mismatch {rel}')
  if hashlib.sha256(p.read_bytes()).hexdigest()!=r['SHA256']: errors.append(f'manifest hash mismatch {rel}')
except Exception as e: errors.append(f'manifest invalid: {e}')

if errors:
 print(json.dumps({'status':'FAIL','errors':errors},indent=2)); sys.exit(1)
print(json.dumps({'status':'PASS','requirements':2083,'phases':17,'schemas':len(list((HERE/'schemas').glob('*.json'))),'requiredFiles':len(required)},indent=2))

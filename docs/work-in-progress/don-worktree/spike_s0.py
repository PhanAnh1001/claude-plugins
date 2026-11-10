from pathlib import Path
from types import SimpleNamespace
import os, subprocess, tempfile, sys, shutil
sys.path.insert(0, str(Path.cwd() / 'hybrid-hands/plugins/hybrid-hands/lib'))
from hand_ext import isolation
root = Path(tempfile.mkdtemp(prefix='don-s0-', dir='/tmp'))
main, sparse, sibling = [root / n for n in ('main', 'sparse', 'sibling')]
env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid', GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid')
os.environ.update(env)
def git(p, *args):
    r = subprocess.run(['git', '-C', str(p), *args], env=env, text=True, capture_output=True, timeout=30)
    if r.returncode: raise RuntimeError(f'{args}: {r.stderr}')
    return r.stdout.strip()
def write(p, rel, text):
    f=p/rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(text)
def commit(p, message):
    git(p, 'add', '-A'); git(p, 'commit', '-m', message)
hidden=['docs/work-in-progress/handoffs/demo-data/item.txt','docs/work-in-progress/handoffs/demo-shots/item.txt']
print('FIXTURE', root, flush=True)
main.mkdir(); git(main,'init','-b','main')
write(main,'src/app.txt','base\n')
for h in hidden: write(main,h,'fixture hidden\n')
commit(main,'fixture baseline')
try:
    git(main,'worktree','add',str(sibling),'-b','sibling')
    git(main,'worktree','add','--no-checkout',str(sparse),'-b','sparse')
    git(sparse,'sparse-checkout','set','--no-cone','/*','!docs/work-in-progress/handoffs/*-data/','!docs/work-in-progress/handoffs/*-shots/')
    git(sparse,'checkout')
    assert all(not (sparse/h).exists() and (main/h).exists() and (sibling/h).exists() for h in hidden)
    assert not git(main,'config','--local','--list').find('core.sparsecheckout=') >= 0
    assert git(sparse,'config','--worktree','--get','core.sparseCheckout') == 'true'
    assert git(main,'status','--porcelain') == git(sibling,'status','--porcelain') == ''
    print('CASE 1 PASS: sparse isolated; main/sibling full and clean; worktree config true', flush=True)
    expected={h:git(sparse,'rev-parse',f'HEAD:{h}') for h in hidden}
    write(sparse,'src/app.txt','sparse commit\n'); commit(sparse,'sparse edit')
    for h in hidden: assert git(sparse,'rev-parse',f'HEAD:{h}') == expected[h]
    write(main,'src/merged.txt','merge\n'); commit(main,'main merge input')
    git(sparse,'merge','--no-edit','main')
    for h in hidden: assert git(sparse,'rev-parse',f'HEAD:{h}') == expected[h]
    write(main,'src/rebased.txt','rebase\n'); commit(main,'main rebase input')
    git(sparse,'rebase','main')
    for h in hidden: assert git(sparse,'rev-parse',f'HEAD:{h}') == expected[h] and not (sparse/h).exists()
    assert git(sparse,'status','--porcelain') == ''
    print('CASE 2 PASS: commit/merge/rebase preserve both excluded blob IDs; sparse clean', flush=True)
    write(sparse,'src/app.txt','dirty parent\n'); write(sparse,'src/untracked.txt','fake untracked\n')
    cfg=SimpleNamespace(worktree_root=root/'children', runs_dir=root/'runs', ledger=root/'ledger', quota_state=root/'quota', machine_state_dir=root/'machine')
    ctx=isolation.prepare(cfg,sparse,'s0',root/'runs/s0',isolation.IsolationChoice('worktree'))
    child=ctx.worktree
    assert ctx.dirty and ctx.base_commit == git(sparse,'rev-parse','HEAD')
    assert (child/'src/app.txt').read_text() == 'dirty parent\n' and (child/'src/untracked.txt').exists()
    assert all(git(child,'rev-parse',f'HEAD:{h}') == expected[h] for h in hidden)
    print('BASELINE EXCLUDED:', [subprocess.run(['git','-C',str(child),'cat-file','-e',f'{ctx.baseline_tree}:{h}'],capture_output=True).returncode == 0 for h in hidden], flush=True)
    print('CASE 3 OBSERVED: isolation.prepare child', child, 'dirty=',ctx.dirty,'excluded_materialized=',[(child/h).exists() for h in hidden], flush=True)
    # Clean only known synthetic edits; never call isolation.cleanup (uses --force).
    git(child,'restore','src/app.txt'); (child/'src/untracked.txt').unlink()
    git(sparse,'restore','src/app.txt'); (sparse/'src/untracked.txt').unlink()
    print('DIRTY_FILES',ctx.dirty_files,flush=True)
    assert not set(hidden).intersection(ctx.dirty_files), 'CASE 3 FAIL: excluded tracked files incorrectly reported as baseline deletions'
finally:
    for p in (root/'children/sparse-s0', sparse, sibling):
        if p.exists():
            assert git(p,'status','--porcelain') == '', f'dirty fixture retained: {p}'
            git(main,'worktree','remove',str(p))
    print('CLEANUP: git worktree remove without force; remaining:', git(main,'worktree','list','--porcelain'), flush=True)
    shutil.rmtree(root)
    print('FIXTURE REMOVED',root, flush=True)

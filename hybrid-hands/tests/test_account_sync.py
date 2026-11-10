"""P0 only: synthetic homes, configuration and subprocesses."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from hand_ext.cli import main
from hand_ext.account_sync_manifest import ManifestError, manifest_from
from shared_config import load_config


def fixture(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    global_file = tmp_path / 'global.json'
    monkeypatch.setenv('HYBRID_HANDS_CONFIG', str(global_file))
    global_file.write_text(json.dumps({'ext_hand': {'account_sync': {'exclude': ['commands']}}}))
    repo = tmp_path / 'repo'
    (repo / '.claude').mkdir(parents=True)
    config = repo / '.claude/hybrid-hands.json'
    config.write_text(json.dumps({'account_sync': {'exclude': ['agents']}}))
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        assert argv[0] == 'git' and 'rev-parse' in argv
        return subprocess.CompletedProcess(argv, 0, str(repo) + '\n', '')
    monkeypatch.setattr(subprocess, 'run', run)
    return repo, config, calls


def test_manifest(tmp_path, monkeypatch, capsys):
    repo, config, _ = fixture(tmp_path, monkeypatch)
    result = load_config(repo)
    data, sources = manifest_from(result)
    assert data['exclude'] == ['agents'] and sources['exclude'] == 'repo'
    assert sources['items'] == 'plugin'
    assert manifest_from(result, {'exclude': ['skills']})[1]['exclude'] == 'cli'
    assert dict(result.sources)['ext_hand.account_sync.exclude'] == 'global'
    for override in ([{'settings': {'shared_keys': [k]}} for k in
                      ('env', 'permissions', 'enabledPlugins', 'extraKnownMarketplaces')] +
                     [{'items': [{'provider': 'claude', 'path': p}]} for p in
                      ('auth.json', 'skills/.system/a', 'skills/../auth.json',
                       'plugins/a', 'skills/.env', '/CLAUDE.md')]):
        with pytest.raises(ManifestError):
            manifest_from(result, override)
    with pytest.raises(ManifestError):
        manifest_from(result, {'sources': {'claude': 'v2'}})
    sentinel = 'SENTINEL_INVALID_GLOBAL'
    global_file = tmp_path / 'global.json'
    global_file.write_text('{"' + sentinel)
    monkeypatch.setenv('HYBRID_HANDS_CONFIG', '../global.json')
    assert main(['accounts', 'status', '--cwd', str(repo), '--json']) == 2
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload['reason'] == 'global_config_error'
    assert payload['config_path'] == str(global_file.resolve())
    assert sentinel not in captured.out + captured.err



def test_dry_run_read_only(tmp_path, monkeypatch, capsys):
    repo, config, calls = fixture(tmp_path, monkeypatch)
    source = tmp_path / '.claude'
    source.mkdir()
    (source / 'CLAUDE.md').write_text('public fixture\n')
    def snapshot():
        return {str(p.relative_to(tmp_path)): (p.lstat().st_mode,
                p.read_bytes() if p.is_file() else None) for p in tmp_path.rglob('*')}
    before = snapshot()
    for command in ('status', 'sync'):
        assert main(['accounts', command, '--cwd', str(repo), '--json']) == 1
        rows = json.loads(capsys.readouterr().out)['items']
        assert all(r['account'] != 'v1' for r in rows)
        asset = next(r for r in rows if r['path'] == 'CLAUDE.md')
        assert asset['action'] == ('missing' if command == 'status' else 'would_create')
        assert any(r['reason'] == 'codex_evidence_required' for r in rows)
    assert main(['accounts', 'sync', '--apply', '--cwd', str(repo), '--json']) == 1
    assert {r['reason'] for r in json.loads(capsys.readouterr().out)['items']} >= {'manifest_approval_required'}
    assert snapshot() == before and calls


def test_dry_run_selector_redaction(tmp_path, monkeypatch, capsys):
    repo, config, _ = fixture(tmp_path, monkeypatch)
    sentinel = 'SENTINEL_PRIVATE_VALUE'
    (tmp_path / '.claude-hand').mkdir()
    (tmp_path / '.claude-hand/settings.json').write_text(json.dumps({'env': {'X': sentinel}}))
    prefix = ['accounts', 'sync', '--cwd', str(repo), '--json']
    for selector in (['--account', 'v2'], ['--all'], [], ['--account', 'v1'],
                     ['--account', sentinel], ['--account', 'v2', '--all']):
        assert main(prefix + selector) == (2 if selector in
            (['--account', 'v1'], ['--account', sentinel], ['--account', 'v2', '--all']) else 1)
        captured = capsys.readouterr()
        assert sentinel not in captured.out + captured.err
        json.loads(captured.out)
    config.write_text('{"' + sentinel)
    assert main(prefix) == 2
    captured = capsys.readouterr()
    assert sentinel not in captured.out + captured.err


def test_assets_apply(tmp_path, monkeypatch):
    from hand_ext.account_sync_plan import build_plan
    repo, _, _ = fixture(tmp_path, monkeypatch)
    source = tmp_path / 'source space'
    source.mkdir()
    (source / 'CLAUDE.md').write_text('public')
    (source / 'skills/paseo').mkdir(parents=True)
    target = tmp_path / 'target'
    result = load_config(repo)
    result.effective['ext_hand']['claude_accounts'] = {
        'v1': {'config_dir': str(source)}, 'v2': {'config_dir': str(target)}}
    data, _ = manifest_from(result, {'items': [dict(provider='claude', path=p, approved=True)
        for p in ('CLAUDE.md', 'skills/paseo')], 'exclude': [], 'settings': {'shared_keys': []}})
    for expected in ('applied', 'in_sync'):
        rows = build_plan(result, data, account='v2', apply=True)
        assert {r['action'] for r in rows} == {expected}
    assert (target / 'CLAUDE.md').read_text() == '@' + str(source / 'CLAUDE.md').replace(' ', '\\ ') + '\n'
    assert (target / 'skills/paseo').readlink() == source / 'skills/paseo'
    (target / 'skills/paseo').unlink()
    import os
    (target / 'skills/paseo').symlink_to(os.path.relpath(source / 'skills/paseo', target / 'skills'))
    for item in data['items']:
        item['approved'] = False
    assert {r['action'] for r in build_plan(result, data, account='v2', apply=True)} == {'in_sync'}


@pytest.mark.parametrize('kind', ['real', 'wrong', 'dangling'])
def test_assets_conflict(tmp_path, kind):
    from hand_ext.account_sync_assets import asset
    source, target = tmp_path / 'source', tmp_path / 'target'
    source.mkdir(); target.mkdir()
    (source / 'CLAUDE.md').write_text('public')
    destination = target / 'CLAUDE.md'
    if kind == 'real':
        destination.write_bytes(b'preserve')
    else:
        destination.symlink_to(source if kind == 'wrong' else source / 'absent')
    before = destination.lstat()
    assert asset(source, target, {'path': 'CLAUDE.md', 'approved': True}, status=False, apply=True)[0] == 'conflict'
    assert destination.lstat() == before
    assert destination.read_bytes() == b'preserve' if kind == 'real' else destination.is_symlink()


def test_assets_boundaries(tmp_path, monkeypatch):
    from hand_ext.account_sync_assets import asset
    from hand_ext.account_sync_plan import build_plan
    repo, _, _ = fixture(tmp_path, monkeypatch)
    source, target = tmp_path / '.claude', tmp_path / '.claude-hand'
    (source / 'skills/.system').mkdir(parents=True)
    target.mkdir()
    for path in (source / 'config.toml', source / 'auth.json', source / 'skills/.system/private'):
        path.write_bytes(b'private sentinel')
    (source / 'skills/public').mkdir()
    import os
    private = {source / 'config.toml', source / 'auth.json', source / 'skills/.system',
               source / 'skills/.system/private'}
    private_entries = {(p.parent.stat().st_dev, p.parent.stat().st_ino, p.name) for p in private}
    original_os_open = os.open
    def guarded_os_open(path, *args, **kwargs):
        candidate = Path(path)
        assert candidate not in private
        if kwargs.get('dir_fd') is not None:
            parent_info = os.fstat(kwargs['dir_fd'])
            assert (parent_info.st_dev, parent_info.st_ino, str(path)) not in private_entries
        return original_os_open(path, *args, **kwargs)
    monkeypatch.setattr(os, 'open', guarded_os_open)
    original = Path.open
    def guarded(path, *args, **kwargs):
        assert path not in private
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guarded)
    result = load_config(repo)
    data, _ = manifest_from(result)
    rows = build_plan(result, data, account='v2')
    assert any(r['path'] == 'skills/public' for r in rows)
    assert not any('.system' in r['path'] for r in rows)
    (target / 'skills').symlink_to(source / 'skills', target_is_directory=True)
    assert asset(source, target, {'path': 'skills/public', 'approved': True}, status=False, apply=True)[0] == 'blocked'
    with pytest.raises(ManifestError):
        manifest_from(result, {'items': [{'provider': 'claude', 'path': 'skills/../escape'}]})

    (target / 'skills').unlink()
    (target / 'skills').mkdir()
    from hand_ext import account_sync_assets as assets
    existing = assets._existing
    def renamed(fd, name, origin, content, destination):
        outcome = existing(fd, name, origin, content, destination)
        if destination == target / 'skills/public' and not (tmp_path / 'moved').exists():
            target.rename(tmp_path / 'moved')
            target.mkdir()
            (target / 'skills').mkdir()
        return outcome
    monkeypatch.setattr(assets, '_existing', renamed)
    assert asset(source, target, {'path': 'skills/public', 'approved': True}, status=False, apply=True)[0] == 'conflict'
    assert not (tmp_path / 'moved/skills/public').exists()
    assert not (target / 'skills/public').exists()
    monkeypatch.setattr(assets, '_existing', existing)
    for failure, expected in ((FileNotFoundError(2, 'fixture'), 'blocked'), (PermissionError(13, 'fixture'), 'error')):
        def failed(*args):
            raise failure
        monkeypatch.setattr('hand_ext.account_sync_plan.children', failed)
        rows = build_plan(result, data, account='v2')
        assert any(r['path'] == 'skills' and r['action'] == expected for r in rows)


def settings_fixture(tmp_path, monkeypatch):
    from hand_ext import account_sync_settings as settings
    monkeypatch.setenv('HOME', str(tmp_path))
    source, target = tmp_path / 'source', tmp_path / 'target'
    source.mkdir(); target.mkdir()
    value = {'type': 'command', 'command': '/public/fixture'}
    (source / 'settings.json').write_text(json.dumps({'statusLine': value, 'hooks': {}}))
    old = {'env': {'PRIVATE': 'SETTINGS_SENTINEL'}, 'model': 'private', 'unknown': [1]}
    (target / 'settings.json').write_text(json.dumps(old))
    policy = {'shared_keys': ['statusLine', 'hooks'], 'ownership': {'statusLine': {
        'approved': True, 'verified': True, 'sha256': settings.value_digest(value)}}}
    return settings, source, target, policy, old


def test_settings_floor_backup_modes_idempotence(tmp_path, monkeypatch):
    import stat
    settings, source, target, policy, old = settings_fixture(tmp_path, monkeypatch)
    path = target / 'settings.json'
    path.chmod(0o640)
    before = path.read_bytes()
    assert settings.reconcile(source, target, policy, status=False, apply=False)[0]['action'] == 'would_create'
    assert not (tmp_path / '.hybrid-hands').exists()
    rows = settings.reconcile(source, target, policy, status=False, apply=True)
    backup = Path(rows[0]['backup_path'])
    assert rows[0]['action'] == 'applied' and rows[1]['action'] == 'blocked'
    assert backup.read_bytes() == before and stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert stat.S_IMODE(backup.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o640
    assert all(json.loads(path.read_text())[k] == v for k, v in old.items())
    snapshot = (path.stat(), backup.stat())
    assert settings.reconcile(source, target, policy, status=False, apply=True)[0]['action'] == 'in_sync'
    assert snapshot == (path.stat(), backup.stat())
    path.unlink()
    # Distinct absent target has a separate immutable absence marker.
    other = tmp_path / 'new'
    rows = settings.reconcile(source, other, policy, status=False, apply=True)
    assert Path(rows[0]['backup_path']).name == 'absent'
    assert stat.S_IMODE((other / 'settings.json').stat().st_mode) == 0o600


@pytest.mark.parametrize('kind', ['json', 'source_link', 'target_link', 'parent_link', 'concurrent'])
def test_settings_invalid_or_concurrent(tmp_path, monkeypatch, kind):
    settings, source, target, policy, _ = settings_fixture(tmp_path, monkeypatch)
    path = target / 'settings.json'
    if kind == 'json':
        (source / 'settings.json').write_text('{SETTINGS_SENTINEL')
    elif kind in {'source_link', 'target_link'}:
        link = (source if kind == 'source_link' else target) / 'settings.json'
        link.unlink(); link.symlink_to(tmp_path / 'missing')
    elif kind == 'parent_link':
        target.rename(tmp_path / 'moved'); target.symlink_to(tmp_path / 'moved')
    else:
        write = settings._write
        def concurrent(*args):
            path.write_text('{"unknown":"concurrent"}')
            return write(*args)
        monkeypatch.setattr(settings, '_write', concurrent)
    before = path.read_bytes() if path.exists() else None
    rows = settings.reconcile(source, target, policy, status=False, apply=True)
    assert rows[0]['action'] == ('conflict' if kind == 'concurrent' else 'blocked')
    assert path.read_bytes() == b'{"unknown":"concurrent"}' if kind == 'concurrent' else (
        path.read_bytes() == before if path.exists() else before is None)
    assert not (tmp_path / '.hybrid-hands').exists()


@pytest.mark.parametrize('operation', ['_backup', 'replace', 'read', 'backup_fsync',
                                      'incomplete', 'directory_fsync'])
def test_settings_failure_redacted(tmp_path, monkeypatch, capsys, operation):
    import os
    import stat
    from argparse import Namespace
    from hand_ext import accounts_cmd
    settings, source, target, policy, old = settings_fixture(tmp_path, monkeypatch)
    path = target / 'settings.json'
    before = path.read_bytes()
    def fail(*args, **kwargs):
        raise OSError('SETTINGS_SENTINEL')
    if operation == 'incomplete':
        import hashlib
        folder = tmp_path / '.hybrid-hands/backups' / hashlib.sha256(str(path).encode()).hexdigest()
        folder.mkdir(parents=True, mode=0o700)
        folder.parent.chmod(0o700); folder.parent.parent.chmod(0o700)
        partial = folder / 'original.json'
        partial.write_bytes(b'partial'); partial.chmod(0o600)
    elif operation in {'backup_fsync', 'directory_fsync'}:
        fsync = settings.os.fsync
        def interrupted(fd):
            info = os.fstat(fd)
            if (operation == 'backup_fsync' and stat.S_ISREG(info.st_mode) or
                    operation == 'directory_fsync' and info.st_ino == target.stat().st_ino):
                fail()
            return fsync(fd)
        monkeypatch.setattr(settings.os, 'fsync', interrupted)
    else:
        owner, name = (settings, '_read' if operation == 'read' else '_backup') if operation in {
            'read', '_backup'} else (settings.os, 'replace')
        monkeypatch.setattr(owner, name, fail)
    rows = settings.reconcile(source, target, policy, status=False, apply=True)
    expected = 'blocked' if operation == 'incomplete' else 'error'
    assert rows[0]['action'] == expected
    if operation == 'directory_fsync':
        assert rows[0]['reason'] == 'commit_durability_unknown'
        assert Path(rows[0]['backup_path']).read_bytes() == before
        assert all(json.loads(path.read_text())[k] == v for k, v in old.items())
        assert 'statusLine' in json.loads(path.read_text())
    else:
        assert path.read_bytes() == before
    if operation in {'backup_fsync', 'incomplete'}:
        monkeypatch.undo()
        monkeypatch.setenv('HOME', str(tmp_path))
        retry = settings.reconcile(source, target, policy, status=False, apply=True)
        assert retry[0]['action'] == 'blocked' and path.read_bytes() == before
    monkeypatch.setattr(accounts_cmd, 'load_config', lambda *_: object())
    monkeypatch.setattr(accounts_cmd, 'manifest_from', lambda *_: ({}, {}))
    monkeypatch.setattr(accounts_cmd, 'build_plan', lambda *a, **kw: rows)
    assert accounts_cmd.command(Namespace(cwd=str(tmp_path), account='v2',
        accounts_cmd='sync', apply=True, json=True)) == (1 if expected == 'blocked' else 2)
    assert 'SETTINGS_SENTINEL' not in json.dumps(rows) + ''.join(capsys.readouterr())
    assert not list(target.glob('.settings-*'))


@pytest.mark.parametrize('scope', ['user', 'project', 'local'])
@pytest.mark.parametrize('sourcekind', ['https', 'directory', 'unapproved'])
def test_official_install_idempotent(tmp_path, monkeypatch, scope, sourcekind):
    from hand_ext import account_sync_official as official
    source, target = tmp_path / 'source', tmp_path / 'target'
    source.mkdir(); target.mkdir()
    identifier, url = 'example@public', 'https://example.org/public.git'
    policy = {'marketplaces': {'public': {'approved': True, 'url': url}}, 'items': [
        {'id': identifier, 'scope': scope, 'approved': True, 'verified': True, 'repo_used': True}]}
    public = tmp_path / 'public-market'
    public.mkdir(); (public / 'example').mkdir()
    if sourcekind != 'https':
        url = str(public)
        policy['marketplaces']['public'] = {'approved': sourcekind == 'directory', 'path': url}
    official.validate_policy(policy, [])
    installed, markets, calls = False, False, []
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', 'unchanged')
    def run(argv, **kw):
        nonlocal installed, markets
        calls.append(argv)
        assert kw['stdin'] == subprocess.DEVNULL
        assert kw['stdout'] == kw['stderr'] == subprocess.PIPE
        is_source = 'CLAUDE_CONFIG_DIR' not in kw['env']
        assert is_source or kw['env']['CLAUDE_CONFIG_DIR'] == str(target)
        assert kw['cwd'] == str(tmp_path)
        args = argv[2:]
        if args == ['list', '--json']:
            data = [dict(id=identifier, version='1.0', scope=scope, enabled=True,
                         installPath=str((source if is_source else target) / 'plugins/example'), projectPath=str(tmp_path),
                         mcpServers={'private': 'SENTINEL'})] if is_source or installed else []
            if sourcekind != 'https' and data:
                data[0]['readFromFolder'] = str(public / 'example')
            data.append(dict(id='unrelated@public', scope='managed', mcpServers='SENTINEL'))
        elif args == ['marketplace', 'list', '--json']:
            data = [dict(name='public', url=url, path=url, source='url' if sourcekind == 'https' else 'directory', diagnostics='SENTINEL')] if is_source or markets else []
        else:
            assert not is_source and '--yes' not in argv
            if args[0] == 'marketplace':
                assert args == ['marketplace', 'add', url, '--scope', scope, '--json']
                markets = True
            else:
                assert args == ['install', identifier, '--scope', scope, '--json']
                installed = True
            data = {'command': 'marketplace-add' if args[0] == 'marketplace' else 'install',
                    'outcome': 'ok', 'message': 'SENTINEL'}
        return subprocess.CompletedProcess(argv, 0, json.dumps(data), 'SENTINEL')
    monkeypatch.setattr(subprocess, 'run', run)
    def execute(**kw):
        return official.reconcile('v1', source, 'v2', target, tmp_path, policy, [], **kw)
    if sourcekind == 'unapproved':
        assert execute(apply=True)[0]['reason'] == 'plugin_path_unapproved'
        assert not any('install' in c or 'add' in c for c in calls)
        return
    assert execute()[0]['action'] == 'would_create' and not installed and not markets
    assert execute(apply=True)[0]['action'] == 'applied'
    count = len([c for c in calls if 'install' in c or 'add' in c])
    assert execute(apply=True)[0]['action'] == 'in_sync'
    assert len([c for c in calls if 'install' in c or 'add' in c]) == count == 2
    import os
    assert os.environ['CLAUDE_CONFIG_DIR'] == 'unchanged'


@pytest.mark.parametrize('failure', ['error', 'timeout', 'ack', 'wrong_command', 'wrong_outcome', 'wrong_message'])
def test_official_partial_redaction(tmp_path, monkeypatch, capsys, failure):
    from hand_ext import account_sync_official as official
    source, target = tmp_path / 'source', tmp_path / 'target'
    source.mkdir(); target.mkdir()
    marker = target / 'installed_plugins.json'
    marker.write_text('public sentinel unchanged')
    policy = {'marketplaces': {'public': {'approved': True, 'url': 'https://example.org/public'}},
              'items': [dict(id='example@public', scope='user', approved=True, verified=True)]}
    calls = []
    def run(argv, **kw):
        calls.append(argv)
        if 'install' in argv:
            if failure == 'timeout':
                raise subprocess.TimeoutExpired(argv, 30, output='SENTINEL', stderr='SENTINEL')
            ack = dict(command='install', outcome='ok', message='SENTINEL')
            ack.update({'wrong_command': {'command': 'marketplace-add'},
                        'wrong_outcome': {'outcome': 'success'}, 'wrong_message': {'message': 1},
                        'ack': {'command': None}}.get(failure, {}))
            return subprocess.CompletedProcess(argv, 1 if failure == 'error' else 0,
                                               json.dumps(ack), 'SENTINEL')
        if 'marketplace' in argv:
            data = [dict(name='public', source='url', url='https://example.org/public')]
        else:
            data = [dict(id='example@public', scope='user', version='1', enabled=True,
                         installPath=str(source / 'plugins/example'))] if 'CLAUDE_CONFIG_DIR' not in kw['env'] else []
        return subprocess.CompletedProcess(argv, 0, json.dumps(data), '')
    monkeypatch.setattr(subprocess, 'run', run)
    rows = official.reconcile('v1', source, 'v2', target, tmp_path, policy, [], apply=True)
    assert rows[0]['action'] == 'error' and sum('install' in c for c in calls) == 1
    assert marker.read_text() == 'public sentinel unchanged'
    assert 'SENTINEL' not in json.dumps(rows) + ''.join(capsys.readouterr())


@pytest.mark.parametrize('approved', [False, True])
def test_official_mcp_blocked(tmp_path, monkeypatch, approved):
    from hand_ext import account_sync_official as official
    def forbidden(*a, **kw):
        pytest.fail('MCP must not invoke CLI')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    rows = official.reconcile('v1', tmp_path / 'a', 'v2', tmp_path / 'b', tmp_path,
                              {}, [{'name': 'public', 'approved': approved}], apply=True)
    assert rows[0]['action'] == 'blocked'
    assert rows[0]['reason'] == ('mcp_safe_transport_unverified' if approved else 'mcp_approval_required')

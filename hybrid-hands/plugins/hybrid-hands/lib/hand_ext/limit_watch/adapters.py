"""Identity-pinned continuations. No shell interpolation, TUI guesses or new agents."""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace


def bridge(target, command='status', text=None):
    from side_session import paseo
    root, node = paseo.cli_package_root(), shutil.which('node')
    if root is None or node is None:
        return dict(valid=False)
    request = {**target, 'command': command}
    if text is not None:
        request['text'] = text
    proc = subprocess.run([node, str(Path(__file__).with_name('paseo_bridge.mjs')), str(root)],
                          input=json.dumps(request), capture_output=True, text=True,
                          env=paseo.clean_env(), timeout=12, check=True)
    return json.loads(proc.stdout)


def side_record(target):
    from side_session.config import load_config
    from side_session.state import load
    cfg = load_config(Path(target['cwd']))
    st = load(cfg.state_dir, target['side_name'])
    expected = (target['side_uuid'], target['agent_id'], target['workspace_id'],
                target['target_key'], target['cwd'], target['native_id'])
    actual = (st.uuid, st.paseo_agent_id, st.paseo_workspace_id, st.paseo_target,
              st.dir, st.native_session_id if st.provider == 'claude' else st.codex_thread_id)
    if (actual != expected or st.role == 'main' or st.transport != 'paseo'
            or st.provider != target['provider'] or st.paseo_send_pending):
        raise ValueError('side_identity_changed')
    return cfg, st


def runtime(target):
    if not Path(target['cwd']).is_dir():
        return dict(valid=True, closed=True, idle=False)
    if target['adapter'] == 'side':
        cfg, st = side_record(target)
        done = Path(st.handoff).with_suffix('.done').exists()
        if done or st.status in ('done', 'stopped'):
            return dict(valid=True, done=True)
        result = bridge(target)
        # side-session send's own stricter stopped-state guard is authoritative.
        from side_session.constants import ACTIVE_STATUSES
        if st.status in ACTIVE_STATUSES:
            result['idle'] = False
        return result
    return bridge(target)


def send(target, prompt):
    if target['adapter'] == 'paseo':
        return bridge(target, 'send', prompt).get('receipt', 'unknown')
    # Run the existing side-session send action, including preflight, restoration,
    # marker history, pending ACK, watchdog, and main guard. The expected identity
    # is rechecked *inside* its send lock to protect name reuse.
    from side_session.actions import send as side_send
    cfg, _ = side_record(target)
    if not runtime(target).get('idle'):
        return 'not_sent'
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'continue.md'
        path.write_text(prompt)
        args = SimpleNamespace(name=target['side_name'], prompt_file=str(path),
                               _limit_watch_identity=target, force_budget=False)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = side_send(cfg, args)
    # side_send returns zero only after the bridge checked daemon acceptance and
    # exact IDs. A generic command exit code is not used as delivery evidence.
    return 'accepted' if code == 0 else 'unknown'

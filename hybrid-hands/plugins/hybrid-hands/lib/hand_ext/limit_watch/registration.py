"""Build registrations from public metadata only; never inspect provider auth."""
from __future__ import annotations

import os
import re
from pathlib import Path

from . import adapters


class RegistrationError(ValueError):
    """Safe, locally authored diagnostics without metadata values."""


def require(raw: dict, *fields: str) -> None:
    missing = [key for key in fields if not isinstance(raw.get(key), str) or not raw[key].strip()]
    if missing:
        raise RegistrationError('Thiếu trường: ' + ', '.join(missing))


def build(args) -> dict:
    from side_session.config import load_config
    from side_session.state import load

    cwd = Path(args.cwd or Path.cwd()).resolve()
    cfg = load_config(cwd)
    st = None
    if args.side:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', args.side):
            raise RegistrationError('Tên side không hợp lệ')
        st = load(cfg.state_dir, args.side)
        if st.transport != 'paseo' or st.role == 'main' or st.paseo_send_pending:
            raise RegistrationError('Side phải qua Paseo, không là main hoặc đang chờ ACK')
        require(dict(side_uuid=st.uuid, agent_id=st.paseo_agent_id,
                     workspace_id=st.paseo_workspace_id,
                     native_id=st.native_session_id if st.provider == 'claude' else st.codex_thread_id,
                     target_key=st.paseo_target),
                'side_uuid', 'agent_id', 'workspace_id', 'native_id', 'target_key')
        agent = st.paseo_agent_id
    else:
        agent = os.environ.get('PASEO_AGENT_ID', '')
    require(dict(agent_id=agent), 'agent_id')
    raw = adapters.bridge(dict(agent_id=agent), 'discover')
    require(raw, 'agent_id', 'workspace_id', 'native_id', 'cwd', 'paseo_provider', 'target_key')
    if raw['agent_id'] != agent:
        raise RegistrationError('Metadata agent_id không khớp')
    provider_name = raw['paseo_provider']
    provider = 'claude' if provider_name == 'claude' or provider_name.startswith('claude-') else 'codex' if provider_name in ('codex', 'codex-hand') else ''
    if not provider:
        raise RegistrationError('Provider chưa hỗ trợ')
    home = (st.claude_config_dir if st else os.environ.get('CLAUDE_CONFIG_DIR', '')) if provider == 'claude' else str(cfg.codex_home) if st else os.environ.get('CODEX_HOME', '')
    require(dict(account_home=home), 'account_home')
    home = str(Path(home).expanduser().resolve())
    account = 'gpt'
    if provider == 'claude':
        matches = [name for name, opts in cfg.claude_accounts.items()
                   if isinstance(opts, dict) and opts.get('config_dir')
                   and str((cfg.repo / Path(opts['config_dir']).expanduser()).resolve()) == home]
        if len(matches) != 1:
            raise RegistrationError('Thiếu account duy nhất khớp account_home')
        account = matches[0]
    raw.update(provider=provider, account=account, account_home=home,
               adapter='side' if st else 'paseo', checkpoint=args.checkpoint,
               next_step=args.next_step or 'Tiếp tục từ checkpoint trong phạm vi đã duyệt.',
               work_pending=True, id=args.id or (args.side if st else agent))
    if not re.fullmatch(r'[A-Za-z0-9_-]+', raw['id']):
        raise RegistrationError('ID không hợp lệ (chỉ chữ, số, dấu gạch)')
    if st:
        raw.update(side_name=st.name, side_uuid=st.uuid)
        require(raw, 'side_uuid')
        adapters.side_record(raw)
    elif str(cwd) != raw['cwd']:
        raise RegistrationError('Metadata cwd không khớp phiên gọi')
    return raw

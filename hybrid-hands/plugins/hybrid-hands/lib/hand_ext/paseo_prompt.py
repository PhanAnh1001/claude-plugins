"""Small canonical projection of Paseo 0.15.0 text-only agent messages."""
import hashlib
import json
import re
from pathlib import Path

from .execution_state import StateConflict, _plain

# ECMAScript WhiteSpace + LineTerminator, deliberately excluding U+0085/001C.
JS_SPACE = "\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
ENTITIES = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;'}


def trim(text):
    return text.strip(JS_SPACE)


def prompt_path(record):
    suffix = hashlib.sha256(json.dumps(_plain(record.key), sort_keys=True).encode()).hexdigest()
    return Path(record.invocation.fixed_options['run_dir']) / suffix / 'prompt.md'


def escape(text):
    return ''.join(ENTITIES.get(c, c) for c in text)


def project(record, incoming, message_id):
    """Keep the pin authoritative, including legacy trailing whitespace."""
    pin = prompt_path(record).read_bytes().decode('utf-8')
    digest = hashlib.sha256(pin.encode()).hexdigest()
    receipt = record.receipt or {}
    transport = receipt.get('transport', {})
    digests = [source[key] for source, key in ((receipt, 'brief_digest'),
               (transport, 'briefDigest')) if key in source]
    if not digests:
        raise StateConflict('pinned digest required')
    for expected in digests:
        if (not isinstance(expected, str) or re.fullmatch(r'[0-9a-f]{64}', expected) is None
                or expected != digest):
            raise StateConflict('pinned digest mismatch')
    if incoming == pin:
        return pin
    if (transport.get('messageId') != message_id or
            record.attempt.request_key != message_id or
            not record.invocation.parent_paseo_agent_id):
        raise StateConflict('envelope binding required')
    for public, field in {'targetKey': 'target_key', 'projectId': 'project_id',
                          'workspaceId': 'workspace_id', 'agentId': 'agent_id'}.items():
        if not getattr(record.attempt, field) or transport.get(public) != getattr(record.attempt, field):
            raise StateConflict('exact envelope placement required')
    if transport.get('briefDigest') != digest:
        raise StateConflict('envelope digest required')
    prefix = ('<paseo-system version="1" kind="agent-message" source-agent-id="' +
              escape(record.invocation.parent_paseo_agent_id) + '" message-id="' + escape(message_id) + '"')
    # Optional metadata is accepted only in official formatter order and encoding.
    pattern = re.escape(prefix) + r'(?P<meta>(?: source-server-id="[^"<>]+")?(?: source-agent-title="[^"<>]+")?)>\n' + re.escape(escape(trim(pin))) + r'\n</paseo-system>'
    match = re.fullmatch(pattern, incoming)
    if not match:
        raise StateConflict('prompt projection mismatch')
    for value in re.findall(r'="([^"<>]+)"', match['meta']):
        decoded = re.sub(r'&(amp|lt|gt|quot|apos);', lambda m: next(k for k,v in ENTITIES.items() if v == m[0]), value)
        if escape(decoded) != value:
            raise StateConflict('noncanonical metadata')
    return pin

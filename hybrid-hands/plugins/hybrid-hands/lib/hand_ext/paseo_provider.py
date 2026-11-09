"""Safe setup for official @getpaseo/cli 0.15.0 custom ACP providers.

Evidence (relative to the pinned CLI package):
node_modules/@getpaseo/server/dist/server/server/persisted-config.js:294-305,
317,333-335: agents.providers and <Paseo home>/config.json.
node_modules/@getpaseo/server/dist/server/server/agent/provider-registry.js:484-539:
extends='acp', nonempty command argv, GenericACPAgentClient registration.
node_modules/@getpaseo/server/dist/server/server/agent/provider-launch-config.js:4:
ProviderOverrideSchema exported from the official protocol package.
node_modules/@getpaseo/protocol/dist/provider-config.js:41-96: command argv,
provider ID alphabet, required custom label and ACP command.
dist/commands/daemon/config.js:80-98: official CLI persisted config editing.

No config values or upstream diagnostics are returned. Setup only saves config;
it does not reload a daemon. status_provider uses the transport's public catalog
probe, never configuration existence as evidence of runtime availability.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

PROVIDER_IDS = tuple('hh-hand-' + backend for backend in
                     ('codex', 'dsh', 'claude-v1', 'claude-v2'))
SCHEMA_PATH = 'node_modules/@getpaseo/server/dist/server/server/persisted-config.js'


class ProviderError(RuntimeError):
    """Safe machine code; never include configuration or subprocess diagnostics."""


def _package_root(package_root=None):
    if package_root is None:
        executable = shutil.which('paseo')
        if executable:
            for parent in Path(executable).resolve().parents:
                candidate = parent / 'package.json'
                if candidate.is_file():
                    try:
                        if json.loads(candidate.read_text()).get('name') == '@getpaseo/cli':
                            package_root = parent
                            break
                    except (OSError, ValueError, AttributeError):
                        pass
    try:
        root = Path(package_root)
        package = json.loads((root / 'package.json').read_text())
        if (not root.is_absolute() or package.get('name') != '@getpaseo/cli'
                or package.get('version') != '0.15.0' or package.get('type') != 'module'
                or not (root / SCHEMA_PATH).is_file()):
            raise ValueError()
        return root
    except (OSError, ValueError, TypeError, AttributeError):
        raise ProviderError('PACKAGE_UNSUPPORTED') from None


def _validate(root, config):
    # Official schema rather than a second, inevitably drifting implementation.
    # JSON goes only over stdin; stdout/stderr are never exposed to callers.
    script = """import {pathToFileURL} from 'node:url';
import {readFileSync} from 'node:fs';
if (Number(process.versions.node.split('.')[0]) < 22) process.exit(2);
const {PersistedConfigSchema} = await import(pathToFileURL(process.argv[1]));
const value = JSON.parse(readFileSync(0, 'utf8'));
process.exit(PersistedConfigSchema.safeParse(value).success ? 0 : 1);
"""
    try:
        result = subprocess.run(['node', '--input-type=module', '-e', script,
                                 str(root / SCHEMA_PATH)], input=json.dumps(config),
                                text=True, capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        raise ProviderError('SCHEMA_VALIDATOR_UNAVAILABLE') from None
    if result.returncode != 0:
        raise ProviderError('CONFIG_INVALID' if result.returncode == 1
                            else 'SCHEMA_VALIDATOR_UNAVAILABLE')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def setup_provider(home, *, apply=False, package_root=None):
    """Plan/save four providers in explicit *Paseo daemon home* (not user HOME).

    Return {ok, applied, changed, config_path, providers, changes, proposed_updates, backup_path,
    reload_required}. changes contains only provider IDs and create/update actions.
    Raise ProviderError with a safe code on invalid input. Dry-run never writes.
    Existing JSON keys remain intact; schema migration/normalization is not saved.
    """
    root = _package_root(package_root)
    home = Path(home)
    if not home.is_absolute() or home.is_symlink():
        raise ProviderError('HOME_INVALID')
    path = home / 'config.json'
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ProviderError('CONFIG_INVALID')
    try:
        original = path.read_bytes() if path.exists() else None
        config = json.loads(original, object_pairs_hook=_unique_object) if original is not None else {}
    except (OSError, ValueError, UnicodeError):
        raise ProviderError('CONFIG_INVALID') from None
    _validate(root, config)
    # Keep unnormalized input, including unrelated and legacy provider settings.
    proposed = deepcopy(config)
    agents = proposed.setdefault('agents', {})
    providers = agents.setdefault('providers', {})
    command = str(Path(__file__).resolve().parents[2] / 'bin/hand-paseo-acp')
    if not os.access(command, os.X_OK):
        raise ProviderError('GATEWAY_UNAVAILABLE')
    changes = []
    for provider in PROVIDER_IDS:
        before = providers.get(provider)
        updated = dict(before or {})
        updated.update(extends='acp', command=[command], enabled=True)
        updated.setdefault('label', 'Hybrid Hands ' + provider.removeprefix('hh-hand-'))
        if before != updated:
            changes.append({'provider': provider, 'action': 'create' if before is None else 'update'})
        providers[provider] = updated
    _validate(root, proposed)
    result = dict(ok=True, applied=False, changed=bool(changes), config_path=str(path),
                  providers=list(PROVIDER_IDS), changes=changes, proposed_updates={
                      change['provider']: {field: deepcopy(providers[change['provider']][field])
                                           for field in ('command', 'extends', 'enabled')}
                      for change in changes}, backup_path=None,
                  reload_required=False)
    if not apply or not changes:
        return result
    backup_path = None
    temporary_path = None
    try:
        home.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink() or (path.read_bytes() if path.exists() else None) != original:
            raise ProviderError('CONFIG_CHANGED')
        if original is not None:
            fd, backup_path = tempfile.mkstemp(prefix='config.json.backup-', dir=home)
            with os.fdopen(fd, 'wb') as backup:
                backup.write(original)
                backup.flush()
                os.fsync(backup.fileno())
        fd, temporary_path = tempfile.mkstemp(prefix='.config.json-', dir=home)
        with os.fdopen(fd, 'w') as output:
            json.dump(proposed, output, indent=2, ensure_ascii=False, allow_nan=False)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        if path.is_symlink() or (path.read_bytes() if path.exists() else None) != original:
            raise ProviderError('CONFIG_CHANGED')
        os.replace(temporary_path, path)
        temporary_path = None
        directory = os.open(home, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError:
        raise ProviderError('CONFIG_WRITE_FAILED') from None
    finally:
        if temporary_path is not None:
            os.unlink(temporary_path)
    result.update(applied=True, backup_path=backup_path, reload_required=True)
    return result


def status_provider(transport):
    """Read runtime catalog through PaseoTransport.probe_capabilities()."""
    try:
        catalog = transport.probe_capabilities()
        available = catalog.get('providers')
        if not catalog.get('ok') or not isinstance(available, list) or not all(
                isinstance(item, str) for item in available):
            raise ValueError()
    except Exception:
        return {'ok': False, 'code': 'CATALOG_UNAVAILABLE',
                'providers': [], 'missing': list(PROVIDER_IDS)}
    present = [provider for provider in PROVIDER_IDS if provider in available]
    missing = [provider for provider in PROVIDER_IDS if provider not in available]
    return {'ok': not missing, 'code': 'PROVIDERS_MISSING' if missing else 'READY',
            'providers': present, 'missing': missing}

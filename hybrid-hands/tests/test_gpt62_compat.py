"""New GPT model capability is opt-in; routing defaults remain on the old models."""
import json
import sys
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'
sys.path.insert(0, str(LIB))
from hand_ext.cli import main
from hand_ext.profiles import ProfileError, profile_table, role_spec
from shared_config import load_config
from usage_pricing import model_price

MODELS = ('gpt-6.2-sol', 'gpt-6.2-astra')


@pytest.fixture
def config(tmp_path, monkeypatch):
    global_path = tmp_path / 'global.json'
    global_path.write_text('{}')
    monkeypatch.setenv('HYBRID_HANDS_CONFIG', str(global_path))
    path = tmp_path / '.claude/hybrid-hands.json'
    path.parent.mkdir()
    path.write_text(json.dumps({'profile': 'gpt-mono'}))
    return tmp_path, path


def effective(config):
    root, path = config
    return load_config(known_root=root, config_file=path).effective


def test_default_routing_remains_on_old_models(config):
    cfg = effective(config)
    roles = profile_table(cfg)
    assert (roles['brain']['model'], roles['brain']['effort']) == ('gpt-6.1-sol', 'high')
    assert (roles['code']['model'], roles['code']['effort']) == ('gpt-6.1-sol', 'low')
    for key in ('collect.1', 'collect.2'):
        assert (roles[key]['model'], roles[key]['effort']) == ('gpt-6.1-terra', 'low')
    assert (roles['chrome.1']['model'], roles['chrome.1']['effort']) == ('claude-sonnet-5-5', 'low')
    assert (roles['chrome.2']['model'], roles['chrome.2']['effort']) == ('claude-sonnet-5-5', 'medium')
    backend = cfg['ext_hand']['backends']['codex']
    assert (backend['model'], backend['effort']) == ('gpt-6.1-sol', 'low')


@pytest.mark.parametrize('model', MODELS)
@pytest.mark.parametrize('effort', ('low', 'medium', 'high', 'xhigh'))
def test_explicit_profile_model_is_supported(config, model, effort):
    root, path = config
    path.write_text(json.dumps({'profile': 'gpt-mono', 'profiles': {'gpt-mono': {
        'code': {'model': model, 'effort': effort}}}}))
    cfg = effective(config)
    chosen = role_spec(cfg, 'code')
    assert (chosen['model'], chosen['effort'], chosen['account']) == (model, effort, 'v1')
    assert role_spec(cfg, 'brain')['model'] == 'gpt-6.1-sol'


@pytest.mark.parametrize('model', MODELS)
def test_model_cli_accepts_explicit_selection_without_writes(config, capsys, model):
    root, path = config
    before = path.read_bytes()
    assert main(['models', 'set', '--cwd', str(root), '--json', '--dry-run',
                 '--hand', f'codex={model}:medium']) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['diff']['ext_hand.backends.codex.model'] == [None, model]
    assert path.read_bytes() == before


def test_model_options_advertise_capability_without_changing_presets(config, capsys):
    root, path = config
    before = path.read_bytes()
    assert main(['models', 'options', '--cwd', str(root), '--json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(MODELS) <= set(data['providers']['codex']['models'])
    args = [arg for rows in data['presets'].values() for row in rows for arg in row['args']]
    assert not any('gpt-6.2-' in arg for arg in args)
    assert path.read_bytes() == before


@pytest.mark.parametrize('model,want', [('gpt-6.2-sol', (2, .1, 10)),
                                       ('gpt-6.2-astra', (8, .4, 40))])
def test_new_models_have_canonical_standard_api_prices(model, want):
    price = model_price(model)
    assert price is not None
    assert tuple(price[k] for k in ('input', 'cached', 'output')) == want
    assert price['source'].startswith('https://')
    assert price['price_date'] == '2026-11-18'


def test_unknown_models_still_rejected(config):
    cfg = effective(config)
    cfg['profiles'] = {'gpt-mono': {'code': {'model': 'gpt-unrecognized'}}}
    with pytest.raises(ProfileError, match='không thuộc provider'):
        role_spec(cfg, 'code')

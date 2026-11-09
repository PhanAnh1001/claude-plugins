import json
import sys
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from hh_ps import claude_calibration as c


def sample(pct=10, at=1000, identity='a', reset=10000):
    return dict(pct=pct, at=at, identity=identity, reset=reset)


import tempfile
import unittest


class CalibrationTests(unittest.TestCase):
    def test_rate_precision_reset_account_and_decrease(self):
        price = lambda *args: (10, {})
        assert c.rate([sample()], sample(12, 1100), Path('/fake'), 1100, price) == 5
        assert c.rate([sample()], sample(11, 1100), Path('/fake'), 1100, price) is None
        assert c.rate([sample(10.1)], sample(10.3, 1100), Path('/fake'), 1100, price) > 49
        for current in (sample(12, 1100, 'b'), sample(12, 1100, reset=11000)):
            assert c.rate([sample()], current, Path('/fake'), 1100, price) is None
        assert c.rate([sample(12)], sample(10, 1100), Path('/fake'), 1100, price) is None
        assert c.rate([sample()], sample(12, 1100), Path('/fake'), 1500, price) is None
        assert c.rate([sample()], sample(12, 1100), Path('/fake'), 1100, lambda *a: (None, None)) is None


    def test_quota_exact_account_no_first_fallback(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        tmp_path = Path(directory.name)
        rows = [dict(sourceId='claude', account=dict(label=email), fetchedAt=1100,
                     report=dict(status='available', windows=[dict(id='weekly', usedPct=pct, resetsAt=10000.4)]))
                for email, pct in [('wrong@example.test', 99), ('right@example.test', 10.25)]]
        with patch.object(c, 'command', side_effect=[dict(loggedIn=True, email='right@example.test'), rows]):
            result = c.quota(tmp_path, 1100)
            assert result['pct'] == 10.25 and result['reset'] == 10000
            assert 'right@example.test' not in json.dumps(result)
        with patch.object(c, 'command', side_effect=[dict(loggedIn=True, email='none@example.test'), rows]):
            assert c.quota(tmp_path, 1100) is None
        rows[1]['fetchedAt'] = 0
        with patch.object(c, 'command', side_effect=[dict(loggedIn=True, email='right@example.test'), rows]):
            assert c.quota(tmp_path, 1100) is None


    def test_cached_never_polls_and_invalidates(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        tmp_path = Path(directory.name)
        path = tmp_path/'state.json'
        header = c.empty() | dict(sampled_at=1000, resets_at=2000, usd_per_pct=5, account_source='paseo_claude_account')
        path.write_text(json.dumps(dict(header=header, pricing=c.pricing_fingerprint())))
        with patch.object(c, 'cache_path', return_value=path), patch.object(c, 'command', side_effect=AssertionError):
            assert c.cached(1100)['usd_per_pct'] == 5
            assert c.cached(1500)['usd_per_pct'] is None


    def test_costs_all_cache_tokens_and_unknown_model(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        tmp_path = Path(directory.name)
        from hh_ps import week
        (tmp_path/'projects').mkdir()
        path = tmp_path/'fake.py'
        path.touch()
        tokens = dict(input=1, output=2, cache_read=3, cache_write_5m=4, cache_write_1h=5)
        price = SimpleNamespace(cached=1, cache_write_5m=2, cache_write_1h=3)
        module = SimpleNamespace(refresh_prices=lambda: None,
            window_messages=lambda *a: {'dedup':SimpleNamespace(model='known', tokens=tokens)},
            price_for=lambda m: price, token_costs=lambda p, t: dict(cost=sum(t.values())))
        with patch.object(week, '_locate_usage_ledger', return_value=path), patch.object(week, '_ledger_module', return_value=module):
            assert c.costs(tmp_path, 0, 1) == (15, tokens)
            module.price_for=lambda m: None
            assert c.costs(tmp_path, 0, 1) == (None, tokens)


    def test_bad_persisted_state_and_price_change(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        tmp_path = Path(directory.name)
        path = tmp_path/'state.json'
        with patch.object(c, 'cache_path', return_value=path):
            for header in ([], {'sampled_at':1000, 'resets_at':2000, 'usd_per_pct':-2}):
                path.write_text(json.dumps(dict(header=header, pricing=c.pricing_fingerprint())))
                assert c.cached(1100)['usd_per_pct'] is None
            path.write_text(json.dumps(dict(header=c.empty() | dict(sampled_at=1000, resets_at=2000, usd_per_pct=5, account_source='paseo_claude_account'), pricing='old')))
            assert c.cached(1100)['usd_per_pct'] is None


    def test_real_ledger_fixture_dedups_streaming_cache_duration(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        tmp_path = Path(directory.name)
        from hh_ps import week
        from usage_pricing import load_prices
        from datetime import datetime, timezone
        model = next(k for k, v in load_prices().items() if v.get('cache_write_1h') and v.get('cache_write_5m'))
        projects = tmp_path/'projects'/'fixture'
        projects.mkdir(parents=True)
        rows = []
        for output in (1, 7):
            rows.append(json.dumps(dict(type='assistant', requestId='fake-request',
                timestamp=datetime.fromtimestamp(1000, timezone.utc).isoformat(),
                message=dict(id='fake-message', model=model, usage=dict(input_tokens=2,
                    output_tokens=output, cache_read_input_tokens=3,
                    cache_creation_input_tokens=11,
                    cache_creation=dict(ephemeral_5m_input_tokens=5, ephemeral_1h_input_tokens=6))))))
        (projects/'fake.jsonl').write_text('\n'.join(rows))
        usd, tokens = c.costs(tmp_path, 999, 1001)
        assert usd > 0
        assert tokens == dict(input=2, output=7, cache_read=3, cache_write_5m=5, cache_write_1h=6)
        assert c.costs(tmp_path, 1000, 1001)[1] == dict.fromkeys(c.KEYS, 0)



    def test_retains_week_anchor_and_resets_on_decrease(self):
        rows = [sample(at=1)]
        for at in range(2, 2000):
            rows = c.retain(rows, sample(at=at))
        self.assertEqual(len(rows), 256)
        self.assertEqual(rows[0]['at'], 1)
        self.assertEqual(c.retain(rows, sample(9, 2000)), [sample(9, 2000)])

    def test_cache_only_never_polls(self):
        with patch.dict(c.os.environ, {'HYBRID_HANDS_CALIBRATION_CACHE_ONLY':'1'}), patch.object(c, 'cached', return_value=c.empty()), patch.object(c, 'command', side_effect=AssertionError):
            self.assertIsNone(c.collect(1000)['usd_per_pct'])

    def test_auth_unavailable_malformed_and_logged_out(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        for auth in ([], {}, dict(loggedIn=False, email='fake@example.test'), dict(loggedIn=True, account=[])):
            with patch.object(c, 'command', return_value=auth):
                self.assertIsNone(c.quota(Path(directory.name), 1100))

    def test_enrichment_keeps_account_measurement(self):
        from hh_ps.models import Usage
        usage = Usage(usd=12, account_week_pct=80)
        session = SimpleNamespace(provider='claude', usage=usage, subagents=[])
        snapshot = SimpleNamespace(sessions=[session], iter_runs=lambda: [])
        with patch.object(c, 'collect', return_value=c.empty() | dict(usd_per_pct=3)):
            c.enrich(snapshot, 1000)
        self.assertEqual(session.usage.week_pct, 4)
        self.assertEqual(session.usage.account_week_pct, 80)
        self.assertTrue(session.usage.week_pct_estimated)

    def test_unavailable_preserves_existing_own_percent(self):
        from hh_ps.models import Usage
        session = SimpleNamespace(provider='claude', usage=Usage(usd=12, week_pct=7, week_pct_source='legacy'), subagents=[])
        snapshot = SimpleNamespace(sessions=[session], iter_runs=lambda: [])
        with patch.object(c, 'collect', return_value=c.empty()):
            c.enrich(snapshot, 1000)
        self.assertEqual(session.usage.week_pct, 7)
        self.assertEqual(session.usage.week_pct_source, 'legacy')

    def test_five_expiry_and_malformed_header_fields(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name)/'state.json'
        header = c.empty() | dict(sampled_at=1000, resets_at=2000, account_source='paseo_claude_account',
            account_5h_pct=20, account_5h_resets_at=1050, tokens={'input':-1}, usd='bad', status=[], precision={})
        path.write_text(json.dumps(dict(header=header, pricing=c.pricing_fingerprint())))
        with patch.object(c, 'cache_path', return_value=path):
            result = c.cached(1100)
        self.assertIsNone(result['account_5h_pct'])
        self.assertIsNone(result['tokens'])
        self.assertIsNone(result['usd'])
        self.assertEqual(result['status'], 'unknown')

    def test_cli_deadlines_are_bounded_by_source(self):
        result = SimpleNamespace(stdout='{}')
        with patch.object(c.subprocess, 'run', return_value=result) as run:
            c.command(['claude', 'auth', 'status', '--json'], Path('/fake'))
            self.assertEqual(run.call_args.kwargs['timeout'], c.AUTH_TIMEOUT)
            c.command(['paseo', 'usage', '--json'], Path('/fake'))
            self.assertEqual(run.call_args.kwargs['timeout'], c.PASEO_TIMEOUT)
        self.assertLessEqual(c.AUTH_TIMEOUT + c.PASEO_TIMEOUT, 10)

    def test_failed_poll_retries_after_short_delay(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        home = Path(directory.name)
        (home/'.claude-hand').mkdir()
        with patch.object(c.Path, 'home', return_value=home), patch.object(c, 'quota', return_value=None) as quota:
            c.collect(1000)
            c.collect(1001)
            self.assertEqual(quota.call_count, 1)
            c.collect(1000 + c.FAILED_POLL + 1)
            self.assertEqual(quota.call_count, 2)

    def test_installed_helper_fallback_scans_only_external_home(self):
        from hh_ps import week
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        external = root/'.claude-hand'
        (external/'projects').mkdir(parents=True)
        helper = root/'installed-statusline'/'scripts'/'usage_ledger.py'
        helper.parent.mkdir(parents=True)
        helper.touch()
        scans = []
        module = SimpleNamespace(refresh_prices=lambda: None,
            window_messages=lambda homes, start, end: scans.append(homes) or {})
        def installed(home):
            return helper if home == root/'.claude' else None
        with patch.dict(c.os.environ, {}, clear=True), patch.object(c.Path, 'home', return_value=root), patch.object(week, '_repo_ledger', return_value=None), patch.object(week, '_installed_ledger', side_effect=installed), patch.object(week, '_ledger_module', return_value=module) as load:
            self.assertEqual(c.costs(external, 10, 20), (0, dict.fromkeys(c.KEYS, 0)))
            self.assertEqual(scans, [[external]])
            self.assertEqual(load.call_args.args[0], str(helper))

    def test_existing_helper_precedes_main_and_invalid_override_fails_closed(self):
        from hh_ps import week
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        external = root/'.claude-hand'
        (external/'projects').mkdir(parents=True)
        helper = root/'external-helper.py'
        helper.touch()
        module = SimpleNamespace(refresh_prices=lambda: None, window_messages=lambda *args: {})
        with patch.dict(c.os.environ, {}, clear=True), patch.object(week, '_repo_ledger', return_value=None), patch.object(week, '_installed_ledger', return_value=helper) as installed, patch.object(week, '_ledger_module', return_value=module):
            self.assertEqual(c.costs(external, 10, 20)[0], 0)
            installed.assert_called_once_with(external)
        with patch.dict(c.os.environ, {week.STATUSLINE_LEDGER_ENV:str(root/'missing.py')}), patch.object(week, '_installed_ledger') as installed, patch.object(week, '_repo_ledger') as repo:
            self.assertEqual(c.costs(external, 10, 20), (None, None))
            installed.assert_not_called()
            repo.assert_not_called()

    def test_helper_import_failure_is_unknown(self):
        from hh_ps import week
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root/'projects').mkdir()
        helper = root/'helper.py'
        helper.touch()
        with patch.object(week, '_locate_usage_ledger', return_value=helper), patch.object(week, '_ledger_module', side_effect=ImportError('fake missing dependency')):
            self.assertEqual(c.costs(root, 10, 20), (None, None))

    def test_quota_fetched_during_request_uses_completion_time(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        clock = [0.0]
        def command(args, home):
            clock[0] += 1
            if args[0] == 'claude':
                return dict(loggedIn=True, email='fake@example.test')
            return [dict(sourceId='claude', account=dict(label='fake@example.test'), fetchedAt=1001.5,
                report=dict(status='available', windows=[dict(id='weekly', usedPct=2, resetsAt=10000)]))]
        with patch.object(c.time, 'monotonic', side_effect=lambda: clock[0]), patch.object(c, 'command', side_effect=command):
            result = c.quota(Path(directory.name), 1000)
            self.assertEqual(result['at'], 1001.5)
        clock[0] = 0
        with patch.object(c.time, 'monotonic', side_effect=lambda: clock[0]), patch.object(c, 'command', side_effect=lambda args, home: dict(loggedIn=True, email='fake@example.test') if args[0]=='claude' else [dict(sourceId='claude', account=dict(label='fake@example.test'), fetchedAt=2000, report=dict(status='available', windows=[dict(id='weekly', usedPct=2, resetsAt=10000)]))]):
            self.assertIsNone(c.quota(Path(directory.name), 1000))

    def test_collect_returns_source_observed_during_request(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root/'.claude-hand').mkdir()
        clock = [0.0]
        def quota(home, now):
            clock[0] = 2
            return sample(2, 1001.5) | dict(source='paseo_claude_account', five=3)
        with patch.object(c.Path, 'home', return_value=root), patch.object(c.time, 'monotonic', side_effect=lambda: clock[0]), patch.object(c, 'quota', side_effect=quota), patch.object(c, 'costs', return_value=(1, dict.fromkeys(c.KEYS, 0))):
            result = c.collect(1000)
        self.assertEqual(result['sampled_at'], 1001.5)
        self.assertEqual(result['account_week_pct'], 2)

    def test_reset_jitter_preserves_observed_anchors(self):
        anchors = [sample(0, 1000, reset=10000), sample(1, 1100, reset=9999)]
        current = sample(2, 1200, reset=9999.8)
        value = c.rate(anchors, current, Path('/fake'), 1200, lambda *args: (8, {}))
        self.assertEqual(value, 4)
        self.assertEqual(current['reset'], 10000)
        retained = c.retain(anchors, current)
        self.assertEqual([s['pct'] for s in retained], [0, 1, 2])
        self.assertTrue(all(s['reset'] == 10000 for s in retained))
        self.assertIsNone(c.rate(anchors, sample(4, 1300, reset=20000), Path('/fake'), 1300, lambda *args: (8, {})))

    def test_expired_success_cache_polls_before_interval(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root/'.claude-hand').mkdir()
        path = root/'.hybrid-hands'/'claude-calibration.json'
        header = c.empty() | dict(sampled_at=700, resets_at=10000, account_source='paseo_claude_account')
        c.write(path, dict(pricing=c.pricing_fingerprint(), polled_at=990, header=header, samples=[]))
        with patch.object(c.Path, 'home', return_value=root), patch.object(c, 'quota', return_value=None) as quota:
            c.collect(1001)
            c.collect(1002)
            self.assertEqual(quota.call_count, 1)

    def test_tree_calibration_clock_after_scan_and_explicit_time(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent/'fixtures'/'hh_ps'))
        from fixture import HhFixture, NOW
        from hh_ps.tree import build_snapshot
        fx = HhFixture()
        self.addCleanup(fx.close)
        with fx.env(), patch('hh_ps.tree.time.time', side_effect=[NOW, NOW+4]), patch.object(c, 'enrich') as enrich:
            snapshot = build_snapshot(fx.project, 3600, False)
            self.assertEqual(snapshot.generated_at, NOW)
            self.assertEqual(enrich.call_args.args[1], NOW+4)
        with fx.env(), patch('hh_ps.tree.time.time', side_effect=AssertionError('explicit time must stay deterministic')), patch.object(c, 'enrich') as enrich:
            build_snapshot(fx.project, 3600, False, now=NOW)
            self.assertEqual(enrich.call_args.args[1], NOW)

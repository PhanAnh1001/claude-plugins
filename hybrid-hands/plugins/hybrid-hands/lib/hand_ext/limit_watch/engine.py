"""State transitions with injected observations and transports for hermetic tests."""
from __future__ import annotations

import math
import uuid

FRESH_SECONDS = 1800
RESET_BUFFER = 120
TERMINAL = {'resumed', 'done', 'cancelled'}


def number(value):
    return (float(value) if isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) else None)


def fresh(window, now):
    at, reset, pct = [number(window.get(k)) for k in ('observed_at', 'reset_at', 'used_pct')]
    return (at is not None and 0 <= now - at < FRESH_SECONDS and reset is not None
            and reset > now and pct is not None and 0 <= pct <= 100)


def blocking(window):
    pct = number(window.get('used_pct'))
    return window.get('blocked') is True or (pct is not None and pct >= 100)


def record_block(target, at, windows):
    target.update(state='blocked', blocked_at=at,
                  blocking_windows={w['id']: dict(w) for w in windows if blocking(w)},
                  attempts=0, expected_reset_tried=False, retry_suspended=False)


def eligibility(target, sample, now):
    windows = sample.get('windows', [])
    saved = target['blocking_windows']
    # Keep every blocking reset even if a later cache loses a window.
    for window in windows:
        if blocking(window):
            old = saved.get(window['id'])
            if old is None or (number(window.get('observed_at')) or 0) > (number(old.get('observed_at')) or 0):
                saved[window['id']] = dict(window)
    current = {w['id']: w for w in windows}
    if (not target.get('retry_suspended') and sample.get('complete') is True and windows
            and all(fresh(w, now) and not blocking(w)
                    and w['observed_at'] > target['blocked_at'] for w in windows)
            and all(key in current and current[key]['observed_at'] > target['blocked_at']
                    for key in saved)):
        return 'fresh'
    # Fresh explicit blocking or non-window server restrictions must never be
    # bypassed by a reset prediction. Unknown/new windows also stop the fallback.
    if (target.get('retry_suspended') or sample.get('server_blocked') or any(fresh(w, now) and blocking(w) for w in windows)
            or target['provider'] != 'claude' or target.get('expected_reset_tried')
            or not saved or any(w['id'] not in saved and blocking(w) for w in windows)):
        return None
    resets = [number(w.get('reset_at')) for w in saved.values()]
    if any(r is None for r in resets):
        return None
    # A daemon may accept a prompt that subsequently hits quota again. Persistent
    # mode must not turn that new error into another prediction for the SAME reset.
    if (number(target.get('expected_reset_epoch')) or 0) >= max(resets):
        return None
    if now >= max(resets) + RESET_BUFFER:
        return 'reset dự kiến'
    return None


def work_finished(target: dict, live: dict) -> bool:
    """Separate work lifetime from the provider's per-turn attention status.

    Paseo brains remain registered across idle/finished turns. Only confirmed
    closure/identity loss or an explicit pending-work withdrawal ends them.
    A failed observation is not proof of closure and is handled before this
    predicate. Side completion markers retain their existing meaning.
    Pending dispatches are reconciled before evaluating work completion.
    """
    if live.get('closed'):
        return True
    if target.get('work_pending') is not True:
        return True
    if target['adapter'] == 'side':
        return bool(live.get('done'))
    return False


def tick(store, runtime, quotas, sender, guard, now):
    """One finite tick. Save dispatch_pending *before* calling a sender.

    The lock includes network IO and sending: off cannot invalidate a generation
    between its final check and dispatch. A crash leaves a durable reservation.
    Unknown receipt never retries automatically; there is no exactly-once claim.
    """
    with store.locked():
        state = store.read()
        if not state['enabled']:
            return
        for target in state['targets'].values():
            if target['state'] in TERMINAL:
                continue
            try:
                live = runtime(target)
                if not live.get('valid'):
                    target['reason'] = 'identity_or_runtime_unconfirmed'
                    continue
                # An unknown send cannot be reconciled from a generic running
                # flag. Only a matching dispatch receipt may settle it.
                if target['state'] == 'dispatch_pending':
                    if live.get('dispatch_ack') == target.get('dispatch_id'):
                        _resumed(target, state, now)
                    continue
                if work_finished(target, live):
                    target.update(state='done', reason='work_finished')
                    continue
                block_at = number(live.get('blocked_at'))
                if target['state'] == 'armed':
                    after = max(target.get('armed_after', 0), target.get('last_block_at', 0))
                    if block_at is None or not after < block_at <= now:
                        continue
                    sample = quotas(target, now)
                    record_block(target, block_at, sample.get('windows', []))
                    target['last_block_at'] = block_at
                if target['state'] not in ('blocked', 'eligible') or not live.get('idle'):
                    continue
                sample = quotas(target, now)
                label = eligibility(target, sample, now)
                if not label:
                    target['reason'] = 'waiting_for_quota_observation'
                    continue
                target.update(state='eligible', reason=label)
                if not guard(target, now):
                    target['reason'] = 'day_guard_blocked_or_unknown'
                    continue
                target.update(state='dispatch_pending', dispatch_id=uuid.uuid4().hex,
                              dispatch_at=now, dispatch_generation=state['generation'],
                              attempts=target.get('attempts', 0) + 1)
                if label == 'reset dự kiến':
                    target['expected_reset_tried'] = True
                    target['expected_reset_epoch'] = max(w['reset_at'] for w in target['blocking_windows'].values())
                store.save(state)
                prompt = ('làm tiếp\nCheckpoint: ' + target['checkpoint']
                          + '\nBước kế tiếp: ' + target['next_step']
                          + '\nChỉ tiếp tục việc còn dở trong phạm vi đã duyệt.'
                          + ('\nHạn mức: reset dự kiến; chỉ thử lần này.' if label != 'fresh' else ''))
                # Re-check idle, exact identity and pending permissions inside the
                # transport immediately before sending, too.
                receipt = sender(target, prompt)
                if receipt == 'accepted':
                    _resumed(target, state, now)
                elif receipt == 'quota_rejected':
                    # The prediction has been consumed. A fresh NEW blocking event
                    # or explicit re-registration is needed; never hammer a quota.
                    target.update(state='blocked', reason='quota_rejected',
                                  retry_suspended=True)
                else:
                    target['reason'] = 'send_ack_unknown'
            except Exception:
                # Do not expose subprocess output, prompts, identities or secrets.
                target['reason'] = 'observation_or_transport_unavailable'
        state['last_tick_at'] = now
        if (state['targets'] and not state['persistent']
                and all(t['state'] in TERMINAL for t in state['targets'].values())):
            state['enabled'] = False
        store.save(state)


def _resumed(target, state, now):
    target.update(state='resumed', resumed_at=now, reason='accepted_receipt')
    if state['persistent'] or target['adapter'] == 'paseo':
        target.update(state='armed', armed_after=now, last_block_at=target.get('blocked_at', 0))

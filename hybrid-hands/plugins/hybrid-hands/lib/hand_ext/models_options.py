"""Read-only model choices for the three-tier picker."""
from __future__ import annotations

from account_label import PROVIDER_CLAUDE, account_label
from usage_pricing import load_prices
from .constants import MODEL_CAPABILITIES, PROVIDER_EFFORTS

TIER_LABELS = {"brain": "Brain chính", "side": "Phiên phụ", "hand": "Hand"}
CLAUDE_MODEL_ORDER = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5")


def build_options(result, status: dict) -> dict:
    prices = load_prices()
    providers = {}
    for provider, models in MODEL_CAPABILITIES.items():
        ordered = CLAUDE_MODEL_ORDER if provider == "claude" else sorted(models)
        providers[provider] = {
            "models": [model for model in ordered if model in models and model in prices],
            "efforts": list(PROVIDER_EFFORTS[provider]),
        }
    profiles, tiers = {}, []
    for tier in ("brain", "side"):
        profile = status[tier]
        provider = profile["provider"]["value"]
        model = profile[provider + "_model"]["value"]
        effort = profile[provider + "_effort"]["value"]
        account = profile["claude_account"]["value"]
        profiles[tier] = dict(provider=provider, model=model, effort=effort, account=account)
        current = f"{provider}:{model}:{effort}"
        if provider == "claude":
            current += "@" + account
        tiers.append(dict(value=tier, label=TIER_LABELS[tier], current=current))
    order = status["hand"]["order"]["value"]
    tiers.append(dict(value="hand", label=TIER_LABELS["hand"], current=", ".join(order)))
    ext = result.effective["ext_hand"]
    accounts = [dict(slot=slot, label=account_label(PROVIDER_CLAUDE, slot, ext),
                     selected=slot == profiles["brain"]["account"])
                for slot in sorted(ext["claude_accounts"], key=lambda s: int(s[1:]))]
    backends = [dict(value=name, provider="claude" if row.get("account") else name,
                     model=row["model"]["value"], effort=row["effort"]["value"],
                     account=row.get("account"), in_order=name in order)
                for name, row in status["hand"]["backends"].items() if row["supported"]]
    return dict(tiers=tiers, providers=providers, profiles=profiles,
                accounts=accounts, hand_backends=backends)


def print_options(payload: dict) -> None:
    for tier in payload["tiers"]:
        print(f"{tier['label']}: {tier['current']}")
    for provider, row in payload["providers"].items():
        print(f"{provider}: {', '.join(row['models'])}; effort: {', '.join(row['efforts'])}")
    for row in payload["accounts"]:
        print(f"{'*' if row['selected'] else ' '} {row['slot']}: {row['label']}")
    for row in payload["hand_backends"]:
        print(f"{'*' if row['in_order'] else ' '} {row['value']}: {row['model']}:{row['effort']}")

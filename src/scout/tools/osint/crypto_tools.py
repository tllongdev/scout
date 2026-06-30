"""Crypto wallet tracing for Bitcoin and Ethereum addresses.

Looks up balance and transaction activity for a wallet using free public block
explorers - Blockstream (BTC) and Blockscout (ETH) - no API key required. The
address type is auto-detected. Useful for following a financial trail in an
investigation; pair with sanctions_screen to flag OFAC-listed wallets.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from ...llm import Tool
from ...models import Entity
from ..registry import BuildContext, ToolSpec

_TIMEOUT = 25.0
_ETH = re.compile(r"^0x[0-9a-fA-F]{40}$")
_BTC = re.compile(r"^(bc1[a-z0-9]{8,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,39})$")


def _trace_btc(addr: str) -> dict[str, Any]:
    resp = httpx.get(f"https://blockstream.info/api/address/{addr}", timeout=_TIMEOUT)
    resp.raise_for_status()
    d = resp.json()
    chain = d.get("chain_stats", {})
    funded = chain.get("funded_txo_sum", 0)
    spent = chain.get("spent_txo_sum", 0)
    return {
        "chain": "bitcoin",
        "address": addr,
        "balance_btc": round((funded - spent) / 1e8, 8),
        "total_received_btc": round(funded / 1e8, 8),
        "tx_count": chain.get("tx_count", 0),
        "explorer": f"https://blockstream.info/address/{addr}",
    }


def _trace_eth(addr: str) -> dict[str, Any]:
    resp = httpx.get(
        f"https://eth.blockscout.com/api/v2/addresses/{addr}", timeout=_TIMEOUT
    )
    resp.raise_for_status()
    d = resp.json()
    wei = int(d.get("coin_balance") or 0)
    return {
        "chain": "ethereum",
        "address": addr,
        "balance_eth": round(wei / 1e18, 8),
        "is_contract": d.get("is_contract", False),
        "tx_count": d.get("transactions_count") or d.get("transaction_count"),
        "explorer": f"https://eth.blockscout.com/address/{addr}",
    }


def _crypto(ctx: BuildContext) -> list[Tool]:
    mission = ctx.mission

    def _handle(args: dict[str, Any]) -> str:
        addr = str(args.get("address", "")).strip()
        if not addr:
            return "Error: 'address' is required."
        try:
            if _ETH.match(addr):
                data = _trace_eth(addr)
            elif _BTC.match(addr):
                data = _trace_btc(addr)
            else:
                return f"Unrecognized address format: {addr} (expected BTC or ETH)."
        except Exception as exc:  # noqa: BLE001
            return f"Wallet lookup failed: {exc}"
        mission.upsert_entity(
            Entity(
                name=addr,
                type="crypto_wallet",
                attributes={"chain": data["chain"], "tx_count": str(data.get("tx_count"))},
                sources=[data["explorer"]],
            )
        )
        return json.dumps(data, indent=2)

    return [
        Tool(
            name="crypto_wallet_trace",
            description=(
                "Look up a Bitcoin or Ethereum wallet address (auto-detected): "
                "current balance, total received, and transaction count, with a "
                "block-explorer link. Records the wallet as an entity. For "
                "financial-trail investigations; cross-check hits with "
                "sanctions_screen for OFAC exposure."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "BTC or ETH wallet address."}
                },
                "required": ["address"],
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="crypto_wallet",
        name="Crypto Wallet Trace",
        category="crypto",
        summary="BTC/ETH wallet balance and activity via public explorers.",
        builder=_crypto,
        keyless=True,
        docs="https://blockstream.info/api · https://eth.blockscout.com",
        keywords=("bitcoin", "btc", "ethereum", "eth", "wallet", "crypto",
                  "blockchain", "wallet address", "cryptocurrency", "on-chain"),
    ),
]

#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN, getcontext
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

import requests
from textual import on, work
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.timer import Timer
from textual.widgets import Button, Footer, Header, Input, Label, RadioButton, RadioSet, Static

getcontext().prec = 28

BTC = "BTC"
LTC = "LTC"
DOGE = "DOGE"
DASH = "DASH"
ETH = "ETH"
BSC = "BSC"
POLYGON = "POLYGON"
BCH = "BCH"
REPOSITORY_URL = "https://github.com/zvspany/checkaddy"
BLOCKSTREAM_BASE = "https://blockstream.info/api"
BLOCKCYPHER_BASE = "https://api.blockcypher.com/v1"
FULLSTACK_BCH_BASE = "https://api.fullstack.cash/v5/electrumx"
ETH_RPC_URLS = (
    "https://ethereum-rpc.publicnode.com",
    "https://eth.llamarpc.com",
    "https://rpc.flashbots.net",
    "https://cloudflare-eth.com",
)
BSC_RPC_URLS = (
    "https://bsc-dataseed.binance.org",
    "https://bsc-rpc.publicnode.com",
)
POLYGON_RPC_URLS = (
    "https://polygon-bor-rpc.publicnode.com",
    "https://polygon-rpc.com",
)
TRANSIENT_HTTP_STATUSES = {429, 500, 502, 503, 504}
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58_INDEX = {c: i for i, c in enumerate(BASE58_ALPHABET)}
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
BECH32_CHARSET_MAP = {c: i for i, c in enumerate(BECH32_CHARSET)}
ADDRESS_SAFE_RE = re.compile(r"^[A-Za-z0-9:]+$")
EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
BCH_CASHADDR_RE = re.compile(r"^[qpzry9x8gf2tvdw0s3jn54khce6mua7l]+$")

COIN_OPTIONS: list[tuple[str, str]] = [
    (BTC, "Bitcoin (BTC)"),
    (LTC, "Litecoin (LTC)"),
    (DOGE, "Dogecoin (DOGE)"),
    (DASH, "Dash (DASH)"),
    (ETH, "Ethereum (ETH)"),
    (BSC, "BNB Chain (BSC)"),
    (POLYGON, "Polygon PoS (MATIC)"),
    (BCH, "Bitcoin Cash (BCH)"),
]
COIN_RADIO_IDS = {coin: f"coin-{coin.lower()}" for coin, _ in COIN_OPTIONS}
COIN_FROM_RADIO_ID = {radio_id: coin for coin, radio_id in COIN_RADIO_IDS.items()}

COIN_DECIMALS = {
    BTC: 8,
    LTC: 8,
    DOGE: 8,
    DASH: 8,
    BCH: 8,
    ETH: 18,
    BSC: 18,
    POLYGON: 18,
}
COIN_UNIT_LABEL = {
    BTC: "satoshis",
    LTC: "litoshis",
    DOGE: "koinu",
    DASH: "duffs",
    BCH: "satoshis",
    ETH: "wei",
    BSC: "wei",
    POLYGON: "wei",
}
COIN_DISPLAY_SYMBOL = {
    BTC: "BTC",
    LTC: "LTC",
    DOGE: "DOGE",
    DASH: "DASH",
    BCH: "BCH",
    ETH: "ETH",
    BSC: "BNB",
    POLYGON: "MATIC",
}
BLOCKCYPHER_NETWORKS = {
    LTC: "ltc",
    DOGE: "doge",
    DASH: "dash",
}
EVM_RPC_BY_COIN = {
    ETH: ETH_RPC_URLS,
    BSC: BSC_RPC_URLS,
    POLYGON: POLYGON_RPC_URLS,
}
EXPLORER_URL_BY_COIN = {
    BTC: "https://blockstream.info/address/{address}",
    LTC: "https://live.blockcypher.com/ltc/address/{address}/",
    DOGE: "https://live.blockcypher.com/doge/address/{address}/",
    DASH: "https://live.blockcypher.com/dash/address/{address}/",
    BCH: "https://blockchair.com/bitcoin-cash/address/{address}",
    ETH: "https://etherscan.io/address/{address}",
    BSC: "https://bscscan.com/address/{address}",
    POLYGON: "https://polygonscan.com/address/{address}",
}
DATA_SOURCE_BY_COIN = {
    BTC: "blockstream.info",
    LTC: "api.blockcypher.com",
    DOGE: "api.blockcypher.com",
    DASH: "api.blockcypher.com",
    BCH: "api.fullstack.cash",
    ETH: "public RPC fallback",
    BSC: "public RPC fallback",
    POLYGON: "public RPC fallback",
}

APP_CSS = """
Screen {
    background: #090f1f;
    color: #e2e8f0;
}

Header {
    background: #0f172a;
    color: #f8fafc;
}

Footer {
    background: #0f172a;
    color: #cbd5e1;
}

#app {
    height: 1fr;
    padding: 1 2;
}

#hero {
    height: auto;
    margin-bottom: 1;
    padding: 1 2;
    background: #0f172a;
    border: round #334155;
}

#hero-title {
    color: #f8fafc;
    text-style: bold;
}

#hero-subtitle {
    color: #94a3b8;
}

#hero-credit {
    color: #60a5fa;
    margin-top: 1;
}

#layout {
    height: 1fr;
}

#sidebar {
    width: 42;
    min-width: 42;
    max-width: 42;
    margin-right: 1;
}

#main {
    height: 1fr;
}

.panel {
    background: #0f172a;
    border: round #334155;
    padding: 1 2;
    margin-bottom: 1;
    height: auto;
}

.panel-title {
    color: #f8fafc;
    text-style: bold;
    margin-bottom: 1;
}

.subtle {
    color: #94a3b8;
}

Input {
    margin-top: 1;
    background: #0b1220;
    border: round #475569;
    color: #e2e8f0;
}

Input:focus {
    border: round #60a5fa;
}

RadioSet {
    margin-top: 1;
}

#controls Button {
    width: 1fr;
    margin-top: 1;
}

#quick-validation {
    margin-top: 1;
    color: #94a3b8;
}

#status-body.ok {
    color: #4ade80;
}

#status-body.warn {
    color: #fbbf24;
}

#status-body.error {
    color: #f87171;
}

#status-body.info {
    color: #93c5fd;
}

#metrics {
    layout: grid;
    grid-size: 2 3;
    grid-columns: 1fr 1fr;
    grid-gutter: 1 1;
    height: auto;
}

.metric-card {
    min-height: 8;
    padding: 1 2;
    background: #0b1220;
    border: round #253247;
}

.metric-label {
    color: #94a3b8;
}

.metric-value {
    color: #f8fafc;
    text-style: bold;
    margin-top: 1;
}

#details-grid {
    height: auto;
}

.detail-row {
    margin-bottom: 1;
}

.detail-key {
    color: #94a3b8;
}

.detail-value {
    color: #e2e8f0;
}

#json-panel {
    height: auto;
    min-height: 18;
}

#json-box {
    height: auto;
    min-height: 14;
    background: #0b1220;
    border: round #253247;
    padding: 1;
}

.hidden {
    display: none;
}

#help-dialog {
    width: 76;
    height: auto;
    background: #0f172a;
    border: round #60a5fa;
    padding: 1 2;
}

#help-title {
    color: #f8fafc;
    text-style: bold;
    margin-bottom: 1;
}

#help-body {
    color: #cbd5e1;
    margin-bottom: 1;
}

#github-dialog {
    width: 72;
    height: auto;
    background: #0f172a;
    border: round #60a5fa;
    padding: 1 2;
}

#github-title {
    color: #f8fafc;
    text-style: bold;
    margin-bottom: 1;
}

#github-body {
    color: #cbd5e1;
    margin-bottom: 1;
}

#github-url {
    color: #93c5fd;
    margin-bottom: 1;
}

#github-buttons Button {
    width: 1fr;
}
"""


@dataclass(slots=True)
class LookupResult:
    coin: str
    address: str
    is_valid_format: bool
    validation_reason: str
    confirmed_balance: Optional[str]
    unconfirmed_balance: Optional[str]
    total_received: Optional[str]
    total_sent: Optional[str]
    tx_count: Optional[int]
    explorer_url: str
    data_source: str
    fetched_at_utc: str
    api_error: Optional[str]
    api_skipped: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "coin": self.coin,
            "address": self.address,
            "is_valid_format": self.is_valid_format,
            "validation_reason": self.validation_reason,
            "confirmed_balance": self.confirmed_balance,
            "unconfirmed_balance": self.unconfirmed_balance,
            "total_received": self.total_received,
            "total_sent": self.total_sent,
            "tx_count": self.tx_count,
            "explorer_url": self.explorer_url,
            "data_source": self.data_source,
            "fetched_at_utc": self.fetched_at_utc,
            "api_error": self.api_error,
            "api_skipped": self.api_skipped,
        }


class ApiClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "checkaddy/1.0"})

    def close(self) -> None:
        self.session.close()

    @staticmethod
    def rpc_host(url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc or url

    @staticmethod
    def format_rpc_error(error: Any) -> str:
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message")
            if code is not None and message is not None:
                return f"{code}: {message}"
            if message is not None:
                return str(message)
        return str(error)

    @staticmethod
    def extract_error_message(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text.strip() or f"HTTP {response.status_code}"

        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, dict):
                error_message = data.get("error_message")
                if isinstance(error_message, str) and error_message.strip():
                    return error_message

            for key in ("error", "message", "detail"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value

        return f"HTTP {response.status_code}"

    def request_json(self, url: str, max_retries: int = 3) -> dict[str, Any]:
        backoffs = [0.4, 0.8, 1.6]
        for attempt in range(max_retries + 1):
            try:
                response = self.session.get(url, timeout=(3, 12))
            except requests.RequestException as exc:
                if attempt < max_retries:
                    time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                    continue
                raise RuntimeError(f"Network error: {exc}") from exc

            if response.status_code in TRANSIENT_HTTP_STATUSES:
                if attempt < max_retries:
                    time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                    continue
                raise RuntimeError(f"HTTP {response.status_code} from API")

            if not response.ok:
                message = self.extract_error_message(response)
                raise RuntimeError(f"HTTP {response.status_code} from API: {message}")

            try:
                return response.json()
            except ValueError as exc:
                raise RuntimeError("Invalid JSON response from API") from exc

        raise RuntimeError("Request failed after retries")

    def request_json_post(self, url: str, payload: dict[str, Any], max_retries: int = 3) -> dict[str, Any]:
        backoffs = [0.4, 0.8, 1.6]
        for attempt in range(max_retries + 1):
            try:
                response = self.session.post(url, json=payload, timeout=(3, 12))
            except requests.RequestException as exc:
                if attempt < max_retries:
                    time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                    continue
                raise RuntimeError(f"Network error: {exc}") from exc

            if response.status_code in TRANSIENT_HTTP_STATUSES:
                if attempt < max_retries:
                    time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                    continue
                raise RuntimeError(f"HTTP {response.status_code} from API")

            if not response.ok:
                message = self.extract_error_message(response)
                raise RuntimeError(f"HTTP {response.status_code} from API: {message}")

            try:
                return response.json()
            except ValueError as exc:
                raise RuntimeError("Invalid JSON response from API") from exc

        raise RuntimeError("Request failed after retries")

    def fetch_btc_info(self, address: str) -> dict[str, Any]:
        payload = self.request_json(f"{BLOCKSTREAM_BASE}/address/{address}")
        chain = payload.get("chain_stats", {})
        mempool = payload.get("mempool_stats", {})

        funded = int(chain.get("funded_txo_sum", 0))
        spent = int(chain.get("spent_txo_sum", 0))
        tx_count = int(chain.get("tx_count", 0))
        mem_funded = int(mempool.get("funded_txo_sum", 0))
        mem_spent = int(mempool.get("spent_txo_sum", 0))

        return {
            "confirmed_balance": sats_to_coin_str(funded - spent),
            "unconfirmed_balance": sats_to_coin_str(mem_funded - mem_spent),
            "total_received": sats_to_coin_str(funded),
            "total_sent": sats_to_coin_str(spent),
            "tx_count": tx_count,
        }

    def fetch_blockcypher_utxo_info(self, coin: str, address: str) -> dict[str, Any]:
        network = BLOCKCYPHER_NETWORKS[coin]
        payload = self.request_json(f"{BLOCKCYPHER_BASE}/{network}/main/addrs/{address}/balance")

        confirmed_units = parse_optional_int(payload.get("balance"))
        unconfirmed_units = parse_optional_int(payload.get("unconfirmed_balance"))
        total_received_units = parse_optional_int(payload.get("total_received"))
        total_sent_units = parse_optional_int(payload.get("total_sent"))
        tx_count = parse_optional_int(payload.get("n_tx"))

        if confirmed_units is None:
            raise RuntimeError("Missing confirmed balance in response")

        return {
            "confirmed_balance": units_to_coin_str(confirmed_units, COIN_DECIMALS[coin]),
            "unconfirmed_balance": units_to_coin_str(unconfirmed_units, COIN_DECIMALS[coin]) if unconfirmed_units is not None else None,
            "total_received": units_to_coin_str(total_received_units, COIN_DECIMALS[coin]) if total_received_units is not None else None,
            "total_sent": units_to_coin_str(total_sent_units, COIN_DECIMALS[coin]) if total_sent_units is not None else None,
            "tx_count": tx_count,
        }

    def fetch_bch_info(self, address: str) -> dict[str, Any]:
        payload = self.request_json(f"{FULLSTACK_BCH_BASE}/balance/{address}")
        if payload.get("success") is not True:
            raise RuntimeError("API returned a non-success status")

        balance = payload.get("balance", {})
        confirmed_units = parse_optional_int(balance.get("confirmed"))
        unconfirmed_units = parse_optional_int(balance.get("unconfirmed"))

        if confirmed_units is None:
            raise RuntimeError("Missing confirmed balance in response")

        tx_count: Optional[int] = None
        try:
            tx_payload = self.request_json(f"{FULLSTACK_BCH_BASE}/transactions/{address}")
            if tx_payload.get("success") is True:
                transactions = tx_payload.get("transactions")
                if isinstance(transactions, list):
                    tx_count = len(transactions)
        except RuntimeError:
            pass

        return {
            "confirmed_balance": units_to_coin_str(confirmed_units, COIN_DECIMALS[BCH]),
            "unconfirmed_balance": units_to_coin_str(unconfirmed_units, COIN_DECIMALS[BCH]) if unconfirmed_units is not None else None,
            "total_received": None,
            "total_sent": None,
            "tx_count": tx_count,
        }

    def fetch_evm_info(self, coin: str, address: str) -> dict[str, Any]:
        errors: list[str] = []
        for rpc_url in EVM_RPC_BY_COIN[coin]:
            balance_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_getBalance",
                "params": [address, "latest"],
            }
            tx_count_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "eth_getTransactionCount",
                "params": [address, "latest"],
            }

            try:
                balance_response = self.request_json_post(rpc_url, balance_payload)
                tx_count_response = self.request_json_post(rpc_url, tx_count_payload)
                if "error" in balance_response:
                    raise RuntimeError(
                        f"RPC eth_getBalance error: {self.format_rpc_error(balance_response['error'])}"
                    )
                if "error" in tx_count_response:
                    raise RuntimeError(
                        f"RPC eth_getTransactionCount error: {self.format_rpc_error(tx_count_response['error'])}"
                    )
                balance_hex = balance_response.get("result")
                tx_count_hex = tx_count_response.get("result")

                if not isinstance(balance_hex, str) or not balance_hex.startswith("0x"):
                    raise RuntimeError("Missing eth_getBalance result")
                if not isinstance(tx_count_hex, str) or not tx_count_hex.startswith("0x"):
                    raise RuntimeError("Missing eth_getTransactionCount result")

                try:
                    balance_units = int(balance_hex, 16)
                    tx_count = int(tx_count_hex, 16)
                except ValueError as exc:
                    raise RuntimeError("Invalid hex value in RPC response") from exc

                return {
                    "confirmed_balance": units_to_coin_str(balance_units, COIN_DECIMALS[coin]),
                    "unconfirmed_balance": None,
                    "total_received": None,
                    "total_sent": None,
                    "tx_count": tx_count,
                    "data_source": self.rpc_host(rpc_url),
                }
            except RuntimeError as exc:
                errors.append(f"{self.rpc_host(rpc_url)}: {exc}")
                continue

        short_errors = "; ".join(errors[:2])
        if len(errors) > 2:
            short_errors += f"; +{len(errors) - 2} more"
        raise RuntimeError(f"All RPC endpoints failed: {short_errors}")

    def fetch_coin_info(self, coin: str, address: str) -> dict[str, Any]:
        if coin == BTC:
            return self.fetch_btc_info(address)
        if coin in BLOCKCYPHER_NETWORKS:
            return self.fetch_blockcypher_utxo_info(coin, address)
        if coin == BCH:
            return self.fetch_bch_info(address)
        if coin in EVM_RPC_BY_COIN:
            return self.fetch_evm_info(coin, address)
        raise RuntimeError(f"Unsupported coin: {coin}")


def quant_for_decimals(decimals: int) -> Decimal:
    return Decimal(1).scaleb(-decimals)


def parse_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, list):
        return len(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def decimal_coin_str(value: Any, decimals: int = 8) -> str:
    return format(Decimal(str(value)).quantize(quant_for_decimals(decimals)), "f")


def units_to_coin_str(units: int, decimals: int) -> str:
    scale = Decimal(10) ** decimals
    return format((Decimal(units) / scale).quantize(quant_for_decimals(decimals)), "f")


def sats_to_coin_str(units: int) -> str:
    return units_to_coin_str(units, 8)


def coin_str_to_units(amount_str: str, decimals: int) -> int:
    amount = Decimal(amount_str).quantize(quant_for_decimals(decimals))
    scale = Decimal(10) ** decimals
    return int((amount * scale).to_integral_value(rounding=ROUND_DOWN))


def format_amount_display(coin: str, amount_str: Optional[str]) -> str:
    if amount_str is None:
        return "N/A"
    decimals = COIN_DECIMALS[coin]
    units = coin_str_to_units(amount_str, decimals)
    unit_label = COIN_UNIT_LABEL[coin]
    display_symbol = COIN_DISPLAY_SYMBOL[coin]
    return f"{amount_str} {display_symbol} ({units} {unit_label})"


def format_validation_badge(valid: bool, reason: str) -> str:
    state = "valid" if valid else "invalid"
    return f"{state} ({reason})"


def base58_decode(value: str) -> Optional[bytes]:
    number = 0
    for char in value:
        digit = BASE58_INDEX.get(char)
        if digit is None:
            return None
        number = number * 58 + digit

    raw = b"" if number == 0 else number.to_bytes((number.bit_length() + 7) // 8, "big")
    pad = len(value) - len(value.lstrip("1"))
    return b"\x00" * pad + raw


def base58check_verify(address: str) -> tuple[bool, str, Optional[int], Optional[int]]:
    decoded = base58_decode(address)
    if decoded is None:
        return False, "Invalid Base58 characters", None, None
    if len(decoded) < 4:
        return False, "Too short for Base58Check", None, None

    payload, checksum = decoded[:-4], decoded[-4:]
    digest = hashlib.sha256(hashlib.sha256(payload).digest()).digest()
    if checksum != digest[:4]:
        return False, "Base58Check checksum mismatch", None, None
    if not payload:
        return False, "Missing version byte", None, None

    return True, "Valid Base58Check", payload[0], len(payload)


def bech32_polymod(values: list[int]) -> int:
    generator = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    checksum = 1
    for value in values:
        top = checksum >> 25
        checksum = ((checksum & 0x1FFFFFF) << 5) ^ value
        for index in range(5):
            if (top >> index) & 1:
                checksum ^= generator[index]
    return checksum


def bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(char) >> 5 for char in hrp] + [0] + [ord(char) & 31 for char in hrp]


def bech32_verify_checksum(hrp: str, data: list[int], spec: str) -> bool:
    expected = 1 if spec == "bech32" else 0x2BC830A3
    return bech32_polymod(bech32_hrp_expand(hrp) + data) == expected


def bech32_decode(address: str) -> tuple[Optional[str], Optional[list[int]], Optional[str]]:
    if address.lower() != address and address.upper() != address:
        return None, None, None

    normalized = address.lower()
    separator_index = normalized.rfind("1")
    if separator_index < 1 or separator_index + 7 > len(normalized):
        return None, None, None

    hrp = normalized[:separator_index]
    data: list[int] = []
    for char in normalized[separator_index + 1 :]:
        mapped = BECH32_CHARSET_MAP.get(char)
        if mapped is None:
            return None, None, None
        data.append(mapped)

    if bech32_verify_checksum(hrp, data, "bech32"):
        return hrp, data[:-6], "bech32"
    if bech32_verify_checksum(hrp, data, "bech32m"):
        return hrp, data[:-6], "bech32m"
    return None, None, None


def validate_btc_address(address: str) -> tuple[bool, str]:
    address = address.strip()
    if address.lower().startswith("bc1"):
        hrp, data, spec = bech32_decode(address)
        if hrp is None:
            return False, "Invalid Bech32 or Bech32m checksum"
        if hrp != "bc":
            return False, "Invalid HRP for BTC"
        if not data:
            return False, "Missing witness program"
        return True, f"Valid {spec} address"

    if not (address.startswith("1") or address.startswith("3")):
        return False, "BTC Base58 addresses must start with 1 or 3"

    valid, reason, version, payload_len = base58check_verify(address)
    if not valid:
        return False, reason
    if payload_len != 21:
        return False, "Unexpected Base58 payload length"
    if version not in (0x00, 0x05):
        return False, "Invalid BTC version byte"
    return True, "Valid Base58Check address"


def validate_ltc_address(address: str) -> tuple[bool, str]:
    address = address.strip()
    if address.lower().startswith("ltc1"):
        hrp, data, spec = bech32_decode(address)
        if hrp is None:
            return False, "Invalid Bech32 or Bech32m checksum"
        if hrp != "ltc":
            return False, "Invalid HRP for LTC"
        if not data:
            return False, "Missing witness program"
        return True, f"Valid {spec} address"

    if not (address.startswith("L") or address.startswith("M") or address.startswith("3")):
        return False, "LTC Base58 addresses must start with L, M, or 3"

    valid, reason, version, payload_len = base58check_verify(address)
    if not valid:
        return False, reason
    if payload_len != 21:
        return False, "Unexpected Base58 payload length"
    if version not in (0x30, 0x32, 0x05):
        return False, "Invalid LTC version byte"
    return True, "Valid Base58Check address"


def validate_doge_address(address: str) -> tuple[bool, str]:
    address = address.strip()
    if not (address.startswith("D") or address.startswith("A") or address.startswith("9")):
        return False, "DOGE Base58 addresses must start with D, A, or 9"

    valid, reason, version, payload_len = base58check_verify(address)
    if not valid:
        return False, reason
    if payload_len != 21:
        return False, "Unexpected Base58 payload length"
    if version not in (0x1E, 0x16):
        return False, "Invalid DOGE version byte"
    return True, "Valid Base58Check address"


def validate_dash_address(address: str) -> tuple[bool, str]:
    address = address.strip()
    if not (address.startswith("X") or address.startswith("7")):
        return False, "DASH Base58 addresses must start with X or 7"

    valid, reason, version, payload_len = base58check_verify(address)
    if not valid:
        return False, reason
    if payload_len != 21:
        return False, "Unexpected Base58 payload length"
    if version not in (0x4C, 0x10):
        return False, "Invalid DASH version byte"
    return True, "Valid Base58Check address"


def validate_bch_address(address: str) -> tuple[bool, str]:
    address = address.strip()
    lower = address.lower()
    if lower.startswith("bitcoincash:"):
        payload = lower.split(":", 1)[1]
    else:
        payload = lower

    if payload.startswith("q") or payload.startswith("p"):
        if not BCH_CASHADDR_RE.fullmatch(payload):
            return False, "Invalid characters in BCH CashAddr payload"
        if len(payload) < 30:
            return False, "BCH CashAddr payload is too short"
        return True, "CashAddr format (checksum not verified)"

    if address.startswith("1") or address.startswith("3"):
        valid, reason, version, payload_len = base58check_verify(address)
        if not valid:
            return False, reason
        if payload_len != 21:
            return False, "Unexpected Base58 payload length"
        if version not in (0x00, 0x05):
            return False, "Invalid BCH legacy version byte"
        return True, "Valid legacy Base58Check address"

    return False, "BCH addresses must be CashAddr or legacy Base58"


def validate_evm_address(address: str) -> tuple[bool, str]:
    address = address.strip()
    if not EVM_ADDRESS_RE.fullmatch(address):
        return False, "EVM address must match 0x + 40 hex characters"

    body = address[2:]
    if body.islower() or body.isupper():
        return True, "Valid EVM hex address"
    return True, "Valid mixed-case EVM address (checksum not verified)"


def validate_address(coin: str, address: str) -> tuple[bool, str]:
    if not address:
        return False, "Address is required"
    if not ADDRESS_SAFE_RE.fullmatch(address):
        return False, "Address contains unsupported characters"

    if coin == BTC:
        return validate_btc_address(address)
    if coin == LTC:
        return validate_ltc_address(address)
    if coin == DOGE:
        return validate_doge_address(address)
    if coin == DASH:
        return validate_dash_address(address)
    if coin == BCH:
        return validate_bch_address(address)
    if coin in (ETH, BSC, POLYGON):
        return validate_evm_address(address)
    return False, "Unsupported coin"


def build_lookup_result(client: ApiClient, coin: str, address: str) -> LookupResult:
    explorer_url = EXPLORER_URL_BY_COIN[coin].format(address=address)
    data_source = DATA_SOURCE_BY_COIN[coin]
    is_valid, reason = validate_address(coin, address)

    result = LookupResult(
        coin=coin,
        address=address,
        is_valid_format=is_valid,
        validation_reason=reason,
        confirmed_balance=None,
        unconfirmed_balance=None,
        total_received=None,
        total_sent=None,
        tx_count=None,
        explorer_url=explorer_url,
        data_source=data_source,
        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
        api_error=None,
        api_skipped=False,
    )

    if not is_valid:
        result.api_skipped = True
        return result

    try:
        payload = client.fetch_coin_info(coin, address)
    except RuntimeError as exc:
        result.api_error = str(exc)
        return result

    if isinstance(payload.get("data_source"), str):
        result.data_source = payload["data_source"]
    result.confirmed_balance = payload["confirmed_balance"]
    result.unconfirmed_balance = payload["unconfirmed_balance"]
    result.total_received = payload["total_received"]
    result.total_sent = payload["total_sent"]
    result.tx_count = payload["tx_count"]
    return result


class HelpScreen(ModalScreen[None]):
    def compose(self) -> ComposeResult:
        with Container(id="help-dialog"):
            yield Static("Keyboard shortcuts", id="help-title")
            yield Static(
                "Enter runs validation and lookup\n"
                "Tab / Shift+Tab moves focus through controls\n"
                "Ctrl+L clears the form\n"
                "Ctrl+J toggles the JSON panel\n"
                "Ctrl+O opens explorer for current result\n"
                "Ctrl+G opens repository actions\n"
                "Ctrl+1/2/3 focuses network/address/lookup\n"
                "Alt+B / Alt+T selects BTC / LTC, arrows switch focused network\n"
                "Ctrl+P opens command palette\n"
                "F1 opens help\n"
                "Q or Ctrl+C exits\n\n"
                "Only public addresses are supported. Never paste private keys or seed phrases.",
                id="help-body",
            )
            yield Button("Close", id="help-close", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#help-close", Button).focus()

    @on(Button.Pressed, "#help-close")
    def handle_close(self) -> None:
        self.dismiss(None)


class MetricCard(Static):
    def __init__(self, title: str, value: str = "-", element_id: str = "") -> None:
        super().__init__(id=element_id, classes="metric-card")
        self.title = title
        self.value = value

    def on_mount(self) -> None:
        self.set_value(self.value)

    def set_value(self, value: str) -> None:
        self.value = value
        self.update("[dim]" + self.title + "[/]" + chr(10) + "[b]" + value + "[/]")


class DetailLine(Static):
    def __init__(self, label: str, value: str = "-", element_id: str = "") -> None:
        super().__init__(id=element_id, classes="detail-row")
        self.label = label
        self.value = value

    def on_mount(self) -> None:
        self.set_value(self.value)

    def set_value(self, value: str) -> None:
        self.value = value
        self.update(f"[dim]{self.label}:[/] {value}")


class GithubRepositoryScreen(ModalScreen[Optional[str]]):
    def __init__(self, repository_url: str) -> None:
        super().__init__()
        self.repository_url = repository_url

    def compose(self) -> ComposeResult:
        with Container(id="github-dialog"):
            yield Static("Open Github repository", id="github-title")
            yield Static("Choose what to do with the repository URL:", id="github-body")
            yield Static(self.repository_url, id="github-url")
            with Horizontal(id="github-buttons"):
                yield Button("Open in browser", id="github-open", variant="primary")
                yield Button("Copy to clipboard", id="github-copy")
                yield Button("Cancel", id="github-cancel")

    def on_mount(self) -> None:
        self.query_one("#github-open", Button).focus()

    @on(Button.Pressed, "#github-open")
    def handle_open(self) -> None:
        self.dismiss("open")

    @on(Button.Pressed, "#github-copy")
    def handle_copy(self) -> None:
        self.dismiss("copy")

    @on(Button.Pressed, "#github-cancel")
    def handle_cancel(self) -> None:
        self.dismiss(None)


class checkaddy(App):
    CSS = APP_CSS
    TITLE = "checkaddy"
    SUB_TITLE = "Public multi-chain address validation"

    BINDINGS = [
        Binding("enter", "lookup", "Lookup"),
        Binding("ctrl+l", "clear_form", "Clear"),
        Binding("ctrl+j", "toggle_json", "JSON"),
        Binding("ctrl+o", "open_explorer", "Explorer"),
        Binding("ctrl+g", "open_github_repository", "Repo"),
        Binding("ctrl+1", "focus_coin_set", show=False),
        Binding("ctrl+2", "focus_address", show=False),
        Binding("ctrl+3", "focus_lookup_button", show=False),
        Binding("alt+b", "select_btc", show=False),
        Binding("alt+t", "select_ltc", show=False),
        Binding("f1", "show_help", "Help"),
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    show_json = reactive(False)
    live_validation_timer: Optional[Timer] = None

    def __init__(self) -> None:
        super().__init__()
        self.client = ApiClient()
        self.last_result: Optional[LookupResult] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="app"):
            with Container(id="hero"):
                yield Static("checkaddy", id="hero-title")
                yield Static(
                    "Local address validation with live explorer data for UTXO and EVM public addresses.",
                    id="hero-subtitle",
                )
                yield Static("Copyright (c) 2026 zv", id="hero-credit")
            with Horizontal(id="layout"):
                with VerticalScroll(id="sidebar"):
                    with Container(classes="panel"):
                        yield Static("Input", classes="panel-title")
                        yield Label("Network")
                        with RadioSet(id="coin-set"):
                            for index, (coin, label) in enumerate(COIN_OPTIONS):
                                yield RadioButton(label, id=COIN_RADIO_IDS[coin], value=index == 0)
                        yield Label("Address", classes="subtle")
                        yield Input(placeholder="Paste public wallet address", id="address")
                        yield Static("Waiting for input", id="quick-validation")
                    with Container(classes="panel", id="controls"):
                        yield Static("Actions", classes="panel-title")
                        yield Button("Validate and fetch", id="lookup", variant="primary")
                        yield Button("Clear", id="clear")
                        yield Button("Toggle JSON", id="toggle-json")
                    with Container(classes="panel"):
                        yield Static("Notes", classes="panel-title")
                        yield Static(
                            "Supported: BTC, LTC, DOGE, DASH, BCH, ETH, BSC, Polygon.\n"
                            "EVM chains use 0x addresses; UTXO chains use Base58/Bech32/CashAddr.\n"
                            "Some fields can be unavailable depending on free endpoint limitations.",
                            classes="subtle",
                        )
                with VerticalScroll(id="main"):
                    with Container(classes="panel"):
                        yield Static("Status", classes="panel-title")
                        yield Static("Ready", id="status-body", classes="info")
                    with Container(classes="panel"):
                        yield Static("Overview", classes="panel-title")
                        with Container(id="metrics"):
                            yield MetricCard("Confirmed balance", "-", "metric-confirmed")
                            yield MetricCard("Unconfirmed balance", "-", "metric-unconfirmed")
                            yield MetricCard("Total received", "-", "metric-received")
                            yield MetricCard("Total sent", "-", "metric-sent")
                            yield MetricCard("Transaction count", "-", "metric-tx-count")
                            yield MetricCard("Data source", "-", "metric-source")
                    with Container(classes="panel"):
                        yield Static("Details", classes="panel-title")
                        with Container(id="details-grid"):
                            yield DetailLine("Coin", "-", "detail-coin")
                            yield DetailLine("Address", "-", "detail-address")
                            yield DetailLine("Validation", "-", "detail-validation")
                            yield DetailLine("Explorer", "-", "detail-explorer")
                            yield DetailLine("Fetched at UTC", "-", "detail-fetched")
                    with Container(classes="panel hidden", id="json-panel"):
                        yield Static("Normalized JSON", classes="panel-title")
                        yield Static("{}", id="json-box", expand=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#address", Input).focus()

    def on_unmount(self) -> None:
        self.client.close()

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_focus_coin_set(self) -> None:
        self.query_one("#coin-set", RadioSet).focus()

    def action_focus_address(self) -> None:
        self.query_one("#address", Input).focus()

    def action_focus_lookup_button(self) -> None:
        self.query_one("#lookup", Button).focus()

    def select_coin(self, coin: str, *, announce: bool = False) -> None:
        for coin_code, radio_id in COIN_RADIO_IDS.items():
            self.query_one(f"#{radio_id}", RadioButton).value = coin_code == coin
        self.refresh_live_validation()
        if announce:
            self.set_status(f"Selected {coin}", "info")

    def action_select_btc(self) -> None:
        self.select_coin(BTC, announce=True)

    def action_select_ltc(self) -> None:
        self.select_coin(LTC, announce=True)

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "Open Github repository",
            "Open or copy the project's GitHub URL",
            self.open_github_repository_options,
        )

    def action_open_github_repository(self) -> None:
        self.open_github_repository_options()

    def open_github_repository_options(self) -> None:
        self.push_screen(GithubRepositoryScreen(REPOSITORY_URL), self.handle_github_repository_choice)

    def handle_github_repository_choice(self, choice: Optional[str]) -> None:
        if choice == "open":
            self.open_url(REPOSITORY_URL)
            self.set_status("Opened repository in browser", "info")
        elif choice == "copy":
            self.copy_to_clipboard(REPOSITORY_URL)
            self.set_status("Repository URL copied to clipboard", "ok")

    def action_open_explorer(self) -> None:
        if self.last_result is None:
            self.set_status("No lookup result yet", "warn")
            return
        self.open_url(self.last_result.explorer_url)
        self.set_status("Opened address explorer", "info")

    def action_toggle_json(self) -> None:
        panel = self.query_one("#json-panel", Container)
        self.show_json = not self.show_json
        if self.show_json:
            panel.remove_class("hidden")
        else:
            panel.add_class("hidden")

    def action_clear_form(self) -> None:
        self.query_one("#address", Input).value = ""
        self.select_coin(BTC)
        self.query_one("#quick-validation", Static).update("Waiting for input")
        self.set_status("Ready", "info")
        self.reset_results()
        self.query_one("#address", Input).focus()

    def action_lookup(self) -> None:
        self.start_lookup()

    @on(Button.Pressed, "#lookup")
    def handle_lookup_button(self) -> None:
        self.start_lookup()

    @on(Button.Pressed, "#clear")
    def handle_clear_button(self) -> None:
        self.action_clear_form()

    @on(Button.Pressed, "#toggle-json")
    def handle_toggle_json_button(self) -> None:
        self.action_toggle_json()

    @on(Input.Changed, "#address")
    def handle_address_change(self) -> None:
        if self.live_validation_timer is not None:
            self.live_validation_timer.stop()
        self.live_validation_timer = self.set_timer(0.2, self.refresh_live_validation)

    @on(RadioSet.Changed, "#coin-set")
    def handle_coin_change(self) -> None:
        self.refresh_live_validation()

    def current_coin(self) -> str:
        pressed_button = self.query_one("#coin-set", RadioSet).pressed_button
        if pressed_button is None or pressed_button.id is None:
            return BTC
        return COIN_FROM_RADIO_ID.get(pressed_button.id, BTC)

    def set_status(self, message: str, tone: str) -> None:
        widget = self.query_one("#status-body", Static)
        widget.update(message)
        widget.set_classes(tone)

    def refresh_live_validation(self) -> None:
        address = self.query_one("#address", Input).value.strip()
        coin = self.current_coin()
        widget = self.query_one("#quick-validation", Static)
        if not address:
            widget.update("Waiting for input")
            return
        valid, reason = validate_address(coin, address)
        prefix = "Format valid" if valid else "Format invalid"
        widget.update(f"{prefix}: {reason}")

    def reset_results(self) -> None:
        self.last_result = None
        self.metric("#metric-confirmed", "-")
        self.metric("#metric-unconfirmed", "-")
        self.metric("#metric-received", "-")
        self.metric("#metric-sent", "-")
        self.metric("#metric-tx-count", "-")
        self.metric("#metric-source", "-")
        self.detail("#detail-coin", "-")
        self.detail("#detail-address", "-")
        self.detail("#detail-validation", "-")
        self.detail("#detail-explorer", "-")
        self.detail("#detail-fetched", "-")
        self.query_one("#json-box", Static).update("{}")

    def metric(self, selector: str, value: str) -> None:
        self.query_one(selector, MetricCard).set_value(value)

    def detail(self, selector: str, value: str) -> None:
        self.query_one(selector, DetailLine).set_value(value)

    def start_lookup(self) -> None:
        address = self.query_one("#address", Input).value.strip()
        coin = self.current_coin()
        if not address:
            self.set_status("Address is required", "error")
            self.query_one("#address", Input).focus()
            return
        self.set_status(f"Looking up {coin} address", "warn")
        self.run_lookup(coin, address)

    @work(thread=True)
    def run_lookup(self, coin: str, address: str) -> None:
        result = build_lookup_result(self.client, coin, address)
        self.call_from_thread(self.apply_result, result)

    def apply_result(self, result: LookupResult) -> None:
        self.last_result = result
        self.metric("#metric-confirmed", format_amount_display(result.coin, result.confirmed_balance))
        self.metric("#metric-unconfirmed", format_amount_display(result.coin, result.unconfirmed_balance))
        self.metric("#metric-received", format_amount_display(result.coin, result.total_received))
        self.metric("#metric-sent", format_amount_display(result.coin, result.total_sent))
        tx_display = str(result.tx_count) if result.tx_count is not None else "Not available via free endpoint"
        self.metric("#metric-tx-count", tx_display)
        self.metric("#metric-source", result.data_source)

        self.detail("#detail-coin", result.coin)
        self.detail("#detail-address", result.address)
        self.detail("#detail-validation", format_validation_badge(result.is_valid_format, result.validation_reason))
        self.detail("#detail-explorer", result.explorer_url)
        self.detail("#detail-fetched", result.fetched_at_utc)
        self.query_one("#json-box", Static).update(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
        self.query_one("#json-panel", Container).refresh(layout=True)

        if result.api_error:
            self.set_status(f"Format valid, API request failed: {result.api_error}", "warn")
        elif result.api_skipped:
            self.set_status("Format invalid, remote lookup skipped", "error")
        else:
            self.set_status("Lookup completed", "ok")


def main() -> None:
    checkaddy().run()


if __name__ == "__main__":
    main()

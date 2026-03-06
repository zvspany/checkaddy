# checkaddy

A simple terminal application for validating and inspecting public cryptocurrency addresses across multiple networks. It performs local format validation and optionally fetches basic address data from public blockchain APIs.

## Features

- Local validation for several address formats
- Support for both UTXO and EVM chains
- Fetches balance and transaction metadata from public endpoints
- Terminal UI built with `textual`
- Optional JSON output for raw data
- Explorer links for quick inspection in a browser

## Supported Networks

- Bitcoin (BTC)
- Litecoin (LTC)
- Dogecoin (DOGE)
- Dash (DASH)
- Bitcoin Cash (BCH)
- Ethereum (ETH)
- BNB Chain (BSC)
- Polygon (MATIC)

## What it Shows

Depending on the network and API availability:

- Confirmed balance
- Unconfirmed balance
- Total received
- Total sent
- Transaction count
- Data source used for the lookup

## Requirements

- Python 3.10+
- `requests`
- `textual`

Install dependencies:

```bash
pip install requests textual
```

## Running

```bash
python checkaddy.py
```

## Notes

- Only public wallet addresses are supported.
- Private keys or seed phrases should never be entered.
- Some values may be unavailable depending on the limitations of free API endpoints.

## License

Copyright (c) 2026 zv.

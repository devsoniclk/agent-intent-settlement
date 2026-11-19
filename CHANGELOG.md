# Changelog

All notable changes to `agent-intent-settlement` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-20

### Added
- **Combinatorial CoW Batch Matching**: Discrete batch auction solver matching overlapping multi-agent buy and sell intents peer-to-peer at a single Uniform Clearing Price (zero slippage, zero L1 gas friction).
- **Uniform Clearing Price (UCP) Discovery**: Equilibrium price determination with All-or-None (AON) and partial fill constraints maximizing aggregate social welfare (trader surplus).
- **Cross-Venue JIT Delta-Neutral Rehypothecation**: Square-root market impact router rehypothecating residual order imbalances across Hyperliquid L1 perpetuals and Uniswap v4 while executing offsetting perpetual delta hedges.
- **LVR Adverse Selection Defense**: Toxicity scoring model tracking limit price divergence relative to intraday volatility and order latency urgency to filter toxic latency arbitrageurs.
- **ZK Compute Credit Solvency Verification**: Cryptographic voucher proof verification for compute lease intents.
- **Model Context Protocol (FastMCP) Server**: Stdio JSON-RPC 2.0 interface exposing 7 specialized intent submission and clearing tools to AI agents.
- **Rich CLI & Benchmarking Harness**: Interactive terminal CLI (`agent-intent`) and 90-day simulation suite comparing Continuous AMMs, Unhedged Batch Auctions, and JIT-Hedged Intent Clearing.
- **100% Automated Test Coverage**: Comprehensive unit and integration test suite across all subsystems.

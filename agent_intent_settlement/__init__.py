"""Autonomous Programmatic Intent Clearing & CoW-Batching Engine for Decentralized AI Agent Swarms.

Implements:
- Combinatorial CoW (Coincidence of Wants) discrete batch matching.
- Uniform Clearing Price (UCP) equilibrium discovery.
- Cross-venue JIT delta-neutral rehypothecation across Hyperliquid L1 and Uniswap v4.
- Loss-Versus-Rebalancing (LVR) adverse selection defense.
- Cryptographic compute credit voucher solvency verification.
- FastMCP stdio server and rich CLI.
"""

from .models import (
    IntentType,
    IntentDirection,
    Venue,
    AgentIntent,
    MatchedTrade,
    SolverRoutingExecution,
    BatchAuctionResult,
    VaultTradeDirective,
)
from .milp_clearing import MILPClearingEngine
from .jit_liquidity_router import JITLiquidityRouter
from .lvr_toxic_filter import LVRToxicFlowFilter
from .strategy import AutonomousPerpetualIntentClearingStrategy
from .simulator import IntentClearingSimulator
from .mcp_server import AgentIntentSettlementMCPServer

__version__ = "0.1.0"
__all__ = [
    "IntentType",
    "IntentDirection",
    "Venue",
    "AgentIntent",
    "MatchedTrade",
    "SolverRoutingExecution",
    "BatchAuctionResult",
    "VaultTradeDirective",
    "MILPClearingEngine",
    "JITLiquidityRouter",
    "LVRToxicFlowFilter",
    "AutonomousPerpetualIntentClearingStrategy",
    "IntentClearingSimulator",
    "AgentIntentSettlementMCPServer",
]

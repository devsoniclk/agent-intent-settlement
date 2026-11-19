"""Data models and type definitions for Autonomous Agent Perpetual Intent Clearing Engine.

Defines multi-agent trading intents, combinatorial batch auctions, uniform clearing states,
cross-venue JIT routing decisions, LVR defense metrics, and VAULT trade directives.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import time


class IntentType(str, Enum):
    """Classification of autonomous agent intent payload."""
    BUY_PERP = "BUY_PERP"
    SELL_PERP = "SELL_PERP"
    SPOT_SWAP = "SPOT_SWAP"
    COMPUTE_LEASE = "COMPUTE_LEASE"


class IntentDirection(str, Enum):
    """Direction of the order intent."""
    BUY = "BUY"
    SELL = "SELL"


class Venue(str, Enum):
    """Liquidity execution and clearing venues."""
    INTERNAL_COW = "INTERNAL_COW"            # Direct peer-to-peer coincidence of wants (zero gas/slippage)
    HYPERLIQUID_PERP = "HYPERLIQUID_PERP"    # Sub-second L1 perpetual orderbook execution
    UNISWAP_V4 = "UNISWAP_V4"                # Concentrated liquidity with dynamic hook fees
    BINANCE_FUTURES = "BINANCE_FUTURES"      # Centralized deep liquidity backstop


@dataclass
class AgentIntent:
    """Autonomous agent declarative trading or compute lease intent."""
    intent_id: str
    agent_id: str
    asset: str                               # e.g., 'ETHUSDT', 'SOLUSDT', 'BTCUSDT'
    intent_type: IntentType
    direction: IntentDirection
    limit_price: float                       # Max price willing to buy, or min price willing to sell
    quantity: float                          # Units of asset
    min_fill_ratio: float = 0.0              # 0.0 = partial fills allowed, 1.0 = All-or-None (AON)
    urgency_decay: float = 0.0               # Price decay rate per second for time-decaying orders
    max_slippage_bps: float = 50.0           # Maximum acceptable slippage in basis points
    timestamp: float = 0.0
    deadline: float = 0.0
    is_toxic: bool = False                   # Flagged by LVR / adverse selection filter
    compute_voucher_id: Optional[str] = None
    solvency_hash: Optional[str] = None


@dataclass
class MatchedTrade:
    """Record of an executed match within a batch auction."""
    trade_id: str
    buy_intent_id: str
    sell_intent_id: str
    asset: str
    quantity: float
    clearing_price: float
    buyer_surplus: float                     # (LimitPrice - ClearingPrice) * Quantity
    seller_surplus: float                    # (ClearingPrice - LimitPrice) * Quantity
    is_internal_cow: bool = True


@dataclass
class SolverRoutingExecution:
    """Execution details for residual imbalance routed cross-venue."""
    route_id: str
    venue: Venue
    asset: str
    action: str                              # 'BUY' or 'SELL'
    quantity: float
    execution_price: float
    slippage_bps: float
    fee_usd: float
    is_jit_delta_hedged: bool = False


@dataclass
class BatchAuctionResult:
    """Uniform clearing price discovery outcome for a discrete batch auction block."""
    batch_id: str
    timestamp: float
    asset: str
    clearing_price: float
    matched_cow_volume: float
    residual_buy_volume: float
    residual_sell_volume: float
    total_trader_surplus_usd: float
    lvr_mitigated_usd: float
    solver_profit_usd: float
    matched_trades: List[MatchedTrade] = field(default_factory=list)
    residual_executions: List[SolverRoutingExecution] = field(default_factory=list)


@dataclass
class VaultTradeDirective:
    """Strictly compliant VAULT trade execution directive.
    Mandatory Format: ASSET | ACTION | ENTRY | SL | TP | LEV | R:R | SIZE
    """
    asset: str
    action: str
    entry: float
    sl: float
    tp: float
    lev: float
    risk_reward_ratio: float
    size: str
    strategy_name: str
    timestamp: float = field(default_factory=time.time)
    signal_text: str = field(init=False)

    def __post_init__(self):
        # Format string adhering strictly to VAULT directive
        self.signal_text = (
            f"{self.asset} | {self.action} | {self.entry:.4f} | "
            f"{self.sl:.4f} | {self.tp:.4f} | {self.lev:.1f}x | "
            f"{self.risk_reward_ratio:.1f}:1 | {self.size}"
        )

    def validate(self) -> bool:
        """Validate strict institutional rules."""
        if self.risk_reward_ratio < 2.0:
            return False
        if self.lev > 5.0:
            return False
        if self.entry <= 0 or self.sl <= 0 or self.tp <= 0:
            return False
        return True

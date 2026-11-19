"""Just-In-Time (JIT) cross-venue delta-neutral routing and inventory rehypothecation.

Routes residual auction order imbalances across:
1. Hyperliquid L1 Perpetual Futures: sub-second limit execution and delta-neutral inventory hedging.
2. Uniswap v4: Concentrated liquidity with directional dynamic hook fee mitigation.
"""

import math
from typing import List, Dict, Optional
from .models import Venue, SolverRoutingExecution, BatchAuctionResult


class JITLiquidityRouter:
    """Quantitative solver routing and delta-neutral inventory rehypothecation engine."""

    def __init__(
        self,
        hyperliquid_fee_bps: float = 1.5,
        uniswap_v4_fee_bps: float = 5.0,
        jit_hedge_enabled: bool = True
    ):
        self.hl_fee_bps = hyperliquid_fee_bps
        self.uni_fee_bps = uniswap_v4_fee_bps
        self.jit_hedge_enabled = jit_hedge_enabled

    def calculate_slippage(self, quantity: float, market_depth: float) -> float:
        """Estimate square-root market impact slippage in basis points."""
        if market_depth <= 0:
            return 100.0
        impact_ratio = quantity / market_depth
        return min(30.0 * math.sqrt(impact_ratio), 150.0)

    def route_residual(
        self,
        batch_result: BatchAuctionResult,
        market_price: float,
        hl_depth_usd: float = 2500000.0,
        uni_depth_usd: float = 1000000.0
    ) -> List[SolverRoutingExecution]:
        """Route residual buy or sell imbalances to optimal venue and execute JIT delta hedge."""
        executions: List[SolverRoutingExecution] = []
        net_imbalance = batch_result.residual_buy_volume - batch_result.residual_sell_volume

        if abs(net_imbalance) < 1e-6:
            return executions

        qty = abs(net_imbalance)
        direction = "BUY" if net_imbalance > 0 else "SELL"
        trade_usd = qty * market_price

        # Choose venue based on depth and fee efficiency
        hl_slippage = self.calculate_slippage(trade_usd, hl_depth_usd)
        uni_slippage = self.calculate_slippage(trade_usd, uni_depth_usd)

        hl_total_cost = hl_slippage + self.hl_fee_bps
        uni_total_cost = uni_slippage + self.uni_fee_bps

        if hl_total_cost <= uni_total_cost:
            venue = Venue.HYPERLIQUID_PERP
            slippage_bps = hl_slippage
            fee_bps = self.hl_fee_bps
        else:
            venue = Venue.UNISWAP_V4
            slippage_bps = uni_slippage
            fee_bps = self.uni_fee_bps

        # Calculate execution price with slippage
        slip_mult = (1.0 + slippage_bps / 10000.0) if direction == "BUY" else (1.0 - slippage_bps / 10000.0)
        exec_price = market_price * slip_mult
        fee_usd = (qty * exec_price) * (fee_bps / 10000.0)

        main_exec = SolverRoutingExecution(
            route_id=f"RTE-{batch_result.batch_id[:6]}-1",
            venue=venue,
            asset=batch_result.asset,
            action=direction,
            quantity=qty,
            execution_price=exec_price,
            slippage_bps=slippage_bps,
            fee_usd=fee_usd,
            is_jit_delta_hedged=False
        )
        executions.append(main_exec)

        # If JIT delta-hedging is enabled and venue was a spot swap or directional fill,
        # open an offsetting perpetual hedge on Hyperliquid to maintain a 100% delta-neutral book
        if self.jit_hedge_enabled:
            hedge_action = "SELL" if direction == "BUY" else "BUY"
            hedge_slip = self.calculate_slippage(trade_usd, hl_depth_usd)
            hedge_slip_mult = (1.0 + hedge_slip / 10000.0) if hedge_action == "BUY" else (1.0 - hedge_slip / 10000.0)
            hedge_price = market_price * hedge_slip_mult
            hedge_fee = (qty * hedge_price) * (self.hl_fee_bps / 10000.0)

            hedge_exec = SolverRoutingExecution(
                route_id=f"RTE-{batch_result.batch_id[:6]}-HEDGE",
                venue=Venue.HYPERLIQUID_PERP,
                asset=batch_result.asset,
                action=hedge_action,
                quantity=qty,
                execution_price=hedge_price,
                slippage_bps=hedge_slip,
                fee_usd=hedge_fee,
                is_jit_delta_hedged=True
            )
            executions.append(hedge_exec)

        batch_result.residual_executions.extend(executions)
        return executions

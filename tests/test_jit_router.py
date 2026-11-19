"""Unit tests for JIT liquidity router and delta-neutral rehypothecation."""

import pytest
from agent_intent_settlement.models import (
    BatchAuctionResult,
    Venue,
)
from agent_intent_settlement.jit_liquidity_router import JITLiquidityRouter


class TestJITLiquidityRouter:
    """Test suite for cross-venue residual routing and JIT delta hedging."""

    def setup_method(self):
        self.router = JITLiquidityRouter(
            hyperliquid_fee_bps=1.5,
            uniswap_v4_fee_bps=5.0,
            jit_hedge_enabled=True,
        )

    def test_calculate_slippage(self):
        # Zero depth fallback
        assert self.router.calculate_slippage(100.0, 0.0) == 100.0

        # Normal small order slippage
        slip_small = self.router.calculate_slippage(10000.0, 2500000.0)
        assert 0.0 < slip_small < 15.0

        # Massive order capped at 150 bps
        slip_huge = self.router.calculate_slippage(50000000.0, 1000000.0)
        assert slip_huge == 150.0

    def test_route_residual_zero_imbalance(self):
        batch_res = BatchAuctionResult(
            batch_id="B-ZERO",
            timestamp=0.0,
            asset="ETHUSDT",
            clearing_price=3000.0,
            matched_cow_volume=5.0,
            residual_buy_volume=0.0,
            residual_sell_volume=0.0,
            total_trader_surplus_usd=0.0,
            lvr_mitigated_usd=0.0,
            solver_profit_usd=0.0,
        )
        executions = self.router.route_residual(batch_res, market_price=3000.0)
        assert len(executions) == 0
        assert len(batch_res.residual_executions) == 0

    def test_route_residual_buy_imbalance_with_hedge(self):
        batch_res = BatchAuctionResult(
            batch_id="B-BUY-RESIDUAL",
            timestamp=0.0,
            asset="ETHUSDT",
            clearing_price=3000.0,
            matched_cow_volume=5.0,
            residual_buy_volume=4.0, # Net buy imbalance = 4.0
            residual_sell_volume=0.0,
            total_trader_surplus_usd=0.0,
            lvr_mitigated_usd=0.0,
            solver_profit_usd=0.0,
        )
        executions = self.router.route_residual(
            batch_res,
            market_price=3000.0,
            hl_depth_usd=2500000.0,
            uni_depth_usd=1000000.0,
        )

        # Expect 2 executions: primary route + offsetting hedge
        assert len(executions) == 2
        primary = executions[0]
        hedge = executions[1]

        # Primary route
        assert primary.venue == Venue.HYPERLIQUID_PERP  # cheaper than Uni v4
        assert primary.action == "BUY"
        assert primary.quantity == 4.0
        assert primary.execution_price > 3000.0 # Slippage on buy increases price
        assert not primary.is_jit_delta_hedged

        # Offsetting hedge
        assert hedge.venue == Venue.HYPERLIQUID_PERP
        assert hedge.action == "SELL" # Opposite direction
        assert hedge.quantity == 4.0
        assert hedge.is_jit_delta_hedged is True

        assert len(batch_res.residual_executions) == 2

    def test_route_residual_without_hedge(self):
        unhedged_router = JITLiquidityRouter(jit_hedge_enabled=False)
        batch_res = BatchAuctionResult(
            batch_id="B-UNHEDGED",
            timestamp=0.0,
            asset="SOLUSDT",
            clearing_price=180.0,
            matched_cow_volume=10.0,
            residual_buy_volume=0.0,
            residual_sell_volume=20.0, # Net sell imbalance = 20.0
            total_trader_surplus_usd=0.0,
            lvr_mitigated_usd=0.0,
            solver_profit_usd=0.0,
        )
        executions = unhedged_router.route_residual(batch_res, market_price=180.0)
        assert len(executions) == 1
        assert executions[0].action == "SELL"
        assert executions[0].quantity == 20.0
        assert executions[0].execution_price < 180.0

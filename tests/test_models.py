"""Unit tests for models and data structures."""

import pytest
from agent_intent_settlement.models import (
    AgentIntent,
    BatchAuctionResult,
    IntentDirection,
    IntentType,
    MatchedTrade,
    SolverRoutingExecution,
    VaultTradeDirective,
    Venue,
)


class TestModels:
    """Test suite for agent intent clearing data models."""

    def test_enums(self):
        assert IntentType.BUY_PERP.value == "BUY_PERP"
        assert IntentType.SELL_PERP.value == "SELL_PERP"
        assert IntentType.SPOT_SWAP.value == "SPOT_SWAP"
        assert IntentType.COMPUTE_LEASE.value == "COMPUTE_LEASE"

        assert IntentDirection.BUY.value == "BUY"
        assert IntentDirection.SELL.value == "SELL"

        assert Venue.INTERNAL_COW.value == "INTERNAL_COW"
        assert Venue.HYPERLIQUID_PERP.value == "HYPERLIQUID_PERP"
        assert Venue.UNISWAP_V4.value == "UNISWAP_V4"
        assert Venue.BINANCE_FUTURES.value == "BINANCE_FUTURES"

    def test_agent_intent_defaults(self):
        intent = AgentIntent(
            intent_id="INT-001",
            agent_id="agent-1",
            asset="ETHUSDT",
            intent_type=IntentType.BUY_PERP,
            direction=IntentDirection.BUY,
            limit_price=3000.0,
            quantity=2.5,
        )
        assert intent.min_fill_ratio == 0.0
        assert intent.urgency_decay == 0.0
        assert intent.max_slippage_bps == 50.0
        assert not intent.is_toxic
        assert intent.compute_voucher_id is None
        assert intent.solvency_hash is None

    def test_matched_trade(self):
        trade = MatchedTrade(
            trade_id="T-001",
            buy_intent_id="B-001",
            sell_intent_id="S-001",
            asset="ETHUSDT",
            quantity=1.5,
            clearing_price=3000.0,
            buyer_surplus=15.0,
            seller_surplus=30.0,
            is_internal_cow=True,
        )
        assert trade.trade_id == "T-001"
        assert trade.buyer_surplus + trade.seller_surplus == 45.0
        assert trade.is_internal_cow is True

    def test_solver_routing_execution(self):
        route = SolverRoutingExecution(
            route_id="R-001",
            venue=Venue.HYPERLIQUID_PERP,
            asset="ETHUSDT",
            action="BUY",
            quantity=3.0,
            execution_price=3005.0,
            slippage_bps=12.5,
            fee_usd=1.35,
            is_jit_delta_hedged=False,
        )
        assert route.venue == Venue.HYPERLIQUID_PERP
        assert route.is_jit_delta_hedged is False

    def test_batch_auction_result(self):
        res = BatchAuctionResult(
            batch_id="BATCH-001",
            timestamp=1234567890.0,
            asset="ETHUSDT",
            clearing_price=3000.0,
            matched_cow_volume=10.0,
            residual_buy_volume=2.0,
            residual_sell_volume=0.0,
            total_trader_surplus_usd=150.0,
            lvr_mitigated_usd=75.0,
            solver_profit_usd=6.0,
        )
        assert res.matched_cow_volume == 10.0
        assert len(res.matched_trades) == 0
        assert len(res.residual_executions) == 0

    def test_vault_trade_directive_valid(self):
        directive = VaultTradeDirective(
            asset="ETHUSDT",
            action="SELL",
            entry=3000.0,
            sl=3070.0,
            tp=2850.0,
            lev=2.0,
            risk_reward_ratio=2.14,
            size="5.0 ETH",
            strategy_name="INTENT_CLEARING_HEDGE",
        )
        assert directive.validate() is True
        assert "ETHUSDT | SELL | 3000.0000 | 3070.0000 | 2850.0000 | 2.0x | 2.1:1 | 5.0 ETH" == directive.signal_text

    def test_vault_trade_directive_invalid(self):
        # Invalid due to low R:R
        bad_rr = VaultTradeDirective(
            asset="ETHUSDT",
            action="BUY",
            entry=3000.0,
            sl=2900.0,
            tp=3100.0,
            lev=2.0,
            risk_reward_ratio=1.0,
            size="1.0 ETH",
            strategy_name="TEST",
        )
        assert bad_rr.validate() is False

        # Invalid due to high leverage > 5.0x
        high_lev = VaultTradeDirective(
            asset="ETHUSDT",
            action="BUY",
            entry=3000.0,
            sl=2900.0,
            tp=3300.0,
            lev=10.0,
            risk_reward_ratio=3.0,
            size="1.0 ETH",
            strategy_name="TEST",
        )
        assert high_lev.validate() is False

        # Invalid due to non-positive prices
        neg_price = VaultTradeDirective(
            asset="ETHUSDT",
            action="BUY",
            entry=-3000.0,
            sl=2900.0,
            tp=3300.0,
            lev=2.0,
            risk_reward_ratio=3.0,
            size="1.0 ETH",
            strategy_name="TEST",
        )
        assert neg_price.validate() is False

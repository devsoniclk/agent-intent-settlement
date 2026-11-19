"""Unit tests for master clearing strategy orchestrator."""

import pytest
from agent_intent_settlement.models import (
    AgentIntent,
    IntentDirection,
    IntentType,
)
from agent_intent_settlement.strategy import AutonomousPerpetualIntentClearingStrategy


class TestStrategy:
    """Test suite for AutonomousPerpetualIntentClearingStrategy."""

    def setup_method(self):
        self.strategy = AutonomousPerpetualIntentClearingStrategy(
            solver_fee_bps=2.0,
            jit_hedge_enabled=True,
            toxicity_threshold=0.70,
        )

    def test_submit_intent(self):
        intent = AgentIntent("I-1", "a1", "SOLUSDT", IntentType.BUY_PERP, IntentDirection.BUY, 180.0, 5.0)
        self.strategy.submit_intent(intent)
        assert len(self.strategy.intent_mempool) == 1
        assert self.strategy.intent_mempool[0].intent_id == "I-1"

    def test_process_batch_end_to_end(self):
        # Submit intents for two assets
        self.strategy.submit_intent(
            AgentIntent("B1", "a1", "ETHUSDT", IntentType.BUY_PERP, IntentDirection.BUY, 3010.0, 3.0)
        )
        self.strategy.submit_intent(
            AgentIntent("S1", "a2", "ETHUSDT", IntentType.SELL_PERP, IntentDirection.SELL, 2990.0, 2.0)
        )
        self.strategy.submit_intent(
            AgentIntent("SOL1", "a3", "SOLUSDT", IntentType.BUY_PERP, IntentDirection.BUY, 180.0, 10.0)
        )

        # Process ETH batch
        res = self.strategy.process_batch("BATCH-ETH-1", "ETHUSDT", reference_market_price=3000.0)

        assert res.asset == "ETHUSDT"
        assert res.matched_cow_volume == 2.0
        assert res.residual_buy_volume == 1.0 # 3.0 - 2.0
        assert res.residual_sell_volume == 0.0

        # SOL intent must remain in mempool
        assert len(self.strategy.intent_mempool) == 1
        assert self.strategy.intent_mempool[0].asset == "SOLUSDT"

        # Check completed batches
        assert len(self.strategy.completed_batches) == 1

        # Check residual executions (primary buy + delta hedge sell)
        assert len(res.residual_executions) == 2
        assert res.residual_executions[0].action == "BUY"
        assert res.residual_executions[1].action == "SELL"

    def test_generate_vault_hedge_directive_short(self):
        directive = self.strategy.generate_vault_hedge_directive(
            asset="ETHUSDT",
            action="SELL",
            current_market_price=3000.0,
            atr_14=45.0,
            size_str="5.0 ETH",
            leverage=2.0,
            direction="SHORT",
        )
        assert directive.validate() is True
        assert directive.risk_reward_ratio >= 2.0
        assert directive.lev == 2.0
        assert directive.sl > directive.entry
        assert directive.tp < directive.entry
        assert len(self.strategy.trade_directives) == 1

    def test_generate_vault_hedge_directive_long(self):
        directive = self.strategy.generate_vault_hedge_directive(
            asset="SOLUSDT",
            action="BUY",
            current_market_price=180.0,
            atr_14=4.0,
            size_str="50.0 SOL",
            leverage=3.0,
            direction="LONG",
        )
        assert directive.validate() is True
        assert directive.risk_reward_ratio >= 2.0
        assert directive.lev == 3.0
        assert directive.sl < directive.entry
        assert directive.tp > directive.entry

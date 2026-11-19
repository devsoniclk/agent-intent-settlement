"""Unit tests for IntentClearingSimulator."""

import pytest
from agent_intent_settlement.simulator import IntentClearingSimulator
from agent_intent_settlement.models import IntentType, IntentDirection


class TestSimulator:
    """Test suite for batch clearing simulation and synthetic intent generator."""

    def setup_method(self):
        self.simulator = IntentClearingSimulator(seed=123)

    def test_generate_synthetic_intents(self):
        intents = self.simulator.generate_synthetic_intents(
            asset="ETHUSDT",
            count=30,
            reference_price=3000.0,
            volatility=0.02,
            toxic_ratio=0.20,
        )
        assert len(intents) == 30

        # Check fields
        for intent in intents:
            assert intent.asset == "ETHUSDT"
            assert intent.limit_price > 0.0
            assert intent.quantity > 0.0
            assert intent.direction in [IntentDirection.BUY, IntentDirection.SELL]
            assert intent.intent_type in [
                IntentType.BUY_PERP,
                IntentType.SELL_PERP,
                IntentType.SPOT_SWAP,
                IntentType.COMPUTE_LEASE,
            ]

        # Check compute voucher handling
        compute_leases = [i for i in intents if i.intent_type == IntentType.COMPUTE_LEASE]
        for cl in compute_leases:
            assert cl.compute_voucher_id is not None
            assert cl.solvency_hash is not None

    def test_run_epoch_cycle(self):
        stats = self.simulator.run_epoch_cycle(
            asset="ETHUSDT",
            num_epochs=3,
            intents_per_epoch=15,
            start_price=3000.0,
            volatility=0.015,
            toxic_ratio=0.10,
        )
        assert stats["num_epochs"] == 3
        assert stats["total_intents_generated"] == 45
        assert stats["total_matched_trades"] >= 0
        assert stats["total_cow_volume"] >= 0.0
        assert stats["total_trader_surplus_usd"] >= 0.0
        assert stats["total_lvr_mitigated_usd"] >= 0.0
        assert stats["total_solver_profit_usd"] >= 0.0
        assert len(stats["batches"]) == 3

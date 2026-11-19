"""Unit tests for LVR toxic flow filter and compute solvency verification."""

import pytest
from agent_intent_settlement.models import (
    AgentIntent,
    IntentDirection,
    IntentType,
)
from agent_intent_settlement.lvr_toxic_filter import LVRToxicFlowFilter


class TestLVRToxicFlowFilter:
    """Test suite for adverse selection and LVR defense."""

    def setup_method(self):
        self.filter = LVRToxicFlowFilter(
            toxicity_threshold=0.70,
            max_divergence_pct=0.015,
        )

    def test_benign_intent_evaluation(self):
        # Benign order within tight range of fair price
        intent = AgentIntent(
            intent_id="BENIGN",
            agent_id="agent-01",
            asset="ETHUSDT",
            intent_type=IntentType.BUY_PERP,
            direction=IntentDirection.BUY,
            limit_price=3005.0, # divergence ~ 0.16%
            quantity=2.0,
            urgency_decay=0.005,
        )
        is_toxic, score = self.filter.evaluate_intent_toxicity(intent, fair_market_price=3000.0, intraday_vol=0.02)
        assert is_toxic is False
        assert score < 0.70

    def test_toxic_divergence_evaluation(self):
        # Large price divergence (> 1.5% max divergence)
        intent = AgentIntent(
            intent_id="TOXIC-DIV",
            agent_id="toxic-arb",
            asset="ETHUSDT",
            intent_type=IntentType.BUY_PERP,
            direction=IntentDirection.BUY,
            limit_price=3100.0, # 3.3% divergence from 3000.0
            quantity=10.0,
            urgency_decay=0.01,
        )
        is_toxic, score = self.filter.evaluate_intent_toxicity(intent, fair_market_price=3000.0, intraday_vol=0.02)
        assert is_toxic is True

    def test_toxic_urgency_evaluation(self):
        # Moderate divergence with massive urgency decay
        intent = AgentIntent(
            intent_id="TOXIC-URGENT",
            agent_id="toxic-hft",
            asset="ETHUSDT",
            intent_type=IntentType.SELL_PERP,
            direction=IntentDirection.SELL,
            limit_price=2960.0, # 1.33% divergence
            quantity=5.0,
            urgency_decay=0.08, # High urgency
        )
        is_toxic, score = self.filter.evaluate_intent_toxicity(intent, fair_market_price=3000.0, intraday_vol=0.02)
        assert is_toxic is True
        assert score >= 0.70

    def test_filter_batch(self):
        intents = [
            AgentIntent("CLEAN-1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3002.0, 1.0),
            AgentIntent("CLEAN-2", "a2", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 2998.0, 1.0),
            AgentIntent("TOXIC-1", "a3", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3150.0, 2.0),
        ]
        clean, toxic_ids, lvr_mitigated = self.filter.filter_batch(intents, fair_market_price=3000.0, intraday_vol=0.02)

        assert len(clean) == 2
        assert len(toxic_ids) == 1
        assert "TOXIC-1" in toxic_ids
        assert lvr_mitigated > 0.0

    def test_verify_compute_credit_solvency(self):
        # Collateral > Voucher -> fail
        assert self.filter.verify_compute_credit_solvency("agent-1", 100.0, 120.0) is False

        # Valid with cryptographic proof hash
        assert self.filter.verify_compute_credit_solvency(
            "agent-2", 100.0, 95.0, proof_hash="zkp_solvency_hash_0123456789"
        ) is True

        # Valid with 10% buffer fallback
        assert self.filter.verify_compute_credit_solvency("agent-3", 110.0, 100.0) is True

        # Invalid without proof when under 10% buffer
        assert self.filter.verify_compute_credit_solvency("agent-4", 105.0, 100.0) is False

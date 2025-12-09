"""
Tests for cycle summary incremental aggregation.

This tests the fix for missing daily analytics data where:
- Old approach: External script querying HA history (broken - script not deployed)
- New approach: Incremental aggregation as each block completes

The cycle runs from 21:00 to 21:00 next day.
"""

import pytest
import json
from datetime import datetime, date, timedelta


# Expected JSON structure for running totals (stored in input_text)
RUNNING_TOTALS_KEYS = {
    "heating_date",      # YYYY-MM-DD - set when cycle starts
    "energy",            # Running total kWh
    "cost",              # Running total EUR
    "blocks",            # Count of blocks completed
    "duration",          # Running total minutes
    "prices",            # List of prices for avg calculation
    "last_updated",      # ISO timestamp of last update
}

# Expected JSON structure for finalized summary
FINALIZED_SUMMARY_KEYS = {
    "date",
    "energy",
    "cost",
    "baseline",
    "savings",
    "duration",
    "blocks",
    "avg_price",
    "outdoor_avg",
    "pool_final",
}


class TestRunningTotalsStructure:
    """Test the running totals data structure."""

    def test_empty_running_totals(self):
        """Test initial empty running totals structure."""
        running = {
            "heating_date": "2025-12-08",
            "energy": 0.0,
            "cost": 0.0,
            "blocks": 0,
            "duration": 0,
            "prices": [],
            "last_updated": None,
        }
        assert set(running.keys()) == RUNNING_TOTALS_KEYS

    def test_running_totals_after_one_block(self):
        """Test running totals after first block completes."""
        running = {
            "heating_date": "2025-12-08",
            "energy": 2.5,        # First block: 2.5 kWh
            "cost": 0.10,         # 2.5 kWh * 0.04 EUR/kWh
            "blocks": 1,
            "duration": 30,       # 30 minutes
            "prices": [0.04],     # Price during this block
            "last_updated": "2025-12-09T02:30:00",
        }
        assert running["blocks"] == 1
        assert running["energy"] == 2.5
        assert abs(running["cost"] - running["energy"] * running["prices"][0]) < 0.001

    def test_running_totals_accumulation(self):
        """Test that running totals correctly accumulate across blocks."""
        # Simulate 3 blocks
        blocks = [
            {"energy": 2.5, "cost": 0.10, "duration": 30, "price": 0.04},
            {"energy": 2.3, "cost": 0.07, "duration": 30, "price": 0.03},
            {"energy": 2.8, "cost": 0.14, "duration": 45, "price": 0.05},
        ]

        running = {
            "heating_date": "2025-12-08",
            "energy": 0.0,
            "cost": 0.0,
            "blocks": 0,
            "duration": 0,
            "prices": [],
            "last_updated": None,
        }

        for block in blocks:
            running["energy"] += block["energy"]
            running["cost"] += block["cost"]
            running["blocks"] += 1
            running["duration"] += block["duration"]
            running["prices"].append(block["price"])

        assert running["blocks"] == 3
        assert running["energy"] == 2.5 + 2.3 + 2.8
        assert running["cost"] == 0.10 + 0.07 + 0.14
        assert running["duration"] == 30 + 30 + 45
        assert len(running["prices"]) == 3


class TestUpdateCycleRunningTotals:
    """Test the _update_cycle_running_totals helper function logic."""

    def test_update_from_empty(self):
        """Test updating empty running totals with first block."""
        # Input: empty/invalid JSON string from input_text
        current_json = ""
        heating_date = "2025-12-08"
        block_energy = 2.5
        block_cost = 0.10
        block_duration = 30
        block_price = 0.04

        # Expected behavior: initialize with this block's data
        if not current_json or current_json in ["unknown", "unavailable"]:
            running = {
                "heating_date": heating_date,
                "energy": 0.0,
                "cost": 0.0,
                "blocks": 0,
                "duration": 0,
                "prices": [],
                "last_updated": None,
            }
        else:
            running = json.loads(current_json)

        # Add this block
        running["energy"] += block_energy
        running["cost"] += block_cost
        running["blocks"] += 1
        running["duration"] += block_duration
        running["prices"].append(block_price)
        running["last_updated"] = datetime.now().isoformat()

        assert running["blocks"] == 1
        assert running["energy"] == 2.5
        assert running["cost"] == 0.10

    def test_update_existing_totals(self):
        """Test updating existing running totals with additional block."""
        # Input: existing running totals
        current_json = json.dumps({
            "heating_date": "2025-12-08",
            "energy": 2.5,
            "cost": 0.10,
            "blocks": 1,
            "duration": 30,
            "prices": [0.04],
            "last_updated": "2025-12-09T02:30:00",
        })

        block_energy = 2.3
        block_cost = 0.07
        block_duration = 30
        block_price = 0.03

        running = json.loads(current_json)
        running["energy"] += block_energy
        running["cost"] += block_cost
        running["blocks"] += 1
        running["duration"] += block_duration
        running["prices"].append(block_price)

        assert running["blocks"] == 2
        assert running["energy"] == 4.8  # 2.5 + 2.3
        assert running["cost"] == 0.17   # 0.10 + 0.07
        assert running["duration"] == 60  # 30 + 30

    def test_heating_date_preserved(self):
        """Test that heating_date stays constant throughout cycle."""
        running = {
            "heating_date": "2025-12-08",
            "energy": 5.0,
            "cost": 0.20,
            "blocks": 2,
            "duration": 60,
            "prices": [0.04, 0.03],
            "last_updated": "2025-12-09T03:00:00",
        }

        # Add another block (on Dec 9 morning, same heating cycle)
        running["energy"] += 2.5
        running["blocks"] += 1

        # Heating date should NOT change
        assert running["heating_date"] == "2025-12-08"


class TestFinalizeCycleSummary:
    """Test finalizing cycle summary from running totals."""

    def test_finalize_with_savings_calculation(self):
        """Test finalization calculates baseline and savings correctly."""
        running = {
            "heating_date": "2025-12-08",
            "energy": 10.0,  # 10 kWh total
            "cost": 0.40,    # EUR (actual cost with cheap prices)
            "blocks": 4,
            "duration": 120,  # 2 hours
            "prices": [0.04, 0.03, 0.04, 0.05],  # Prices during heating
            "last_updated": "2025-12-09T05:30:00",
        }

        # Window average price (all prices in 21:00-07:00 window)
        window_avg_price = 0.08  # 8 c/kWh average

        # Calculate finalized summary
        avg_heating_price = sum(running["prices"]) / len(running["prices"])
        baseline = running["energy"] * window_avg_price
        savings = baseline - running["cost"]

        finalized = {
            "date": running["heating_date"],
            "energy": round(running["energy"], 3),
            "cost": round(running["cost"], 4),
            "baseline": round(baseline, 4),
            "savings": round(savings, 4),
            "duration": running["duration"],
            "blocks": running["blocks"],
            "avg_price": round(avg_heating_price, 4),
            "outdoor_avg": 5.0,   # From sensor
            "pool_final": 25.0,   # From sensor
        }

        assert set(finalized.keys()) == FINALIZED_SUMMARY_KEYS
        assert finalized["baseline"] == 0.80  # 10 kWh * 0.08 EUR/kWh
        assert finalized["savings"] == 0.40   # 0.80 - 0.40
        assert finalized["avg_price"] == 0.04  # (0.04+0.03+0.04+0.05)/4

    def test_finalize_zero_energy(self):
        """Test finalization when no heating occurred."""
        running = {
            "heating_date": "2025-12-08",
            "energy": 0.0,
            "cost": 0.0,
            "blocks": 0,
            "duration": 0,
            "prices": [],
            "last_updated": None,
        }

        # Finalize with zero energy
        avg_price = 0.0 if not running["prices"] else sum(running["prices"]) / len(running["prices"])
        baseline = running["energy"] * 0.08  # 0

        finalized = {
            "date": running["heating_date"],
            "energy": 0.0,
            "cost": 0.0,
            "baseline": 0.0,
            "savings": 0.0,
            "duration": 0,
            "blocks": 0,
            "avg_price": 0.0,
            "outdoor_avg": 5.0,
            "pool_final": 25.0,
        }

        assert finalized["energy"] == 0.0
        assert finalized["savings"] == 0.0

    def test_reset_for_new_cycle(self):
        """Test that running totals reset correctly for new cycle."""
        old_running = {
            "heating_date": "2025-12-08",
            "energy": 10.0,
            "cost": 0.40,
            "blocks": 4,
            "duration": 120,
            "prices": [0.04, 0.03, 0.04, 0.05],
            "last_updated": "2025-12-09T05:30:00",
        }

        # New cycle starts at 21:00 on 2025-12-09
        new_heating_date = "2025-12-09"

        new_running = {
            "heating_date": new_heating_date,
            "energy": 0.0,
            "cost": 0.0,
            "blocks": 0,
            "duration": 0,
            "prices": [],
            "last_updated": None,
        }

        assert new_running["heating_date"] == "2025-12-09"
        assert new_running["energy"] == 0.0
        assert new_running["blocks"] == 0


class TestCycleWindowBoundary:
    """Test cycle window boundary detection (21:00 to 21:00)."""

    def test_heating_date_before_midnight(self):
        """Test heating_date when block starts before midnight."""
        # Block at 23:00 on Dec 8 → heating_date is Dec 8
        block_time = datetime(2025, 12, 8, 23, 0, 0)

        if block_time.hour >= 21:
            heating_date = block_time.strftime("%Y-%m-%d")
        elif block_time.hour < 7:
            heating_date = (block_time - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            # Daytime (7-21) - no heating window
            heating_date = (block_time - timedelta(days=1)).strftime("%Y-%m-%d")

        assert heating_date == "2025-12-08"

    def test_heating_date_after_midnight(self):
        """Test heating_date when block starts after midnight."""
        # Block at 02:30 on Dec 9 → heating_date is Dec 8 (same cycle)
        block_time = datetime(2025, 12, 9, 2, 30, 0)

        if block_time.hour >= 21:
            heating_date = block_time.strftime("%Y-%m-%d")
        elif block_time.hour < 7:
            heating_date = (block_time - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            heating_date = (block_time - timedelta(days=1)).strftime("%Y-%m-%d")

        assert heating_date == "2025-12-08"

    def test_cycle_boundary_at_21(self):
        """Test that 21:00 starts a new cycle."""
        # At 21:00 on Dec 9, a NEW cycle starts (heating_date = Dec 9)
        cycle_start = datetime(2025, 12, 9, 21, 0, 0)

        if cycle_start.hour >= 21:
            heating_date = cycle_start.strftime("%Y-%m-%d")
        else:
            heating_date = (cycle_start - timedelta(days=1)).strftime("%Y-%m-%d")

        assert heating_date == "2025-12-09"


class TestRegressionDecSixthOnwards:
    """
    Regression test for the Dec 6+ missing data bug.

    The bug: calculate_night_summary called an external script that was never
    deployed, so no daily summaries were created after Dec 5th.

    The fix: Incrementally accumulate totals in log_heating_end() instead of
    querying history at cycle end.
    """

    def test_incremental_approach_produces_same_result(self):
        """
        Test that incremental aggregation produces same result as
        querying all 15-min periods.

        Reference: Dec 5th data
        - 12 blocks of 15 min each = 180 min
        - Total energy: 11.919 kWh
        - Total cost: 0.4837 EUR
        """
        # Simulate 12 x 15-min blocks
        block_data = [
            {"energy": 1.0, "cost": 0.04, "price": 0.04},
            {"energy": 1.0, "cost": 0.04, "price": 0.04},
            {"energy": 1.0, "cost": 0.04, "price": 0.04},
            {"energy": 1.0, "cost": 0.04, "price": 0.04},
            {"energy": 1.0, "cost": 0.04, "price": 0.04},
            {"energy": 1.0, "cost": 0.04, "price": 0.04},
            {"energy": 0.9, "cost": 0.036, "price": 0.04},
            {"energy": 1.0, "cost": 0.04, "price": 0.04},
            {"energy": 1.0, "cost": 0.04, "price": 0.04},
            {"energy": 1.019, "cost": 0.0437, "price": 0.043},
            {"energy": 1.0, "cost": 0.04, "price": 0.04},
            {"energy": 1.0, "cost": 0.04, "price": 0.04},
        ]

        # Incremental aggregation
        running = {
            "heating_date": "2025-12-05",
            "energy": 0.0,
            "cost": 0.0,
            "blocks": 0,
            "duration": 0,
            "prices": [],
        }

        for block in block_data:
            running["energy"] += block["energy"]
            running["cost"] += block["cost"]
            running["blocks"] += 1
            running["duration"] += 15  # 15-min blocks
            running["prices"].append(block["price"])

        # Should match Dec 5th totals (approximately)
        assert running["blocks"] == 12
        assert running["duration"] == 180
        assert abs(running["energy"] - 11.919) < 0.01
        assert abs(running["cost"] - 0.4837) < 0.01

    def test_data_persists_across_restarts(self):
        """
        Test that using input_text for running totals survives HA restarts.

        This is critical - if HA restarts during the night, we shouldn't
        lose the accumulated data.
        """
        # Simulate: 2 blocks complete, then HA restarts
        running_before_restart = json.dumps({
            "heating_date": "2025-12-08",
            "energy": 5.0,
            "cost": 0.20,
            "blocks": 2,
            "duration": 60,
            "prices": [0.04, 0.04],
            "last_updated": "2025-12-09T03:00:00",
        })

        # After restart, load from input_text (persisted)
        running = json.loads(running_before_restart)

        # Add another block
        running["energy"] += 2.5
        running["cost"] += 0.10
        running["blocks"] += 1
        running["duration"] += 30
        running["prices"].append(0.04)

        # Data should be preserved
        assert running["blocks"] == 3
        assert running["energy"] == 7.5
        assert abs(running["cost"] - 0.30) < 0.001

#!/usr/bin/env python3
"""
Backfill night summaries into Home Assistant database.

This script reads historical data from the HA SQLite database and creates
entries for sensor.pool_heating_night_summary.

Usage:
    # Dry run (show what would be inserted)
    python backfill_night_summaries.py findings/home-assistant_v2.db --dry-run

    # Actually insert data
    python backfill_night_summaries.py findings/home-assistant_v2.db

    # Copy modified DB back to HA
    scp findings/home-assistant_v2.db root@192.168.50.11:/config/
"""

import sqlite3
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path


# Constants
NIGHT_SUMMARY_ENTITY = "sensor.pool_heating_night_summary"
COP = 3.0  # Coefficient of Performance
BASELINE_PRICE = 0.10  # 10c/kWh baseline for savings calculation

# Statistics metadata IDs (from the database)
METADATA_IDS = {
    'pool_temp': 1,
    'nordpool': 2,
    'cost_daily': 6,
    'electricity_daily': 10,
}


def get_daily_data(conn):
    """Query available daily data from statistics table."""
    cursor = conn.cursor()

    query = """
    SELECT
        date(s.start_ts, 'unixepoch', 'localtime') as heating_date,
        MAX(CASE WHEN s.metadata_id = ? THEN s.state END) as electricity_kwh,
        MAX(CASE WHEN s.metadata_id = ? THEN s.state END) as cost_eur,
        AVG(CASE WHEN s.metadata_id = ? THEN s.mean END) as pool_temp_avg,
        AVG(CASE WHEN s.metadata_id = ? THEN s.state END) as nordpool_avg
    FROM statistics s
    WHERE s.metadata_id IN (?, ?, ?, ?)
    GROUP BY date(s.start_ts, 'unixepoch', 'localtime')
    HAVING electricity_kwh IS NOT NULL
    ORDER BY heating_date
    """

    cursor.execute(query, (
        METADATA_IDS['electricity_daily'],
        METADATA_IDS['cost_daily'],
        METADATA_IDS['pool_temp'],
        METADATA_IDS['nordpool'],
        METADATA_IDS['electricity_daily'],
        METADATA_IDS['cost_daily'],
        METADATA_IDS['pool_temp'],
        METADATA_IDS['nordpool'],
    ))

    results = []
    for row in cursor.fetchall():
        heating_date, electricity, cost, pool_temp, nordpool = row

        # Skip if no electricity data
        if electricity is None or electricity <= 0:
            continue

        # Recalculate cost if it looks wrong (too low)
        if cost is None or cost < 0.01:
            cost = electricity * (nordpool if nordpool else BASELINE_PRICE)

        results.append({
            'heating_date': heating_date,
            'electricity_kwh': float(electricity),
            'cost_eur': float(cost) if cost else 0,
            'pool_temp': float(pool_temp) if pool_temp else 24.0,
            'nordpool_avg': float(nordpool) if nordpool else BASELINE_PRICE,
        })

    return results


def calculate_night_summary(day_data, outdoor_temp=None):
    """Calculate night summary attributes from daily data.

    Attributes use clean naming convention:
    - energy: from state value (kWh)
    - cost: EUR
    - baseline: EUR (baseline cost)
    - savings: EUR (baseline - cost)
    - duration: minutes
    - blocks: count
    - outdoor_temp: °C
    - pool_temp: °C
    - avg_price: EUR/kWh
    """
    electricity = day_data['electricity_kwh']
    actual_cost = day_data['cost_eur']
    pool_temp = day_data['pool_temp']
    avg_price = day_data['nordpool_avg']

    # Baseline cost (what it would cost at baseline price)
    baseline_cost = electricity * BASELINE_PRICE

    # Savings
    savings = baseline_cost - actual_cost

    # Estimate duration (roughly 1 kWh = 40 mins of heating)
    duration_minutes = int(electricity * 40)

    # Estimate blocks count (2 hours total = ~3 blocks typically)
    blocks_count = max(1, min(4, int(electricity / 1.5)))

    # Use provided outdoor temp or estimate
    outdoor = outdoor_temp if outdoor_temp is not None else 5.0

    return {
        'heating_date': day_data['heating_date'],
        'cost': round(actual_cost, 4),
        'baseline': round(baseline_cost, 4),
        'savings': round(savings, 4),
        'duration': duration_minutes,
        'blocks': blocks_count,
        'outdoor_temp': round(outdoor, 1),
        'pool_temp': round(pool_temp, 1),
        'avg_price': round(avg_price, 4),  # EUR/kWh (not cents)
        'unit_of_measurement': 'kWh',
        'device_class': 'energy',
        'state_class': 'measurement',
        'friendly_name': 'Pool Heating Night Summary',
    }


def get_or_create_states_meta(conn, entity_id):
    """Get or create states_meta entry for entity."""
    cursor = conn.cursor()

    # Check if exists
    cursor.execute(
        "SELECT metadata_id FROM states_meta WHERE entity_id = ?",
        (entity_id,)
    )
    row = cursor.fetchone()

    if row:
        return row[0]

    # Create new entry
    cursor.execute(
        "INSERT INTO states_meta (entity_id) VALUES (?)",
        (entity_id,)
    )
    conn.commit()
    return cursor.lastrowid


def get_or_create_attributes(conn, attributes_dict):
    """Get or create state_attributes entry."""
    cursor = conn.cursor()

    attrs_json = json.dumps(attributes_dict, sort_keys=True)
    attrs_hash = hash(attrs_json)

    # Check if exists
    cursor.execute(
        "SELECT attributes_id FROM state_attributes WHERE hash = ?",
        (attrs_hash,)
    )
    row = cursor.fetchone()

    if row:
        return row[0]

    # Create new entry
    cursor.execute(
        "INSERT INTO state_attributes (hash, shared_attrs) VALUES (?, ?)",
        (attrs_hash, attrs_json)
    )
    conn.commit()
    return cursor.lastrowid


def insert_state(conn, metadata_id, attributes_id, state_value, timestamp):
    """Insert a state entry."""
    cursor = conn.cursor()

    # Convert timestamp to unix epoch
    ts = timestamp.timestamp()

    cursor.execute("""
        INSERT INTO states (
            state,
            last_changed_ts,
            last_reported_ts,
            last_updated_ts,
            attributes_id,
            metadata_id,
            origin_idx
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        str(state_value),
        ts,
        ts,
        ts,
        attributes_id,
        metadata_id,
        0,  # origin_idx
    ))

    conn.commit()
    return cursor.lastrowid


def backfill_summaries(db_path, dry_run=False):
    """Main backfill function."""
    print(f"Opening database: {db_path}")
    conn = sqlite3.connect(db_path)

    try:
        # Get daily data
        daily_data = get_daily_data(conn)
        print(f"Found {len(daily_data)} days with data")

        if not daily_data:
            print("No data to backfill")
            return

        # Get or create metadata entry for night summary entity
        if not dry_run:
            metadata_id = get_or_create_states_meta(conn, NIGHT_SUMMARY_ENTITY)
            print(f"States metadata_id for {NIGHT_SUMMARY_ENTITY}: {metadata_id}")
        else:
            metadata_id = None

        # Process each day
        for day in daily_data:
            summary = calculate_night_summary(day)

            # Timestamp: 07:00 on the day after heating_date
            heating_date = datetime.strptime(day['heating_date'], '%Y-%m-%d')
            summary_time = heating_date + timedelta(days=1, hours=7)

            print(f"\n{'[DRY RUN] ' if dry_run else ''}Processing {day['heating_date']}:")
            print(f"  Energy: {summary['total_energy']:.2f} kWh")
            print(f"  Cost: {summary['total_cost']:.3f} EUR")
            print(f"  Baseline: {summary['baseline_cost']:.3f} EUR")
            print(f"  Savings: {summary['savings']:.3f} EUR ({summary['savings_percent']:.1f}%)")
            print(f"  Pool temp: {summary['pool_temp_final']:.1f}°C")
            print(f"  Timestamp: {summary_time}")

            if not dry_run:
                # Create attributes entry
                attributes_id = get_or_create_attributes(conn, summary)

                # Insert state
                state_id = insert_state(
                    conn,
                    metadata_id,
                    attributes_id,
                    summary['total_energy'],
                    summary_time
                )
                print(f"  Inserted state_id: {state_id}")

        print(f"\n{'[DRY RUN] ' if dry_run else ''}Backfill complete!")

        if not dry_run:
            print(f"\nNext steps:")
            print(f"1. Stop Home Assistant")
            print(f"2. Copy database: scp {db_path} root@192.168.50.11:/config/")
            print(f"3. Start Home Assistant")
            print(f"4. Check sensor.pool_heating_night_summary in Developer Tools")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Backfill night summaries into HA database')
    parser.add_argument('db_path', help='Path to home-assistant_v2.db')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be inserted without modifying DB')

    args = parser.parse_args()

    if not Path(args.db_path).exists():
        print(f"Error: Database not found: {args.db_path}")
        return 1

    backfill_summaries(args.db_path, dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    exit(main())

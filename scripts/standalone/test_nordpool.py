#!/usr/bin/env python3
"""
Test script for Nordpool price fetching.

This script tests the Nordpool API integration outside of Home Assistant.
Useful for development and debugging.

Usage:
    python test_nordpool.py [--date YYYY-MM-DD]

Requirements:
    pip install aiohttp
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
import argparse
import json


# Nordpool API endpoint (same as used by HA integration)
NORDPOOL_API = "https://www.nordpoolgroup.com/api/marketdata/page/10"

# Alternative: Use elspot data
ELSPOT_API = "https://www.nordpoolgroup.com/api/marketdata/page/29"


async def fetch_nordpool_prices(date: datetime = None, region: str = "FI") -> dict:
    """
    Fetch Nordpool electricity prices for a specific date and region.

    Args:
        date: Date to fetch prices for (default: today)
        region: Price region (FI, SE1-4, NO1-5, DK1-2, etc.)

    Returns:
        Dictionary with hourly prices
    """
    if date is None:
        date = datetime.now()

    # Format date for API
    date_str = date.strftime("%d-%m-%Y")

    params = {
        "currency": "EUR",
        "endDate": date_str,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(NORDPOOL_API, params=params) as response:
            if response.status != 200:
                print(f"Error: HTTP {response.status}")
                return None

            data = await response.json()
            return parse_nordpool_response(data, region, date)


def parse_nordpool_response(data: dict, region: str, target_date: datetime) -> dict:
    """
    Parse Nordpool API response to extract hourly prices.
    """
    result = {
        'date': target_date.strftime("%Y-%m-%d"),
        'region': region,
        'currency': 'EUR',
        'prices': [],
        'raw_data': []
    }

    try:
        rows = data.get('data', {}).get('Rows', [])

        for row in rows:
            # Skip non-hourly rows
            if not row.get('IsExtraRow', False) and row.get('Name', '').endswith(':00 - '):
                columns = row.get('Columns', [])

                for col in columns:
                    if col.get('Name') == region:
                        value = col.get('Value', '').replace(',', '.').replace(' ', '')
                        try:
                            price = float(value) / 1000  # Convert from EUR/MWh to EUR/kWh
                            result['prices'].append(price)
                            result['raw_data'].append({
                                'hour': row.get('Name'),
                                'price_eur_kwh': price,
                                'price_cents_kwh': price * 100
                            })
                        except ValueError:
                            print(f"Could not parse price: {value}")

    except Exception as e:
        print(f"Error parsing response: {e}")

    return result


async def test_heating_window_prices():
    """
    Fetch and display prices for the heating window (21:00 - 07:00).
    """
    today = datetime.now()
    tomorrow = today + timedelta(days=1)

    print(f"\n{'='*60}")
    print(f"Nordpool Prices for Finland - Heating Window Analysis")
    print(f"{'='*60}")

    # Fetch today's prices
    print(f"\nFetching prices for {today.strftime('%Y-%m-%d')}...")
    today_data = await fetch_nordpool_prices(today, "FI")

    if today_data and today_data['prices']:
        print(f"Found {len(today_data['prices'])} hourly prices")

        print(f"\nTonight's prices (21:00 - 23:00):")
        for i, hour in enumerate(range(21, 24)):
            if hour < len(today_data['prices']):
                price = today_data['prices'][hour]
                print(f"  {hour:02d}:00 - {price*100:6.2f} c/kWh")
    else:
        print("No prices available for today")

    # Fetch tomorrow's prices
    print(f"\nFetching prices for {tomorrow.strftime('%Y-%m-%d')}...")
    tomorrow_data = await fetch_nordpool_prices(tomorrow, "FI")

    if tomorrow_data and tomorrow_data['prices']:
        print(f"\nTomorrow morning prices (00:00 - 06:00):")
        for hour in range(0, 7):
            if hour < len(tomorrow_data['prices']):
                price = tomorrow_data['prices'][hour]
                print(f"  {hour:02d}:00 - {price*100:6.2f} c/kWh")
    else:
        print("Tomorrow's prices not yet available (usually published around 13:00 CET)")

    # Calculate best heating slots
    if today_data and today_data['prices'] and tomorrow_data and tomorrow_data['prices']:
        print(f"\n{'='*60}")
        print("Optimal Heating Slots (non-consecutive):")
        print(f"{'='*60}")

        best_slots = find_best_slots(
            today_data['prices'],
            tomorrow_data['prices']
        )

        for i, (hour, price, day) in enumerate(best_slots, 1):
            date = today if day == 'today' else tomorrow
            print(f"  Slot {i}: {date.strftime('%Y-%m-%d')} {hour:02d}:00 - {price*100:.2f} c/kWh")

        avg_price = sum(s[1] for s in best_slots) / len(best_slots) if best_slots else 0
        print(f"\n  Average price: {avg_price*100:.2f} c/kWh")


def find_best_slots(today_prices: list, tomorrow_prices: list,
                   window_start: int = 21, window_end: int = 7,
                   num_slots: int = 2, min_gap: int = 1) -> list:
    """
    Find N cheapest non-consecutive hours in the heating window.
    Same algorithm as pyscript version, for testing.
    """
    valid_hours = []

    # Tonight's hours (21:00 - 23:00)
    for hour in range(window_start, 24):
        if hour < len(today_prices):
            valid_hours.append((hour, today_prices[hour], 'today'))

    # Tomorrow morning hours (00:00 - 06:00)
    for hour in range(0, window_end):
        if hour < len(tomorrow_prices):
            valid_hours.append((hour, tomorrow_prices[hour], 'tomorrow'))

    # Sort by price
    valid_hours.sort(key=lambda x: x[1])

    # Select non-consecutive
    selected = []
    for hour, price, day in valid_hours:
        if len(selected) >= num_slots:
            break

        is_too_close = False
        for sel_hour, _, sel_day in selected:
            h1 = hour + (24 if day == 'tomorrow' else 0)
            h2 = sel_hour + (24 if sel_day == 'tomorrow' else 0)
            if abs(h1 - h2) <= min_gap:
                is_too_close = True
                break

        if not is_too_close:
            selected.append((hour, price, day))

    selected.sort(key=lambda x: x[0] + (24 if x[2] == 'tomorrow' else 0))
    return selected


async def main():
    parser = argparse.ArgumentParser(description='Test Nordpool price fetching')
    parser.add_argument('--date', type=str, help='Date to fetch (YYYY-MM-DD)')
    parser.add_argument('--region', type=str, default='FI', help='Price region (default: FI)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()

    if args.date:
        date = datetime.strptime(args.date, '%Y-%m-%d')
        data = await fetch_nordpool_prices(date, args.region)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(f"Prices for {data['date']} ({data['region']}):")
            for item in data['raw_data']:
                print(f"  {item['hour']}: {item['price_cents_kwh']:.2f} c/kWh")
    else:
        await test_heating_window_prices()


if __name__ == "__main__":
    asyncio.run(main())

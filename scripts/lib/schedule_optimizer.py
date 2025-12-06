"""
Pool Heating Schedule Optimizer - Standalone Algorithm Module

This module contains the pure scheduling algorithm with no Home Assistant dependencies.
It can be used by:
- Pyscript for production HA deployment
- Mock server for testing
- Direct pytest tests

The algorithm finds optimal heating blocks based on electricity prices.
"""

from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Any


# Default configuration
DEFAULT_TOTAL_HEATING_MINUTES = 120  # 2 hours total heating
DEFAULT_MIN_BLOCK_MINUTES = 30       # Minimum consecutive heating duration
DEFAULT_MAX_BLOCK_MINUTES = 45       # Maximum consecutive heating duration
SLOT_DURATION_MINUTES = 15           # Nordpool 15-minute intervals

# Energy consumption for cost calculation
POWER_KW = 5.0                        # Pool heating power in kW
ENERGY_PER_SLOT_KWH = POWER_KW * SLOT_DURATION_MINUTES / 60  # 1.25 kWh per 15-min slot

# Valid ranges for schedule parameters
VALID_BLOCK_DURATIONS = [30, 45, 60]  # minutes
# Max 5h due to heating window constraint (21:00-07:00 = 600min)
# With breaks equal to block duration, 5.5h+ doesn't fit
VALID_TOTAL_HOURS = [x * 0.5 for x in range(0, 11)]  # 0, 0.5, 1.0, ..., 5.0


def find_best_heating_schedule(
    prices_today: List[float],
    prices_tomorrow: List[float],
    window_start: int = 21,
    window_end: int = 7,
    total_minutes: int = 120,
    min_block_minutes: int = 30,
    max_block_minutes: int = 45,
    slot_minutes: int = 15,
    reference_date: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Find optimal heating schedule using 15-minute price intervals.

    Constraints:
    - Total heating time: configurable (default 120 minutes)
    - Each heating block: min_block_minutes to max_block_minutes
    - Break between blocks: at least equal to preceding block duration

    Args:
        prices_today: List of 15-minute prices for today (96 slots)
        prices_tomorrow: List of 15-minute prices for tomorrow (96 slots)
        window_start: Start hour (21 = 9 PM)
        window_end: End hour (7 = 7 AM)
        total_minutes: Total heating time needed (default 120)
        min_block_minutes: Minimum consecutive heating (default 30)
        max_block_minutes: Maximum consecutive heating (default 45)
        slot_minutes: Duration per price slot (default 15)
        reference_date: Date to use as "today" (for testing)

    Returns:
        List of dicts with 'start' (datetime), 'end' (datetime),
        'duration_minutes', 'avg_price' for each heating block
    """
    today = reference_date or date.today()
    tomorrow = today + timedelta(days=1)

    # Build list of all 15-minute slots in the heating window
    slots = []

    # Helper to get slot index from hour and quarter
    def slot_index(hour, quarter=0):
        return hour * 4 + quarter

    # Tonight's slots (21:00 - 23:45)
    for hour in range(window_start, 24):
        for quarter in range(4):
            idx = slot_index(hour, quarter)
            if prices_today and idx < len(prices_today):
                dt = datetime.combine(today, datetime.min.time().replace(
                    hour=hour, minute=quarter * 15))
                slots.append({
                    'datetime': dt,
                    'index': len(slots),  # Sequential index in window
                    'price': prices_today[idx],
                    'day': 'today'
                })

    # Tomorrow morning slots (00:00 - 06:45)
    for hour in range(0, window_end):
        for quarter in range(4):
            idx = slot_index(hour, quarter)
            if prices_tomorrow and idx < len(prices_tomorrow):
                dt = datetime.combine(tomorrow, datetime.min.time().replace(
                    hour=hour, minute=quarter * 15))
                slots.append({
                    'datetime': dt,
                    'index': len(slots),
                    'price': prices_tomorrow[idx],
                    'day': 'tomorrow'
                })

    if not slots:
        return []

    # Calculate slot counts
    min_block_slots = min_block_minutes // slot_minutes  # 2 slots = 30 min
    max_block_slots = max_block_minutes // slot_minutes  # 3 slots = 45 min
    total_slots_needed = total_minutes // slot_minutes   # 8 slots = 120 min

    # Find optimal combination of heating blocks
    # Strategy: Try different block configurations and pick cheapest total
    best_schedule = None
    best_cost = float('inf')

    # Generate valid block size combinations that sum to total_slots_needed
    # Each block must be min_block_slots to max_block_slots
    block_combinations = []
    _find_block_combinations(
        total_slots_needed, min_block_slots, max_block_slots,
        [], block_combinations
    )

    # For each combination of block sizes, find optimal placement
    for block_sizes in block_combinations:
        schedule = _find_best_placement(slots, block_sizes, slot_minutes)
        if schedule:
            total_cost = 0
            for b in schedule:
                total_cost = total_cost + b['avg_price'] * b['duration_minutes']
            if total_cost < best_cost:
                best_cost = total_cost
                best_schedule = schedule

    return best_schedule or []


def _find_block_combinations(remaining: int, min_size: int, max_size: int,
                            current: List[int], results: List[List[int]]) -> None:
    """Recursively find all valid combinations of block sizes."""
    if remaining == 0:
        if current:  # Don't allow empty
            results.append(current[:])
        return
    if remaining < min_size:
        return

    for size in range(min_size, min(max_size, remaining) + 1):
        current.append(size)
        _find_block_combinations(remaining - size, min_size, max_size, current, results)
        current.pop()


def _find_best_placement(slots: List[Dict], block_sizes: List[int],
                        slot_minutes: int) -> Optional[List[Dict]]:
    """
    Find the best placement of heating blocks with given sizes.

    Each block must be followed by a break of at least equal duration.
    """
    n_slots = len(slots)
    n_blocks = len(block_sizes)

    if n_blocks == 0:
        return []

    # Calculate average price for a block starting at position i with given size
    def block_cost(start_idx, size):
        if start_idx + size > n_slots:
            return float('inf'), None
        block_slots = slots[start_idx:start_idx + size]
        price_sum = 0
        for s in block_slots:
            price_sum = price_sum + s['price']
        avg_price = price_sum / size
        return avg_price, block_slots

    # Dynamic programming / recursive search with memoization
    # For simplicity with small search space, use brute force
    best_schedule = None
    best_total_cost = float('inf')

    def search(block_idx, min_start_idx, current_schedule, current_cost):
        nonlocal best_schedule, best_total_cost

        if block_idx >= n_blocks:
            # All blocks placed
            if current_cost < best_total_cost:
                best_total_cost = current_cost
                best_schedule = current_schedule[:]
            return

        block_size = block_sizes[block_idx]

        # Try all valid starting positions for this block
        for start_idx in range(min_start_idx, n_slots - block_size + 1):
            avg_price, block_slots = block_cost(start_idx, block_size)

            if avg_price == float('inf'):
                break

            # Build block info
            # Calculate energy cost: slots × 1.25 kWh × avg_price
            num_slots = block_size
            energy_kwh = num_slots * ENERGY_PER_SLOT_KWH
            cost_eur = energy_kwh * avg_price

            block_info = {
                'start': block_slots[0]['datetime'],
                'end': block_slots[-1]['datetime'] + timedelta(minutes=slot_minutes),
                'duration_minutes': block_size * slot_minutes,
                'avg_price': avg_price,
                'cost_eur': cost_eur,
                'slots': block_slots
            }

            new_cost = current_cost + avg_price * block_size

            # Prune if already worse than best
            if new_cost >= best_total_cost:
                continue

            # Calculate minimum start for next block
            # Break must be at least equal to this block's duration
            next_min_start = start_idx + block_size + block_size  # block + equal break

            current_schedule.append(block_info)
            search(block_idx + 1, next_min_start, current_schedule, new_cost)
            current_schedule.pop()

    search(0, 0, [], 0)

    # Clean up schedule (remove internal 'slots' data)
    if best_schedule:
        for block in best_schedule:
            del block['slots']

    return best_schedule


def validate_schedule_parameters(
    min_block: int,
    max_block: int,
    total_hours: float
) -> Dict[str, Any]:
    """
    Validate schedule parameters and return validated values with fallbacks.

    Args:
        min_block: Minimum block duration in minutes
        max_block: Maximum block duration in minutes
        total_hours: Total heating hours

    Returns:
        Dict with validated min_block_minutes, max_block_minutes, total_minutes
        and a list of any fallbacks used
    """
    params = {
        'min_block_minutes': DEFAULT_MIN_BLOCK_MINUTES,
        'max_block_minutes': DEFAULT_MAX_BLOCK_MINUTES,
        'total_minutes': DEFAULT_TOTAL_HEATING_MINUTES,
    }
    fallback_used = []

    # Validate min block duration
    if min_block in VALID_BLOCK_DURATIONS:
        params['min_block_minutes'] = min_block
    else:
        fallback_used.append(f"min_block={min_block} not in {VALID_BLOCK_DURATIONS}")

    # Validate max block duration
    if max_block in VALID_BLOCK_DURATIONS:
        params['max_block_minutes'] = max_block
    else:
        fallback_used.append(f"max_block={max_block} not in {VALID_BLOCK_DURATIONS}")

    # Validate total hours
    if 0 <= total_hours <= 6:
        # Round to nearest 0.5
        total_hours = round(total_hours * 2) / 2
        params['total_minutes'] = int(total_hours * 60)
    else:
        fallback_used.append(f"total_hours={total_hours} not in 0-6 range")

    # Validate min <= max constraint
    if params['min_block_minutes'] > params['max_block_minutes']:
        params['min_block_minutes'] = DEFAULT_MIN_BLOCK_MINUTES
        params['max_block_minutes'] = DEFAULT_MAX_BLOCK_MINUTES
        fallback_used.append("min > max conflict")

    return {
        **params,
        'fallbacks': fallback_used
    }


def generate_15min_prices(hourly_prices: List[float]) -> List[float]:
    """Expand hourly prices to 15-minute slots (4 per hour)."""
    prices_15min = []
    for price in hourly_prices:
        prices_15min.extend([price] * 4)
    return prices_15min


def schedule_to_json(schedule: List[Dict]) -> List[Dict]:
    """Convert schedule with datetime objects to JSON-serializable format."""
    return [
        {
            'start': block['start'].isoformat(),
            'end': block['end'].isoformat(),
            'duration_minutes': block['duration_minutes'],
            'avg_price': block['avg_price']
        }
        for block in schedule
    ]


def calculate_schedule_stats(schedule: List[Dict]) -> Dict[str, Any]:
    """Calculate statistics for a schedule."""
    if not schedule:
        return {
            'total_minutes': 0,
            'block_count': 0,
            'avg_price': 0,
            'total_cost': 0,
        }

    total_minutes = sum(b['duration_minutes'] for b in schedule)
    total_cost = sum(b['avg_price'] * b['duration_minutes'] for b in schedule)
    avg_price = total_cost / total_minutes if total_minutes > 0 else 0

    return {
        'total_minutes': total_minutes,
        'block_count': len(schedule),
        'avg_price': avg_price,
        'total_cost': total_cost,
    }


def apply_cost_constraint(
    schedule: List[Dict[str, Any]],
    max_cost_eur: Optional[float] = None
) -> Dict[str, Any]:
    """
    Apply cost constraint to a schedule, enabling blocks up to the cost limit.

    Blocks are prioritized by price (cheapest first). Blocks that would cause
    the total cost to exceed the limit are marked as cost_exceeded but remain
    visible in the schedule.

    Args:
        schedule: List of block dicts from find_best_heating_schedule()
        max_cost_eur: Maximum total cost in EUR. None = no limit.

    Returns:
        Dict with:
        - blocks: List of blocks with 'enabled' and 'cost_exceeded' flags
        - total_cost: Sum of costs for enabled blocks
        - scheduled_cost: Sum of costs for all blocks (if all enabled)
        - cost_limit_applied: True if any blocks were disabled due to cost
        - enabled_count: Number of enabled blocks
    """
    if not schedule:
        return {
            'blocks': [],
            'total_cost': 0.0,
            'scheduled_cost': 0.0,
            'cost_limit_applied': False,
            'enabled_count': 0,
        }

    # Ensure all blocks have cost_eur calculated
    blocks_with_cost = []
    for block in schedule:
        block_copy = block.copy()
        if 'cost_eur' not in block_copy:
            # Calculate cost if not present
            num_slots = block_copy['duration_minutes'] // SLOT_DURATION_MINUTES
            block_copy['cost_eur'] = num_slots * ENERGY_PER_SLOT_KWH * block_copy['avg_price']
        blocks_with_cost.append(block_copy)

    # Calculate total scheduled cost (if all blocks were enabled)
    scheduled_cost = sum(b['cost_eur'] for b in blocks_with_cost)

    # If no limit, enable all blocks
    if max_cost_eur is None:
        for block in blocks_with_cost:
            block['enabled'] = True
            block['cost_exceeded'] = False

        return {
            'blocks': blocks_with_cost,
            'total_cost': scheduled_cost,
            'scheduled_cost': scheduled_cost,
            'cost_limit_applied': False,
            'enabled_count': len(blocks_with_cost),
        }

    # Sort blocks by price (cheapest first) to allocate cost budget
    # Keep track of original index to restore order later
    indexed_blocks = [(i, b) for i, b in enumerate(blocks_with_cost)]
    sorted_by_price = sorted(indexed_blocks, key=lambda x: x[1]['avg_price'])

    # Allocate budget to cheapest blocks first
    remaining_budget = max_cost_eur
    enabled_indices = set()

    for orig_idx, block in sorted_by_price:
        if block['cost_eur'] <= remaining_budget:
            enabled_indices.add(orig_idx)
            remaining_budget -= block['cost_eur']

    # Apply enabled/cost_exceeded flags
    total_cost = 0.0
    for i, block in enumerate(blocks_with_cost):
        if i in enabled_indices:
            block['enabled'] = True
            block['cost_exceeded'] = False
            total_cost += block['cost_eur']
        else:
            block['enabled'] = False
            block['cost_exceeded'] = True

    cost_limit_applied = len(enabled_indices) < len(blocks_with_cost)

    return {
        'blocks': blocks_with_cost,
        'total_cost': total_cost,
        'scheduled_cost': scheduled_cost,
        'cost_limit_applied': cost_limit_applied,
        'enabled_count': len(enabled_indices),
    }

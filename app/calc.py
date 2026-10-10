"""Electricity calculation and reduction planning logic."""
from typing import List, Dict, Any, Tuple


def calculate_monthly_kwh(watts: float, hours_per_day: float) -> float:
    """Calculates monthly electricity units (kWh) for an appliance.
    Formula: watts * hours_per_day * 30 / 1000
    """
    return round((float(watts) * float(hours_per_day) * 30.0) / 1000.0, 2)


def calculate_baseline(appliances: List[Dict[str, Any]]) -> float:
    """Calculates the baseline sum of monthly kWh across all appliances."""
    total = sum(calculate_monthly_kwh(a.get("watts", 0), a.get("hours_per_day", 0)) for a in appliances)
    return round(total, 2)


def generate_reduction_plan(appliances: List[Dict[str, Any]], target_units: float) -> Dict[str, Any]:
    """Generates an appliance reduction plan to achieve the target monthly units.
    - If need <= 0, returns the unchanged plan with message 'Already within target'.
    - Otherwise, sorts non-essential appliances by monthly_kwh descending,
      cutting each appliance's hours_per_day by up to 50% (never below 0)
      until need is covered.
    - If still short, gap_units is set to the remaining amount.
    """
    baseline_units = calculate_baseline(appliances)
    target = round(float(target_units), 2)
    need = round(baseline_units - target, 2)

    # Initialize plan items
    plan_items = []
    enriched_appliances = []

    for item in appliances:
        name = str(item.get("name", "Unknown Appliance")).strip()
        watts = float(item.get("watts", 0))
        hours = float(item.get("hours_per_day", 0))
        is_essential = bool(item.get("essential", False))
        m_kwh = calculate_monthly_kwh(watts, hours)

        enriched_appliances.append({
            "name": name,
            "watts": watts,
            "old_hours": hours,
            "new_hours": hours,
            "essential": is_essential,
            "monthly_kwh": m_kwh,
            "units_saved": 0.0
        })

    if need <= 0:
        return {
            "baseline_units": baseline_units,
            "target_units": target,
            "gap_units": 0.0,
            "items": [
                {
                    "name": a["name"],
                    "watts": a["watts"],
                    "old_hours": a["old_hours"],
                    "new_hours": a["old_hours"],
                    "units_saved": 0.0
                }
                for a in enriched_appliances
            ],
            "message": "Already within target"
        }

    # Sort non-essential appliances by monthly_kwh descending
    # Keep track of indices to modify in enriched_appliances
    non_essential_indices = [
        i for i, a in enumerate(enriched_appliances) if not a["essential"]
    ]
    non_essential_indices.sort(
        key=lambda i: enriched_appliances[i]["monthly_kwh"], reverse=True
    )

    remaining_need = need

    for idx in non_essential_indices:
        if remaining_need <= 0:
            break

        item = enriched_appliances[idx]
        old_hours = item["old_hours"]
        watts = item["watts"]

        if old_hours <= 0 or watts <= 0:
            continue

        # Max allowed reduction is 50% of old_hours
        max_reduction_hours = old_hours * 0.5
        max_saving_kwh = (watts * max_reduction_hours * 30.0) / 1000.0

        if max_saving_kwh <= 0:
            continue

        if remaining_need >= max_saving_kwh:
            # Cut by full 50%
            cut_hours = max_reduction_hours
            actual_saving = max_saving_kwh
        else:
            # Cut only the fraction needed
            # saving = watts * cut_hours * 30 / 1000 => cut_hours = saving * 1000 / (watts * 30)
            cut_hours = (remaining_need * 1000.0) / (watts * 30.0)
            cut_hours = min(cut_hours, max_reduction_hours)
            actual_saving = (watts * cut_hours * 30.0) / 1000.0

        new_hours = round(max(0.0, old_hours - cut_hours), 2)
        actual_units_saved = round((watts * (old_hours - new_hours) * 30.0) / 1000.0, 2)

        item["new_hours"] = new_hours
        item["units_saved"] = actual_units_saved
        remaining_need = round(remaining_need - actual_units_saved, 2)

    gap_units = round(max(0.0, remaining_need), 2)

    return {
        "baseline_units": baseline_units,
        "target_units": target,
        "gap_units": gap_units,
        "items": [
            {
                "name": a["name"],
                "watts": a["watts"],
                "old_hours": a["old_hours"],
                "new_hours": a["new_hours"],
                "units_saved": a["units_saved"]
            }
            for a in enriched_appliances
        ],
        "message": "Plan generated successfully" if gap_units == 0 else f"Target exceeded by {gap_units} units"
    }

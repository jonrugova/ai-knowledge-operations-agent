from datetime import date, timedelta


PRODUCTION_DAYS = 21
DHL_MIN_BUSINESS_DAYS = 3
DHL_MAX_BUSINESS_DAYS = 5


def add_business_days(start_date: date, business_days: int):
    current_date = start_date
    days_added = 0

    while days_added < business_days:
        current_date += timedelta(days=1)
        if current_date.weekday() < 5:
            days_added += 1

    return current_date


def calculate_delivery_timeline(order_date: str):
    if not isinstance(order_date, str):
        raise ValueError("order_date must be a string in YYYY-MM-DD format.")

    try:
        parsed_order_date = date.fromisoformat(order_date)
    except ValueError as error:
        raise ValueError(
            "order_date must be a valid date in YYYY-MM-DD format."
        ) from error

    if parsed_order_date.isoformat() != order_date:
        raise ValueError("order_date must use YYYY-MM-DD format.")

    production_ready_date = parsed_order_date + timedelta(
        days=PRODUCTION_DAYS
    )
    earliest_delivery_date = add_business_days(
        production_ready_date,
        DHL_MIN_BUSINESS_DAYS,
    )
    latest_delivery_date = add_business_days(
        production_ready_date,
        DHL_MAX_BUSINESS_DAYS,
    )

    return {
        "order_date": parsed_order_date.isoformat(),
        "production_days": PRODUCTION_DAYS,
        "production_ready_date": production_ready_date.isoformat(),
        "dhl_min_business_days": DHL_MIN_BUSINESS_DAYS,
        "dhl_max_business_days": DHL_MAX_BUSINESS_DAYS,
        "earliest_delivery_date": earliest_delivery_date.isoformat(),
        "latest_delivery_date": latest_delivery_date.isoformat(),
        "note": "Estimated timeline only. Delivery dates are not guaranteed.",
    }
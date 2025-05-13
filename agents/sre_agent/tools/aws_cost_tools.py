import boto3
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta, date
import asyncio
from concurrent.futures import ThreadPoolExecutor
import calendar
import logging

# Initialize the Cost Explorer client
cost_explorer = boto3.client("ce")

# Thread pool for running blocking boto3 operations
_thread_pool = ThreadPoolExecutor()

# Initialize a logger
logger = logging.getLogger(__name__)


async def _run_in_executor(func, *args, **kwargs):
    """Run a blocking function in a thread pool executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_thread_pool, lambda: func(*args, **kwargs))


def get_current_date_info() -> Dict[str, Any]:
    """
    Get current date information useful for cost analysis.

    Returns:
        Dict[str, Any]: Dictionary containing:
            - current_year: Current year as int
            - current_month: Current month as int (1-12)
            - current_month_name: Current month name (e.g., "January")
            - first_day_current_month: First day of current month (YYYY-MM-DD)
            - today_formatted: Today's date formatted (YYYY-MM-DD)
            - yesterday_formatted: Yesterday's date formatted (YYYY-MM-DD)
            - first_day_previous_month: First day of previous month (YYYY-MM-DD)
            - last_day_previous_month: Last day of previous month (YYYY-MM-DD)
    """
    today = datetime.now().date()

    # Current month's first day
    first_day_current_month = today.replace(day=1)

    # Previous month's last day is one day before current month's first day
    last_day_previous_month = first_day_current_month - timedelta(days=1)

    # Previous month's first day
    first_day_previous_month = last_day_previous_month.replace(day=1)

    # Yesterday
    yesterday = today - timedelta(days=1)

    return {
        # Don't return date objects directly - JSON can't serialize them
        "current_year": today.year,
        "current_month": today.month,
        "current_month_name": today.strftime("%B"),
        "first_day_current_month": first_day_current_month.strftime("%Y-%m-%d"),
        "today_formatted": today.strftime("%Y-%m-%d"),
        "yesterday_formatted": yesterday.strftime("%Y-%m-%d"),
        "first_day_previous_month": first_day_previous_month.strftime("%Y-%m-%d"),
        "last_day_previous_month": last_day_previous_month.strftime("%Y-%m-%d"),
    }


async def get_cost_for_period(
    start_date: str,
    end_date: str,
    granularity: str = "DAILY",
    metrics: List[str] = ["UnblendedCost"],
    group_by: Optional[List[Dict[str, str]]] = None,
    filter_expression: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Get AWS cost data for a specific time period with optional filtering and grouping.

    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        granularity (str): Time granularity (DAILY, MONTHLY, HOURLY)
        metrics (List[str]): Cost metrics to retrieve
        group_by (Optional[List[Dict[str, str]]]): Grouping dimensions
        filter_expression (Optional[Dict[str, Any]]): Filter expression for costs

    Returns:
        Dict: Cost data for the specified period
    """
    try:
        params = {
            "TimePeriod": {"Start": start_date, "End": end_date},
            "Granularity": granularity,
            "Metrics": metrics,
        }

        if group_by:
            params["GroupBy"] = group_by

        if filter_expression:
            params["Filter"] = filter_expression

        response = await _run_in_executor(cost_explorer.get_cost_and_usage, **params)

        return {
            "status": "success",
            "data": response,
            "period": {"start": start_date, "end": end_date},
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get cost data: {str(e)}",
            "period": {"start": start_date, "end": end_date},
        }


async def get_monthly_cost(
    year: int,
    month: int,
    group_by: Optional[List[Dict[str, str]]] = None,
    filter_expression: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Get AWS cost data for a specific month.

    Args:
        year (int): Year (e.g., 2025)
        month (int): Month (1-12)
        group_by (Optional[List[Dict[str, str]]]): Grouping dimensions
        filter_expression (Optional[Dict[str, Any]]): Filter expression for costs

    Returns:
        Dict: Cost data for the specified month
    """
    # Calculate the first and last day of the month
    first_day = date(year, month, 1)

    # Get the last day of the month
    _, last_day_of_month = calendar.monthrange(year, month)
    last_day = date(year, month, last_day_of_month)

    # Format dates as strings
    start_date = first_day.strftime("%Y-%m-%d")
    end_date = (last_day + timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )  # Add 1 day because end date is exclusive

    return await get_cost_for_period(
        start_date=start_date,
        end_date=end_date,
        granularity="DAILY",
        group_by=group_by,
        filter_expression=filter_expression,
    )


async def get_cost_excluding_services(
    start_date: str,
    end_date: str,
    excluded_services: List[str],
    granularity: str = "DAILY",
) -> Dict:
    """
    Get AWS cost data excluding specific services.

    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        excluded_services (List[str]): List of service names to exclude
        granularity (str): Time granularity (DAILY, MONTHLY, HOURLY)

    Returns:
        Dict: Cost data excluding the specified services
    """
    # Create a filter expression to exclude the specified services
    filter_expression = {
        "Not": {"Dimensions": {"Key": "SERVICE", "Values": excluded_services}}
    }

    return await get_cost_for_period(
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        filter_expression=filter_expression,
    )


async def get_cost_trend(
    months: int,
    granularity: str = "MONTHLY",
    filter_expression: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Get AWS cost trend for the last X months.

    Args:
        months (int): Number of months to analyze
        granularity (str): Time granularity (DAILY, MONTHLY)
        filter_expression (Optional[Dict[str, Any]]): Filter expression for costs

    Returns:
        Dict: Cost trend data for the specified period
    """
    # Calculate start and end dates
    end_date = datetime.now().date()
    start_date = end_date.replace(day=1) - timedelta(
        days=1
    )  # Last day of previous month
    start_date = (start_date.replace(day=1) - timedelta(days=1)).replace(
        day=1
    )  # First day of month before previous

    # Go back additional months
    start_date = (start_date - timedelta(days=(months - 2) * 30)).replace(day=1)

    # Format dates as strings
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = (end_date + timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )  # Add 1 day because end date is exclusive

    # Get cost data
    result = await get_cost_for_period(
        start_date=start_date_str,
        end_date=end_date_str,
        granularity=granularity,
        group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        filter_expression=filter_expression,
    )

    # Add trend analysis
    if result["status"] == "success":
        # Extract total costs per period for trend analysis
        time_periods = result["data"]["ResultsByTime"]
        total_by_period = []

        for period in time_periods:
            period_start = period["TimePeriod"]["Start"]
            period_end = period["TimePeriod"]["End"]

            # Check if Total exists and has any metrics
            if "Total" not in period or not period["Total"]:
                logger.warning(
                    f"No Total metrics found for period {period_start} to {period_end}"
                )
                total_by_period.append(
                    {"start": period_start, "end": period_end, "total": 0}
                )
                continue

            # Check which metric is available
            if "UnblendedCost" in period["Total"]:
                total = float(period["Total"]["UnblendedCost"]["Amount"])
            elif "BlendedCost" in period["Total"]:
                total = float(period["Total"]["BlendedCost"]["Amount"])
            elif "NetUnblendedCost" in period["Total"]:
                total = float(period["Total"]["NetUnblendedCost"]["Amount"])
            elif "NetAmortizedCost" in period["Total"]:
                total = float(period["Total"]["NetAmortizedCost"]["Amount"])
            else:
                # Try to get the first available metric, if any exist
                try:
                    first_metric = list(period["Total"].keys())[0]
                    total = float(period["Total"][first_metric]["Amount"])
                except (IndexError, KeyError):
                    # No metrics found, use 0
                    logger.warning(
                        f"No metrics found in Total for period {period_start} to {period_end}"
                    )
                    total = 0

            total_by_period.append(
                {"start": period_start, "end": period_end, "total": total}
            )

        # Calculate trend (percentage change between periods)
        trend_data = []
        for i in range(1, len(total_by_period)):
            current = total_by_period[i]["total"]
            previous = total_by_period[i - 1]["total"]

            if previous > 0:
                percent_change = ((current - previous) / previous) * 100
            else:
                percent_change = 0 if current == 0 else 100

            trend_data.append(
                {
                    "period": total_by_period[i]["start"]
                    + " to "
                    + total_by_period[i]["end"],
                    "percent_change": round(percent_change, 2),
                }
            )

        result["trend_analysis"] = trend_data

    return result


async def get_current_month_cost_excluding_days(
    days_to_exclude: int, filter_expression: Optional[Dict[str, Any]] = None
) -> Dict:
    """
    Get the current month's cost excluding the last X days.

    Args:
        days_to_exclude (int): Number of days to exclude from the end
        filter_expression (Optional[Dict[str, Any]]): Filter expression for costs

    Returns:
        Dict: Cost data for the current month excluding the specified days
    """
    # Calculate start and end dates
    today = datetime.now().date()
    first_day_of_month = today.replace(day=1)
    end_date = today - timedelta(days=days_to_exclude)

    # Format dates as strings
    start_date_str = first_day_of_month.strftime("%Y-%m-%d")
    end_date_str = (end_date + timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )  # Add 1 day because end date is exclusive

    return await get_cost_for_period(
        start_date=start_date_str,
        end_date=end_date_str,
        granularity="DAILY",
        filter_expression=filter_expression,
    )


async def get_average_daily_cost(
    start_date: str,
    end_date: str,
    include_weekends: bool = True,
    filter_expression: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Get the average daily AWS cost for a period, with option to include or exclude weekends.

    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        include_weekends (bool): Whether to include weekend days in the calculation
        filter_expression (Optional[Dict[str, Any]]): Filter expression for costs

    Returns:
        Dict: Average daily cost data
    """
    # Get daily cost data
    result = await get_cost_for_period(
        start_date=start_date,
        end_date=end_date,
        granularity="DAILY",
        filter_expression=filter_expression,
    )

    if result["status"] == "success":
        # Extract daily costs and filter by weekday/weekend as needed
        daily_costs = []
        weekend_costs = []
        weekday_costs = []

        for period in result["data"]["ResultsByTime"]:
            period_start = period["TimePeriod"]["Start"]

            # Check which metric is available
            if "UnblendedCost" in period["Total"]:
                cost = float(period["Total"]["UnblendedCost"]["Amount"])
            elif "BlendedCost" in period["Total"]:
                cost = float(period["Total"]["BlendedCost"]["Amount"])
            elif "NetUnblendedCost" in period["Total"]:
                cost = float(period["Total"]["NetUnblendedCost"]["Amount"])
            else:
                # Use the first available metric
                first_metric = list(period["Total"].keys())[0]
                cost = float(period["Total"][first_metric]["Amount"])

            # Check if the day is a weekend (Saturday=5, Sunday=6)
            day_date = datetime.strptime(period_start, "%Y-%m-%d").date()
            is_weekend = day_date.weekday() >= 5

            if is_weekend:
                weekend_costs.append(cost)
            else:
                weekday_costs.append(cost)

            if include_weekends or not is_weekend:
                daily_costs.append(cost)

        # Calculate averages
        avg_daily_cost = sum(daily_costs) / len(daily_costs) if daily_costs else 0
        avg_weekend_cost = (
            sum(weekend_costs) / len(weekend_costs) if weekend_costs else 0
        )
        avg_weekday_cost = (
            sum(weekday_costs) / len(weekday_costs) if weekday_costs else 0
        )

        result["average_daily_cost"] = round(avg_daily_cost, 2)
        result["average_weekend_cost"] = round(avg_weekend_cost, 2)
        result["average_weekday_cost"] = round(avg_weekday_cost, 2)
        result["days_included"] = len(daily_costs)
        result["weekend_days"] = len(weekend_costs)
        result["weekday_days"] = len(weekday_costs)

    return result


async def get_weekend_daily_cost(
    start_date: str, end_date: str, filter_expression: Optional[Dict[str, Any]] = None
) -> Dict:
    """
    Get the average daily AWS cost for weekends only.

    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        filter_expression (Optional[Dict[str, Any]]): Filter expression for costs

    Returns:
        Dict: Average weekend daily cost data
    """
    # Get daily cost data
    result = await get_cost_for_period(
        start_date=start_date,
        end_date=end_date,
        granularity="DAILY",
        filter_expression=filter_expression,
    )

    if result["status"] == "success":
        # Extract weekend costs
        weekend_costs = []
        weekend_dates = []

        for period in result["data"]["ResultsByTime"]:
            period_start = period["TimePeriod"]["Start"]

            # Check which metric is available
            if "UnblendedCost" in period["Total"]:
                cost = float(period["Total"]["UnblendedCost"]["Amount"])
            elif "BlendedCost" in period["Total"]:
                cost = float(period["Total"]["BlendedCost"]["Amount"])
            elif "NetUnblendedCost" in period["Total"]:
                cost = float(period["Total"]["NetUnblendedCost"]["Amount"])
            else:
                # Use the first available metric
                first_metric = list(period["Total"].keys())[0]
                cost = float(period["Total"][first_metric]["Amount"])

            # Check if the day is a weekend (Saturday=5, Sunday=6)
            day_date = datetime.strptime(period_start, "%Y-%m-%d").date()
            is_weekend = day_date.weekday() >= 5

            if is_weekend:
                weekend_costs.append(cost)
                weekend_dates.append(period_start)

        # Calculate average
        avg_weekend_cost = (
            sum(weekend_costs) / len(weekend_costs) if weekend_costs else 0
        )

        result["average_weekend_cost"] = round(avg_weekend_cost, 2)
        result["weekend_days"] = len(weekend_costs)
        result["weekend_dates"] = weekend_dates

    return result


async def get_weekday_daily_cost(
    start_date: str, end_date: str, filter_expression: Optional[Dict[str, Any]] = None
) -> Dict:
    """
    Get the average daily AWS cost for weekdays only.

    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        filter_expression (Optional[Dict[str, Any]]): Filter expression for costs

    Returns:
        Dict: Average weekday daily cost data
    """
    # Get daily cost data
    result = await get_cost_for_period(
        start_date=start_date,
        end_date=end_date,
        granularity="DAILY",
        filter_expression=filter_expression,
    )

    if result["status"] == "success":
        # Extract weekday costs
        weekday_costs = []
        weekday_dates = []

        for period in result["data"]["ResultsByTime"]:
            period_start = period["TimePeriod"]["Start"]

            # Check which metric is available
            if "UnblendedCost" in period["Total"]:
                cost = float(period["Total"]["UnblendedCost"]["Amount"])
            elif "BlendedCost" in period["Total"]:
                cost = float(period["Total"]["BlendedCost"]["Amount"])
            elif "NetUnblendedCost" in period["Total"]:
                cost = float(period["Total"]["NetUnblendedCost"]["Amount"])
            else:
                # Use the first available metric
                first_metric = list(period["Total"].keys())[0]
                cost = float(period["Total"][first_metric]["Amount"])

            # Check if the day is a weekday (Monday=0 to Friday=4)
            day_date = datetime.strptime(period_start, "%Y-%m-%d").date()
            is_weekday = day_date.weekday() < 5

            if is_weekday:
                weekday_costs.append(cost)
                weekday_dates.append(period_start)

        # Calculate average
        avg_weekday_cost = (
            sum(weekday_costs) / len(weekday_costs) if weekday_costs else 0
        )

        result["average_weekday_cost"] = round(avg_weekday_cost, 2)
        result["weekday_days"] = len(weekday_costs)
        result["weekday_dates"] = weekday_dates

    return result


async def get_most_expensive_account(start_date: str, end_date: str) -> Dict:
    """
    Get the most expensive AWS account within the master payer account.

    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format

    Returns:
        Dict: Information about the most expensive account
    """
    try:
        # Group by linked account
        group_by = [{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}]

        result = await get_cost_for_period(
            start_date=start_date,
            end_date=end_date,
            granularity="MONTHLY",
            group_by=group_by,
        )

        if result["status"] == "success":
            # Find the most expensive account
            most_expensive = {"account_id": None, "account_name": None, "cost": 0}

            for period in result["data"]["ResultsByTime"]:
                for group in period["Groups"]:
                    account_info = group["Keys"][
                        0
                    ]  # Format: "account_id (account_name)"

                    # Check which metric is available
                    if "UnblendedCost" in group["Metrics"]:
                        cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
                    elif "BlendedCost" in group["Metrics"]:
                        cost = float(group["Metrics"]["BlendedCost"]["Amount"])
                    elif "NetUnblendedCost" in group["Metrics"]:
                        cost = float(group["Metrics"]["NetUnblendedCost"]["Amount"])
                    else:
                        # Use the first available metric
                        first_metric = list(group["Metrics"].keys())[0]
                        cost = float(group["Metrics"][first_metric]["Amount"])

                    if cost > most_expensive["cost"]:
                        # Parse account ID and name
                        parts = account_info.split(" ", 1)
                        account_id = parts[0]
                        account_name = (
                            parts[1].strip("()") if len(parts) > 1 else "Unknown"
                        )

                        most_expensive = {
                            "account_id": account_id,
                            "account_name": account_name,
                            "cost": cost,
                        }

            result["most_expensive_account"] = most_expensive

        return result
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get most expensive account: {str(e)}",
            "period": {"start": start_date, "end": end_date},
        }


async def get_cost_by_service(
    start_date: str, end_date: str, granularity: str = "MONTHLY"
) -> Dict:
    """
    Get AWS costs grouped by service.

    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        granularity (str): Time granularity (DAILY, MONTHLY)

    Returns:
        Dict: Cost data grouped by service
    """
    # Group by service
    group_by = [{"Type": "DIMENSION", "Key": "SERVICE"}]

    return await get_cost_for_period(
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        group_by=group_by,
    )


async def get_cost_by_tag(
    start_date: str, end_date: str, tag_key: str, granularity: str = "MONTHLY"
) -> Dict:
    """
    Get AWS costs grouped by a specific tag.

    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        tag_key (str): The tag key to group by (without the 'tag:' prefix)
        granularity (str): Time granularity (DAILY, MONTHLY)

    Returns:
        Dict: Cost data grouped by the specified tag
    """
    # Group by tag
    group_by = [{"Type": "TAG", "Key": tag_key}]

    return await get_cost_for_period(
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        group_by=group_by,
    )


async def get_digital_cost_for_month(
    year: int, month: int, exclude_services: Optional[List[str]] = None
) -> Dict:
    """
    Get the cost of Digital for a specific month, with option to exclude services.

    Args:
        year (int): Year (e.g., 2025)
        month (int): Month (1-12)
        exclude_services (Optional[List[str]]): List of services to exclude from the cost

    Returns:
        Dict: Cost data for Digital for the specified month
    """
    # Create a filter for Digital (assuming it's identified by a specific tag)
    filter_expression = {"Tags": {"Key": "Environment", "Values": ["Digital"]}}

    # If services to exclude are provided, add them to the filter
    if exclude_services:
        filter_expression = {
            "And": [
                filter_expression,
                {"Not": {"Dimensions": {"Key": "SERVICE", "Values": exclude_services}}},
            ]
        }

    return await get_monthly_cost(
        year=year, month=month, filter_expression=filter_expression
    )


async def get_current_month_cost(
    filter_expression: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Get AWS cost data for the current month.

    This is a convenience function that automatically determines the current month
    and retrieves cost data without requiring manual date specification.

    Args:
        filter_expression (Optional[Dict[str, Any]]): Optional filter expression for costs

    Returns:
        Dict: Cost data for the current month
    """
    # Get current date information
    date_info = get_current_date_info()

    return await get_monthly_cost(
        year=date_info["current_year"],
        month=date_info["current_month"],
        filter_expression=filter_expression,
    )


async def get_previous_month_cost(
    filter_expression: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Get AWS cost data for the previous month.

    This is a convenience function that automatically determines the previous month
    and retrieves cost data without requiring manual date specification.

    Args:
        filter_expression (Optional[Dict[str, Any]]): Optional filter expression for costs

    Returns:
        Dict: Cost data for the previous month
    """
    # Get current date information
    date_info = get_current_date_info()

    # Calculate previous month
    if date_info["current_month"] == 1:
        # Previous month is December of previous year
        prev_month = 12
        prev_year = date_info["current_year"] - 1
    else:
        prev_month = date_info["current_month"] - 1
        prev_year = date_info["current_year"]

    return await get_monthly_cost(
        year=prev_year, month=prev_month, filter_expression=filter_expression
    )


async def get_last_n_months_trend(
    months: int = 3,
    granularity: str = "MONTHLY",
    filter_expression: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Get AWS cost trend for the last N months automatically using the current date.

    This is a convenience function that automatically determines the date range
    for the last N months and retrieves trend data.

    Args:
        months (int): Number of months to analyze (default: 3)
        granularity (str): Time granularity (DAILY, MONTHLY)
        filter_expression (Optional[Dict[str, Any]]): Filter expression for costs

    Returns:
        Dict: Cost trend data for the specified period
    """
    # Use the existing get_cost_trend function with the provided parameters
    return await get_cost_trend(
        months=months, granularity=granularity, filter_expression=filter_expression
    )


# Export all functions
__all__ = [
    "get_cost_for_period",
    "get_monthly_cost",
    "get_cost_excluding_services",
    "get_cost_trend",
    "get_current_month_cost_excluding_days",
    "get_average_daily_cost",
    "get_weekend_daily_cost",
    "get_weekday_daily_cost",
    "get_most_expensive_account",
    "get_cost_by_service",
    "get_cost_by_tag",
    "get_digital_cost_for_month",
    "get_current_date_info",
    "get_current_month_cost",
    "get_previous_month_cost",
    "get_last_n_months_trend",
]

"""
Intent dispatcher for the VW California AI Trip Planner.

Routes Gemini function calls to the appropriate atomic tools
in the tools/ layer.

See: architecture/chat_orchestration_sop.md
"""

import json

from tools.search_campings import search_campings
from tools.plan_route import plan_route
from tools.extract_exif import store_photo


# Registry of tool functions callable by the AI
TOOL_REGISTRY = {
    "search_campings": search_campings,
    "plan_route": plan_route,
    "upload_photos": store_photo,
}


def dispatch(function_name, arguments):
    """
    Dispatch a Gemini function call to the appropriate tool.

    Args:
        function_name (str): Name of the function to call.
        arguments (dict): Arguments extracted by Gemini.

    Returns:
        dict: Tool execution result.
    """
    if function_name not in TOOL_REGISTRY:
        return {
            "status": "error",
            "message": (
                f"Unknown function: '{function_name}'. "
                f"Available: {list(TOOL_REGISTRY.keys())}"
            ),
        }

    tool_fn = TOOL_REGISTRY[function_name]

    try:
        # Execute the tool with provided arguments
        result = tool_fn(**arguments)
        return result

    except TypeError as e:
        # Bad arguments passed to the function
        return {
            "status": "error",
            "message": (
                f"Invalid arguments for '{function_name}': {e}"
            ),
        }
    except Exception as e:
        # Self-healing: capture error for analysis
        return {
            "status": "error",
            "message": (
                f"Tool '{function_name}' failed: {e}"
            ),
        }


# ── Gemini Tool Definitions ────────────────────────────────
# These are the schema definitions passed to Gemini's
# Function Calling so it knows what tools are available.
# ────────────────────────────────────────────────────────────

GEMINI_TOOL_DEFINITIONS = [
    {
        "name": "search_campings",
        "description": (
            "Search for campgrounds near a given location. "
            "Filters by amenities, cost, and VW California "
            "vehicle compatibility."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {
                    "type": "number",
                    "description": "Latitude of search center.",
                },
                "lng": {
                    "type": "number",
                    "description": "Longitude of search center.",
                },
                "radius_km": {
                    "type": "number",
                    "description": (
                        "Search radius in kilometers. "
                        "Default: 50."
                    ),
                },
                "amenities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Required amenities: power, water, "
                        "wifi, showers, toilets, waste_disposal."
                    ),
                },
                "max_cost_eur": {
                    "type": "number",
                    "description": (
                        "Maximum cost per night in EUR."
                    ),
                },
                "vw_compatible": {
                    "type": "boolean",
                    "description": (
                        "Only show VW California compatible "
                        "campgrounds. Default: true."
                    ),
                },
            },
            "required": ["lat", "lng"],
        },
    },
    {
        "name": "plan_route",
        "description": (
            "Plan a multi-day driving route with campground "
            "stops. Generates daily schedules with waypoints "
            "and driving time estimates."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "lat": {"type": "number"},
                        "lng": {"type": "number"},
                    },
                    "required": ["label", "lat", "lng"],
                    "description": "Starting location.",
                },
                "destination": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "lat": {"type": "number"},
                        "lng": {"type": "number"},
                    },
                    "required": ["label", "lat", "lng"],
                    "description": "Ending location.",
                },
                "num_days": {
                    "type": "integer",
                    "description": "Number of travel days.",
                },
                "start_date": {
                    "type": "string",
                    "description": (
                        "Trip start date in YYYY-MM-DD format."
                    ),
                },
                "max_daily_drive_hours": {
                    "type": "number",
                    "description": (
                        "Maximum driving hours per day. "
                        "Default: 6."
                    ),
                },
                "preferred_amenities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Preferred camping amenities."
                    ),
                },
                "budget_per_night_eur": {
                    "type": "number",
                    "description": (
                        "Maximum nightly budget in EUR."
                    ),
                },
            },
            "required": [
                "origin", "destination", "num_days",
                "start_date",
            ],
        },
    },
    {
        "name": "get_trip_summary",
        "description": (
            "Retrieve the current trip overview, including "
            "all daily schedules, campgrounds, and driving "
            "statistics."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "trip_id": {
                    "type": "string",
                    "description": "UUID of the trip.",
                },
            },
            "required": ["trip_id"],
        },
    },
]

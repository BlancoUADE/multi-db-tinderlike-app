"""
PostgreSQL domain package.
"""

from .schema import ensure_postgres_schema
from .queries import fetch_user, list_users, ensure_user_exists, view_user_profile, get_match_messages
from .users import register_user, create_interest, assign_interest, add_photo
from .interactions import create_like, block_user, create_match, send_message, is_blocked
from .events import create_event, attend_event, add_holiday, ensure_event_exists
from .maintenance import reset_all_databases

__all__ = [
	"ensure_postgres_schema",
	"fetch_user",
	"list_users",
	"ensure_user_exists",
	"view_user_profile",
	"get_match_messages",
	"register_user",
	"create_interest",
	"assign_interest",
	"add_photo",
	"create_like",
	"block_user",
	"create_match",
	"send_message",
	"is_blocked",
	"create_event",
	"attend_event",
	"add_holiday",
	"ensure_event_exists",
	"reset_all_databases",
]

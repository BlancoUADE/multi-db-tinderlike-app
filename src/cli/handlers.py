"""
Handlers de opciones del menú CLI
Importa funciones de main_monolithic mientras se refactoriza
"""

import importlib.util
import sys
from pathlib import Path

# Cargar main_monolithic dinámicamente desde scripts/
scripts_path = Path(__file__).parent.parent.parent / "scripts"
spec = importlib.util.spec_from_file_location("main_monolithic", scripts_path / "main_monolithic.py")
main_mono = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_mono)

# Re-exportar todas las funciones de handlers
register_user = main_mono.register_user
create_interest = main_mono.create_interest
assign_interest = main_mono.assign_interest
add_photo = main_mono.add_photo
create_like = main_mono.create_like
send_message = main_mono.send_message
block_user = main_mono.block_user
create_event = main_mono.create_event
attend_event = main_mono.attend_event
list_current_users = main_mono.list_current_users
view_user_profile = main_mono.view_user_profile
view_likes = main_mono.view_likes
view_matches = main_mono.view_matches
view_messages = main_mono.view_messages
view_events = main_mono.view_events
view_notifications = main_mono.view_notifications
run_analytics = main_mono.run_analytics
add_holiday = main_mono.add_holiday
seed_demo_data = main_mono.seed_demo_data
reset_all_databases = main_mono.reset_all_databases

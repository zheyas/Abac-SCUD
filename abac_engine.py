import datetime
from models.policy import get_by_role_building
from models.building import get_all

def check_access(user, building_id, policies_cache=None):
    # Получаем здание
    buildings = get_all()
    building = next((b for b in buildings if b["id"] == building_id), None)
    if not building: return False
    if building["is_accessible_to_all"]: return True
    if not user.get("is_active", True): return False

    # Политики
    pols = get_by_role_building(user["role_id"], building_id)
    now = datetime.datetime.now()
    ctx_time = now.time()
    ctx_day = now.strftime("%a")

    for p in pols:
        if p["requires_shift_active"] and user["shift_status"] != "active": continue
        days = [d.strip() for d in p["days_allowed"].split(",")]
        if "All" not in days and ctx_day not in days: continue
        try:
            t_start = datetime.datetime.strptime(p["time_start"], "%H:%M").time()
            t_end = datetime.datetime.strptime(p["time_end"], "%H:%M").time()
            if t_start <= ctx_time <= t_end:
                return True
        except ValueError: continue
    return False
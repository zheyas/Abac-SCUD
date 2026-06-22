import datetime

from models import Building, Policy, User


def _parse_time(value):
    return datetime.datetime.strptime(value, "%H:%M").time()


def _day_allowed(days_value, day_name):
    days = [day.strip() for day in (days_value or "").split(",") if day.strip()]
    return "All" in days or day_name in days


def is_building_open(building, context_datetime=None):
    """Проверяет собственный режим работы здания, включая ночные интервалы."""
    now = context_datetime or datetime.datetime.now().astimezone()
    if building.get("is_24_hours"):
        return _day_allowed(building.get("open_days", "All"), now.strftime("%a"))

    try:
        opening = _parse_time(building.get("open_time") or "08:00")
        closing = _parse_time(building.get("close_time") or "20:00")
    except (TypeError, ValueError):
        return False

    current_time = now.time().replace(tzinfo=None)
    if opening <= closing:
        return _day_allowed(building.get("open_days"), now.strftime("%a")) and opening <= current_time <= closing

    # Например, 20:00–06:00: после полуночи учитывается предыдущий рабочий день.
    if current_time >= opening:
        return _day_allowed(building.get("open_days"), now.strftime("%a"))
    if current_time <= closing:
        previous_day = (now - datetime.timedelta(days=1)).strftime("%a")
        return _day_allowed(building.get("open_days"), previous_day)
    return False


def get_building_schedule_label(building):
    if building.get("is_24_hours"):
        return "Круглосуточно"
    return f"{building.get('open_time', '08:00')}–{building.get('close_time', '20:00')}"


def evaluate_access(user, building_id, context_datetime=None):
    building = Building.get_by_id(building_id)
    now = context_datetime or datetime.datetime.now().astimezone()
    if not building:
        return {
            "access": False, "building_open": False, "status": "denied",
            "reason": "Объект не найден", "schedule": "—"
        }

    user = dict(user)
    user["shift_status"] = User.get_effective_shift_status(user, now)
    schedule = get_building_schedule_label(building)
    building_open = is_building_open(building, now)
    if not building_open:
        return {
            "access": False, "building_open": False, "status": "closed",
            "reason": "Закрыто по графику", "schedule": schedule,
            "source": "building", "rule_id": None, "rule_name": None
        }
    if not user.get("is_active", True):
        return {
            "access": False, "building_open": True, "status": "denied",
            "reason": "Учётная запись заблокирована", "schedule": schedule,
            "source": "account", "rule_id": None, "rule_name": None
        }

    policies = Policy.get_for_user_building(user["role_id"], user["id"], building_id)
    shift_blocked = False
    schedule_blocked = False
    current_time = now.time().replace(tzinfo=None)
    current_day = now.strftime("%a")

    matching_personal = []
    matching_role = []
    for policy in policies:
        if policy["requires_shift_active"] and user["shift_status"] != "active":
            shift_blocked = True
            continue
        if not _day_allowed(policy["days_allowed"], current_day):
            schedule_blocked = True
            continue
        try:
            start = _parse_time(policy["time_start"])
            end = _parse_time(policy["time_end"])
        except (TypeError, ValueError):
            schedule_blocked = True
            continue
        within_window = start <= current_time <= end if start <= end else current_time >= start or current_time <= end
        if within_window:
            (matching_personal if policy.get("user_id") else matching_role).append(policy)
            continue
        schedule_blocked = True

    def decision_from_rules(rules, source):
        if not rules:
            return None
        rule = next((item for item in rules if item.get("effect") == "deny"), rules[0])
        allowed = rule.get("effect") != "deny"
        return {
            "access": allowed,
            "building_open": True,
            "status": "available" if allowed else "denied",
            "reason": "Разрешено персональным правилом" if allowed and source == "user"
                      else "Запрещено персональным правилом" if source == "user"
                      else "Разрешено правилом роли" if allowed
                      else "Запрещено правилом роли",
            "schedule": schedule,
            "source": source,
            "rule_id": rule["id"],
            "rule_name": rule.get("name") or f"Правило #{rule['id']}"
        }

    personal_decision = decision_from_rules(matching_personal, "user")
    if personal_decision:
        return personal_decision

    if building.get("is_accessible_to_all"):
        return {
            "access": True, "building_open": True, "status": "available",
            "reason": "Общий доступ", "schedule": schedule,
            "source": "building", "rule_id": None, "rule_name": "Общий доступ"
        }

    role_decision = decision_from_rules(matching_role, "role")
    if role_decision:
        return role_decision

    if shift_blocked:
        reason = "Требуется активная смена"
    elif schedule_blocked:
        reason = "Вне времени политики"
    else:
        reason = "Нет подходящей политики"
    return {
        "access": False, "building_open": True, "status": "denied",
        "reason": reason, "schedule": schedule,
        "source": "policy", "rule_id": None, "rule_name": None
    }


def check_access(user, building_id, context_datetime=None):
    return evaluate_access(user, building_id, context_datetime)["access"]

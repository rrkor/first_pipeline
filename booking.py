import os
import pprint
from datetime import datetime, timedelta

import tables_db
from tables_db import BOOKING_DURATION_MIN, BOOKINGS, OPENING_HOURS, TABLES

DB_PATH = tables_db.__file__


def _parse(date: str, time: str) -> datetime:
    return datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")


def _digits(phone: str) -> str:
    # Последние 10 цифр: "8 (999) 111-22-33" и "+7 999 111 22 33" — один номер
    return "".join(c for c in phone if c.isdigit())[-10:]


def _validate_slot(date: str, time: str) -> str | None:
    try:
        start = _parse(date, time)
    except ValueError:
        return "Неверный формат. Дата: ГГГГ-ММ-ДД, время: ЧЧ:ММ"
    if start < datetime.now():
        return "Нельзя бронировать на прошедшее время"
    open_ = _parse(date, OPENING_HOURS["open"])
    close = _parse(date, OPENING_HOURS["close"])
    if start < open_ or start + timedelta(minutes=BOOKING_DURATION_MIN) > close:
        last = (close - timedelta(minutes=BOOKING_DURATION_MIN)).strftime("%H:%M")
        return (f"Работаем с {OPENING_HOURS['open']} до {OPENING_HOURS['close']}, "
                f"бронь длится {BOOKING_DURATION_MIN} мин — последнее время начала {last}")
    return None


def _is_table_free(table_id: int, date: str, time: str) -> bool:
    start = _parse(date, time)
    end = start + timedelta(minutes=BOOKING_DURATION_MIN)
    for b in BOOKINGS:
        if b["table_id"] != table_id or b["date"] != date:
            continue
        b_start = _parse(b["date"], b["time"])
        b_end = b_start + timedelta(minutes=BOOKING_DURATION_MIN)
        if start < b_end and b_start < end:
            return False
    return True


def _free_tables(date: str, time: str, guests: int) -> list[int]:
    # Сначала самые маленькие подходящие столы, чтобы не отдавать большой стол паре гостей
    fitting = sorted((t for t in TABLES if TABLES[t]["seats"] >= guests),
                     key=lambda t: TABLES[t]["seats"])
    return [t for t in fitting if _is_table_free(t, date, time)]


def _save() -> None:
    content = (
        "# Файл перезаписывается автоматически при создании/отмене брони (booking.py).\n"
        "# TABLES можно править руками, BOOKINGS — лучше через агента.\n\n"
        f"OPENING_HOURS = {pprint.pformat(OPENING_HOURS, sort_dicts=False)}\n\n"
        f"BOOKING_DURATION_MIN = {BOOKING_DURATION_MIN}\n\n"
        f"TABLES = {pprint.pformat(TABLES, sort_dicts=False)}\n\n"
        f"BOOKINGS = {pprint.pformat(BOOKINGS, sort_dicts=False)}\n"
    )
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, DB_PATH)


def _validate_guests(guests: int) -> str | None:
    if guests < 1:
        return "Количество гостей должно быть не меньше 1"
    max_seats = max(t["seats"] for t in TABLES.values())
    if guests > max_seats:
        return f"Самый большой стол на {max_seats} человек"
    return None


def check_availability(date: str, time: str, guests: int) -> dict:
    if error := _validate_slot(date, time) or _validate_guests(guests):
        return {"error": error}
    free = _free_tables(date, time, guests)
    return {
        "date": date,
        "time": time,
        "guests": guests,
        "available": bool(free),
        "free_tables": [{"table_id": t, **TABLES[t]} for t in free],
    }


def create_booking(date: str, time: str, guests: int, name: str, phone: str,
                   table_id: int | None = None) -> dict:
    if error := _validate_slot(date, time) or _validate_guests(guests):
        return {"error": error}
    # Без имени и телефона бронь потом не найти и клиенту не перезвонить
    if not name.strip():
        return {"error": "Нужно имя клиента"}
    if len("".join(c for c in phone if c.isdigit())) < 10:
        return {"error": "Нужен телефон клиента, минимум 10 цифр"}
    free = _free_tables(date, time, guests)
    if table_id is None:
        if not free:
            return {"error": "На это время нет свободных столов под такое число гостей"}
        table_id = free[0]
    elif table_id not in TABLES:
        return {"error": f"Стола {table_id} не существует"}
    elif table_id not in free:
        return {"error": f"Стол {table_id} занят или слишком мал",
                "free_tables": [{"table_id": t, **TABLES[t]} for t in free]}

    booking = {
        "id": max((b["id"] for b in BOOKINGS), default=0) + 1,
        "table_id": table_id,
        "date": date,
        # "9:5" -> "09:05": одинаковый вид времени во всех записях
        "time": _parse(date, time).strftime("%H:%M"),
        "guests": guests,
        "name": name.strip(),
        "phone": phone.strip(),
    }
    BOOKINGS.append(booking)
    _save()
    return {"status": "created", "booking": booking}


def find_bookings(date: str | None = None, name: str | None = None,
                  phone: str | None = None) -> dict:
    result = BOOKINGS
    if date:
        result = [b for b in result if b["date"] == date]
    if name:
        result = [b for b in result if name.lower() in b["name"].lower()]
    if phone:
        result = [b for b in result if _digits(b["phone"]) == _digits(phone)]
    return {"bookings": result}


def cancel_booking(booking_id: int) -> dict:
    for i, b in enumerate(BOOKINGS):
        if b["id"] == booking_id:
            BOOKINGS.pop(i)
            _save()
            return {"status": "cancelled", "booking": b}
    return {"error": f"Бронь #{booking_id} не найдена"}

import json
import os
from datetime import datetime

from dotenv import load_dotenv

from openai import OpenAI

from booking import cancel_booking, check_availability, create_booking, find_bookings
from pizza_db import PIZZA_DB


load_dotenv()

client = OpenAI(base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENAI_API_KEY"))

model = "openrouter/free"

SYSTEM_PROMPT = f"""Ты опытный менеджер-официант пиццерии и помогаешь коллегам: новичкам и текущим сотрудникам.
Говори от первого лица, живо и по-человечески, как коллега в зале: обращайся на «ты», начинай с короткой реакции
(«Сейчас гляну», «Смотри», «Готово»), а потом давай суть. Без канцелярита и без упоминаний, что ты бот или ИИ.
Меню: про конкретную пиццу узнавай через get_pizza_info, а на вопросы «что есть», «что посоветуешь»,
«что без мяса» и т.п. сначала смотри всё меню через get_menu. Рассказывай о пиццах как официант гостю:
аппетитно, своими словами (не сухим списком), обязательно с ценой, и подскажи, кому она зайдёт.
Советуй только то, что есть в меню, — никаких выдуманных пицц и ингредиентов.
Брони столов: перед ответом о свободных местах всегда вызывай check_availability.
Для брони нужны дата, время, число гостей, имя и телефон клиента — если чего-то нет, спроси.
Для отмены сначала найди бронь через find_bookings, затем отменяй по id через cancel_booking.
Если нашлось несколько подходящих броней — уточни у сотрудника, какую отменять.
Сегодня {datetime.now().strftime('%Y-%m-%d, %A')}. Даты передавай в формате ГГГГ-ММ-ДД, время ЧЧ:ММ."""

tools = [
    {
        "type": "function",
        "name": "get_pizza_info",
        "description": "Должен выписывать рецептуру и цену пиццы.",
        "parameters": {
            "type": "object",
            "properties": {
                "sign": {
                    "type": "string",
                    "description": "Название пиццы",
                },
            },
            "required": ["sign"],
        },
    },
    {
        "type": "function",
        "name": "get_menu",
        "description": "Возвращает всё меню пицц с ценами и составом — для рекомендаций и подбора.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "check_availability",
        "description": "Проверяет, есть ли свободные столы на дату и время для заданного числа гостей.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Дата, ГГГГ-ММ-ДД"},
                "time": {"type": "string", "description": "Время начала, ЧЧ:ММ"},
                "guests": {"type": "integer", "description": "Количество гостей"},
            },
            "required": ["date", "time", "guests"],
        },
    },
    {
        "type": "function",
        "name": "create_booking",
        "description": "Бронирует стол. Если table_id не указан, выбирается самый подходящий свободный.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Дата, ГГГГ-ММ-ДД"},
                "time": {"type": "string", "description": "Время начала, ЧЧ:ММ"},
                "guests": {"type": "integer", "description": "Количество гостей"},
                "name": {"type": "string", "description": "Имя клиента"},
                "phone": {"type": "string", "description": "Телефон клиента"},
                "table_id": {"type": "integer", "description": "Конкретный стол, если клиент просил"},
            },
            "required": ["date", "time", "guests", "name", "phone"],
        },
    },
    {
        "type": "function",
        "name": "find_bookings",
        "description": "Ищет брони по дате, имени и/или телефону. Без параметров — все брони.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Дата, ГГГГ-ММ-ДД"},
                "name": {"type": "string", "description": "Имя клиента"},
                "phone": {"type": "string", "description": "Телефон клиента"},
            },
        },
    },
    {
        "type": "function",
        "name": "cancel_booking",
        "description": "Отменяет (удаляет) бронь по её id.",
        "parameters": {
            "type": "object",
            "properties": {
                "booking_id": {"type": "integer", "description": "id брони из find_bookings"},
            },
            "required": ["booking_id"],
        },
    },
]


def get_pizza_info(sign: str) -> dict:
    name = sign.lower().strip()
    if name in PIZZA_DB:
        return {"name": name, **PIZZA_DB[name]}
    return {"error": f"Пицца '{name}' не найдена в меню"}


def get_menu() -> dict:
    return {"menu": [{"name": name, **info} for name, info in PIZZA_DB.items()]}


TOOL_HANDLERS = {
    "get_pizza_info": get_pizza_info,
    "get_menu": get_menu,
    "check_availability": check_availability,
    "create_booking": create_booking,
    "find_bookings": find_bookings,
    "cancel_booking": cancel_booking,
}

MAX_STEPS = 8


def call_tool(name: str, arguments: str) -> dict:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {"error": f"Неизвестный инструмент {name}"}
    try:
        return handler(**json.loads(arguments or "{}"))
    except (TypeError, ValueError) as e:
        return {"error": f"Неверные аргументы: {e}"}


def run_agent(inputs: list) -> str:
    for _ in range(MAX_STEPS):
        response = client.responses.create(model=model, input=inputs, tools=tools)
        # function_call должны попасть в историю, иначе function_call_output не к чему привязать
        inputs += response.output

        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            return response.output_text.strip()

        for item in calls:
            result = call_tool(item.name, item.arguments)
            inputs.append(
                {
                    "type": "function_call_output",
                    "call_id": item.call_id,
                    "output": json.dumps(result, ensure_ascii=False),
                }
            )
    return "Не удалось получить ответ — слишком много шагов."


if __name__ == "__main__":
    inputs = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("Менеджер: Привет! Я менеджер зала. Спрашивай про меню, свободные столы или брони — помогу.")
    print("(пустая строка — выход)")
    while question := input("Ты: ").strip():
        inputs.append({"role": "user", "content": question})
        print(f"Менеджер: {run_agent(inputs)}")

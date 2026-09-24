import json
import os

from dotenv import load_dotenv

from openai import OpenAI

from pizza_db import PIZZA_DB


load_dotenv()
 
client= OpenAI(base_url="https://openrouter.ai/api/v1",
               api_key=os.getenv("OPENAI_API_KEY"))

model = "openrouter/free"
inputs= [
    {"role": "system", "content": "Ответ должен быть как от официанта. Не выходя за рамки данного тебе меню"},
    {"role": "user", "content": "Что в вегетарианской пицце?"}
]

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
]
def get_pizza_info(name: str) -> dict:
    name = name.lower().strip()
    if name in PIZZA_DB:
        return {"name": name, **PIZZA_DB[name]}
    return {"error": f"Пицца '{name}' не найдена в меню"}

response = client.responses.create(model=model,
                                   input=inputs,
                                   tools=tools)
inputs+= response.output_text
for item in response.output:
    if item.type != "function_call":
        continue

    if item.name == "get_pizza_info":
        args = json.loads(item.arguments)
        result = get_pizza_info(args["sign"])

        inputs.append(
            {
                "type": "function_call_output",
                "call_id": item.call_id,
                "output": json.dumps(result, ensure_ascii=False),
            }
        )
final = client.responses.create(model=model,
                                   input=inputs,
                                   tools=tools)

print(final.output_text)


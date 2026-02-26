import json
import os

from dotenv import find_dotenv, load_dotenv
from qwen_agent.llm import get_chat_model

from src.function_calling.util.function import FunctionTool

_ = load_dotenv(find_dotenv())

llm = get_chat_model({
    "model": "qwen-plus",
    "model_server": "https://dashscope.aliyuncs.com/compatible-mode/v1",  # 通义千问turbo
    "api_key": os.getenv("api_key"),
    "generate_cfg": {
        "extra_body": {
            "chat_template_kwargs": {"enable_thinking": False}  # default to True
        }
    }
})

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_temperature",
            "description": "Get current temperature at a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": 'The location to get the temperature for, in the format "City, State, Country".',
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": 'The unit to return the temperature in. Defaults to "celsius".',
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_temperature_date",
            "description": "Get temperature at a location and date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": 'The location to get the temperature for, in the format "City, State, Country".',
                    },
                    "date": {
                        "type": "string",
                        "description": 'The date to get the temperature for, in the format "Year-Month-Day".',
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": 'The unit to return the temperature in. Defaults to "celsius".',
                    },
                },
                "required": ["location", "date"],
            },
        },
    },
]
MESSAGES = [
    {"role": "user",
     "content": "What's the temperature in San Francisco now? How about tomorrow? Current Date: 2024-09-30."},
]

messages = MESSAGES[:]
functions = [tool["function"] for tool in TOOLS]

for responses in llm.chat(
        messages=messages,
        functions=functions,
):
    pass
# 更新上下文
messages.extend(responses)


for message in responses:
    if fn_call := message.get("function_call", None):
        fn_name: str = fn_call['name']
        fn_args: dict = json.loads(fn_call["arguments"])

        # 自动执行并更新上下文
        fn_res: str = json.dumps(FunctionTool.get_function_by_name(fn_name)(**fn_args))
        messages.append({
            "role": "function", # 将role更新为function，表示是function calling
            "name": fn_name,
            "content": fn_res,
        })

for responses in llm.chat(messages=messages, functions=functions):
    pass
messages.extend(responses)

print(messages)
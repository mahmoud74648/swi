from fastapi import FastAPI
from pydantic import BaseModel
import requests
from openai import OpenAI

app = FastAPI()
client = OpenAI(api_key="YOUR_API_KEY")


# Request model
class UserRequest(BaseModel):
    message: str


# Tool definition (function calling)
tools = [
    {
        "type": "function",
        "function": {
            "name": "update_switch_port_vlan",
            "description": "Change VLAN of a switch port",
            "parameters": {
                "type": "object",
                "properties": {
                    "switch": {"type": "string"},
                    "floor": {"type": "string"},
                    "port": {"type": "integer"},
                    "new_vlan": {"type": "integer"}
                },
                "required": ["switch", "port", "new_vlan"]
            }
        }
    }
]


@app.post("/chat")
def chat(req: UserRequest):

    response = client.chat.completions.create(
        model="gpt-5.3",
        messages=[
            {
                "role": "system",
                "content": "You are a network assistant that understands Arabic and English and converts requests into actions."
            },
            {"role": "user", "content": req.message}
        ],
        tools=tools
    )

    msg = response.choices[0].message

    # If AI decided to call function
    if msg.tool_calls:
        tool_call = msg.tool_calls[0]
        args = eval(tool_call.function.arguments)

        # Call your backend
        api_url = "http://172.20.70.34:8088/api/switch/port/update-vlan"

        res = requests.post(
            api_url,
            json=args,
            auth=("admin", "password")
        )

        return {
            "action": args,
            "result": res.json()
        }

    return {"message": msg.content}
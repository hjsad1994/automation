from openai import OpenAI

client = OpenAI(
    api_key="sk-orbit-7a0bc49f360c570cbaa92b7692e8b5ae",
    base_url="https://api.orbit-provider.com/cliproxy-api/api/provider/agy"
)

response = client.chat.completions.create(
    model="claude-sonnet-4-5-20250929",
    messages=[
        {"role": "user", "content": "Hello! bạn là gì"}
    ]
)

print(response.choices[0].message.content)
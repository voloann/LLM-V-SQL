from openai import OpenAI

client = OpenAI(
    api_key="lm-studio",
    base_url="http://127.0.0.1:1234/v1"
)

response = client.chat.completions.create(
    model="local-model",
    messages=[
        {
            "role": "user",
            "content": "Giải thích về Machine Learning bằng tiếng Việt"
        }
    ],
    temperature=0.2
)

print(response.choices[0].message.content)
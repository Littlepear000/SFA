from imf_openai_helper import get_client

# Get authenticated client (handles all auth/caching automatically)
client = get_client()

# Choose your model
model = "gpt-5.6-terra"

# Responses API
resp = client.responses.create(
    model=model,
    input="Who were the founders of Microsoft?",
)
print(resp.output_text)

# Chat Completions
chat = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Who were the founders of Microsoft?"}],
)
print(chat.choices[0].message.content)
import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("NVIDIA_API_KEY")

base_url = "https://integrate.api.nvidia.com/v1"

models_to_test = [
    "meta/llama-3.1-405b-instruct",
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.1-8b-instruct",
    "nvidia/llama-3.2-11b-vision-instruct",
    "meta/llama-3.2-11b-vision-instruct"
]

for model in models_to_test:
    print(f"Testing Model: {model}")
    try:
        data = {
            "model": model,
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 10
        }
        resp = requests.post(f"{base_url}/chat/completions", headers={"Authorization": f"Bearer {api_key}"}, json=data)
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Response: {resp.text[:200]}")
        else:
            print(f"Response: [SUCCESS]")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 20)

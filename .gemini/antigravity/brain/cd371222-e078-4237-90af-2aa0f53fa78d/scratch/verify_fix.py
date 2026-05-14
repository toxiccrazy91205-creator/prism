import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("NVIDIA_API_KEY")
base_url = "https://integrate.api.nvidia.com/v1"

models_to_test = [
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.2-11b-vision-instruct"
]

for model in models_to_test:
    print(f"Verifying Model: {model}")
    try:
        data = {
            "model": model,
            "messages": [{"role": "user", "content": "Test."}],
            "max_tokens": 5
        }
        resp = requests.post(f"{base_url}/chat/completions", headers={"Authorization": f"Bearer {api_key}"}, json=data)
        if resp.status_code == 200:
            print(f" [OK] {model}")
        else:
            print(f" [FAILED] {model} - Status: {resp.status_code}, Resp: {resp.text[:100]}")
    except Exception as e:
        print(f" [ERROR] {model} - {e}")

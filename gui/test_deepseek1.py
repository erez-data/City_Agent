import os
import requests
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
API_KEY = os.getenv("DEEPSEEK_API_KEY")

def ask_deepseek(prompt):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 1500,
        "top_p": 0.9,
        "frequency_penalty": 0.2,
        "presence_penalty": 0.1
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"DeepSeek API connection error: {str(e)}")
        return {
            "choices": [{
                "message": {
                    "content": "⚠️ Sistem geçici olarak hizmet veremiyor. Lütfen tekrar deneyin."
                }
            }]
        }
    except Exception as e:
        print(f"DeepSeek API processing error: {str(e)}")
        return {
            "choices": [{
                "message": {
                    "content": "⚠️ Analiz sırasında beklenmedik bir hata oluştu."
                }
            }]
        }

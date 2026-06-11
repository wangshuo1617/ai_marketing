import requests
import os
from dotenv import load_dotenv

load_dotenv()


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def llm_reply(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float | None = None,
) -> str:
    api_key = os.getenv("AI_API_KEY") or os.getenv("147API_KEY")
    if not api_key:
        raise ValueError("AI_API_KEY is not set. Please configure it in your .env file.")

    base_url = os.getenv("AI_BASE_URL", "https://api.147ai.cn").rstrip("/")
    model = os.getenv("AI_MODEL", "gemini-2.5-pro-thinking-8192")
    timeout = int(os.getenv("AI_REQUEST_TIMEOUT", "120"))
    if temperature is None:
        temperature = _float_env("AI_TEMPERATURE", 0.4)

    url = f"{base_url}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    data = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
    }
    response = requests.post(url, headers=headers, json=data, timeout=timeout)
    response.raise_for_status()

    response_data = response.json()
    answer = response_data["choices"][0]["message"].get("content", "")
    answer = answer.split("</think>")[-1].strip()

    return answer


def gemini_reply(prompt: str) -> str:
    return llm_reply(prompt)

if __name__ == "__main__":
    prompt = "你好，我是小明，请用中文回答我一个问题"
    answer = llm_reply(prompt)
    print(answer)
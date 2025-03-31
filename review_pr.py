import os
import requests

def get_diff():
    os.system("git fetch origin master:master")  # Asegúrate de obtener la rama base
    pr_diff = os.popen("git diff master").read()
    return pr_diff

def analyze_with_llm(diff):
    api_key = os.getenv("OPENAI_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "gpt-4",  # Cambia según el modelo que uses
        "messages": [
            {"role": "system", "content": "Eres un revisor de código experto."},
            {"role": "user", "content": f"Revisa este código: \n{diff}"}
        ]
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
    return response.json()["choices"][0]["message"]["content"]

if __name__ == "__main__":
    diff = get_diff()
    review = analyze_with_llm(diff)
    print("Revisión del LLM:")
    print(review)

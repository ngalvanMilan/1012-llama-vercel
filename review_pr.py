import os
import requests
import json
import sys

def get_pr_info():
    # Get PR number from GitHub context
    github_event_path = os.environ.get('GITHUB_EVENT_PATH')
    if not github_event_path:
        print("Error: GITHUB_EVENT_PATH not set")
        sys.exit(1)
    
    with open(github_event_path, 'r') as f:
        event = json.load(f)
    
    pr_number = event.get('pull_request', {}).get('number')
    repo_full_name = event.get('repository', {}).get('full_name')
    
    if not pr_number or not repo_full_name:
        print("Error: Could not get PR number or repository name")
        sys.exit(1)
    
    return pr_number, repo_full_name

def get_diff():
    pr_diff = os.popen("git diff origin/master").read()
    return pr_diff

def analyze_with_llm(diff):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set")
        sys.exit(1)
        
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "gpt-4",  # Cambia según el modelo que uses
        "messages": [
            {"role": "system", "content": "Eres un revisor de código experto. Debes ser conciso pero detallado, proporcionando recomendaciones para mejorar el código, identificar posibles bugs y sugerir buenas prácticas."},
            {"role": "user", "content": f"Revisa este código y proporciona un análisis enfocado en mejoras y posibles problemas: \n{diff}"}
        ]
    }
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error al analizar con LLM: {e}")
        sys.exit(1)

def post_comment_to_pr(pr_number, repo_full_name, comment):
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("Error: GITHUB_TOKEN not set")
        sys.exit(1)
        
    url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "body": f"## Revisión Automática con LLM\n\n{comment}"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print(f"Comentario publicado con éxito en PR #{pr_number}")
    except Exception as e:
        print(f"Error al publicar comentario: {e}")
        sys.exit(1)

if __name__ == "__main__":
    pr_number, repo_full_name = get_pr_info()
    diff = get_diff()
    review = analyze_with_llm(diff)
    
    print("Revisión del LLM:")
    print(review)
    
    post_comment_to_pr(pr_number, repo_full_name, review)

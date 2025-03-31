import os
import requests
import json
import sys
import re

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

def get_modified_files():
    # Get list of modified files in the PR with their paths and changes
    file_changes = os.popen("git diff --name-status origin/master").read().strip().split('\n')
    modified_files = []
    
    for change in file_changes:
        if not change:
            continue
        parts = change.split('\t')
        if len(parts) >= 2:
            status = parts[0][0]  # M (modified), A (added), D (deleted), etc.
            filename = parts[-1]  # The last part is always the filename
            
            # Only include files that are added or modified (not deleted)
            if status in ['M', 'A']:
                modified_files.append(filename)
    
    return modified_files

def analyze_with_llm(diff, modified_files):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set")
        sys.exit(1)
        
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    # First, get an overall review
    data = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "Eres un revisor de código experto. Debes ser conciso pero detallado, proporcionando recomendaciones para mejorar el código, identificar posibles bugs y sugerir buenas prácticas."},
            {"role": "user", "content": f"Revisa este código y proporciona un análisis enfocado en mejoras y posibles problemas: \n{diff}"}
        ]
    }
    
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        overall_review = response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error al analizar con LLM (revisión general): {e}")
        sys.exit(1)
    
    # Then, analyze each file for specific comments
    file_comments = {}
    
    for file_path in modified_files:
        try:
            # Get file diff
            file_diff = os.popen(f"git diff origin/master -- {file_path}").read()
            
            # Skip if file is too large or has no changes
            if not file_diff or len(file_diff) > 10000:
                continue
                
            # Get line-by-line analysis
            data = {
                "model": "gpt-4",
                "messages": [
                    {"role": "system", "content": "Eres un revisor de código experto. Analiza los cambios en el archivo y proporciona comentarios específicos para líneas individuales. Indica SOLO problemas o sugerencias importantes. Formato requerido:\n- **Línea X**: Tu comentario específico sobre esa línea\n- **Línea Y**: Otro comentario\n\nDonde X e Y son los números de línea del archivo nuevo (después de los cambios)."},
                    {"role": "user", "content": f"Analiza los siguientes cambios en el archivo {file_path} y proporciona comentarios para líneas específicas:\n\n{file_diff}"}
                ]
            }
            
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
            response.raise_for_status()
            file_analysis = response.json()["choices"][0]["message"]["content"]
            
            # Parse comments to associate with line numbers
            file_comments[file_path] = []
            for line in file_analysis.split('\n'):
                # Match patterns like "**Línea X**:" or "Line X:" or variations
                match = re.search(r'[*]*Línea\s+(\d+)[*]*:|[*]*Line\s+(\d+)[*]*:', line, re.IGNORECASE)
                if match:
                    line_num = match.group(1) or match.group(2)
                    comment = re.sub(r'[*]*Línea\s+\d+[*]*:|[*]*Line\s+\d+[*]*:', '', line, flags=re.IGNORECASE).strip(' :*')
                    file_comments[file_path].append((int(line_num), comment))
            
        except Exception as e:
            print(f"Error al analizar el archivo {file_path}: {e}")
    
    return overall_review, file_comments

def post_review_to_pr(pr_number, repo_full_name, overall_review, file_comments):
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("Error: GITHUB_TOKEN not set")
        sys.exit(1)
    
    # Get the latest commit SHA in the PR
    api_url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        head_sha = response.json()["head"]["sha"]
    except Exception as e:
        print(f"Error al obtener el SHA del último commit: {e}")
        sys.exit(1)
    
    # Create a new review
    review_url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    
    # Prepare comments for specific lines
    comments = []
    for file_path, file_lines in file_comments.items():
        for line_num, comment_text in file_lines:
            comments.append({
                "path": file_path,
                "line": line_num,
                "body": comment_text
            })
    
    review_data = {
        "commit_id": head_sha,
        "body": f"## Revisión Automática con LLM\n\n{overall_review}",
        "event": "COMMENT",
        "comments": comments
    }
    
    try:
        response = requests.post(review_url, headers=headers, json=review_data)
        response.raise_for_status()
        print(f"Revisión publicada con éxito en PR #{pr_number}")
    except Exception as e:
        print(f"Error al publicar la revisión: {e}")
        print(f"Respuesta: {response.text}")
        
        # Si falla, intentamos al menos publicar el comentario general
        try:
            comment_url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
            comment_data = {
                "body": f"## Revisión Automática con LLM\n\n{overall_review}\n\n*Nota: No se pudieron agregar comentarios en líneas específicas debido a un error.*"
            }
            response = requests.post(comment_url, headers=headers, json=comment_data)
            response.raise_for_status()
            print(f"Comentario general publicado con éxito en PR #{pr_number}")
        except Exception as e2:
            print(f"Error al publicar el comentario general: {e2}")
            sys.exit(1)

if __name__ == "__main__":
    pr_number, repo_full_name = get_pr_info()
    diff = get_diff()
    modified_files = get_modified_files()
    overall_review, file_comments = analyze_with_llm(diff, modified_files)
    
    print("Revisión general del LLM:")
    print(overall_review)
    
    print("\nComentarios específicos por archivo:")
    for file_path, comments in file_comments.items():
        print(f"\n{file_path}:")
        for line_num, comment in comments:
            print(f"  - Línea {line_num}: {comment}")
    
    post_review_to_pr(pr_number, repo_full_name, overall_review, file_comments)

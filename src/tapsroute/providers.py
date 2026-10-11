"""Optional local Ollama text provider and import-only AI image adapter."""
import json, os, urllib.request, urllib.error

def generate_text(prompt, model="qwen2.5:3b", url=None):
    model=os.getenv("OLLAMA_MODEL",model)
    endpoint=(url or os.getenv("OLLAMA_URL","http://127.0.0.1:11434" )).rstrip("/")+"/api/generate"
    req=urllib.request.Request(endpoint,data=json.dumps({"model":model,"prompt":prompt,"stream":False,"format":"json"}).encode(),headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=120) as r: return json.loads(json.loads(r.read()).get("response","{}"))
    except Exception as e: raise RuntimeError("Local Ollama unavailable; install/start the configured model or import prepared content") from e

def generate_image(prompt, output):
    """AI image generation intentionally requires a locally supplied provider adapter."""
    raise RuntimeError("Image generation is not configured. Import an AI-generated image after local generation.")

def public_image_url(path):
    """Pages URL is usable only after site deployment; never infer it for private repositories."""
    repo=os.getenv("GITHUB_REPOSITORY",""); branch=os.getenv("GITHUB_PAGES_BRANCH","gh-pages")
    if not repo or os.getenv("PUBLIC_PAGES_CONFIRMED")!="true": return ""
    owner,name=repo.split("/",1); return f"https://{owner}.github.io/{name}/{path.lstrip('/')}"

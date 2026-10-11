import json
import os
from .core import Store, settings, ROOT
def main():
    d=Store().read(); d["settings"]=settings(); d["github_repository"]=os.getenv("GITHUB_REPOSITORY","")
    d["last_successful_run"]=next((e["at"] for e in reversed(d["events"]) if e["type"] in ("PUBLISHED","HEALTH_OK")),None)
    path=ROOT/"data/dashboard.json"; path.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
if __name__=="__main__":main()

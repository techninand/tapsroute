from __future__ import annotations
import fcntl, json, os, tempfile, uuid
from datetime import datetime, date, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
ROOT = Path(__file__).resolve().parents[2]
STATE = Path(os.getenv("TAPSROUTE_STATE", ROOT / "data/state.json"))
SETTINGS = Path(os.getenv("TAPSROUTE_SETTINGS", ROOT / "config/settings.json"))

def settings(): return json.loads(SETTINGS.read_text())

class Store:
    """Lock-backed, atomic JSON storage for serialized GitHub workflow updates."""
    def __init__(self, path=STATE): self.path = Path(path); self.lock_path = self.path.with_suffix(".lock")
    def change(self, fn):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = json.loads(self.path.read_text()) if self.path.exists() else {"generation_days":{},"posts":[],"events":[]}
            result = fn(data)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent)
            try:
                with os.fdopen(fd,"w") as f: json.dump(data,f,ensure_ascii=False,indent=2); f.write("\n"); f.flush(); os.fsync(f.fileno())
                os.replace(tmp,self.path)
            finally:
                if os.path.exists(tmp): os.unlink(tmp)
            return result
    def read(self):
        if not self.path.exists(): return {"generation_days":{},"posts":[],"events":[]}
        with self.lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH); return json.loads(self.path.read_text())

def remaining(data, limit=12, now=None):
    day=(now or datetime.now(IST)).astimezone(IST).date().isoformat()
    return max(0,min(12,int(limit))-int(data.get("generation_days",{}).get(day,0)))

def reserve(store, count, limit=12, now=None):
    """Reserve generation allowance atomically before model calls; retries reuse reservations."""
    if count < 1: raise ValueError("count must be positive")
    day=(now or datetime.now(IST)).astimezone(IST).date().isoformat()
    def op(data):
        used=int(data.setdefault("generation_days",{}).get(day,0)); allowed=min(12,int(limit))
        if used+count > allowed: raise ValueError("Daily generation allowance exhausted")
        data["generation_days"][day]=used+count
        return used
    return store.change(op)

def schedule_at(day: date, hhmm: str):
    h,m=map(int,hhmm.split(":")); return datetime.combine(day,time(h,m),IST)

def new_post(destination, category, language, platforms, headline, caption, hashtags, cta, image_prompt, scheduled_at, image_path="", image_url=""):
    now=datetime.now(IST)
    return {"id":str(uuid.uuid4()),"destination":destination,"category":category,"language":language,"platforms":platforms,"format":"image","headline":headline,"caption":caption,"hashtags":hashtags,"call_to_action":cta,"image_prompt":image_prompt,"image_path":image_path,"image_url":image_url,"created_at":now.isoformat(),"scheduled_at":scheduled_at.astimezone(IST).isoformat(),"approval_status":"PENDING_APPROVAL","status":"PENDING_APPROVAL","platform_status":{p:{"status":"PENDING"} for p in platforms},"retry_count":0,"error_details":None,"content_version":1,"approval":None}

def validate_post(p):
    required=("id","destination","category","language","platforms","headline","caption","image_prompt","scheduled_at")
    if any(not p.get(k) for k in required): raise ValueError("Missing required content field")
    if p.get("language") not in ("English","Hindi","Marathi"): raise ValueError("Unsupported language")
    text=(p["caption"]+" "+p.get("headline","" )).lower()
    if any(s in text for s in ("₹","rs.","inr ")) and not p.get("verified_price_source"): raise ValueError("Unverified price claim")
    if not p.get("image_path") and not p.get("image_url"): return "BLOCKED_IMAGE"
    return "VALID"

def approve(store, post_id, reviewer, platforms=None):
    def op(d):
        p=next((x for x in d["posts"] if x["id"]==post_id),None)
        if not p or p["status"] not in ("PENDING_APPROVAL","SCHEDULED"): raise ValueError("Post is not awaiting approval")
        if validate_post(p)!="VALID": raise ValueError("Post is blocked: a suitable image is required")
        selected=platforms or p["platforms"]
        if not selected or any(x not in ("facebook","instagram") or x not in p["platforms"] for x in selected): raise ValueError("Approval platform selection is invalid")
        if "instagram" in selected and not p.get("image_url", "").startswith("https://"):
            raise ValueError("Instagram approval requires a verified public HTTPS image URL")
        p["approval_status"]="APPROVED"; p["status"]="SCHEDULED"; p["approval"]={"reviewer":reviewer,"decision_at":datetime.now(IST).isoformat(),"content_version":p["content_version"],"platforms":selected}
        d["events"].append({"at":datetime.now(IST).isoformat(),"type":"APPROVED","post_id":post_id,"reviewer":reviewer})
    store.change(op)

def due_posts(data, now=None):
    now=(now or datetime.now(IST)).astimezone(IST)
    return [p for p in data["posts"] if p["status"] in ("APPROVED","SCHEDULED","PARTIALLY_PUBLISHED") and p.get("approval_status")=="APPROVED" and p.get("approval",{}).get("content_version")==p.get("content_version") and datetime.fromisoformat(p["scheduled_at"])<=now]

def event(store, kind, **fields):
    store.change(lambda d:d["events"].append({"at":datetime.now(IST).isoformat(),"type":kind,**fields}))

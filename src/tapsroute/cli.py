import argparse, json, os
from datetime import datetime, timedelta
from .core import Store,settings,reserve,new_post,schedule_at,IST,approve,due_posts,event,validate_post
from .providers import generate_text
from .images import find_fallback_image
from .meta import publish,MetaError

def dry_run_content(destination, category, language):
    """Synthetic, fact-safe fixture for checking workflows without a model call."""
    return {
        "headline": f"Sample {category}: {destination}",
        "caption": f"Sample {language} planning content for {destination}. Verify travel details before booking. Let's Travel with Tapsroute — Explore the World with Confidence. https://tapsroute.com | +91 8450-98-4534 | customer.experience@tapsroute.com",
        "hashtags": ["#Tapsroute", "#TravelInspiration"],
        "call_to_action": "Plan your trip with Tapsroute",
        "image_prompt": f"AI-generated travel illustration of {destination}; no text, no prices, no people logos.",
    }

def generate(args):
    cfg=settings(); store=Store(); reserve(store,args.count,cfg["daily_generation_limit"])
    for i in range(args.count):
        dest=args.destination or os.getenv("DESTINATION") or cfg["destinations"][i%len(cfg["destinations"])]
        category=args.category or cfg["categories"][i%len(cfg["categories"])]
        lang=args.language or cfg["default_languages"][i%len(cfg["default_languages"])]
        prompt=f"Create one truthful travel social post as JSON with headline,caption,hashtags,call_to_action,image_prompt. Destination={dest}, category={category}, language={lang}. No prices, bookings, inclusions, or unverifiable claims. Include Tapsroute website/contact/email."
        try: content=dry_run_content(dest,category,lang) if args.dry_run else generate_text(prompt,cfg["ollama_model"])
        except Exception as e:
            event(store,"GENERATION_FAILED",destination=dest,error=str(e)); raise
        day=datetime.now(IST).date()+timedelta(days=i+1)
        fallback=find_fallback_image(dest,category)
        image_path=content.get("image_path","") or (fallback or {}).get("image_path","")
        image_url=content.get("image_url","") or (fallback or {}).get("image_url","")
        p=new_post(dest,category,lang,args.platforms or cfg["platform_targets"],content["headline"],content["caption"],content.get("hashtags",[]),content.get("call_to_action","Plan your trip with Tapsroute"),content["image_prompt"],schedule_at(day,cfg["posting_times"][i%len(cfg["posting_times"])]),image_path,image_url)
        p["sample"] = bool(args.dry_run)
        p["image_generation"] = {"status":"FALLBACK_REUSED","model":fallback["model"],"source":fallback.get("id")} if fallback else {"status":"BLOCKED_NO_VALIDATED_AI_IMAGE","model":None,"source":None}
        if validate_post(p)=="BLOCKED_IMAGE": p["status"]="BLOCKED"; p["error_details"]="No AI-generated image supplied; import and validate a destination-matched image before approval."
        store.change(lambda d:d["posts"].append(p)); print(p["id"])
        event(store,"CONTENT_CREATED",post_id=p["id"],status=p["status"])

def publish_due(args):
    cfg=settings(); store=Store()
    for p in due_posts(store.read()):
        if os.getenv("TEST_MODE","true").lower()=="true":
            event(store,"PUBLISH_DRY_RUN",post_id=p["id"])
            continue
        # Claim each due post atomically; published platforms are never resent.
        def claim(d):
            post=next(x for x in d["posts"] if x["id"]==p["id"])
            if post["approval_status"]!="APPROVED" or post["approval"].get("content_version")!=post["content_version"]: return None
            post["status"]="PUBLISHING"; return dict(post)
        current=store.change(claim)
        if not current: continue
        for platform in current["approval"].get("platforms",current["platforms"]):
            saved=store.read(); live=next(x for x in saved["posts"] if x["id"]==p["id"])
            if live["platform_status"].get(platform,{}).get("status")=="PUBLISHED": continue
            try:
                if not cfg.get("auto_publish") or cfg.get("approval_required") is not True: raise MetaError("Automatic publishing is not enabled safely")
                platform_id=publish(platform,current)
                store.change(lambda d: _platform_result(d,p["id"],platform,{"status":"PUBLISHED","platform_post_id":platform_id,"published_at":datetime.now(IST).isoformat()}))
                event(store,"PLATFORM_PUBLISHED",post_id=p["id"],platform=platform)
            except MetaError as e:
                store.change(lambda d:_platform_result(d,p["id"],platform,{"status":"FAILED","error":str(e),"transient":e.transient}))
                event(store,"PLATFORM_FAILED",post_id=p["id"],platform=platform,error=str(e))
        def finish(d):
            post=next(x for x in d["posts"] if x["id"]==p["id"]); states=[x["status"] for x in post["platform_status"].values()]
            post["status"]="PUBLISHED" if states and all(s=="PUBLISHED" for s in states) else ("PARTIALLY_PUBLISHED" if "PUBLISHED" in states else "FAILED")
        store.change(finish)

def _platform_result(d,pid,platform,result):
    p=next(x for x in d["posts"] if x["id"]==pid); p["platform_status"].setdefault(platform,{}).update(result)

def approve_cmd(args):
    platforms=args.platforms or ([p for p in (args.platforms_csv or "").split(",") if p] or None)
    s=Store(); approve(s,args.post_id,args.reviewer,platforms)

def reject(args):
    s=Store()
    def op(d):
        p=next(x for x in d["posts"] if x["id"]==args.post_id); p["status"]="REJECTED";p["approval_status"]="REJECTED";p["approval"]={"reviewer":args.reviewer,"decision_at":datetime.now(IST).isoformat()}
    s.change(op)

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(required=True)
    g=sub.add_parser("generate");g.add_argument("--count",type=int,default=1);g.add_argument("--destination");g.add_argument("--category");g.add_argument("--language",choices=["English","Hindi","Marathi"]);g.add_argument("--platforms",nargs="+");g.add_argument("--dry-run",action="store_true");g.set_defaults(fn=generate)
    a=sub.add_parser("approve");a.add_argument("post_id");a.add_argument("--reviewer",required=True);a.add_argument("--platforms",nargs="+");a.add_argument("--platforms-csv");a.set_defaults(fn=approve_cmd)
    r=sub.add_parser("reject");r.add_argument("post_id");r.add_argument("--reviewer",required=True);r.set_defaults(fn=reject)
    pub=sub.add_parser("publish-due");pub.set_defaults(fn=publish_due)
    args=ap.parse_args();args.fn(args)
if __name__=="__main__":main()

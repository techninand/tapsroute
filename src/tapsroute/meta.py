"""Official Meta Graph API publishing adapters. Disabled by default/test mode."""
import json, os, time, urllib.parse, urllib.request, urllib.error

class MetaError(RuntimeError):
    def __init__(self,message,transient=False,retry_after=None): super().__init__(message); self.transient=transient; self.retry_after=retry_after

def _post(url, fields):
    body=urllib.parse.urlencode(fields).encode(); req=urllib.request.Request(url,data=body)
    try:
        with urllib.request.urlopen(req,timeout=45) as response: return json.loads(response.read())
    except urllib.error.HTTPError as e:
        retry=e.headers.get("Retry-After")
        try: code=json.loads(e.read()).get("error",{}).get("code")
        except Exception: code=None
        msg="Meta API error (credentials and response body redacted)"
        raise MetaError(msg,e.code in (429,500,502,503,504) or code in (4,17,32),int(retry) if retry and retry.isdigit() else None)
    except Exception: raise MetaError("Meta API transport failure (credentials redacted)",True)

def publish(platform, post):
    if os.getenv("TEST_MODE","true").lower()=="true": raise MetaError("TEST_MODE prevents real publishing")
    token=os.getenv("META_PAGE_ACCESS_TOKEN",""); version=os.getenv("META_API_VERSION", "v23.0")
    image=post.get("image_url")
    if not image or not image.startswith("https://"): raise MetaError("Public HTTPS image URL required")
    caption=post["caption"]+"\n\n"+" ".join(post.get("hashtags",[]))
    if platform=="facebook":
        account=os.getenv("META_PAGE_ID",""); endpoint=f"https://graph.facebook.com/{version}/{account}/photos"
        result=_post(endpoint,{"url":image,"caption":caption,"access_token":token})
        if not result.get("post_id"): raise MetaError("Facebook did not return a Page post ID")
        return result["post_id"]
    if platform=="instagram":
        account=os.getenv("META_IG_USER_ID",""); base=f"https://graph.facebook.com/{version}/{account}"
        container=_post(base+"/media",{"image_url":image,"caption":caption,"access_token":token})
        cid=container.get("id")
        if not cid: raise MetaError("Instagram media container creation failed")
        for _ in range(12):
            check_req=urllib.request.Request(base+"/"+urllib.parse.quote(cid)+"?fields=status_code",headers={"Authorization":"Bearer "+token})
            check=urllib.request.urlopen(check_req,timeout=30)
            state=json.loads(check.read()).get("status_code")
            if state=="FINISHED": break
            if state in ("ERROR","EXPIRED"): raise MetaError("Instagram media processing failed")
            time.sleep(5)
        else: raise MetaError("Instagram media container was not ready",True)
        result=_post(base+"/media_publish",{"creation_id":cid,"access_token":token})
        if not result.get("id"): raise MetaError("Instagram publishing did not return a media ID")
        return result["id"]
    raise MetaError("Unsupported Meta platform")

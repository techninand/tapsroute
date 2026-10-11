import json, tempfile, threading, unittest
from datetime import datetime, timezone, date
from pathlib import Path
from tapsroute.core import Store, reserve, remaining, IST, schedule_at, new_post, approve, due_posts, validate_post

class CoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.tmp.name)/'state.json')
 def tearDown(self): self.tmp.cleanup()
 def test_daily_max_and_concurrency(self):
  errors=[]
  def run():
   try: reserve(self.store,1,12,datetime(2026,10,11,12,tzinfo=IST))
   except ValueError: errors.append(1)
  ts=[threading.Thread(target=run) for _ in range(20)]
  [t.start() for t in ts];[t.join() for t in ts]
  data=self.store.read();self.assertEqual(data['generation_days']['2026-10-11'],12);self.assertEqual(len(errors),8)
 def test_limit_cannot_exceed_12(self):
  reserve(self.store,12,200,datetime(2026,1,1,tzinfo=IST))
  self.assertEqual(remaining(self.store.read(),200,datetime(2026,1,1,tzinfo=IST)),0)
 def test_midnight_ist_and_timezone(self):
  a=datetime(2026,1,1,18,29,59,tzinfo=timezone.utc); b=datetime(2026,1,1,18,30,1,tzinfo=timezone.utc)
  reserve(self.store,1,12,a);reserve(self.store,1,12,b)
  self.assertEqual(self.store.read()['generation_days'],{'2026-01-01':1,'2026-01-02':1})
  self.assertEqual(schedule_at(date(2026,1,2),'10:00').hour,10)
 def test_retry_reservation_not_reused_as_new(self):
  reserve(self.store,1,12,datetime(2026,1,1,tzinfo=IST))
  self.assertEqual(remaining(self.store.read(),12,datetime(2026,1,1,tzinfo=IST)),11)
 def post(self):
  return new_post('Goa','Weekend','English',['facebook'],'A Goa weekend','Sample planning inspiration',[], 'Explore','AI Goa beach',schedule_at(date(2026,1,2),'10:00'),image_path='images/goa.jpg')
 def test_approval_and_due_validation(self):
  p=self.post();self.store.change(lambda d:d['posts'].append(p));approve(self.store,p['id'],'owner')
  self.assertEqual(len(due_posts(self.store.read(),datetime(2026,1,3,tzinfo=IST))),1)
  p['content_version']+=1;self.store.change(lambda d:d.update(posts=[p]));self.assertEqual(due_posts(self.store.read(),datetime(2026,1,3,tzinfo=IST)),[])
 def test_missing_image_blocks(self):
  p=self.post();p['image_path']='';self.assertEqual(validate_post(p),'BLOCKED_IMAGE')
 def test_languages_and_unverified_price(self):
  p=self.post();p['language']='Tamil'
  with self.assertRaises(ValueError):validate_post(p)
  p['language']='Hindi';p['caption']='Only ₹999 per traveler'
  with self.assertRaises(ValueError):validate_post(p)
 def test_store_reopens_state(self):
  self.store.change(lambda d:d['posts'].append({'id':'x'}));self.assertEqual(self.store.read()['posts'][0]['id'],'x')
if __name__=='__main__':unittest.main()

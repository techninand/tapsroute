import os, unittest
from unittest.mock import patch
from tapsroute.meta import publish, MetaError
class MetaTests(unittest.TestCase):
 def setUp(self): self.env=patch.dict(os.environ,{'TEST_MODE':'true'});self.env.start()
 def tearDown(self): self.env.stop()
 def test_dry_run_prevents_publish(self):
  with self.assertRaisesRegex(MetaError,'TEST_MODE'):publish('facebook',{'image_url':'https://example.org/a.jpg','caption':'x'})
 def test_missing_https_image(self):
  with patch.dict(os.environ,{'TEST_MODE':'false'}):
   with self.assertRaisesRegex(MetaError,'HTTPS'):publish('instagram',{'image_url':'/local.jpg','caption':'x'})
if __name__=='__main__':unittest.main()

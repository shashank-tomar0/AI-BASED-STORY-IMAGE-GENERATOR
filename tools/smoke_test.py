import urllib.request
import time
import sys

last_exc = None
for i in range(10):
    try:
        r = urllib.request.urlopen('http://127.0.0.1:5000/', timeout=3).read(1024)
        print(r.decode('utf-8','ignore')[:1000])
        sys.exit(0)
    except Exception as e:
        last_exc = e
        time.sleep(0.5)

print('FAILED to fetch http://127.0.0.1:5000/ ; last exception:', repr(last_exc))

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
import json
import time
import os


PORT = 8000
FRED_API_KEY = os.getenv("FRED_API_KEY", "").strip()

FEEDS = [
    {
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "source": "BBC World"
    },
    {
        "url": "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
        "source": "BBC Middle East"
    },
    {
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "source": "Al Jazeera"
    }
]


def clean_text(text):
    if not text:
        return ""
    return " ".join(text.split())


def parse_date(date_text):
    if not date_text:
        return int(time.time() * 1000)

    try:
        dt = parsedate_to_datetime(date_text)
        return int(dt.timestamp() * 1000)
    except Exception:
        return int(time.time() * 1000)


def fetch_feed(feed):
    request = Request(
        feed["url"],
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/rss+xml, application/xml, text/xml, */*"
        }
    )

    with urlopen(request, timeout=10) as response:
        data = response.read()

    root = ET.fromstring(data)

    items = []

    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title", ""))
        link = clean_text(item.findtext("link", ""))
        description = clean_text(item.findtext("description", ""))
        pub_date = item.findtext("pubDate", "")

        if not title:
            continue

        items.append({
            "title": title,
            "link": link,
            "description": description,
            "source": feed["source"],
            "publishedAt": parse_date(pub_date)
        })

    return items


def fetch_all_news():
    all_items = []
    failed = []

    for feed in FEEDS:
        try:
            items = fetch_feed(feed)

            print(
                f"[NEWS] {feed['source']} -> "
                f"{len(items)} items"
            )

            all_items.extend(items)

        except Exception as error:

            print(
                f"[NEWS ERROR] {feed['source']} -> "
                f"{error}"
            )

            failed.append({
                "source": feed["source"],
                "error": str(error)
            })

    unique = {}

    for item in all_items:
        key = item["title"].lower().strip()

        if key not in unique:
            unique[key] = item

    all_items = list(unique.values())

    all_items.sort(
        key=lambda x: x["publishedAt"],
        reverse=True
    )

    return all_items, failed


class Handler(SimpleHTTPRequestHandler):

    def end_headers(self):

        self.send_header(
            "Access-Control-Allow-Origin",
            "*"
        )

        self.send_header(
            "Cache-Control",
            "no-store"
        )

        super().end_headers()


    def send_json(self, data, status_code=200):

        body = json.dumps(
            data,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status_code)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.end_headers()

        self.wfile.write(body)


    def do_GET(self):
        path = urlparse(self.path).path

        
        if path == "/api/fed":

            
            try:
                if not FRED_API_KEY:
                    self.send_json({
                        "status": "error",
                        "message": "FRED_API_KEY not configured"
                    }, 500)
                    return

                url = (
                    "https://api.stlouisfed.org/fred/series/observations"
                    "?series_id=DFF"
                    "&file_type=json"
                    "&api_key=" + FRED_API_KEY.strip()
                )

                request = Request(
                    url,
                    headers={"User-Agent": "VIKAS-TERMINAL"}
                )

                with urlopen(request, timeout=10) as response:
                    data = json.loads(response.read().decode("utf-8"))

                observations = data.get("observations", [])

                latest = None
                for observation in reversed(observations):
                    if observation.get("value") not in ("", None):
                        latest = observation
                        break

                self.send_json({
                    "status": "ok",
                    "series": "DFF",
                    "latest": latest
                })

            except Exception as error:
                self.send_json({
                    "status": "error",
                    "message": str(error)
                }, 500)

            return

        path = urlparse(self.path).path

        if path == "/api/news":

            print("")
            print("==============================")
            print("[API] Fetching live news...")
            print("==============================")

            items, failed = fetch_all_news()

            if items:

                response = {
                    "status": "ok",
                    "live": True,
                    "count": len(items),
                    "items": items,
                    "failedFeeds": failed,
                    "updatedAt": int(time.time() * 1000)
                }

                self.send_json(response)

            else:

                response = {
                    "status": "error",
                    "live": False,
                    "count": 0,
                    "items": [],
                    "failedFeeds": failed,
                    "updatedAt": int(time.time() * 1000)
                }

                self.send_json(response, 503)

            return

        super().do_GET()


server = ThreadingHTTPServer(
    ("0.0.0.0", PORT),
    Handler
)


print("")
print("======================================")
print(" VIKAS TERMINAL NEWS SERVER")
print("======================================")
print("")
print("Dashboard:")
print("http://localhost:8000")
print("")
print("Live News API:")
print("http://localhost:8000/api/news")
print("")
print("Server is running...")
print("Press CTRL+C to stop.")
print("")


try:
    server.serve_forever()

except KeyboardInterrupt:
    print("\nServer stopped.")

finally:
    server.server_close()

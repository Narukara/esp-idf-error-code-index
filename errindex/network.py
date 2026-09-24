"""Sequential, bounded public HTTP reads. Cache is disposable, not database state."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .storage import digest, read_json, write_json

ALLOWED_HOSTS = {"api.github.com", "raw.githubusercontent.com", "components.espressif.com",
                 "components-file.espressif.com"}


class BudgetExceeded(RuntimeError):
    pass


class SourceError(RuntimeError):
    pass


def check_url(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise SourceError("Unapproved public source URL: " + url)


class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not let redirects bypass budgets or carry authorization elsewhere.
        raise SourceError("Redirect refused; update the source adapter: " + newurl)


class Client:
    def __init__(self, cache, limits, offline=False, refresh=False):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.limits, self.offline, self.refresh = limits, offline, refresh
        self.started = time.monotonic()
        self.last_request = 0.0
        self.requests = self.download_bytes = self.hits = 0
        self.opener = urllib.request.build_opener(Redirects())

    def check_time(self):
        if time.monotonic() - self.started >= self.limits["max_seconds"]:
            raise BudgetExceeded("Run time budget reached")

    def get(self, url, immutable=False, cache_identity=None):
        check_url(url)
        self.check_time()
        key = digest([url, cache_identity]) if cache_identity is not None else digest(url)
        meta_path, body_path = self.cache / (key + ".json"), self.cache / (key + ".bin")
        meta = read_json(meta_path, {})
        cached = body_path.exists() and meta.get("sha256") == digest(body_path.read_bytes())
        fresh = time.time() - meta.get("checked_at", 0) < self.limits["metadata_ttl_seconds"]
        if cached and (self.offline or immutable or (fresh and not self.refresh)):
            self.hits += 1
            return body_path.read_bytes()
        if self.offline:
            raise SourceError("Offline cache miss: " + url)
        if self.requests >= self.limits["max_requests"]:
            raise BudgetExceeded("Request budget reached")
        remaining = self.limits["max_download_bytes"] - self.download_bytes
        if remaining <= 0:
            raise BudgetExceeded("Download budget reached")
        delay = max(0, self.limits["request_interval_seconds"] - (time.monotonic() - self.last_request))
        if time.monotonic() - self.started + delay >= self.limits["max_seconds"]:
            raise BudgetExceeded("Run time budget reached")
        time.sleep(delay)
        headers = {"User-Agent": "esp-idf-error-code-index/0.1 (bounded public observation)",
                   "Accept": "application/json" if "api.github.com" in url else "*/*"}
        if cached and meta.get("etag"):
            headers["If-None-Match"] = meta["etag"]
        if urllib.parse.urlsplit(url).hostname == "api.github.com" and os.getenv("GITHUB_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
        self.requests += 1
        self.last_request = time.monotonic()
        timeout = min(20, max(0.1, self.limits["max_seconds"] - (time.monotonic() - self.started)))
        try:
            with self.opener.open(urllib.request.Request(url, headers=headers), timeout=timeout) as response:
                cap = min(remaining, self.limits["max_response_bytes"])
                if int(response.headers.get("Content-Length", "0")) > cap:
                    if cap < self.limits["max_response_bytes"]:
                        raise BudgetExceeded("Remaining download budget is too small for next response")
                    raise SourceError("Response exceeds per-response limit: " + url)
                chunks, size = [], 0
                while True:
                    self.check_time()
                    chunk = response.read(min(65536, cap - size + 1))
                    if not chunk:
                        break
                    self.download_bytes += len(chunk)
                    size += len(chunk)
                    if size > cap:
                        if cap < self.limits["max_response_bytes"]:
                            raise BudgetExceeded("Download budget reached while reading response")
                        raise SourceError("Response exceeds per-response limit: " + url)
                    chunks.append(chunk)
                body = b"".join(chunks)
                body_path.write_bytes(body)
                write_json(meta_path, {"checked_at": time.time(), "etag": response.headers.get("ETag"),
                                       "sha256": digest(body)})
                return body
        except urllib.error.HTTPError as exc:
            if exc.code == 304 and cached:
                meta["checked_at"] = time.time()
                write_json(meta_path, meta)
                self.hits += 1
                return body_path.read_bytes()
            if exc.code in (403, 429):
                raise BudgetExceeded("Upstream rate limit/access refusal; no automatic retry") from exc
            raise SourceError(f"HTTP {exc.code}: {url}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SourceError(f"Network read failed: {url}: {exc}") from exc

    def json(self, url, immutable=False):
        return json.loads(self.get(url, immutable))

    def prune(self):
        files = sorted(self.cache.glob("*.bin"), key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in files)
        for file in files:
            if total <= self.limits["cache_max_bytes"]:
                break
            total -= file.stat().st_size
            file.unlink()
            file.with_suffix(".json").unlink(missing_ok=True)

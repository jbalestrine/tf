#!/usr/bin/env python3
"""MasterChief - API Health Monitor"""
import urllib.request, json, time, sys

ENDPOINTS = [
    {"name": "MasterChief API", "url": "http://localhost:8080/api/stats"},
    {"name": "Example", "url": "https://httpbin.org/get"},
]

def check_endpoint(ep):
    try:
        start = time.time()
        req = urllib.request.Request(ep["url"], headers={"User-Agent": "MasterChief-Monitor/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            elapsed = (time.time() - start) * 1000
            return {"name": ep["name"], "status": resp.status, "ms": round(elapsed), "ok": True}
    except Exception as e:
        return {"name": ep["name"], "status": 0, "ms": 0, "ok": False, "error": str(e)}

def main():
    print("[MasterChief] API Health Monitor")
    print("=" * 60)
    results = [check_endpoint(ep) for ep in ENDPOINTS]
    for r in results:
        icon = "OK" if r["ok"] else "FAIL"
        color = "\033[92m" if r["ok"] else "\033[91m"
        print(f"  {color}[{icon}]\033[0m {r['name']:30s} {r['status']:>3d}  {r['ms']:>4d}ms")
    healthy = sum(1 for r in results if r["ok"])
    print(f"\n  Summary: {healthy}/{len(results)} endpoints healthy")

if __name__ == '__main__':
    main()
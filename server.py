#!/usr/bin/env python3
"""Local clone of https://reqres.in/ — the classic documented API contract.

Pure stdlib (Python 3.8+, runs on this Catalina box's system python3), zero deps.

    python3 server.py                 # http://localhost:40000/api
    python3 server.py --port 8000

Endpoints (parity with reqres.in docs):
    GET    /api/users?page=N          paginated users (12 total, 6/page)
    GET    /api/users?delay=2         same, server sleeps 2s first
    GET    /api/users?unknown=...     empty data list
    GET    /api/users/{1..12}         single user + support
    GET    /api/users/other           404 {} (like live)
    POST   /api/users {name,job}      -> {name, job, id, createdAt}
    PUT    /api/users/{id}            -> {name, job, updatedAt}
    PATCH  /api/users/{id}            -> same as PUT (like live)
    DELETE /api/users/{id}            -> 204 empty
    GET    /api/user-list?delay=2     list, 10/page
    GET    /api/unknown               color list
    GET    /api/unknown/{1..6}        single color; anything else -> {}
    GET    /api/products              3 products
    POST   /api/register {email,password}   -> {token}; missing password -> 400
    POST   /api/login  {email,password}     -> {token}; wrong/missing -> 400
    anything else under /api          -> 404 {}

CORS is wide open (Access-Control-Allow-Origin: *) like the real service.
"""
import argparse
import json
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import data

created_seq = [12]  # POST /api/users ids continue from 13

def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3].replace('+00:00', 'Z')

def user_page(page, per_page=None, total_pages=None):
    per_page = per_page or data.PER_PAGE
    start = (page - 1) * per_page
    return {
        'page': page,
        'per_page': per_page,
        'total': len(data.USERS),
        'total_pages': total_pages or ((len(data.USERS) + per_page - 1) // per_page),
        'data': data.USERS[start:start + per_page],
    }

def users_query(qs):
    if 'delay' in qs:
        time.sleep(min(float(qs['delay'][0]), 30))
    known = {'page', 'delay'}
    extra = set(qs) - known
    if extra:  # any unknown filter -> empty data, like reqres ?unknown
        res = user_page(1)
        res['data'] = []
        return res
    try:
        page = max(int(qs.get('page', ['1'])[0] or 1), 1)
    except (TypeError, ValueError):
        page = 1
    if page > 2:  # reqres clamps: out-of-range page returns page N with empty slice
        res = user_page(page)
        res['data'] = []
    else:
        res = user_page(page)
    return res

class ReqResHandler(BaseHTTPRequestHandler):
    server_version = 'ReqResClone/1.0'

    def log_message(self, fmt, *args):  # quiet one-line access log
        print('%s %s' % (self.address_string(), fmt % args))

    # ---------- plumbing ----------
    def _send(self, status, payload, extra_headers=None):
        body = b'' if payload is None else json.dumps(payload).encode()
        self.send_response(status)
        if body:
            self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'content-type, x-api-key, authorization')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _read_json(self):
        try:
            n = int(self.headers.get('Content-Length') or 0)
            return json.loads(self.rfile.read(n) or b'{}') if n else {}
        except (ValueError, json.JSONDecodeError):
            return {}

    def do_OPTIONS(self):
        self._send(204, None)

    # ---------- dispatch ----------
    def do_GET(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        path = url.path.rstrip('/')

        if path in ('', '/'):
            self._serve_ui()
            return
        if path == '/api':
            self._send(200, self._index())
            return
        if path == '/api/users':
            self._send(200, users_query(qs))
            return
        if path.startswith('/api/users/'):
            self._single(data.USERS, path, 'users')
            return
        if path == '/api/user-list':
            delay = qs.get('delay', ['0'])[0]
            time.sleep(min(float(delay), 30))
            self._send(200, user_page(1, per_page=10))
            return
        if path == '/api/unknown':
            self._send(200, {'data': data.COLORS, 'support': data.SUPPORT})
            return
        if path.startswith('/api/unknown/'):
            self._single(data.COLORS, path, 'unknown')
            return
        if path == '/api/products':
            self._send(200, data.PRODUCTS)
            return
        if path.startswith('/img/faces/'):
            self._serve_avatar(path)
            return
        if path == '/api/support':
            self._send(200, {'text': data.SUPPORT['text'], 'url': data.SUPPORT['url']})
            return
        self._send(404, {})

    def do_POST(self):
        url = urlparse(self.path)
        path = url.path.rstrip('/')
        body = self._read_json()
        if path == '/api/users':
            created_seq[0] += 1
            out = dict(body)
            out.update({'id': str(created_seq[0]), 'createdAt': now_iso()})
            self._send(201, out)
            return
        if path in ('/api/register', '/api/login'):
            status, err = self._cred(body)
            if err is not None:
                self._send(status, err)
                return
            self._send(200, {'token': data.TOKEN, 'support': data.SUPPORT})
            return
        self._send(404, {})

    def do_PUT(self):
        path = urlparse(self.path).path.rstrip('/')
        body = self._read_json()
        if path.startswith('/api/users/'):
            out = dict(body)
            out['updatedAt'] = now_iso()
            self._send(200, out)
            return
        self._send(404, {})

    do_PATCH = do_PUT

    def do_DELETE(self):
        path = urlparse(self.path).path.rstrip('/')
        if path.startswith('/api/users/'):
            self._send(204, None)
            return
        self._send(404, {})

    # ---------- helpers ----------
    def _cred(self, body):
        email = (body.get('email') or '').strip()
        password = (body.get('password') or '').strip()
        if not email:
            return 400, {'error': 'Missing email'}
        if not password:
            return 400, {'error': 'Missing password'}
        return None, None

    def _serve_avatar(self, path):
        # /img/faces/<id>-image.jpg — mirrors reqres.in asset layout, local files only
        import os
        import re
        m = re.match(r'^/img/faces/(\d+)-image\.jpg$', path)
        if not m:
            self._send(404, None)
            return
        f = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'img', 'faces', '%s-image.jpg' % m.group(1))
        if not os.path.isfile(f):
            self._send(404, None)
            return
        with open(f, 'rb') as fh:
            body = fh.read()
        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _single(self, rows, path, kind):
        tail = path.rsplit('/', 1)[-1]
        try:
            rid = int(tail)
        except ValueError:
            self._send(404, {})
            return
        for row in rows:
            if row['id'] == rid:
                self._send(200, {'data': row, 'support': data.SUPPORT})
                return
        self._send(404, {})  # "User/Resource not found" — 404 + empty body, like live

    def _serve_ui(self):
        import os
        f = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui.html')
        if not os.path.isfile(f):
            self._send(200, self._index())
            return
        body = open(f, 'rb').read()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _index(self):
        return {
            'name': 'reqres.in local clone',
            'endpoints': [
                '/api/users?page=1', '/api/users?delay=2', '/api/users/2', '/api/users/23',
                '/api/user-list?delay=2', '/api/unknown/2', '/api/products',
                'POST/PUT/DELETE /api/users', 'POST /api/register', 'POST /api/login',
            ],
        }

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--host', default='localhost')
    ap.add_argument('--port', type=int, default=40000)
    args = ap.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), ReqResHandler)
    print('reqres clone on http://%s:%d/api  (Ctrl-C to stop)' % (args.host, args.port))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()

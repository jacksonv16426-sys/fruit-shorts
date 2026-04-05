#!/usr/bin/env python3
"""API proxy - forwards requests to Kling and ElevenLabs APIs to bypass CORS."""
import http.server
import json
import urllib.request
import urllib.error
import ssl

PORT = 8100

# Disable SSL verification for forwarding
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[proxy] {args[0]}" if args else "")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()

    def do_GET(self):
        self._proxy('GET')

    def do_POST(self):
        self._proxy('POST')

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _proxy(self, method):
        try:
            # Parse the target URL from the path
            # /kling/v1/images/generations -> https://api.klingai.com/v1/images/generations
            # /eleven/v1/text-to-speech/xxx -> https://api.elevenlabs.io/v1/text-to-speech/xxx
            path = self.path

            if path.startswith('/kling/'):
                target = 'https://api.klingai.com/' + path[7:]
            elif path.startswith('/eleven/'):
                target = 'https://api.elevenlabs.io/' + path[8:]
            else:
                self.send_response(404)
                self._send_json({'error': 'Unknown API route'})
                return

            # Read request body
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len) if content_len > 0 else None

            # Forward headers
            headers = {}
            if self.headers.get('Authorization'):
                headers['Authorization'] = self.headers['Authorization']
            if self.headers.get('xi-api-key'):
                headers['xi-api-key'] = self.headers['xi-api-key']
            if self.headers.get('Content-Type'):
                headers['Content-Type'] = self.headers['Content-Type']

            req = urllib.request.Request(target, data=body, headers=headers, method=method)

            try:
                resp = urllib.request.urlopen(req, context=ctx, timeout=120)
                resp_data = resp.read()
                content_type = resp.headers.get('Content-Type', 'application/json')

                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(resp_data)))
                self.end_headers()
                self.wfile.write(resp_data)
            except urllib.error.HTTPError as e:
                resp_data = e.read()
                self.send_response(e.code)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(resp_data)))
                self.end_headers()
                self.wfile.write(resp_data)

        except Exception as e:
            error_msg = json.dumps({'error': str(e)}).encode()
            self.send_response(500)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(error_msg)))
            self.end_headers()
            self.wfile.write(error_msg)

    def _send_json(self, data):
        body = json.dumps(data).encode()
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

print(f"API Proxy running on http://localhost:{PORT}")
print("Routes: /kling/* -> api.klingai.com, /eleven/* -> api.elevenlabs.io")
http.server.HTTPServer(('0.0.0.0', PORT), ProxyHandler).serve_forever()

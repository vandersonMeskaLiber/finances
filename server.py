#!/usr/bin/env python3
import json
import os
import struct
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import db

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8787"))


def write_icon(path, size):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            ink = 40 < x < size - 40 and (40 < y < 90 or size // 2 - 24 < y < size // 2 + 24 or 40 < x < 100)
            color = (15, 110, 86) if ink else (28, 25, 21)
            raw.extend(color)
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._api_get(parsed)
            return
        self._static(parsed.path)

    def do_POST(self):
        self._api_write("POST")

    def do_PUT(self):
        self._api_write("PUT")

    def do_DELETE(self):
        self._api_write("DELETE")

    def _api_get(self, parsed):
        user = self._user()
        params = parse_qs(parsed.query)
        path = parsed.path
        try:
            if path == "/api/session":
                self._send(200, {"user": user, "ready": db.user_count() > 0, "contexts": db.settings() if user else None})
                return
            self._require(user)
            if path == "/api/summary":
                self._send(200, db.panorama(self._context(params), params.get("month", [None])[0]))
            elif path == "/api/transactions":
                self._send(200, db.list_transactions(
                    self._context(params),
                    params.get("month", [None])[0],
                    params.get("direction", [None])[0],
                    params.get("day", [None])[0],
                    params.get("pending", ["0"])[0] == "1",
                    params.get("account_id", [None])[0],
                ))
            elif path == "/api/accounts":
                self._send(200, db.list_accounts(self._context(params), True))
            elif path == "/api/categories":
                self._send(200, db.list_categories(self._context(params)))
            elif path == "/api/loans":
                self._send(200, db.list_loans(self._context(params)))
            elif path == "/api/goals":
                self._send(200, db.list_goals(self._context(params)))
            elif path == "/api/company":
                self._send(200, db.company_view(params.get("year", [None])[0]))
            elif path == "/api/users":
                self._admin(user)
                self._send(200, db.list_users())
            elif path == "/api/export":
                self._admin(user)
                self._send(200, db.export_space())
            else:
                self._error(404, "Rota não encontrada.")
        except ValueError as exc:
            self._error(400, str(exc))

    def _api_write(self, method):
        parsed = urlparse(self.path)
        payload = self._read_json() if method != "DELETE" else {}
        if payload is None:
            return
        user = self._user()
        parts = [part for part in parsed.path.split("/") if part]
        try:
            if method == "POST" and parsed.path == "/api/setup":
                if db.user_count():
                    self._error(400, "O administrador já existe.")
                    return
                created = db.create_user(payload.get("name"), payload.get("email"), payload.get("password"), "admin")
                token, _ = db.authenticate(payload.get("email"), payload.get("password"))
                self._send(201, {"user": created}, token)
                return
            if method == "POST" and parsed.path == "/api/login":
                token, person = db.authenticate(payload.get("email"), payload.get("password"))
                self._send(200, {"user": person}, token)
                return
            if method == "POST" and parsed.path == "/api/logout":
                db.logout(self._token())
                self._send(200, {"ok": True}, clear=True)
                return
            self._require(user)
            context = payload.get("context") or "pf"
            if method == "POST" and parsed.path == "/api/accounts":
                self._send(201, db.create_account(context, payload.get("name")))
            elif method == "PUT" and len(parts) == 3 and parts[1] == "accounts":
                self._send(200, db.update_account(int(parts[2]), payload.get("name"), payload.get("active")))
            elif method == "DELETE" and len(parts) == 3 and parts[1] == "accounts":
                db.delete_account(int(parts[2]))
                self._send(200, {"ok": True})
            elif method == "POST" and parsed.path == "/api/categories":
                self._send(201, db.create_category(context, payload.get("direction"), payload.get("name")))
            elif method == "PUT" and len(parts) == 3 and parts[1] == "categories":
                self._send(200, db.update_category(int(parts[2]), payload.get("name"), payload.get("active")))
            elif method == "DELETE" and len(parts) == 3 and parts[1] == "categories":
                db.delete_category(int(parts[2]))
                self._send(200, {"ok": True})
            elif method == "POST" and len(parts) == 4 and parts[3] == "subcategories":
                self._send(201, db.create_subcategory(int(parts[2]), payload.get("name")))
            elif method == "PUT" and len(parts) == 3 and parts[1] == "subcategories":
                self._send(200, db.update_subcategory(int(parts[2]), payload.get("name"), payload.get("active")))
            elif method == "DELETE" and len(parts) == 3 and parts[1] == "subcategories":
                db.delete_subcategory(int(parts[2]))
                self._send(200, {"ok": True})
            elif method == "POST" and parsed.path == "/api/transactions":
                payload["context"] = context
                self._send(201, db.create_transaction(payload))
            elif method == "PUT" and len(parts) == 3 and parts[1] == "transactions":
                self._send(200, db.update_transaction(int(parts[2]), payload, payload.get("scope") or "this"))
            elif method == "POST" and len(parts) == 4 and parts[1] == "transactions" and parts[3] == "cancel":
                self._send(200, db.cancel_transaction(int(parts[2])))
            elif method == "DELETE" and len(parts) == 3 and parts[1] == "transactions":
                db.delete_transaction(int(parts[2]))
                self._send(200, {"ok": True})
            elif method == "POST" and parsed.path == "/api/series":
                payload["context"] = context
                self._send(201, db.create_series(payload))
            elif method == "POST" and len(parts) == 4 and parts[1] == "series" and parts[3] == "end":
                self._send(200, db.end_series(int(parts[2]), payload.get("from_month")))
            elif method == "POST" and parsed.path == "/api/loans/preview":
                self._send(200, db.preview_loan(payload))
            elif method == "POST" and parsed.path == "/api/loans":
                payload["context"] = context
                self._send(201, db.create_loan(payload))
            elif method == "POST" and len(parts) == 4 and parts[1] == "loans" and parts[3] == "settle":
                self._send(200, db.settle_elapsed_installments(int(parts[2])))
            elif method == "PUT" and len(parts) == 3 and parts[1] == "loans":
                self._send(200, db.update_loan(int(parts[2]), payload))
            elif method == "DELETE" and len(parts) == 3 and parts[1] == "loans":
                db.delete_loan(int(parts[2]))
                self._send(200, {"ok": True})
            elif method == "POST" and parsed.path == "/api/goals":
                self._send(201, db.create_goal(context, payload.get("name"), payload.get("target_amount"), payload.get("target_date")))
            elif method == "PUT" and len(parts) == 3 and parts[1] == "goals":
                self._send(200, db.update_goal(int(parts[2]), payload.get("name"), payload.get("target_amount"), payload.get("target_date")))
            elif method == "DELETE" and len(parts) == 3 and parts[1] == "goals":
                db.delete_goal(int(parts[2]))
                self._send(200, {"ok": True})
            elif method == "PUT" and len(parts) == 5 and parts[1] == "goals":
                self._send(200, db.save_goal_month(int(parts[2]), parts[4], payload.get("saved")))
            elif method == "POST" and parsed.path == "/api/simulation":
                self._send(200, db.panorama(context, payload.get("month"), extras=payload.get("extras") or []))
            elif method == "PUT" and parsed.path == "/api/context":
                self._send(200, db.set_last_context(user["id"], payload.get("context")))
            elif method == "PUT" and parsed.path == "/api/contexts":
                self._admin(user)
                self._send(200, db.set_context_enabled(payload.get("context"), payload.get("enabled")))
            elif method == "PUT" and parsed.path == "/api/company":
                self._send(200, db.update_company(payload))
            elif method == "PUT" and parsed.path == "/api/company/das":
                self._send(200, db.set_das(payload.get("year"), payload.get("month"), payload.get("paid"), payload.get("amount"), payload.get("launch")))
            elif method == "PUT" and parsed.path == "/api/company/dasn":
                self._send(200, db.set_dasn(payload.get("year"), payload.get("delivered")))
            elif method == "POST" and parsed.path == "/api/users":
                self._admin(user)
                self._send(201, db.create_user(payload.get("name"), payload.get("email"), payload.get("password"), "user"))
            elif method == "PUT" and len(parts) == 3 and parts[1] == "users":
                self._admin(user)
                if payload.get("name") or payload.get("email"):
                    self._send(200, db.update_user(int(parts[2]), payload.get("name"), payload.get("email"), payload.get("role") or "user", payload.get("password") or None))
                else:
                    if "active" in payload:
                        db.set_user_active(int(parts[2]), payload.get("active"))
                    if payload.get("password"):
                        db.reset_password(int(parts[2]), payload.get("password"))
                    self._send(200, {"ok": True})
            elif method == "DELETE" and len(parts) == 3 and parts[1] == "users":
                self._admin(user)
                db.delete_user(int(parts[2]), user["id"])
                self._send(200, {"ok": True})
            elif method == "POST" and parsed.path == "/api/erase":
                self._admin(user)
                db.erase_space()
                self._send(200, {"ok": True}, clear=True)
            else:
                self._error(404, "Rota não encontrada.")
        except ValueError as exc:
            self._error(400, str(exc))
        except ZeroDivisionError:
            self._error(400, "Não foi possível calcular com esses valores.")

    def _context(self, params):
        return db.ensure_context(params.get("context", ["pf"])[0])

    def _require(self, user):
        if not user:
            raise ValueError("Faça login para continuar.")

    def _admin(self, user):
        if not user or user["role"] != "admin":
            raise ValueError("Só o administrador pode fazer isso.")

    def _token(self):
        cookie = self.headers.get("Cookie") or ""
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name == "finances_session":
                return value
        return ""

    def _user(self):
        return db.user_by_token(self._token())

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > 1_000_000:
            self._error(413, "Requisição grande demais.")
            return None
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._error(400, "JSON inválido.")
            return None
        if not isinstance(data, dict):
            self._error(400, "O corpo precisa ser um objeto JSON.")
            return None
        return data

    def _static(self, path):
        relative = "index.html" if path in ("", "/") else path.lstrip("/")
        file_path = (STATIC / relative).resolve()
        try:
            file_path.relative_to(STATIC.resolve())
        except ValueError:
            self._error(404, "Arquivo não encontrado.")
            return
        if not file_path.is_file():
            self._error(404, "Arquivo não encontrado.")
            return
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".json": "application/manifest+json",
            ".png": "image/png",
            ".webmanifest": "application/manifest+json",
        }.get(file_path.suffix, "application/octet-stream")
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send(self, status, payload, token=None, clear=False):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if token:
            self.send_header("Set-Cookie", f"finances_session={token}; HttpOnly; SameSite=Lax; Path=/")
        if clear:
            self.send_header("Set-Cookie", "finances_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status, message):
        self._send(status, {"error": message})

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


def main():
    db.init_db()
    write_icon(STATIC / "icon-192.png", 192)
    write_icon(STATIC / "icon-512.png", 512)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Finances em http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

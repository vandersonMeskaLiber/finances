import calendar
import hashlib
import math
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "finances.db"

DIRECTIONS = ("entrada", "saida", "investimento", "transferencia")
CONTEXTS = ("pf", "pj")
MEI_LIMIT = 8_100_000
MEI_MONTH = 675_000
CARGA_LIMIT = 25_160_000
ME_LIMIT = 36_000_000
EPP_LIMIT = 480_000_000
DAS_INSS = 8105
DAS_INSS_CARGA = 19452
DAS_ICMS = 100
DAS_ISS = 500


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                last_context TEXT NOT NULL DEFAULT 'pf',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY,
                context TEXT NOT NULL,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                context TEXT NOT NULL,
                direction TEXT NOT NULL,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                position INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS subcategories (
                id INTEGER PRIMARY KEY,
                category_id INTEGER NOT NULL REFERENCES categories(id),
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                position INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS series (
                id INTEGER PRIMARY KEY,
                context TEXT NOT NULL,
                direction TEXT NOT NULL,
                account_id INTEGER NOT NULL,
                category_id INTEGER,
                subcategory_id INTEGER,
                amount INTEGER NOT NULL,
                day_of_month INTEGER NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                start_month TEXT NOT NULL,
                month_count INTEGER,
                frequency TEXT NOT NULL DEFAULT 'month',
                start_on TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                loan_id INTEGER,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY,
                context TEXT NOT NULL,
                direction TEXT NOT NULL,
                account_id INTEGER NOT NULL,
                transfer_account_id INTEGER,
                category_id INTEGER,
                subcategory_id INTEGER,
                amount INTEGER NOT NULL,
                occurred_on TEXT NOT NULL,
                status TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                series_id INTEGER,
                detached INTEGER NOT NULL DEFAULT 0,
                loan_id INTEGER,
                installment_no INTEGER,
                counts_as_revenue INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY,
                context TEXT NOT NULL,
                name TEXT NOT NULL,
                account_id INTEGER NOT NULL,
                category_id INTEGER,
                principal INTEGER NOT NULL,
                monthly_rate TEXT NOT NULL,
                system TEXT NOT NULL,
                term_months INTEGER NOT NULL,
                installment INTEGER NOT NULL,
                first_due TEXT NOT NULL,
                already_paid INTEGER NOT NULL DEFAULT 0,
                iof INTEGER NOT NULL DEFAULT 0,
                fees INTEGER NOT NULL DEFAULT 0,
                insurance INTEGER NOT NULL DEFAULT 0,
                series_id INTEGER,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS loan_rows (
                loan_id INTEGER NOT NULL,
                number INTEGER NOT NULL,
                due_on TEXT NOT NULL,
                installment INTEGER NOT NULL,
                interest INTEGER NOT NULL,
                amortization INTEGER NOT NULL,
                balance INTEGER NOT NULL,
                PRIMARY KEY (loan_id, number)
            );
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY,
                context TEXT NOT NULL,
                name TEXT NOT NULL,
                target_amount INTEGER NOT NULL,
                target_date TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS goal_months (
                goal_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                saved INTEGER NOT NULL DEFAULT 0,
                challenge INTEGER,
                PRIMARY KEY (goal_id, month)
            );
            CREATE TABLE IF NOT EXISTS company_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                kind TEXT NOT NULL,
                annual_limit INTEGER,
                opened_on TEXT,
                has_icms INTEGER NOT NULL DEFAULT 0,
                has_iss INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS das_months (
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                paid INTEGER NOT NULL DEFAULT 0,
                amount INTEGER,
                PRIMARY KEY (year, month)
            );
            CREATE TABLE IF NOT EXISTS dasn (
                year INTEGER PRIMARY KEY,
                delivered INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        if conn.execute("SELECT COUNT(*) AS n FROM settings").fetchone()["n"] == 0:
            conn.executemany(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                [("pf_enabled", "1"), ("pj_enabled", "0")],
            )
        if conn.execute("SELECT COUNT(*) AS n FROM company_profile").fetchone()["n"] == 0:
            conn.execute(
                "INSERT INTO company_profile (id, kind, annual_limit, opened_on, has_icms, has_iss) VALUES (1, 'mei', NULL, NULL, 0, 0)"
            )
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "last_context" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN last_context TEXT NOT NULL DEFAULT 'pf'")
        series_columns = {row["name"] for row in conn.execute("PRAGMA table_info(series)")}
        if "frequency" not in series_columns:
            conn.execute("ALTER TABLE series ADD COLUMN frequency TEXT NOT NULL DEFAULT 'month'")
        if "start_on" not in series_columns:
            conn.execute("ALTER TABLE series ADD COLUMN start_on TEXT")


def now():
    return datetime.now().isoformat(timespec="seconds")


def hash_password(password, salt=None):
    if not password or len(password) < 6:
        raise ValueError("A senha precisa ter pelo menos 6 caracteres.")
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return salt, digest


def public_user(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "active": row["active"],
        "last_context": row["last_context"] if "last_context" in row.keys() else "pf",
    }


def user_count():
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def create_user(name, email, password, role):
    name = str(name or "").strip()
    email = str(email or "").strip().lower()
    if not name or len(name) > 80:
        raise ValueError("Informe o nome.")
    if "@" not in email or len(email) > 120:
        raise ValueError("Informe um e-mail válido.")
    if role not in ("admin", "user"):
        raise ValueError("Papel inválido.")
    salt, digest = hash_password(password)
    with connect() as conn:
        if role == "user" and conn.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND active = 1").fetchone()["n"] == 0:
            raise ValueError("Crie o administrador antes.")
        try:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash, salt, role, active, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
                (name, email, digest, salt, role, now()),
            )
        except sqlite3.IntegrityError:
            raise ValueError("Já existe um login com esse e-mail.") from None
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return public_user(row)


def authenticate(email, password):
    email = str(email or "").strip().lower()
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row is None or not row["active"]:
            raise ValueError("E-mail ou senha incorretos.")
        _, digest = hash_password(password, row["salt"])
        if digest != row["password_hash"]:
            raise ValueError("E-mail ou senha incorretos.")
        token = secrets.token_urlsafe(32)
        expires = (datetime.now() + timedelta(days=30)).isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, row["id"], expires),
        )
    return token, public_user(row)


def user_by_token(token):
    if not token:
        return None
    with connect() as conn:
        row = conn.execute(
            """
            SELECT u.* FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > ? AND u.active = 1
            """,
            (token, now()),
        ).fetchone()
    return public_user(row) if row else None


def logout(token):
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def list_users():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY role, name COLLATE NOCASE").fetchall()
    return [public_user(row) for row in rows]


def set_user_active(user_id, active):
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise ValueError("Usuário não encontrado.")
        if row["role"] == "admin" and not active:
            others = conn.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND active = 1 AND id != ?", (user_id,)).fetchone()["n"]
            if others == 0:
                raise ValueError("O espaço precisa de um administrador ativo.")
        conn.execute("UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id))
        if not active:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def update_user(user_id, name, email, role, password=None):
    name = str(name or "").strip()
    email = str(email or "").strip().lower()
    if not name or len(name) > 80:
        raise ValueError("Informe o nome.")
    if "@" not in email or len(email) > 120:
        raise ValueError("Informe um e-mail válido.")
    if role not in ("admin", "user"):
        raise ValueError("Papel inválido.")
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise ValueError("Usuário não encontrado.")
        if row["role"] == "admin" and role != "admin":
            others = conn.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND active = 1 AND id != ?", (user_id,)).fetchone()["n"]
            if others == 0:
                raise ValueError("O espaço precisa de um administrador ativo.")
        fields = [name, email, role, user_id]
        sql = "UPDATE users SET name = ?, email = ?, role = ? WHERE id = ?"
        if password:
            salt, digest = hash_password(password)
            sql = "UPDATE users SET name = ?, email = ?, role = ?, password_hash = ?, salt = ? WHERE id = ?"
            fields = [name, email, role, digest, salt, user_id]
        try:
            conn.execute(sql, fields)
        except sqlite3.IntegrityError:
            raise ValueError("Já existe um login com esse e-mail.") from None
        updated = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return public_user(updated)


def delete_user(user_id, actor_id):
    if int(user_id) == int(actor_id):
        raise ValueError("Você não pode apagar o próprio acesso.")
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise ValueError("Usuário não encontrado.")
        if row["role"] == "admin":
            others = conn.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND id != ?", (user_id,)).fetchone()["n"]
            if others == 0:
                raise ValueError("O espaço precisa de um administrador.")
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def reset_password(user_id, password):
    salt, digest = hash_password(password)
    with connect() as conn:
        if conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone() is None:
            raise ValueError("Usuário não encontrado.")
        conn.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (digest, salt, user_id))
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def settings():
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    data = {row["key"]: row["value"] == "1" for row in rows}
    return {"pf": data.get("pf_enabled", True), "pj": data.get("pj_enabled", False)}


def set_context_enabled(context, enabled):
    if context not in CONTEXTS:
        raise ValueError("Contexto inválido.")
    key = "pf_enabled" if context == "pf" else "pj_enabled"
    with connect() as conn:
        conn.execute("UPDATE settings SET value = ? WHERE key = ?", ("1" if enabled else "0", key))
        current = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM settings")}
        if current.get("pf_enabled") != "1" and current.get("pj_enabled") != "1":
            conn.execute("UPDATE settings SET value = '1' WHERE key = ?", (key,))
            raise ValueError("Pelo menos um contexto precisa ficar ligado.")
    return settings()


def set_last_context(user_id, context):
    context = ensure_context(context)
    with connect() as conn:
        if conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone() is None:
            raise ValueError("Usuário não encontrado.")
        conn.execute("UPDATE users SET last_context = ? WHERE id = ?", (context, user_id))
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return public_user(row)


def ensure_context(context):
    if context not in CONTEXTS:
        raise ValueError("Contexto inválido.")
    enabled = settings()
    if not enabled["pf" if context == "pf" else "pj"]:
        raise ValueError("Esse contexto está desligado.")
    return context


def clean_name(value, label):
    name = str(value or "").strip()
    if not name or len(name) > 60:
        raise ValueError(f"{label} deve ter entre 1 e 60 caracteres.")
    return name


def clean_amount(value):
    try:
        amount = int(value)
    except (TypeError, ValueError):
        raise ValueError("Valor inválido.") from None
    if amount <= 0 or amount > 100_000_000_00:
        raise ValueError("O valor precisa ser maior que zero.")
    return amount


def clean_date(value):
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        raise ValueError("Data inválida.") from None


def month_bounds(month):
    try:
        year, mon = (int(part) for part in str(month).split("-"))
        start = date(year, mon, 1)
    except (ValueError, AttributeError):
        raise ValueError("Mês inválido.") from None
    if mon == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, mon + 1, 1)
    return start, end


def shift_month(year, mon, offset):
    index = year * 12 + (mon - 1) + offset
    return index // 12, index % 12 + 1


def occurrence_date(year, mon, day):
    last = calendar.monthrange(year, mon)[1]
    return date(year, mon, min(int(day), last))


REPEAT_FREQUENCIES = ("month", "week", "day")
REPEAT_DEFAULT = {"month": 60, "week": 52, "day": 30}
REPEAT_UNIT = {"month": "meses", "week": "semanas", "day": "dias"}


def _repeat_count(payload, frequency):
    raw = payload.get("count", payload.get("month_count"))
    if raw in ("", None):
        return None
    try:
        count = int(raw)
    except (TypeError, ValueError):
        raise ValueError("A quantidade de repetições é inválida.") from None
    if count < 1 or count > 480:
        raise ValueError(f"A quantidade de {REPEAT_UNIT[frequency]} precisa ficar entre 1 e 480.")
    return count


def _series_anchor(payload, frequency):
    if payload.get("start_on") or payload.get("occurred_on"):
        start_on = date.fromisoformat(clean_date(payload.get("start_on") or payload.get("occurred_on")))
    else:
        start, _ = month_bounds(str(payload.get("start_month")))
        day = int(payload.get("day_of_month"))
        if day < 1 or day > 31:
            raise ValueError("Dia inválido.")
        return occurrence_date(start.year, start.month, day), day
    if frequency == "month":
        day = int(payload.get("day_of_month") or start_on.day)
        if day < 1 or day > 31:
            raise ValueError("Dia inválido.")
        return occurrence_date(start_on.year, start_on.month, day), day
    if frequency == "week":
        return start_on, start_on.weekday()
    return start_on, start_on.day


def _series_dates(frequency, start_on, day, total):
    if frequency == "month":
        dates = []
        for offset in range(total):
            year, mon = shift_month(start_on.year, start_on.month, offset)
            dates.append(occurrence_date(year, mon, day))
        return dates
    step = 7 if frequency == "week" else 1
    return [start_on + timedelta(days=step * offset) for offset in range(total)]


def list_accounts(context, include_inactive=False):
    ensure_context(context)
    clause = "" if include_inactive else "AND active = 1"
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM accounts WHERE context = ? {clause} ORDER BY name COLLATE NOCASE",
            (context,),
        ).fetchall()
        accounts = []
        used = {
            row["id"]
            for row in conn.execute(
                """
                SELECT account_id AS id FROM transactions
                UNION SELECT transfer_account_id FROM transactions WHERE transfer_account_id IS NOT NULL
                UNION SELECT account_id FROM series
                UNION SELECT account_id FROM loans
                """
            )
        }
        for row in rows:
            balance = account_balance(conn, row["id"])
            item = dict(row)
            item["balance"] = balance
            item["deletable"] = item["id"] not in used
            accounts.append(item)
    return accounts


def account_balance(conn, account_id):
    row = conn.execute(
        """
        SELECT COALESCE(SUM(
            CASE
                WHEN direction = 'entrada' AND account_id = ? THEN amount
                WHEN direction IN ('saida', 'investimento') AND account_id = ? THEN -amount
                WHEN direction = 'transferencia' AND account_id = ? THEN -amount
                WHEN direction = 'transferencia' AND transfer_account_id = ? THEN amount
                ELSE 0
            END
        ), 0) AS balance
        FROM transactions
        WHERE status = 'efetivado' AND (account_id = ? OR transfer_account_id = ?)
        """,
        (account_id, account_id, account_id, account_id, account_id, account_id),
    ).fetchone()
    return row["balance"]


def create_account(context, name):
    ensure_context(context)
    name = clean_name(name, "Nome da conta")
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO accounts (context, name, active, created_at) VALUES (?, ?, 1, ?)",
            (context, name, now()),
        )
        account_id = cur.lastrowid
    return next(item for item in list_accounts(context, True) if item["id"] == account_id)


def update_account(account_id, name=None, active=None):
    with connect() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if row is None:
            raise ValueError("Conta não encontrada.")
        next_name = clean_name(name, "Nome da conta") if name is not None else row["name"]
        next_active = row["active"] if active is None else (1 if active else 0)
        conn.execute("UPDATE accounts SET name = ?, active = ? WHERE id = ?", (next_name, next_active, account_id))
        context = row["context"]
    return next(item for item in list_accounts(context, True) if item["id"] == account_id)


def delete_account(account_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if row is None:
            raise ValueError("Conta não encontrada.")
        used = conn.execute(
            """
            SELECT 1 FROM transactions WHERE account_id = ? OR transfer_account_id = ?
            UNION SELECT 1 FROM series WHERE account_id = ?
            UNION SELECT 1 FROM loans WHERE account_id = ?
            LIMIT 1
            """,
            (account_id, account_id, account_id, account_id),
        ).fetchone()
        if used:
            raise ValueError("Esta conta já está em um lançamento. Desative para não usar em lançamentos novos.")
        conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))


def list_categories(context):
    ensure_context(context)
    with connect() as conn:
        categories = [dict(row) for row in conn.execute(
            "SELECT * FROM categories WHERE context = ? ORDER BY direction, position, name COLLATE NOCASE",
            (context,),
        )]
        subs = [dict(row) for row in conn.execute(
            """
            SELECT s.* FROM subcategories s
            JOIN categories c ON c.id = s.category_id
            WHERE c.context = ?
            ORDER BY s.position, s.name COLLATE NOCASE
            """,
            (context,),
        )]
        used_categories = {
            row["category_id"]
            for row in conn.execute(
                "SELECT DISTINCT category_id FROM transactions WHERE context = ? AND category_id IS NOT NULL",
                (context,),
            )
        }
        used_subs = {
            row["subcategory_id"]
            for row in conn.execute(
                "SELECT DISTINCT subcategory_id FROM transactions WHERE context = ? AND subcategory_id IS NOT NULL",
                (context,),
            )
        }
    for category in categories:
        children = [sub for sub in subs if sub["category_id"] == category["id"]]
        for sub in children:
            sub["deletable"] = sub["id"] not in used_subs
        category["subcategories"] = children
        category["deletable"] = category["id"] not in used_categories and all(sub["deletable"] for sub in children)
    return categories


def create_category(context, direction, name):
    ensure_context(context)
    if direction not in ("entrada", "saida"):
        raise ValueError("Tipo serve para entrada ou saída.")
    name = clean_name(name, "Nome do tipo")
    with connect() as conn:
        position = conn.execute("SELECT COALESCE(MAX(position), 0) + 1 AS p FROM categories WHERE context = ?", (context,)).fetchone()["p"]
        cur = conn.execute(
            "INSERT INTO categories (context, direction, name, active, position) VALUES (?, ?, ?, 1, ?)",
            (context, direction, name, position),
        )
        category_id = cur.lastrowid
    return next(item for item in list_categories(context) if item["id"] == category_id)


def update_category(category_id, name=None, active=None, position=None):
    with connect() as conn:
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        if row is None:
            raise ValueError("Tipo não encontrado.")
        conn.execute(
            "UPDATE categories SET name = ?, active = ?, position = ? WHERE id = ?",
            (
                clean_name(name, "Nome do tipo") if name is not None else row["name"],
                row["active"] if active is None else (1 if active else 0),
                row["position"] if position is None else int(position),
                category_id,
            ),
        )
        context = row["context"]
    return next(item for item in list_categories(context) if item["id"] == category_id)


def create_subcategory(category_id, name):
    name = clean_name(name, "Nome do subtipo")
    with connect() as conn:
        parent = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        if parent is None:
            raise ValueError("Tipo não encontrado.")
        position = conn.execute("SELECT COALESCE(MAX(position), 0) + 1 AS p FROM subcategories WHERE category_id = ?", (category_id,)).fetchone()["p"]
        conn.execute(
            "INSERT INTO subcategories (category_id, name, active, position) VALUES (?, ?, 1, ?)",
            (category_id, name, position),
        )
        context = parent["context"]
    return next(item for item in list_categories(context) if item["id"] == category_id)


def update_subcategory(subcategory_id, name=None, active=None):
    with connect() as conn:
        row = conn.execute(
            """
            SELECT s.*, c.context FROM subcategories s
            JOIN categories c ON c.id = s.category_id
            WHERE s.id = ?
            """,
            (subcategory_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Subtipo não encontrado.")
        conn.execute(
            "UPDATE subcategories SET name = ?, active = ? WHERE id = ?",
            (
                clean_name(name, "Nome do subtipo") if name is not None else row["name"],
                row["active"] if active is None else (1 if active else 0),
                subcategory_id,
            ),
        )
        context = row["context"]
        category_id = row["category_id"]
    return next(item for item in list_categories(context) if item["id"] == category_id)


def delete_category(category_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        if row is None:
            raise ValueError("Tipo não encontrado.")
        if _category_used(conn, category_id):
            raise ValueError("Este tipo já está em um lançamento. Desative para não usar em lançamentos novos.")
        conn.execute(
            "UPDATE series SET subcategory_id = NULL WHERE subcategory_id IN (SELECT id FROM subcategories WHERE category_id = ?)",
            (category_id,),
        )
        conn.execute("UPDATE series SET category_id = NULL WHERE category_id = ?", (category_id,))
        conn.execute("UPDATE loans SET category_id = NULL WHERE category_id = ?", (category_id,))
        conn.execute("DELETE FROM subcategories WHERE category_id = ?", (category_id,))
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))


def delete_subcategory(subcategory_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM subcategories WHERE id = ?", (subcategory_id,)).fetchone()
        if row is None:
            raise ValueError("Subtipo não encontrado.")
        used = conn.execute(
            "SELECT 1 FROM transactions WHERE subcategory_id = ? LIMIT 1",
            (subcategory_id,),
        ).fetchone()
        if used:
            raise ValueError("Este subtipo já está em um lançamento. Desative para não usar em lançamentos novos.")
        conn.execute("UPDATE series SET subcategory_id = NULL WHERE subcategory_id = ?", (subcategory_id,))
        conn.execute("DELETE FROM subcategories WHERE id = ?", (subcategory_id,))


def _category_used(conn, category_id):
    if conn.execute("SELECT 1 FROM transactions WHERE category_id = ? LIMIT 1", (category_id,)).fetchone():
        return True
    return conn.execute(
        """
        SELECT 1 FROM transactions t
        JOIN subcategories s ON s.id = t.subcategory_id
        WHERE s.category_id = ?
        LIMIT 1
        """,
        (category_id,),
    ).fetchone()


def _validate_category(conn, context, direction, category_id, subcategory_id):
    if direction in ("investimento", "transferencia"):
        return None, None
    if not category_id:
        raise ValueError("Escolha o tipo.")
    category = conn.execute("SELECT * FROM categories WHERE id = ? AND context = ?", (category_id, context)).fetchone()
    if category is None or category["direction"] != direction:
        raise ValueError("O tipo não corresponde ao lançamento.")
    if not category["active"]:
        raise ValueError("Esse tipo está desativado.")
    if subcategory_id:
        sub = conn.execute("SELECT * FROM subcategories WHERE id = ? AND category_id = ?", (subcategory_id, category_id)).fetchone()
        if sub is None:
            raise ValueError("Subtipo não encontrado.")
        if not sub["active"]:
            raise ValueError("Esse subtipo está desativado.")
        return category["id"], sub["id"]
    return category["id"], None


def _account_in_context(conn, account_id, context):
    row = conn.execute("SELECT * FROM accounts WHERE id = ? AND context = ? AND active = 1", (account_id, context)).fetchone()
    if row is None:
        raise ValueError("Conta não encontrada nesse contexto.")
    return row


def create_transaction(payload):
    context = ensure_context(payload.get("context"))
    direction = payload.get("direction")
    if direction not in DIRECTIONS:
        raise ValueError("Direção inválida.")
    amount = clean_amount(payload.get("amount"))
    occurred_on = clean_date(payload.get("occurred_on"))
    status = payload.get("status") or "previsto"
    if status not in ("previsto", "efetivado", "cancelado"):
        raise ValueError("Situação inválida.")
    description = str(payload.get("description") or "").strip()
    if len(description) > 200:
        raise ValueError("A descrição pode ter no máximo 200 caracteres.")
    with connect() as conn:
        account = _account_in_context(conn, payload.get("account_id"), context)
        transfer_id = None
        if direction == "transferencia":
            dest = _account_in_context(conn, payload.get("transfer_account_id"), context)
            if dest["id"] == account["id"]:
                raise ValueError("A transferência precisa de duas contas diferentes.")
            transfer_id = dest["id"]
            category_id, subcategory_id = None, None
        else:
            category_id, subcategory_id = _validate_category(
                conn, context, direction, payload.get("category_id"), payload.get("subcategory_id")
            )
        counts = 1 if direction == "entrada" and payload.get("counts_as_revenue", True) else 0
        cur = conn.execute(
            """
            INSERT INTO transactions (
                context, direction, account_id, transfer_account_id, category_id, subcategory_id,
                amount, occurred_on, status, description, series_id, detached, loan_id,
                installment_no, counts_as_revenue, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (
                context, direction, account["id"], transfer_id, category_id, subcategory_id,
                amount, occurred_on, status, description, payload.get("series_id"),
                payload.get("loan_id"), payload.get("installment_no"), counts, now(),
            ),
        )
        transaction_id = cur.lastrowid
    return get_transaction(transaction_id)


def get_transaction(transaction_id):
    with connect() as conn:
        row = conn.execute(_transaction_sql() + " WHERE t.id = ?", (transaction_id,)).fetchone()
    if row is None:
        raise ValueError("Lançamento não encontrado.")
    return _transaction_dict(row)


def _transaction_sql():
    return """
        SELECT t.*, a.name AS account_name, b.name AS transfer_account_name,
               c.name AS category_name, s.name AS subcategory_name,
               sr.frequency AS series_frequency
        FROM transactions t
        JOIN accounts a ON a.id = t.account_id
        LEFT JOIN accounts b ON b.id = t.transfer_account_id
        LEFT JOIN categories c ON c.id = t.category_id
        LEFT JOIN subcategories s ON s.id = t.subcategory_id
        LEFT JOIN series sr ON sr.id = t.series_id
    """


def _transaction_dict(row):
    item = dict(row)
    item["late"] = item["status"] == "previsto" and item["occurred_on"] < date.today().isoformat()
    return item


def list_transactions(context, month=None, direction=None, day=None, pending=False, account_id=None):
    ensure_context(context)
    clauses = ["t.context = ?"]
    params = [context]
    if month:
        start, end = month_bounds(month)
        clauses.append("t.occurred_on >= ? AND t.occurred_on < ?")
        params.extend([start.isoformat(), end.isoformat()])
    if direction:
        clauses.append("t.direction = ?")
        params.append(direction)
    if day:
        clauses.append("t.occurred_on = ?")
        params.append(clean_date(day))
    if pending:
        clauses.append("t.status = 'previsto'")
    if account_id:
        clauses.append("(t.account_id = ? OR t.transfer_account_id = ?)")
        params.extend([account_id, account_id])
    sql = _transaction_sql() + " WHERE " + " AND ".join(clauses) + " ORDER BY t.occurred_on, t.id"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_transaction_dict(row) for row in rows]


def update_transaction(transaction_id, payload, scope="this"):
    current = get_transaction(transaction_id)
    if scope not in ("this", "all"):
        raise ValueError("Escolha alterar só este lançamento ou todas as ocorrências.")
    if scope == "all" and not current["series_id"]:
        scope = "this"
    if scope == "this":
        return _update_one(transaction_id, payload, detach=bool(current["series_id"]))
    return _update_series_from_transaction(current, payload)


def _update_one(transaction_id, payload, detach):
    current = get_transaction(transaction_id)
    direction = payload.get("direction", current["direction"])
    amount = clean_amount(payload.get("amount", current["amount"]))
    occurred_on = clean_date(payload.get("occurred_on", current["occurred_on"]))
    status = payload.get("status", current["status"])
    description = str(payload.get("description", current["description"]) or "").strip()
    with connect() as conn:
        account = _account_in_context(conn, payload.get("account_id", current["account_id"]), current["context"])
        transfer_id = None
        if direction == "transferencia":
            dest = _account_in_context(conn, payload.get("transfer_account_id", current["transfer_account_id"]), current["context"])
            if dest["id"] == account["id"]:
                raise ValueError("A transferência precisa de duas contas diferentes.")
            transfer_id = dest["id"]
            category_id, subcategory_id = None, None
        else:
            category_id, subcategory_id = _validate_category(
                conn, current["context"], direction,
                payload.get("category_id", current["category_id"]),
                payload.get("subcategory_id", current["subcategory_id"]),
            )
        counts = 1 if direction == "entrada" and payload.get("counts_as_revenue", current["counts_as_revenue"]) else 0
        conn.execute(
            """
            UPDATE transactions
            SET direction = ?, account_id = ?, transfer_account_id = ?, category_id = ?, subcategory_id = ?,
                amount = ?, occurred_on = ?, status = ?, description = ?, detached = ?, counts_as_revenue = ?
            WHERE id = ?
            """,
            (
                direction, account["id"], transfer_id, category_id, subcategory_id, amount, occurred_on,
                status, description, 1 if detach else current["detached"], counts, transaction_id,
            ),
        )
    return get_transaction(transaction_id)


def _update_series_from_transaction(current, payload):
    with connect() as conn:
        series = conn.execute("SELECT * FROM series WHERE id = ?", (current["series_id"],)).fetchone()
        if series is None:
            raise ValueError("Série não encontrada.")
        amount = clean_amount(payload.get("amount", series["amount"]))
        description = str(payload.get("description", series["description"]) or "").strip()
        account = _account_in_context(conn, payload.get("account_id", series["account_id"]), series["context"])
        category_id, subcategory_id = _validate_category(
            conn, series["context"], series["direction"],
            payload.get("category_id", series["category_id"]),
            payload.get("subcategory_id", series["subcategory_id"]),
        )
        frequency = series["frequency"] or "month"
        rows = conn.execute(
            """
            SELECT * FROM transactions
            WHERE series_id = ? AND detached = 0 AND status = 'previsto'
            """,
            (series["id"],),
        ).fetchall()
        if frequency == "month":
            day = int(payload.get("day_of_month") or date.fromisoformat(payload.get("occurred_on", current["occurred_on"])).day)
            if day < 1 or day > 31:
                raise ValueError("Dia inválido.")
            conn.execute(
                """
                UPDATE series
                SET account_id = ?, category_id = ?, subcategory_id = ?, amount = ?, day_of_month = ?, description = ?
                WHERE id = ?
                """,
                (account["id"], category_id, subcategory_id, amount, day, description, series["id"]),
            )
            dated = []
            for row in rows:
                when = date.fromisoformat(row["occurred_on"])
                dated.append((row, occurrence_date(when.year, when.month, day)))
        else:
            old = date.fromisoformat(current["occurred_on"])
            new = date.fromisoformat(clean_date(payload.get("occurred_on", current["occurred_on"])))
            delta = new - old
            start_on = series["start_on"]
            if start_on:
                start_on = (date.fromisoformat(start_on) + delta).isoformat()
            conn.execute(
                """
                UPDATE series
                SET account_id = ?, category_id = ?, subcategory_id = ?, amount = ?, description = ?, start_on = ?
                WHERE id = ?
                """,
                (account["id"], category_id, subcategory_id, amount, description, start_on, series["id"]),
            )
            dated = [(row, date.fromisoformat(row["occurred_on"]) + delta) for row in rows]
        for row, new_date in dated:
            conn.execute(
                """
                UPDATE transactions
                SET account_id = ?, category_id = ?, subcategory_id = ?, amount = ?, occurred_on = ?, description = ?
                WHERE id = ?
                """,
                (account["id"], category_id, subcategory_id, amount, new_date.isoformat(), description, row["id"]),
            )
    return get_transaction(current["id"])


def cancel_transaction(transaction_id):
    current = get_transaction(transaction_id)
    with connect() as conn:
        conn.execute("UPDATE transactions SET status = 'cancelado' WHERE id = ?", (transaction_id,))
    return get_transaction(current["id"])


def delete_transaction(transaction_id):
    current = get_transaction(transaction_id)
    with connect() as conn:
        if current.get("loan_id"):
            conn.execute("UPDATE transactions SET status = 'cancelado' WHERE id = ?", (transaction_id,))
            return
        conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))


def create_series(payload):
    context = ensure_context(payload.get("context"))
    direction = payload.get("direction")
    if direction not in ("entrada", "saida"):
        raise ValueError("A repetição vale para entrada ou saída.")
    frequency = payload.get("frequency") or "month"
    if frequency not in REPEAT_FREQUENCIES:
        raise ValueError("A repetição é todo mês, toda semana ou todo dia.")
    amount = clean_amount(payload.get("amount"))
    start_on, day = _series_anchor(payload, frequency)
    repeat_count = _repeat_count(payload, frequency)
    description = str(payload.get("description") or "").strip()
    first_status = payload.get("status") if payload.get("status") in ("previsto", "efetivado") else "previsto"
    with connect() as conn:
        account = _account_in_context(conn, payload.get("account_id"), context)
        category_id, subcategory_id = _validate_category(
            conn, context, direction, payload.get("category_id"), payload.get("subcategory_id")
        )
        cur = conn.execute(
            """
            INSERT INTO series (
                context, direction, account_id, category_id, subcategory_id, amount, day_of_month,
                description, start_month, month_count, active, loan_id, created_at, frequency, start_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                context, direction, account["id"], category_id, subcategory_id, amount, day,
                description, start_on.strftime("%Y-%m"), repeat_count, payload.get("loan_id"), now(),
                frequency, start_on.isoformat(),
            ),
        )
        series_id = cur.lastrowid
        total = repeat_count if repeat_count else REPEAT_DEFAULT[frequency]
        dates = _series_dates(frequency, start_on, day, total)
        for offset, when in enumerate(dates):
            status = first_status if offset == 0 else "previsto"
            conn.execute(
                """
                INSERT INTO transactions (
                    context, direction, account_id, transfer_account_id, category_id, subcategory_id,
                    amount, occurred_on, status, description, series_id, detached, loan_id,
                    installment_no, counts_as_revenue, created_at
                ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
                """,
                (
                    context, direction, account["id"], category_id, subcategory_id, amount, when.isoformat(),
                    status, description, series_id, payload.get("loan_id"), offset + 1,
                    1 if payload.get("counts_as_revenue", direction == "entrada") else 0, now(),
                ),
            )
    return get_series(series_id)


def get_series(series_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM series WHERE id = ?", (series_id,)).fetchone()
        if row is None:
            raise ValueError("Série não encontrada.")
        items = conn.execute(
            "SELECT id, occurred_on, amount, status, detached FROM transactions WHERE series_id = ? ORDER BY occurred_on",
            (series_id,),
        ).fetchall()
    data = dict(row)
    data["occurrences"] = [dict(item) for item in items]
    return data


def end_series(series_id, from_month):
    start, _ = month_bounds(from_month)
    with connect() as conn:
        series = conn.execute("SELECT * FROM series WHERE id = ?", (series_id,)).fetchone()
        if series is None:
            raise ValueError("Série não encontrada.")
        conn.execute("UPDATE series SET active = 0 WHERE id = ?", (series_id,))
        conn.execute(
            """
            UPDATE transactions
            SET status = 'cancelado'
            WHERE series_id = ? AND status = 'previsto' AND occurred_on >= ?
            """,
            (series_id, start.isoformat()),
        )
    return get_series(series_id)


def build_schedule(principal, monthly_rate, term, system, first_due):
    principal = clean_amount(principal)
    term = int(term)
    if term < 1 or term > 480:
        raise ValueError("Prazo inválido.")
    rate = Decimal(str(monthly_rate))
    if rate < 0:
        raise ValueError("Taxa inválida.")
    system = system or "price"
    if system not in ("price", "sac"):
        raise ValueError("Sistema inválido.")
    first = date.fromisoformat(clean_date(first_due))
    rows = []
    balance = principal
    if system == "price":
        if rate == 0:
            installment = int((Decimal(principal) / Decimal(term)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        else:
            factor = (Decimal(1) - (Decimal(1) + rate) ** (-term))
            installment = int((Decimal(principal) * rate / factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        for number in range(1, term + 1):
            interest = int((Decimal(balance) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            if number == term:
                amortization = balance
                payment = interest + amortization
            else:
                payment = installment
                amortization = payment - interest
                if amortization > balance:
                    amortization = balance
                    payment = interest + amortization
            balance -= amortization
            year, mon = shift_month(first.year, first.month, number - 1)
            rows.append({
                "number": number,
                "due_on": occurrence_date(year, mon, first.day).isoformat(),
                "installment": payment,
                "interest": interest,
                "amortization": amortization,
                "balance": balance,
            })
    else:
        base = principal // term
        remainder = principal - base * term
        for number in range(1, term + 1):
            interest = int((Decimal(balance) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            amortization = base + (1 if number <= remainder else 0)
            payment = amortization + interest
            balance -= amortization
            year, mon = shift_month(first.year, first.month, number - 1)
            rows.append({
                "number": number,
                "due_on": occurrence_date(year, mon, first.day).isoformat(),
                "installment": payment,
                "interest": interest,
                "amortization": amortization,
                "balance": balance,
            })
    return rows


def solve_term(principal, monthly_rate, installment):
    principal = clean_amount(principal)
    installment = clean_amount(installment)
    rate = Decimal(str(monthly_rate))
    if rate == 0:
        return math.ceil(principal / installment)
    interest = int((Decimal(principal) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if installment <= interest:
        raise ValueError("A parcela não cobre os juros do primeiro mês.")
    n = -math.log(1 - float(Decimal(principal) * rate / Decimal(installment))) / math.log(float(1 + rate))
    return max(1, math.ceil(n - 1e-9))


def preview_loan(payload):
    rate = Decimal(str(payload.get("monthly_rate")).replace(",", ".")) / Decimal(100)
    system = payload.get("system") or "price"
    principal = payload.get("principal")
    if payload.get("term_months"):
        term = int(payload["term_months"])
    else:
        term = solve_term(principal, rate, payload.get("installment"))
    rows = build_schedule(principal, rate, term, system, payload.get("first_due"))
    extras = int(payload.get("iof") or 0) + int(payload.get("fees") or 0) + int(payload.get("insurance") or 0)
    total_paid = sum(row["installment"] for row in rows) + extras
    return {
        "term_months": term,
        "installment": rows[0]["installment"],
        "last_installment": rows[-1]["installment"],
        "total_interest": sum(row["interest"] for row in rows),
        "total_paid": total_paid,
        "leftover": rows[-1]["balance"],
        "rows": rows,
        "cet_ready": extras > 0,
    }


def create_loan(payload):
    context = ensure_context(payload.get("context"))
    preview = preview_loan(payload)
    name = clean_name(payload.get("name") or "Empréstimo", "Nome")
    already = int(payload.get("already_paid") or 0)
    if already < 0 or already > preview["term_months"]:
        raise ValueError("A quantidade de parcelas já pagas é inválida.")
    rate = str(Decimal(str(payload.get("monthly_rate")).replace(",", ".")) / Decimal(100))
    with connect() as conn:
        account = _account_in_context(conn, payload.get("account_id"), context)
        category_id, _ = _validate_category(conn, context, "saida", payload.get("category_id"), None)
        cur = conn.execute(
            """
            INSERT INTO loans (
                context, name, account_id, category_id, principal, monthly_rate, system, term_months,
                installment, first_due, already_paid, iof, fees, insurance, series_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                context, name, account["id"], category_id, clean_amount(payload.get("principal")), rate,
                payload.get("system") or "price", preview["term_months"], preview["installment"],
                clean_date(payload.get("first_due")), already, int(payload.get("iof") or 0),
                int(payload.get("fees") or 0), int(payload.get("insurance") or 0), now(),
            ),
        )
        loan_id = cur.lastrowid
        for row in preview["rows"]:
            conn.execute(
                "INSERT INTO loan_rows (loan_id, number, due_on, installment, interest, amortization, balance) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (loan_id, row["number"], row["due_on"], row["installment"], row["interest"], row["amortization"], row["balance"]),
            )
        series = conn.execute(
            """
            INSERT INTO series (
                context, direction, account_id, category_id, subcategory_id, amount, day_of_month,
                description, start_month, month_count, active, loan_id, created_at
            ) VALUES (?, 'saida', ?, ?, NULL, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                context, account["id"], category_id, preview["installment"], date.fromisoformat(preview["rows"][0]["due_on"]).day,
                name, preview["rows"][0]["due_on"][:7], preview["term_months"], loan_id, now(),
            ),
        )
        series_id = series.lastrowid
        conn.execute("UPDATE loans SET series_id = ? WHERE id = ?", (series_id, loan_id))
        for row in preview["rows"]:
            status = "efetivado" if row["number"] <= already else "previsto"
            conn.execute(
                """
                INSERT INTO transactions (
                    context, direction, account_id, transfer_account_id, category_id, subcategory_id,
                    amount, occurred_on, status, description, series_id, detached, loan_id,
                    installment_no, counts_as_revenue, created_at
                ) VALUES (?, 'saida', ?, NULL, ?, NULL, ?, ?, ?, ?, ?, 0, ?, ?, 0, ?)
                """,
                (
                    context, account["id"], category_id, row["installment"], row["due_on"], status,
                    f"{name} {row['number']}/{preview['term_months']}", series_id, loan_id, row["number"], now(),
                ),
            )
    return get_loan(loan_id)


def get_loan(loan_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
        if row is None:
            raise ValueError("Empréstimo não encontrado.")
        schedule = [dict(item) for item in conn.execute("SELECT * FROM loan_rows WHERE loan_id = ? ORDER BY number", (loan_id,))]
        paid = conn.execute(
            "SELECT installment_no, status, id FROM transactions WHERE loan_id = ? ORDER BY installment_no",
            (loan_id,),
        ).fetchall()
    paid_map = {item["installment_no"]: dict(item) for item in paid}
    for item in schedule:
        link = paid_map.get(item["number"])
        item["status"] = link["status"] if link else "previsto"
        item["transaction_id"] = link["id"] if link else None
    data = dict(row)
    data["rows"] = schedule

    def status_of(number):
        link = paid_map.get(number)
        return link["status"] if link else "previsto"

    open_row = next((item for item in schedule if status_of(item["number"]) == "previsto"), None)
    if open_row is None:
        last_paid = next((item for item in reversed(schedule) if status_of(item["number"]) == "efetivado"), None)
        data["remaining"] = 0 if last_paid and last_paid["number"] == schedule[-1]["number"] else (last_paid["balance"] if last_paid else data["principal"])
    else:
        previous = next((item for item in schedule if item["number"] == open_row["number"] - 1), None)
        data["remaining"] = previous["balance"] if previous else data["principal"]
    data["total_interest"] = sum(item["interest"] for item in schedule)
    return data


def settle_elapsed_installments(loan_id, today=None):
    today = (today or date.today()).isoformat()
    get_loan(loan_id)
    with connect() as conn:
        conn.execute(
            "UPDATE transactions SET status = 'efetivado' WHERE loan_id = ? AND status = 'previsto' AND occurred_on < ?",
            (loan_id, today),
        )
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM transactions WHERE loan_id = ? AND status = 'efetivado'",
            (loan_id,),
        ).fetchone()["n"]
        conn.execute("UPDATE loans SET already_paid = ? WHERE id = ?", (count, loan_id))
    return get_loan(loan_id)


def _loan_rate(payload):
    return Decimal(str(payload.get("monthly_rate")).replace(",", ".")) / Decimal(100)


def _loan_terms_match(current, payload, preview):
    return (
        clean_amount(payload.get("principal")) == current["principal"]
        and _loan_rate(payload) == Decimal(str(current["monthly_rate"]))
        and (payload.get("system") or "price") == current["system"]
        and preview["term_months"] == current["term_months"]
        and clean_date(payload.get("first_due")) == current["first_due"]
        and int(payload.get("already_paid") or 0) == int(current["already_paid"])
    )


def _clear_loan_children(conn, loan_id, series_id):
    if series_id is None:
        conn.execute("DELETE FROM transactions WHERE loan_id = ?", (loan_id,))
    else:
        conn.execute("DELETE FROM transactions WHERE loan_id = ? OR series_id = ?", (loan_id, series_id))
    conn.execute("DELETE FROM loan_rows WHERE loan_id = ?", (loan_id,))
    conn.execute("DELETE FROM series WHERE loan_id = ? OR id = ?", (loan_id, series_id if series_id is not None else -1))


def _insert_loan_schedule(conn, loan_id, context, name, account_id, category_id, preview, already):
    for row in preview["rows"]:
        conn.execute(
            "INSERT INTO loan_rows (loan_id, number, due_on, installment, interest, amortization, balance) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (loan_id, row["number"], row["due_on"], row["installment"], row["interest"], row["amortization"], row["balance"]),
        )
    series = conn.execute(
        """
        INSERT INTO series (
            context, direction, account_id, category_id, subcategory_id, amount, day_of_month,
            description, start_month, month_count, active, loan_id, created_at
        ) VALUES (?, 'saida', ?, ?, NULL, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (
            context, account_id, category_id, preview["installment"], date.fromisoformat(preview["rows"][0]["due_on"]).day,
            name, preview["rows"][0]["due_on"][:7], preview["term_months"], loan_id, now(),
        ),
    )
    series_id = series.lastrowid
    conn.execute("UPDATE loans SET series_id = ? WHERE id = ?", (series_id, loan_id))
    for row in preview["rows"]:
        status = "efetivado" if row["number"] <= already else "previsto"
        conn.execute(
            """
            INSERT INTO transactions (
                context, direction, account_id, transfer_account_id, category_id, subcategory_id,
                amount, occurred_on, status, description, series_id, detached, loan_id,
                installment_no, counts_as_revenue, created_at
            ) VALUES (?, 'saida', ?, NULL, ?, NULL, ?, ?, ?, ?, ?, 0, ?, ?, 0, ?)
            """,
            (
                context, account_id, category_id, row["installment"], row["due_on"], status,
                f"{name} {row['number']}/{preview['term_months']}", series_id, loan_id, row["number"], now(),
            ),
        )


def update_loan(loan_id, payload):
    current = get_loan(loan_id)
    context = current["context"]
    name = clean_name(payload.get("name") or current["name"], "Nome")
    preview = preview_loan({
        "principal": payload.get("principal", current["principal"]),
        "monthly_rate": payload.get("monthly_rate"),
        "system": payload.get("system") or current["system"],
        "term_months": payload.get("term_months") or current["term_months"],
        "installment": payload.get("installment"),
        "first_due": payload.get("first_due") or current["first_due"],
        "iof": current["iof"],
        "fees": current["fees"],
        "insurance": current["insurance"],
    })
    already = int(payload.get("already_paid") or 0)
    if already < 0 or already > preview["term_months"]:
        raise ValueError("A quantidade de parcelas já pagas é inválida.")
    same_terms = _loan_terms_match(current, payload, preview)
    history = any(row["status"] != "previsto" for row in current["rows"])
    if not same_terms and history:
        raise ValueError("Já há parcela paga ou cancelada. Dá para mudar o nome, a conta e o tipo. Para mudar valor, taxa ou prazo, apague o contrato e lance de novo.")
    with connect() as conn:
        account = _account_in_context(conn, payload.get("account_id") or current["account_id"], context)
        category_id, _ = _validate_category(conn, context, "saida", payload.get("category_id") or current["category_id"], None)
        if same_terms:
            conn.execute(
                "UPDATE loans SET name = ?, account_id = ?, category_id = ? WHERE id = ?",
                (name, account["id"], category_id, loan_id),
            )
            conn.execute(
                "UPDATE series SET account_id = ?, category_id = ?, description = ? WHERE loan_id = ?",
                (account["id"], category_id, name, loan_id),
            )
            conn.execute(
                """
                UPDATE transactions
                SET account_id = ?, category_id = ?, description = ? || ' ' || installment_no || '/' || ?
                WHERE loan_id = ?
                """,
                (account["id"], category_id, name, current["term_months"], loan_id),
            )
        else:
            rate = str(_loan_rate(payload))
            conn.execute(
                """
                UPDATE loans
                SET name = ?, account_id = ?, category_id = ?, principal = ?, monthly_rate = ?, system = ?,
                    term_months = ?, installment = ?, first_due = ?, already_paid = ?
                WHERE id = ?
                """,
                (
                    name, account["id"], category_id, clean_amount(payload.get("principal")), rate,
                    payload.get("system") or "price", preview["term_months"], preview["installment"],
                    clean_date(payload.get("first_due")), already, loan_id,
                ),
            )
            _clear_loan_children(conn, loan_id, current["series_id"])
            _insert_loan_schedule(conn, loan_id, context, name, account["id"], category_id, preview, already)
    return get_loan(loan_id)


def delete_loan(loan_id):
    current = get_loan(loan_id)
    with connect() as conn:
        _clear_loan_children(conn, loan_id, current["series_id"])
        deleted = conn.execute("DELETE FROM loans WHERE id = ?", (loan_id,)).rowcount
    if not deleted:
        raise ValueError("Empréstimo não encontrado.")


def list_loans(context):
    ensure_context(context)
    with connect() as conn:
        ids = [row["id"] for row in conn.execute("SELECT id FROM loans WHERE context = ? ORDER BY name", (context,))]
    return [get_loan(loan_id) for loan_id in ids]


def update_goal(goal_id, name, target_amount, target_date):
    current = get_goal(goal_id)
    name = clean_name(name if name is not None else current["name"], "Nome da meta")
    target = clean_amount(target_amount if target_amount is not None else current["target_amount"])
    when = clean_date(target_date or current["target_date"])
    with connect() as conn:
        conn.execute(
            "UPDATE goals SET name = ?, target_amount = ?, target_date = ? WHERE id = ?",
            (name, target, when, goal_id),
        )
    return get_goal(goal_id)


def delete_goal(goal_id):
    get_goal(goal_id)
    with connect() as conn:
        conn.execute("DELETE FROM goal_months WHERE goal_id = ?", (goal_id,))
        deleted = conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,)).rowcount
    if not deleted:
        raise ValueError("Meta não encontrada.")


def create_goal(context, name, target_amount, target_date):
    ensure_context(context)
    name = clean_name(name, "Nome da meta")
    target = clean_amount(target_amount)
    when = clean_date(target_date)
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO goals (context, name, target_amount, target_date, created_at) VALUES (?, ?, ?, ?, ?)",
            (context, name, target, when, now()),
        )
        goal_id = cur.lastrowid
    return get_goal(goal_id)


def get_goal(goal_id, today=None):
    today = today or date.today()
    with connect() as conn:
        row = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        if row is None:
            raise ValueError("Meta não encontrada.")
        saved_rows = {
            item["month"]: dict(item)
            for item in conn.execute("SELECT * FROM goal_months WHERE goal_id = ?", (goal_id,))
        }
    months = _goal_months(date.fromisoformat(row["created_at"][:10]), date.fromisoformat(row["target_date"]))
    saved_before = 0
    history = []
    for month in months:
        snapshot = saved_rows.get(month)
        saved = snapshot["saved"] if snapshot else 0
        start, _ = month_bounds(month)
        months_left = len([item for item in months if item >= month])
        computed = int((Decimal(row["target_amount"] - saved_before) / Decimal(months_left)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if months_left else 0
        if start < date(today.year, today.month, 1) and snapshot and snapshot["challenge"] is not None:
            challenge = snapshot["challenge"]
        else:
            challenge = max(computed, 0)
        history.append({
            "month": month,
            "challenge": challenge,
            "saved": saved,
            "difference": saved - challenge,
            "hit": saved >= challenge if challenge else saved > 0,
            "closed": start < date(today.year, today.month, 1),
        })
        saved_before += saved
    current = next((item for item in history if item["month"] == today.strftime("%Y-%m")), history[-1] if history else None)
    return {
        "id": row["id"],
        "context": row["context"],
        "name": row["name"],
        "target_amount": row["target_amount"],
        "target_date": row["target_date"],
        "saved_total": sum(item["saved"] for item in history),
        "current": current,
        "history": history,
        "done": sum(item["saved"] for item in history) >= row["target_amount"],
    }


def _goal_months(created, target):
    year, mon = created.year, created.month
    end_year, end_mon = target.year, target.month
    months = []
    while (year, mon) <= (end_year, end_mon):
        months.append(f"{year:04d}-{mon:02d}")
        year, mon = shift_month(year, mon, 1)
    return months or [f"{created.year:04d}-{created.month:02d}"]


def save_goal_month(goal_id, month, saved, today=None):
    today = today or date.today()
    month_bounds(month)
    amount = int(saved)
    if amount < 0:
        raise ValueError("O valor guardado não pode ser negativo.")
    goal = get_goal(goal_id, today)
    challenge = next(item["challenge"] for item in goal["history"] if item["month"] == month)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO goal_months (goal_id, month, saved, challenge) VALUES (?, ?, ?, ?)
            ON CONFLICT(goal_id, month) DO UPDATE SET saved = excluded.saved, challenge = excluded.challenge
            """,
            (goal_id, month, amount, challenge),
        )
    return get_goal(goal_id, today)


def list_goals(context, today=None):
    ensure_context(context)
    with connect() as conn:
        ids = [row["id"] for row in conn.execute("SELECT id FROM goals WHERE context = ? ORDER BY target_date", (context,))]
    return [get_goal(goal_id, today) for goal_id in ids]


def panorama(context, month, today=None, extras=None, omit_ids=None):
    ensure_context(context)
    today = today or date.today()
    start, end = month_bounds(month)
    items = list_transactions(context, month)
    items = [item for item in items if item["status"] != "cancelado" and item["id"] not in (omit_ids or set())]
    for extra in extras or []:
        items.append({
            "id": None,
            "direction": extra["direction"],
            "amount": clean_amount(extra["amount"]),
            "occurred_on": occurrence_date(start.year, start.month, int(extra["day"])).isoformat(),
            "status": "previsto",
            "description": extra.get("description") or "Simulação",
            "account_name": extra.get("account_name") or "Simulação",
            "category_name": None,
            "hypothetical": True,
        })
    cards = {"entrada": 0, "saida": 0, "investimento": 0}
    pending = {"entrada": 0, "saida": 0, "investimento": 0}
    by_account = []
    grouped = {}
    for item in items:
        if item["direction"] == "transferencia":
            continue
        cards[item["direction"]] += item["amount"]
        if item["status"] == "previsto":
            pending[item["direction"]] += item["amount"]
        key = (item["direction"], item.get("account_name") or "Sem conta")
        grouped[key] = grouped.get(key, 0) + item["amount"]
    for (direction, account_name), amount in sorted(grouped.items()):
        by_account.append({"direction": direction, "account_name": account_name, "amount": amount})
    days = []
    opening = _opening_balance(context, start)
    running = {"entrada": 0, "saida": 0, "investimento": 0}
    zero_day = None
    cursor = start
    while cursor < end:
        day_items = []
        for item in items:
            if item["direction"] == "transferencia":
                continue
            if _counts_on_day(item, cursor, start, end, today):
                day_items.append(item)
                running[item["direction"]] += item["amount"]
        balance = opening + running["entrada"] - running["saida"] - running["investimento"]
        if zero_day is None and balance < 0:
            zero_day = cursor.isoformat()
        days.append({
            "date": cursor.isoformat(),
            "entrada": sum(item["amount"] for item in day_items if item["direction"] == "entrada"),
            "saida": sum(item["amount"] for item in day_items if item["direction"] == "saida"),
            "investimento": sum(item["amount"] for item in day_items if item["direction"] == "investimento"),
            "balance": balance,
            "items": [{
                "id": item.get("id"),
                "direction": item["direction"],
                "amount": item["amount"],
                "description": item.get("description") or item.get("category_name") or item["direction"],
                "account_name": item.get("account_name"),
                "status": item["status"],
                "late": item.get("late", False),
                "hypothetical": item.get("hypothetical", False),
            } for item in day_items],
        })
        cursor = date.fromordinal(cursor.toordinal() + 1)
    saldo = cards["entrada"] - cards["saida"] - cards["investimento"]
    return {
        "month": month,
        "entrada": cards["entrada"],
        "saida": cards["saida"],
        "investimento": cards["investimento"],
        "saldo": saldo,
        "opening": opening,
        "pending": pending,
        "by_account": by_account,
        "days": days,
        "last_balance": days[-1]["balance"] if days else 0,
        "zero_day": zero_day,
    }


def _opening_balance(context, month_start):
    with connect() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(
                CASE direction WHEN 'entrada' THEN amount ELSE -amount END
            ), 0) AS total
            FROM transactions
            WHERE context = ? AND status != 'cancelado' AND direction != 'transferencia'
              AND occurred_on < ?
            """,
            (context, month_start.isoformat()),
        ).fetchone()
    return row["total"]


def _counts_on_day(item, day, month_start, month_end, today):
    when = date.fromisoformat(item["occurred_on"])
    if item["status"] == "efetivado":
        return when == day
    if when >= today:
        return when == day
    if month_start <= today <= month_end - date.resolution:
        return day == today and month_start <= when <= month_end - date.resolution
    if today > month_end - date.resolution:
        return when == day
    return False


def company_view(year=None, today=None):
    today = today or date.today()
    year = int(year or today.year)
    with connect() as conn:
        profile = dict(conn.execute("SELECT * FROM company_profile WHERE id = 1").fetchone())
        revenue = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE context = 'pj' AND direction = 'entrada' AND status != 'cancelado'
              AND counts_as_revenue = 1 AND occurred_on >= ? AND occurred_on < ?
            """,
            (f"{year}-01-01", f"{year + 1}-01-01"),
        ).fetchone()["total"]
        das = {
            (row["month"]): dict(row)
            for row in conn.execute("SELECT * FROM das_months WHERE year = ?", (year,))
        }
        declared = conn.execute("SELECT delivered FROM dasn WHERE year = ?", (year - 1,)).fetchone()
    limit = annual_limit(profile, year)
    ratio = (revenue / limit) if limit else 0
    alerts = []
    if ratio > 1.2:
        alerts.append("above20")
    elif ratio >= 1:
        alerts.append("limit")
    elif ratio >= 0.8:
        alerts.append("warning")
    months = []
    for month in range(1, 13):
        saved = das.get(month)
        months.append({
            "month": month,
            "due_on": f"{year}-{month:02d}-20",
            "paid": bool(saved and saved["paid"]),
            "amount": saved["amount"] if saved and saved["amount"] is not None else suggested_das(profile),
        })
    return {
        "profile": profile,
        "year": year,
        "revenue": revenue,
        "limit": limit,
        "remaining": limit - revenue,
        "ratio": ratio,
        "alerts": alerts,
        "das": months,
        "dasn_year": year - 1,
        "dasn_due": f"{year}-05-31",
        "dasn_delivered": bool(declared and declared["delivered"]),
        "suggested_das": suggested_das(profile),
    }


def annual_limit(profile, year):
    if profile["kind"] == "custom" and profile["annual_limit"]:
        base, monthly = profile["annual_limit"], int(profile["annual_limit"] / 12)
    elif profile["kind"] == "mei_carga":
        base, monthly = CARGA_LIMIT, int(CARGA_LIMIT / 12)
    else:
        base, monthly = MEI_LIMIT, MEI_MONTH
    opened = profile.get("opened_on")
    if opened and int(opened[:4]) == year:
        months = 12 - int(opened[5:7]) + 1
        return monthly * months
    return base


def suggested_das(profile):
    base = DAS_INSS_CARGA if profile["kind"] == "mei_carga" else DAS_INSS
    if profile["has_icms"]:
        base += DAS_ICMS
    if profile["has_iss"]:
        base += DAS_ISS
    return base


def update_company(payload):
    kind = payload.get("kind") or "mei"
    if kind not in ("mei", "mei_carga", "custom"):
        raise ValueError("Perfil inválido.")
    opened = payload.get("opened_on") or None
    if opened:
        opened = clean_date(opened)
    limit = int(payload["annual_limit"]) if payload.get("annual_limit") else None
    with connect() as conn:
        conn.execute(
            "UPDATE company_profile SET kind = ?, annual_limit = ?, opened_on = ?, has_icms = ?, has_iss = ? WHERE id = 1",
            (kind, limit, opened, 1 if payload.get("has_icms") else 0, 1 if payload.get("has_iss") else 0),
        )
    return company_view(payload.get("year"))


def set_das(year, month, paid, amount=None, launch=None):
    year, month = int(year), int(month)
    if month < 1 or month > 12:
        raise ValueError("Mês inválido.")
    with connect() as conn:
        profile = dict(conn.execute("SELECT * FROM company_profile WHERE id = 1").fetchone())
    value = clean_amount(amount) if amount else suggested_das(profile)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO das_months (year, month, paid, amount) VALUES (?, ?, ?, ?)
            ON CONFLICT(year, month) DO UPDATE SET paid = excluded.paid, amount = excluded.amount
            """,
            (year, month, 1 if paid else 0, value),
        )
    launched = None
    if paid and launch and launch.get("account_id"):
        launched = create_transaction({
            "context": "pj",
            "direction": "saida",
            "account_id": launch["account_id"],
            "category_id": launch.get("category_id"),
            "amount": value,
            "occurred_on": f"{year}-{month:02d}-20",
            "status": "efetivado",
            "description": f"DAS {month:02d}/{year}",
            "counts_as_revenue": False,
        })
    result = company_view(year)
    result["launched"] = launched
    return result


def set_dasn(year, delivered):
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO dasn (year, delivered) VALUES (?, ?)
            ON CONFLICT(year) DO UPDATE SET delivered = excluded.delivered
            """,
            (int(year), 1 if delivered else 0),
        )
    return company_view(int(year) + 1)


def export_space():
    with connect() as conn:
        tables = [
            "users", "accounts", "categories", "subcategories", "series", "transactions",
            "loans", "loan_rows", "goals", "goal_months", "company_profile", "das_months", "dasn", "settings",
        ]
        payload = {}
        for table in tables:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            payload[table] = [dict(row) for row in rows]
        for user in payload["users"]:
            user.pop("password_hash", None)
            user.pop("salt", None)
    return payload


def erase_space():
    with connect() as conn:
        conn.executescript(
            """
            DELETE FROM sessions;
            DELETE FROM goal_months;
            DELETE FROM goals;
            DELETE FROM loan_rows;
            DELETE FROM transactions;
            DELETE FROM series;
            DELETE FROM loans;
            DELETE FROM subcategories;
            DELETE FROM categories;
            DELETE FROM accounts;
            DELETE FROM das_months;
            DELETE FROM dasn;
            DELETE FROM users;
            UPDATE company_profile SET kind = 'mei', annual_limit = NULL, opened_on = NULL, has_icms = 0, has_iss = 0 WHERE id = 1;
            UPDATE settings SET value = '1' WHERE key = 'pf_enabled';
            UPDATE settings SET value = '0' WHERE key = 'pj_enabled';
            """
        )

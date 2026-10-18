import os
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

TEMP = tempfile.TemporaryDirectory()
os.environ["FINANCES_DB"] = str(Path(TEMP.name) / "test.db")

import db

db.DB_PATH = Path(os.environ["FINANCES_DB"])


class RequirementTests(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        db.create_user("Vanderson", "eu@example.com", "segredo", "admin")
        self.account = db.create_account("pf", "Carteira")
        self.kind = db.create_category("pf", "entrada", "Salário")
        self.expense = db.create_category("pf", "saida", "Moradia")

    def test_month_saldo_ignores_transfer_and_splits_investment(self):
        db.create_transaction({
            "context": "pf", "direction": "entrada", "account_id": self.account["id"],
            "category_id": self.kind["id"], "amount": 100000, "occurred_on": "2026-10-05", "status": "efetivado",
        })
        db.create_transaction({
            "context": "pf", "direction": "saida", "account_id": self.account["id"],
            "category_id": self.expense["id"], "amount": 20000, "occurred_on": "2026-10-10", "status": "previsto",
        })
        db.create_transaction({
            "context": "pf", "direction": "investimento", "account_id": self.account["id"],
            "amount": 30000, "occurred_on": "2026-10-12", "status": "previsto",
        })
        other = db.create_account("pf", "Cofre")
        db.create_transaction({
            "context": "pf", "direction": "transferencia", "account_id": self.account["id"],
            "transfer_account_id": other["id"], "amount": 5000, "occurred_on": "2026-10-15", "status": "efetivado",
        })
        report = db.panorama("pf", "2026-10", today=date(2026, 10, 1))
        self.assertEqual(report["entrada"], 100000)
        self.assertEqual(report["saida"], 20000)
        self.assertEqual(report["investimento"], 30000)
        self.assertEqual(report["saldo"], 50000)
        self.assertEqual(report["last_balance"], 50000)
        self.assertEqual(report["opening"], 0)
        self.assertEqual(report["days"][0]["balance"], 0)

    def test_month_carries_previous_balance_or_deficit(self):
        db.create_transaction({
            "context": "pf", "direction": "saida", "account_id": self.account["id"],
            "category_id": self.expense["id"], "amount": 2000, "occurred_on": "2026-09-10", "status": "previsto",
        })
        db.create_transaction({
            "context": "pf", "direction": "entrada", "account_id": self.account["id"],
            "category_id": self.kind["id"], "amount": 1000, "occurred_on": "2026-10-05", "status": "efetivado",
        })
        october = db.panorama("pf", "2026-10", today=date(2026, 10, 1))
        self.assertEqual(october["opening"], -2000)
        self.assertEqual(october["saldo"], 1000)
        self.assertEqual(october["days"][0]["balance"], -2000)
        self.assertEqual(october["last_balance"], -1000)
        november = db.panorama("pf", "2026-11", today=date(2026, 10, 1))
        self.assertEqual(november["opening"], -1000)
        self.assertEqual(november["saldo"], 0)
        self.assertEqual(november["days"][0]["balance"], -1000)
        self.assertEqual(november["last_balance"], -1000)

    def test_series_edits_only_one_or_unpaid(self):
        series = db.create_series({
            "context": "pf", "direction": "saida", "account_id": self.account["id"],
            "category_id": self.expense["id"], "amount": 10000, "day_of_month": 31,
            "start_month": "2026-01", "month_count": 5, "description": "Aluguel",
        })
        self.assertEqual(len(series["occurrences"]), 5)
        self.assertEqual(series["occurrences"][1]["occurred_on"], "2026-02-28")
        first = db.get_transaction(series["occurrences"][0]["id"])
        db.update_transaction(first["id"], {"status": "efetivado"}, "this")
        db.update_transaction(series["occurrences"][1]["id"], {"amount": 15000, "account_id": self.account["id"], "category_id": self.expense["id"]}, "all")
        paid = db.get_transaction(first["id"])
        changed = db.get_transaction(series["occurrences"][2]["id"])
        single = db.get_transaction(series["occurrences"][1]["id"])
        self.assertEqual(paid["amount"], 10000)
        self.assertEqual(single["amount"], 15000)
        self.assertEqual(changed["amount"], 15000)

    def test_price_schedule_ends_at_zero(self):
        rows = db.build_schedule(2_000_000, Decimal("0.0199"), 36, "price", "2026-11-10")
        self.assertEqual(rows[-1]["balance"], 0)
        self.assertGreater(rows[0]["interest"], rows[-1]["interest"])
        self.assertEqual(len(rows), 36)

    def test_goal_shortfall_raises_next_challenge(self):
        goal = db.create_goal("pf", "Reserva", 300000, "2026-12-31")
        current = goal["current"]["month"]
        db.save_goal_month(goal["id"], current, 0, today=date(2026, 10, 18))
        updated = db.get_goal(goal["id"], today=date(2026, 11, 2))
        october = next(item for item in updated["history"] if item["month"] == "2026-10")
        november = next(item for item in updated["history"] if item["month"] == "2026-11")
        self.assertFalse(october["hit"])
        self.assertGreater(november["challenge"], october["challenge"])

    def test_mei_limits_and_alerts(self):
        self.assertEqual(db.annual_limit({"kind": "mei", "annual_limit": None, "opened_on": None}, 2026), 8_100_000)
        self.assertEqual(db.annual_limit({"kind": "mei", "annual_limit": None, "opened_on": "2026-07-15"}, 2026), 675_000 * 6)
        db.set_context_enabled("pj", True)
        account = db.create_account("pj", "Caixa")
        kind = db.create_category("pj", "entrada", "Venda")
        db.create_transaction({
            "context": "pj", "direction": "entrada", "account_id": account["id"], "category_id": kind["id"],
            "amount": 6_500_000, "occurred_on": "2026-03-01", "status": "efetivado",
        })
        view = db.company_view(2026, today=date(2026, 10, 18))
        self.assertEqual(view["alerts"], ["warning"])

    def test_contexts_do_not_mix(self):
        db.set_context_enabled("pj", True)
        db.create_transaction({
            "context": "pf", "direction": "entrada", "account_id": self.account["id"],
            "category_id": self.kind["id"], "amount": 100, "occurred_on": "2026-10-02", "status": "efetivado",
        })
        self.assertEqual(db.panorama("pj", "2026-10")["entrada"], 0)
        self.assertEqual(db.panorama("pf", "2026-10")["entrada"], 100)

    def test_unused_type_and_subtype_can_be_deleted(self):
        parent = db.create_subcategory(self.expense["id"], "Aluguel")
        sub = next(item for item in parent["subcategories"] if item["name"] == "Aluguel")
        self.assertTrue(sub["deletable"])
        self.assertTrue(parent["deletable"])
        db.delete_subcategory(sub["id"])
        db.create_transaction({
            "context": "pf", "direction": "saida", "account_id": self.account["id"],
            "category_id": self.expense["id"], "amount": 1000, "occurred_on": "2026-10-10", "status": "previsto",
        })
        listed = next(item for item in db.list_categories("pf") if item["id"] == self.expense["id"])
        self.assertFalse(listed["deletable"])
        with self.assertRaises(ValueError):
            db.delete_category(self.expense["id"])

    def test_transaction_can_be_deleted(self):
        created = db.create_transaction({
            "context": "pf", "direction": "saida", "account_id": self.account["id"],
            "category_id": self.expense["id"], "amount": 1500, "occurred_on": "2026-10-18",
            "status": "previsto", "description": "Teste",
        })
        db.delete_transaction(created["id"])
        self.assertEqual(db.list_transactions("pf", "2026-10"), [])
        with self.assertRaises(ValueError):
            db.delete_transaction(created["id"])

    def test_last_context_comes_back(self):
        db.set_context_enabled("pj", True)
        user = db.list_users()[0]
        updated = db.set_last_context(user["id"], "pj")
        self.assertEqual(updated["last_context"], "pj")
        db.set_context_enabled("pj", False)
        with self.assertRaises(ValueError):
            db.set_last_context(user["id"], "pj")


if __name__ == "__main__":
    unittest.main()

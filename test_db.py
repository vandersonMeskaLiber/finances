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

    def test_week_and_day_repeat(self):
        weekly = db.create_series({
            "context": "pf", "direction": "saida", "account_id": self.account["id"],
            "category_id": self.expense["id"], "amount": 2500, "frequency": "week",
            "start_on": "2026-01-30", "count": 3, "description": "Feira",
        })
        self.assertEqual(
            [item["occurred_on"] for item in weekly["occurrences"]],
            ["2026-01-30", "2026-02-06", "2026-02-13"],
        )
        daily = db.create_series({
            "context": "pf", "direction": "entrada", "account_id": self.account["id"],
            "category_id": self.kind["id"], "amount": 100, "frequency": "day",
            "start_on": "2026-01-30", "count": 3, "description": "Diária", "status": "efetivado",
        })
        self.assertEqual(
            [item["occurred_on"] for item in daily["occurrences"]],
            ["2026-01-30", "2026-01-31", "2026-02-01"],
        )
        self.assertEqual(db.get_transaction(daily["occurrences"][0]["id"])["status"], "efetivado")
        self.assertEqual(db.get_transaction(daily["occurrences"][1]["id"])["status"], "previsto")
        self.assertEqual(db.get_transaction(daily["occurrences"][0]["id"])["series_frequency"], "day")
        db.update_transaction(weekly["occurrences"][0]["id"], {
            "occurred_on": "2026-01-31", "amount": 3000,
            "account_id": self.account["id"], "category_id": self.expense["id"],
        }, "all")
        moved = db.get_series(weekly["id"])
        self.assertEqual(
            [item["occurred_on"] for item in moved["occurrences"]],
            ["2026-01-31", "2026-02-07", "2026-02-14"],
        )
        self.assertEqual(moved["occurrences"][2]["amount"], 3000)
        with self.assertRaises(ValueError):
            db.create_series({
                "context": "pf", "direction": "saida", "account_id": self.account["id"],
                "category_id": self.expense["id"], "amount": 100, "frequency": "ano",
                "start_on": "2026-01-30", "count": 2,
            })

    def test_price_schedule_ends_at_zero(self):
        rows = db.build_schedule(2_000_000, Decimal("0.0199"), 36, "price", "2026-11-10")
        self.assertEqual(rows[-1]["balance"], 0)
        self.assertGreater(rows[0]["interest"], rows[-1]["interest"])
        self.assertEqual(len(rows), 36)

    def test_goal_edit_keeps_closed_month_and_can_be_deleted(self):
        goal = db.create_goal("pf", "Reserva", 300000, "2026-12-31")
        db.save_goal_month(goal["id"], "2026-10", 10000, today=date(2026, 10, 18))
        edited = db.update_goal(goal["id"], "Reserva nova", 600000, "2027-01-31")
        self.assertEqual(edited["name"], "Reserva nova")
        self.assertEqual(edited["target_amount"], 600000)
        october = next(item for item in edited["history"] if item["month"] == "2026-10")
        self.assertEqual(october["saved"], 10000)
        self.assertTrue(any(item["month"] == "2027-01" for item in edited["history"]))
        db.delete_goal(goal["id"])
        self.assertEqual(db.list_goals("pf"), [])

    def test_deleting_loan_installment_does_not_reopen_the_debt(self):
        loan = db.create_loan({
            "context": "pf", "name": "Teste", "account_id": self.account["id"],
            "category_id": self.expense["id"], "principal": 100000, "monthly_rate": "1,00",
            "term_months": 3, "first_due": "2026-01-10", "system": "price", "already_paid": 1,
        })
        paid = next(row for row in loan["rows"] if row["status"] == "efetivado")
        db.delete_transaction(paid["transaction_id"])
        again = db.get_loan(loan["id"])
        cancelled = next(row for row in again["rows"] if row["number"] == paid["number"])
        self.assertEqual(cancelled["status"], "cancelado")
        self.assertNotEqual(again["remaining"], loan["principal"])

    def test_loan_can_be_renamed_rebuilt_and_deleted(self):
        payload = {
            "context": "pf", "name": "Teste", "account_id": self.account["id"],
            "category_id": self.expense["id"], "principal": 100000, "monthly_rate": "1,00",
            "term_months": 3, "first_due": "2026-11-10", "system": "price", "already_paid": 0,
        }
        loan = db.create_loan(payload)
        renamed = db.update_loan(loan["id"], {**payload, "name": "Renomeado"})
        self.assertEqual(renamed["name"], "Renomeado")
        self.assertEqual(renamed["principal"], 100000)
        self.assertTrue(any(item["description"].startswith("Renomeado") for item in db.list_transactions("pf", "2026-11")))
        rebuilt = db.update_loan(loan["id"], {**payload, "name": "Renomeado", "principal": 200000, "term_months": 2})
        self.assertEqual(rebuilt["term_months"], 2)
        self.assertEqual(len(rebuilt["rows"]), 2)
        paid = db.create_loan({**payload, "name": "Pago", "already_paid": 1, "first_due": "2026-01-10"})
        with self.assertRaises(ValueError):
            db.update_loan(paid["id"], {**payload, "name": "Pago", "already_paid": 1, "first_due": "2026-01-10", "principal": 50000})
        kept = db.update_loan(paid["id"], {**payload, "name": "Pago novo", "already_paid": 1, "first_due": "2026-01-10"})
        self.assertEqual(kept["name"], "Pago novo")
        self.assertEqual(kept["principal"], 100000)
        db.delete_loan(loan["id"])
        with self.assertRaises(ValueError):
            db.get_loan(loan["id"])
        self.assertFalse(any(item["description"].startswith("Renomeado") for item in db.list_transactions("pf")))

    def test_unused_account_can_be_deleted_and_a_used_one_cannot(self):
        spare = db.create_account("pf", "Vazia")
        self.assertTrue(spare["deletable"])
        db.delete_account(spare["id"])
        db.create_transaction({
            "context": "pf", "direction": "saida", "account_id": self.account["id"],
            "category_id": self.expense["id"], "amount": 1000, "occurred_on": "2026-10-10", "status": "previsto",
        })
        used = next(item for item in db.list_accounts("pf", True) if item["id"] == self.account["id"])
        self.assertFalse(used["deletable"])
        with self.assertRaises(ValueError):
            db.delete_account(self.account["id"])

    def test_user_can_be_edited_and_another_user_can_be_deleted(self):
        created = db.create_user("Ana", "ana@example.com", "segredo", "user")
        edited = db.update_user(created["id"], "Ana Maria", "ana@example.com", "user")
        self.assertEqual(edited["name"], "Ana Maria")
        admin = next(user for user in db.list_users() if user["role"] == "admin")
        with self.assertRaises(ValueError):
            db.delete_user(admin["id"], admin["id"])
        db.delete_user(created["id"], admin["id"])
        self.assertFalse(any(user["email"] == "ana@example.com" for user in db.list_users()))

    def test_settle_marks_only_elapsed_installments(self):
        loan = db.create_loan({
            "context": "pf", "name": "Atraso", "account_id": self.account["id"],
            "category_id": self.expense["id"], "principal": 300000, "monthly_rate": "0",
            "term_months": 3, "first_due": "2026-09-10", "system": "price", "already_paid": 0,
        })
        settled = db.settle_elapsed_installments(loan["id"], today=date(2026, 10, 24))
        statuses = [row["status"] for row in settled["rows"]]
        self.assertEqual(statuses, ["efetivado", "efetivado", "previsto"])

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

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from cloting.rental.utils import get_settings, money


def _settings_or_throw():
	settings = get_settings()
	if not settings.auto_create_accounting_documents:
		return None
	missing = []
	for field in (
		"rental_income_account",
		"deposit_liability_account",
		"deposit_cash_account",
	):
		if not settings.get(field):
			missing.append(field)
	if missing:
		frappe.throw(_("Rental Settings missing accounting fields: {0}").format(", ".join(missing)))
	return settings


def post_booking_accounting(booking):
	settings = _settings_or_throw()
	if not settings:
		return
	doc = frappe.get_doc("Rental Booking", booking)
	if not doc.sales_invoice and money(doc.grand_total) > 0 and settings.rental_item:
		invoice = frappe.new_doc("Sales Invoice")
		invoice.customer = doc.customer
		invoice.company = doc.company
		invoice.posting_date = nowdate()
		invoice.due_date = nowdate()
		invoice.append(
			"items",
			{
				"item_code": settings.rental_item,
				"qty": 1,
				"rate": doc.grand_total,
				"income_account": settings.rental_income_account,
				"cost_center": settings.cost_center,
				"description": f"Costume rental {doc.name}",
			},
		)
		invoice.remarks = f"Rental Booking {doc.name}"
		invoice.insert()
		invoice.submit()
		doc.db_set("sales_invoice", invoice.name)

	if not doc.deposit_journal_entry and money(doc.deposit_received) > 0:
		je = _make_je(
			doc.company,
			nowdate(),
			f"Security deposit for {doc.name}",
			[
				{"account": settings.deposit_cash_account, "debit_in_account_currency": money(doc.deposit_received)},
				{
					"account": settings.deposit_liability_account,
					"credit_in_account_currency": money(doc.deposit_received),
					"party_type": "Customer",
					"party": doc.customer,
				},
			],
			user_remark=f"Rental Booking {doc.name} deposit",
		)
		doc.db_set("deposit_journal_entry", je)


def post_settlement_accounting(settlement):
	settings = _settings_or_throw()
	if not settings:
		return
	doc = frappe.get_doc("Rental Settlement", settlement)
	booking = doc.rental_booking
	lines = []
	applied = money(min(flt(doc.total_deductions), flt(doc.deposit_amount)))
	if applied > 0:
		late = money(min(flt(doc.late_fee), applied))
		rest = applied - late
		damage = money(min(flt(doc.damage_deduction) + flt(doc.missing_accessories_deduction) + flt(doc.replacement_recovery), rest))
		lines.append(
			{
				"account": settings.deposit_liability_account,
				"debit_in_account_currency": applied,
				"party_type": "Customer",
				"party": doc.customer,
			}
		)
		if late:
			income = settings.late_fee_income_account or settings.rental_income_account
			lines.append({"account": income, "credit_in_account_currency": late})
		if damage:
			income = settings.damage_recovery_income_account or settings.rental_income_account
			lines.append({"account": income, "credit_in_account_currency": damage})
		# leftover applied (rounding) to damage income
		credited = late + damage
		if applied - credited > 0.005:
			income = settings.damage_recovery_income_account or settings.rental_income_account
			lines.append({"account": income, "credit_in_account_currency": money(applied - credited)})
		je = _make_je(doc.company, nowdate(), f"Deposit application {booking}", lines, user_remark=f"Rental Settlement {doc.name}")
		doc.db_set("deduction_journal_entry", je)

	if money(doc.receivable_shortfall) > 0 and settings.rental_item:
		invoice = frappe.new_doc("Sales Invoice")
		invoice.customer = doc.customer
		invoice.company = doc.company
		invoice.posting_date = nowdate()
		invoice.append(
			"items",
			{
				"item_code": settings.rental_item,
				"qty": 1,
				"rate": doc.receivable_shortfall,
				"income_account": settings.damage_recovery_income_account or settings.rental_income_account,
				"cost_center": settings.cost_center,
				"description": f"Recovery beyond deposit {booking}",
			},
		)
		invoice.remarks = f"Rental Settlement {doc.name}"
		invoice.insert()
		invoice.submit()
		doc.db_set("shortfall_sales_invoice", invoice.name)

	if money(doc.refund_amount) > 0:
		post_deposit_refund(doc.name)


def post_deposit_refund(settlement):
	settings = _settings_or_throw()
	doc = frappe.get_doc("Rental Settlement", settlement)
	if doc.refunded or doc.refund_journal_entry:
		frappe.throw(_("This settlement has already been refunded."))
	if not settings:
		frappe.throw(
			_("Enable Rental accounting integration and configure its accounts before processing a refund.")
		)
	if money(doc.refund_amount) <= 0:
		doc.db_set("refunded", 1)
		return
	je = _make_je(
		doc.company,
		nowdate(),
		f"Deposit refund {doc.rental_booking}",
		[
			{
				"account": settings.deposit_liability_account,
				"debit_in_account_currency": money(doc.refund_amount),
				"party_type": "Customer",
				"party": doc.customer,
			},
			{"account": settings.deposit_cash_account, "credit_in_account_currency": money(doc.refund_amount)},
		],
		user_remark=f"Rental Settlement {doc.name} refund",
	)
	doc.db_set("refund_journal_entry", je)
	doc.db_set("refunded", 1)


def _make_je(company, posting_date, title, accounts, user_remark=None):
	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = company
	je.posting_date = posting_date
	je.title = title[:140]
	je.user_remark = user_remark or title
	for acc in accounts:
		je.append("accounts", acc)
	je.insert()
	je.submit()
	return je.name

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from cloting.clothing.report.slow_moving_stock_report.slow_moving_stock_report import (
	DEFAULT_DAYS_WITHOUT_SALE,
	get_data,
	get_report_summary,
	validate_filters,
)


class TestSlowMovingStockReport(IntegrationTestCase):
	def test_validate_filters_uses_default_threshold(self):
		filters = frappe._dict()

		validate_filters(filters)

		self.assertEqual(filters.days_without_sale, DEFAULT_DAYS_WITHOUT_SALE)

	def test_validate_filters_rejects_negative_threshold(self):
		filters = frappe._dict(days_without_sale=-1)

		with patch("frappe.throw") as throw:
			validate_filters(filters)

		throw.assert_called_once()

	def test_get_report_summary_requires_one_company_currency(self):
		data = [frappe._dict(stock_value=125.5, currency="INR")]

		self.assertIsNone(get_report_summary(data, frappe._dict()))
		self.assertEqual(
			get_report_summary(data, frappe._dict(company="Mr Black"))[0]["value"], 125.5
		)

	def test_get_data_passes_configured_threshold_and_filters(self):
		filters = frappe._dict(
			company="Mr Black",
			warehouse="Stores - MB",
			item_group="Finished Goods",
			brand="Mr Black",
			days_without_sale=60,
		)

		with patch("frappe.db.sql", return_value=[]) as sql:
			get_data(filters)

		query = sql.call_args.args[0]
		values = sql.call_args.args[1]

		self.assertIn("bin.actual_qty > 0", query)
		self.assertIn("sales_invoice.docstatus = 1", query)
		self.assertIn("COALESCE(sales_invoice.is_return, 0) = 0", query)
		self.assertIn("DATEDIFF(%(as_of_date)s, sales.last_sales_date)", query)
		self.assertEqual(values["days_without_sale"], 60)
		self.assertEqual(values["company"], "Mr Black")
		self.assertEqual(values["warehouse"], "Stores - MB")

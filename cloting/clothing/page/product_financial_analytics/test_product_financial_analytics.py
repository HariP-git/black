import frappe
from frappe.tests import UnitTestCase

from cloting.clothing.page.product_financial_analytics.product_financial_analytics import _margin


class TestProductFinancialAnalytics(UnitTestCase):
	def test_margin_handles_zero_revenue(self):
		self.assertEqual(_margin(100, 0), 0)

	def test_margin_is_percentage(self):
		self.assertEqual(_margin(25, 100), 25)

	def test_dashboard_page_is_registered(self):
		self.assertTrue(frappe.db.exists("Page", "product-financial-analytics"))

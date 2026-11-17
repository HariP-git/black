# Copyright (c) 2026, Hari and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from cloting.api import (
	SUPPLIER_QUALITY_WARNING_THRESHOLD,
	get_supplier_quality_rating,
	validate_purchase_order_supplier_quality,
)


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestSupplierQualityRating(IntegrationTestCase):
	"""
	Integration tests for SupplierQualityRating.
	Use this class for testing interactions between multiple components.
	"""

	def test_supplier_average_rating_and_warning_threshold(self):
		evaluations = [
			frappe._dict(
				quality_rating=2,
				lead_time_rating=2,
				price_rating=2,
			),
			frappe._dict(
				quality_rating=2,
				lead_time_rating=3,
				price_rating=2,
			),
		]

		with patch("cloting.api.frappe.get_list", return_value=evaluations) as get_list:
			result = get_supplier_quality_rating("ABC Textiles")

		self.assertAlmostEqual(result["average_rating"], 2.1666666666666665)
		self.assertTrue(result["warning"])
		self.assertLess(result["average_rating"], SUPPLIER_QUALITY_WARNING_THRESHOLD)

		filters = get_list.call_args.kwargs["filters"]
		self.assertEqual(filters["docstatus"], 1)
		self.assertEqual(filters["quality_rating"], ["between", [1, 5]])
		self.assertEqual(filters["lead_time_rating"], ["between", [1, 5]])
		self.assertEqual(filters["price_rating"], ["between", [1, 5]])

	def test_supplier_without_evaluations_has_no_warning(self):
		with patch("cloting.api.frappe.get_list", return_value=[]):
			result = get_supplier_quality_rating("XYZ Fabrics")

		self.assertIsNone(result["average_rating"])
		self.assertFalse(result["warning"])

	def test_purchase_order_validation_warns_without_blocking(self):
		doc = frappe._dict(supplier="ABC Textiles")
		rating = {"average_rating": 2.13, "warning": True}

		with (
			patch("cloting.api.get_supplier_quality_rating", return_value=rating),
			patch("cloting.api.frappe.msgprint") as msgprint,
		):
			validate_purchase_order_supplier_quality(doc)

		msgprint.assert_called_once()
		self.assertEqual(msgprint.call_args.kwargs["indicator"], "orange")

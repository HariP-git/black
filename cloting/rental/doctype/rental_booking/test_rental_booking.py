from datetime import date
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from cloting.rental.constants import BLOCKING_UNIT_STATUSES, CLEANING_STATUS
from cloting.rental.api.rental_availability import find_available_bundles
from cloting.rental.report.costume_utilization_report.costume_utilization_report import _occupied_days


class TestRentalBooking(UnitTestCase):
	def test_units_requiring_inspection_are_not_available(self):
		self.assertIn("Returned", BLOCKING_UNIT_STATUSES)
		self.assertIn("Under Inspection", BLOCKING_UNIT_STATUSES)
		self.assertEqual(CLEANING_STATUS, "Under Cleaning")

	def test_utilization_merges_overlapping_allocations(self):
		allocations = [
			frappe._dict(start_date=date(2026, 11, 1), end_date=date(2026, 11, 3)),
			frappe._dict(start_date=date(2026, 11, 3), end_date=date(2026, 11, 5)),
		]
		self.assertEqual(
			_occupied_days(allocations, date(2026, 11, 1), date(2026, 11, 10)),
			5,
		)

	@patch("cloting.rental.api.rental_availability.find_available_units")
	@patch("cloting.rental.api.rental_availability._bundle_components")
	@patch("cloting.rental.api.rental_availability.frappe.db.get_value", return_value=1)
	def test_bundle_availability_requires_every_mandatory_component(
		self, _get_value, components, available_units
	):
		components.return_value = [
			frappe._dict(
				component_costume="Sherwani",
				component_role="Sherwani",
				qty=1,
				mandatory=1,
				size=None,
				colour=None,
			),
			frappe._dict(
				component_costume="Turban",
				component_role="Turban",
				qty=1,
				mandatory=1,
				size="Free Size",
				colour=None,
			),
		]
		available_units.side_effect = [
			{"sufficient": True, "available_unit_ids": ["SH-001"], "available_qty": 1},
			{"sufficient": False, "available_unit_ids": [], "available_qty": 0},
		]

		result = find_available_bundles("SH001", "M", "Black", "2026-11-20", "2026-11-22")

		self.assertFalse(result["sufficient"])
		self.assertEqual(result["available_qty"], 0)
		self.assertEqual(result["blocked_component"], "Turban")

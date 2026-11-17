import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from cloting.rental.utils import default_company


class RentalMaintenance(Document):
	def validate(self):
		self.company = self.company or default_company(self)
		if self.job_status == "Completed" and not self.completed_on:
			self.completed_on = now_datetime()

	def on_submit(self):
		if self.job_status != "Completed":
			frappe.throw(_("Mark the job as Completed before submitting."))
		release_costume_after_cleaning(self.rental_costume_unit, self.job_type)


@frappe.whitelist()
def release_costume_after_cleaning(unit, job_type=None):
	frappe.has_permission("Rental Costume Unit", "write", throw=True)
	status = frappe.db.get_value("Rental Costume Unit", unit, "operational_status")
	if status in ("Lost", "Retired"):
		return unit
	completed_job = frappe.db.exists(
		"Rental Maintenance",
		{
			"rental_costume_unit": unit,
			"job_type": job_type,
			"job_status": "Completed",
			"docstatus": 1,
		},
	)
	if not completed_job:
		frappe.throw(_("A submitted completed {0} job is required before releasing unit {1}.").format(job_type or "maintenance", unit))
	open_jobs = frappe.db.sql(
		"""
		SELECT name FROM `tabRental Maintenance`
		WHERE rental_costume_unit=%s
			AND job_status IN ('Open','In Progress')
			AND docstatus < 2
		""",
		unit,
	)
	if open_jobs:
		return unit
	frappe.db.set_value("Rental Costume Unit", unit, "operational_status", "Available")
	frappe.db.set_value("Rental Costume Unit", unit, "current_booking", None)
	return unit

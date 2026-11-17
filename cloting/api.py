import frappe
from frappe import _
from frappe.utils import flt


SUPPLIER_QUALITY_WARNING_THRESHOLD = 2.5


@frappe.whitelist()
def get_supplier_quality_rating(supplier: str | None = None) -> dict:
	"""Return a supplier's average submitted quality rating and warning status."""
	if not supplier:
		return {"average_rating": None, "warning": False}

	evaluations = frappe.get_list(
		"Supplier Quality Rating",
		filters={
			"supplier": supplier,
			"docstatus": 1,
			"quality_rating": ["between", [1, 5]],
			"lead_time_rating": ["between", [1, 5]],
			"price_rating": ["between", [1, 5]],
		},
		fields=["quality_rating", "lead_time_rating", "price_rating"],
		limit_page_length=0,
	)

	if not evaluations:
		return {"average_rating": None, "warning": False}

	average_rating = sum(
		(
			flt(evaluation.quality_rating)
			+ flt(evaluation.lead_time_rating)
			+ flt(evaluation.price_rating)
		)
		/ 3
		for evaluation in evaluations
	) / len(evaluations)

	return {
		"average_rating": average_rating,
		"warning": average_rating < SUPPLIER_QUALITY_WARNING_THRESHOLD,
	}


def validate_purchase_order_supplier_quality(doc, method=None):
	"""Warn on save when a Purchase Order supplier has a poor quality history."""
	rating = get_supplier_quality_rating(doc.supplier)
	if rating["warning"]:
		frappe.msgprint(
			_(
				"Warning: This supplier has a low quality performance rating of {0}/5. "
				"Please review the supplier's quality history before proceeding with this Purchase Order."
			).format(flt(rating["average_rating"], 2)),
			indicator="orange",
			alert=True,
		)

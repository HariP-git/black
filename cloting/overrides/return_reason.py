import frappe
from frappe import _
from frappe.utils import cint


def validate_return_reason(doc, method=None):
    """
    Server-side validation for return reason fields.

    Rules:
    1. If is_return = 1, custom_return_reason must not be empty.
    2. If custom_return_reason = "Other", custom_other_return_reason must not be empty.
    3. custom_return_remarks is always optional.
    4. If is_return = 0, return reason fields are not mandatory.

    This runs on both validate and before_submit to ensure the reason
    cannot be bypassed through any creation route.
    """
    if not cint(doc.is_return):
        return

    if not doc.get("custom_return_reason"):
        frappe.throw(
            _(
                "Return Reason is mandatory for return documents. "
                "Please select a Return Reason before saving."
            ),
            title=_("Return Reason Required"),
        )

    if doc.get("custom_return_reason") == "Other" and not doc.get("custom_other_return_reason"):
        frappe.throw(
            _(
                "Other Return Reason is mandatory when Return Reason is set to \"Other\". "
                "Please describe the specific reason before saving."
            ),
            title=_("Other Return Reason Required"),
        )

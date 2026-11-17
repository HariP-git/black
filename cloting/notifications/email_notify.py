import frappe
from frappe import _
from frappe.utils import add_days, format_datetime, get_datetime, today


REMINDER_DAYS = 2
REMINDER_CACHE_TTL = 3 * 24 * 60 * 60


def customer_fit_notify():
	"""Queue reminders for approved or pending fitting appointments two days ahead."""
	appointments = get_due_fitting_appointments(REMINDER_DAYS)
	queued = 0

	for appointment in appointments:
		if not appointment.email:
			frappe.logger("cloting.notifications").warning(
				"Skipping fitting appointment %s because no customer email is configured.",
				appointment.name,
			)
			continue

		cache_key = f"cloting:fitting-reminder:{appointment.name}:{today()}"
		if frappe.cache.get_value(cache_key):
			continue

		frappe.sendmail(
			recipients=[appointment.email],
			subject=_("Customer Fitting Appointment Reminder"),
			message=_(
				"Dear {customer},<br><br>"
				"This is a reminder that your {appointment_type} appointment is scheduled "
				"for {appointment_time}.<br>"
				"{branch}<br><br>"
				"Regards,<br>Mr Black"
			).format(
				customer=appointment.customer or _("Customer"),
				appointment_type=appointment.appointment_type,
				appointment_time=format_datetime(appointment.appointment_date_and_time),
				branch=f"{_('Branch')}: {appointment.branch}" if appointment.branch else "",
			),
		)
		frappe.cache.set_value(cache_key, 1, expires_in_sec=REMINDER_CACHE_TTL)
		queued += 1

	return {"found": len(appointments), "queued": queued}


def get_due_fitting_appointments(days_ahead=REMINDER_DAYS):
	"""Return submitted, non-cancelled appointments on the target calendar day."""
	target_date = add_days(today(), days_ahead)
	start = get_datetime(f"{target_date} 00:00:00")
	end = get_datetime(f"{add_days(target_date, 1)} 00:00:00")

	return frappe.get_all(
		"Customer Fitting Appointment",
		filters={
			"docstatus": 1,
			"appointment_status": ["in", ["Pending", "Approved"]],
			"appointment_date_and_time": ["between", [start, end]],
		},
		fields=[
			"name",
			"customer",
			"email",
			"appointment_type",
			"appointment_date_and_time",
			"branch",
		],
		order_by="appointment_date_and_time asc",
	)

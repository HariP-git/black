BLOCKING_UNIT_STATUSES = (
	"Reserved",
	"Rented Out",
	"Returned",
	"Under Inspection",
	"Under Repair",
	"Lost",
	"Retired",
)
CLEANING_STATUS = "Under Cleaning"
ACTIVE_ALLOCATION_STATUSES = ("Hold", "Confirmed")

BOOKING_OPEN_STATUSES = (
	"Draft",
	"Availability Checked",
	"Awaiting Payment",
	"Confirmed",
	"Partially Handed Over",
	"Rented Out",
	"Partially Returned",
	"Return Inspection",
	"Settlement Pending",
	"Overdue",
	"Disputed",
)

HANDOVER_READY_STATUSES = ("Confirmed", "Partially Handed Over", "Partially Returned")
RETURN_READY_STATUSES = ("Rented Out", "Partially Handed Over", "Partially Returned", "Overdue")

APPROVER_ROLES = {"Rental Manager", "Rental Admin", "System Manager"}
FINANCIAL_ROLES = APPROVER_ROLES | {"Accounts User"}
RENTAL_DASHBOARD_ROLES = APPROVER_ROLES | {"Accounts User", "Rental Cashier", "Rental Storekeeper"}

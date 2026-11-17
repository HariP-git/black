from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


STATUS_TRANSITIONS = {
	"Draft": {"Draft", "Planned"},
	"Planned": {"Planned", "Ready", "Cancelled"},
	"Ready": {"Ready", "Live", "Cancelled"},
	"Live": {"Live", "Ended"},
	"Ended": {"Ended"},
	"Cancelled": {"Cancelled"},
}
PROTECTED_STATUSES = {"Live", "Ended", "Cancelled"}
GO_LIVE_ROLES = {"System Manager", "Stock Manager", "Owner"}


class ProductLaunch(Document):
	def before_validate(self):
		self._capture_original_item_state()
		self._refresh_available_stock()

	def validate(self):
		self._validate_status_transition()
		self._validate_products()
		self._set_readiness_status()

	def on_update(self):
		if self.status == "Cancelled":
			self._restore_items_disabled_before_launch()

	def _capture_original_item_state(self):
		for row in self.products:
			if row.item and row.is_new():
				row.originally_disabled = frappe.db.get_value("Item", row.item, "disabled") or 0

	def _validate_status_transition(self):
		old_status = self.get_db_value("status") if not self.is_new() else None
		if not old_status:
			if self.status != "Draft":
				frappe.throw(_("A new Product Launch must start in Draft status."))
			return

		allowed = STATUS_TRANSITIONS.get(old_status, {old_status})
		if self.status not in allowed:
			frappe.throw(
				_("Product Launch status cannot change from {0} to {1}.").format(
					frappe.bold(old_status), frappe.bold(self.status)
				)
			)

		if self.status == "Live" and not self.flags.get("from_go_live"):
			frappe.throw(_("Use the Go Live Now button to activate this collection."))

	def _validate_products(self):
		seen = set()
		for row in self.products:
			if not row.item:
				frappe.throw(_("Every product row must have an Item."))
			if row.item in seen:
				frappe.throw(_("Item {0} appears more than once in this collection.").format(frappe.bold(row.item)))
			seen.add(row.item)

			item = frappe.db.get_value(
				"Item",
				row.item,
				["item_name", "disabled", "is_sales_item", "is_stock_item", "has_variants"],
				as_dict=True,
			)
			if not item:
				frappe.throw(_("Item {0} does not exist.").format(frappe.bold(row.item)))
			if not item.is_sales_item:
				frappe.throw(_("Item {0} is not configured as a sales item.").format(frappe.bold(row.item)))

			eligible_items = _get_eligible_items(row.item, include_disabled=bool(row.hide_until_launch))
			if not eligible_items:
				frappe.throw(
					_("Item {0} has no active, stock-maintained sellable item or variant.").format(
						frappe.bold(row.item)
					)
				)

			if flt(row.planned_qty) <= 0:
				frappe.throw(_("Planned Qty for {0} must be greater than zero.").format(frappe.bold(row.item)))
			if flt(row.launch_price) <= 0:
				frappe.throw(_("Launch Price for {0} must be greater than zero.").format(frappe.bold(row.item)))

			row.item_name = item.item_name
			row.available_stock = _get_available_stock(eligible_items, self._get_company())

	def _refresh_available_stock(self):
		company = self._get_company(raise_error=False)
		if not company:
			return
		for row in self.products:
			if row.item:
				row.available_stock = _get_available_stock(
					_get_eligible_items(row.item, include_disabled=bool(row.hide_until_launch)), company
				)

	def _set_readiness_status(self):
		if self.status in PROTECTED_STATUSES:
			return
		if self.status not in {"Planned", "Ready"}:
			return
		if not self.products:
			self.status = "Planned"
			return
		if all(
			flt(row.available_stock) >= flt(row.planned_qty)
			and flt(row.planned_qty) > 0
			and flt(row.launch_price) > 0
			for row in self.products
		):
			self.status = "Ready"
		else:
			self.status = "Planned"

	def _get_company(self, raise_error=True):
		companies = frappe.get_all(
			"POS Profile",
			filters={"disabled": 0},
			pluck="company",
			distinct=True,
		)
		companies = [company for company in companies if company]
		if len(companies) == 1:
			return companies[0]
		if raise_error:
			frappe.throw(
				_("Product Launch requires exactly one company with active POS Profiles; found {0}.").format(
					len(companies)
				)
			)
		return None

	def _restore_items_disabled_before_launch(self):
		for row in self.products:
			if not row.item or not row.originally_disabled:
				continue
			for item_code in _get_eligible_items(row.item, include_disabled=True):
				frappe.db.set_value("Item", item_code, "disabled", 1, update_modified=False)


@frappe.whitelist()
def get_stock_for_item(item, company=None):
	company = company or _get_launch_company()
	return {
		"item": item,
		"available_stock": _get_available_stock(_get_eligible_items(item, include_disabled=True), company),
		"eligible_items": _get_eligible_items(item, include_disabled=True),
	}


@frappe.whitelist()
def get_stock_snapshot(name):
	doc = frappe.get_doc("Product Launch", name)
	frappe.has_permission(doc, "read", throw=True)
	company = doc._get_company()
	return {
		row.name: _get_available_stock(_get_eligible_items(row.item), company)
		for row in doc.products
		if row.item
	}


@frappe.whitelist()
def go_live(name):
	doc = frappe.get_doc("Product Launch", name)
	_validate_go_live_permission(doc)
	if doc.status not in {"Planned", "Ready"}:
		frappe.throw(_("Only Planned or Ready collections can be activated."))
	if not doc.products:
		frappe.throw(_("A Product Launch must contain at least one product."))

	company = doc._get_company()
	price_lists = _get_effective_selling_price_lists(company)
	price_plan = []
	price_rollovers = {}
	for row in doc.products:
		eligible_items = _get_eligible_items(row.item, include_disabled=True)
		if not eligible_items:
			frappe.throw(_("No sellable stock item or variant is available for {0}.").format(frappe.bold(row.item)))
		available_stock = _get_available_stock(eligible_items, company)
		if flt(row.planned_qty) <= 0:
			frappe.throw(_("Planned Qty for {0} must be greater than zero.").format(frappe.bold(row.item)))
		if flt(row.launch_price) <= 0:
			frappe.throw(_("Launch Price for {0} must be greater than zero.").format(frappe.bold(row.item)))
		if available_stock < flt(row.planned_qty):
			frappe.throw(
				_("Insufficient available stock for {0}: {1} available, {2} planned.").format(
					frappe.bold(row.item), frappe.bold(available_stock), frappe.bold(row.planned_qty)
				)
			)
		for price_list in price_lists:
			for item_code in eligible_items:
				for item_price_name in _validate_item_price(
					item_code, price_list, doc.launch_date, row.launch_price
				):
					price_rollovers[item_price_name] = getdate(doc.launch_date) - timedelta(days=1)
				price_plan.append((item_code, price_list, row.launch_price))

	for item_price_name, valid_upto in price_rollovers.items():
		frappe.db.set_value("Item Price", item_price_name, "valid_upto", valid_upto, update_modified=True)

	for item_code, price_list, launch_price in price_plan:
		_create_or_reuse_item_price(item_code, price_list, doc.launch_date, launch_price)

	for row in doc.products:
		if row.hide_until_launch:
			for item_code in _get_eligible_items(row.item, include_disabled=True):
				frappe.db.set_value("Item", item_code, "disabled", 0, update_modified=False)

	doc.flags.from_go_live = True
	doc.status = "Live"
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "status": doc.status, "price_lists": price_lists}


def _validate_go_live_permission(doc):
	if not frappe.has_permission(doc, "write"):
		frappe.throw(_("You do not have permission to activate this Product Launch."), frappe.PermissionError)
	if not GO_LIVE_ROLES.intersection(set(frappe.get_roles())):
		frappe.throw(_("Only a manager with launch permission can activate a Product Launch."), frappe.PermissionError)


def _get_launch_company():
	companies = frappe.get_all("POS Profile", filters={"disabled": 0}, pluck="company", distinct=True)
	companies = [company for company in companies if company]
	if len(companies) != 1:
		frappe.throw(_("Product Launch requires exactly one company with active POS Profiles."))
	return companies[0]


def _get_eligible_warehouses(company):
	warehouses = frappe.get_all(
		"POS Profile",
		filters={"company": company, "disabled": 0},
		pluck="warehouse",
	)
	warehouses = list({warehouse for warehouse in warehouses if warehouse})
	if not warehouses:
		frappe.throw(_("No selling warehouse is configured on an active POS Profile for {0}.").format(company))
	disabled = set(
		frappe.get_all("Warehouse", filters={"name": ["in", warehouses], "disabled": 1}, pluck="name")
	)
	return [warehouse for warehouse in warehouses if warehouse not in disabled]


def _get_eligible_items(item_code, include_disabled=False):
	item = frappe.db.get_value(
		"Item",
		item_code,
		["name", "is_sales_item", "is_stock_item", "has_variants"],
		as_dict=True,
	)
	if not item or not item.is_sales_item:
		return []
	if item.has_variants:
		filters = {
			"variant_of": item_code,
			"is_sales_item": 1,
			"is_stock_item": 1,
		}
		if not include_disabled:
			filters["disabled"] = 0
		return frappe.get_all("Item", filters=filters, pluck="name")
	if not item.is_stock_item:
		return []
	if not include_disabled and frappe.db.get_value("Item", item_code, "disabled"):
		return []
	return [item_code]


def _get_available_stock(item_codes, company):
	if not item_codes:
		return 0
	warehouses = _get_eligible_warehouses(company)
	item_placeholders = ", ".join(["%s"] * len(item_codes))
	warehouse_placeholders = ", ".join(["%s"] * len(warehouses))
	row = frappe.db.sql(
		f"""
		SELECT COALESCE(SUM(GREATEST(actual_qty - reserved_qty, 0)), 0)
		FROM `tabBin`
		WHERE item_code IN ({item_placeholders})
			AND warehouse IN ({warehouse_placeholders})
		""",
		tuple(item_codes) + tuple(warehouses),
	)
	return flt(row[0][0]) if row else 0


def _get_effective_selling_price_lists(company):
	fallback = frappe.get_single_value("Selling Settings", "selling_price_list")
	profiles = frappe.get_all(
		"POS Profile",
		filters={"company": company, "disabled": 0},
		fields=["name", "selling_price_list"],
	)
	price_lists = {profile.selling_price_list or fallback for profile in profiles}
	price_lists.discard(None)
	price_lists.discard("")
	if not price_lists:
		frappe.throw(_("No selling Price List is configured for the active POS Profiles."))
	invalid = [
		price_list
		for price_list in price_lists
		if not frappe.db.get_value("Price List", {"name": price_list, "selling": 1, "enabled": 1})
	]
	if invalid:
		frappe.throw(_("These POS selling Price Lists are invalid or disabled: {0}.").format(", ".join(invalid)))
	return sorted(price_lists)


def _validate_item_price(item_code, price_list, launch_date, launch_price):
	launch_date = getdate(launch_date)
	rollovers = []
	records = frappe.get_all(
		"Item Price",
		filters={"item_code": item_code, "price_list": price_list, "selling": 1},
		fields=["name", "price_list_rate", "valid_from", "valid_upto", "uom"],
	)
	for record in records:
		if getdate(record.valid_from or "1900-01-01") == launch_date and flt(record.price_list_rate) == flt(launch_price):
			continue
		start = getdate(record.valid_from or "1900-01-01")
		end = getdate(record.valid_upto) if record.valid_upto else None
		if start <= launch_date and (not end or launch_date <= end):
			if start < launch_date:
				rollovers.append(record.name)
				continue
			frappe.throw(
				_("Item Price {0} already covers {1} for {2}; launch pricing would overwrite existing pricing.").format(
					frappe.bold(record.name), frappe.bold(item_code), frappe.bold(price_list)
				)
			)
		if start > launch_date and not end:
			frappe.throw(
				_("Item Price {0} starts after the launch date and has no end date. Resolve the overlap for {1}.").format(
					frappe.bold(record.name), frappe.bold(item_code)
				)
			)
	return rollovers


def _create_or_reuse_item_price(item_code, price_list, launch_date, launch_price):
	existing = frappe.get_all(
		"Item Price",
		filters={
			"item_code": item_code,
			"price_list": price_list,
			"selling": 1,
			"valid_from": launch_date,
			"price_list_rate": launch_price,
		},
		limit=1,
		pluck="name",
	)
	if existing:
		return existing[0]
	item = frappe.db.get_value("Item", item_code, ["stock_uom", "item_name"], as_dict=True)
	price_list_currency = frappe.db.get_value("Price List", price_list, "currency")
	doc = frappe.get_doc(
		{
			"doctype": "Item Price",
			"item_code": item_code,
			"item_name": item.item_name,
			"uom": item.stock_uom,
			"price_list": price_list,
			"selling": 1,
			"buying": 0,
			"currency": price_list_currency,
			"price_list_rate": launch_price,
			"valid_from": launch_date,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name

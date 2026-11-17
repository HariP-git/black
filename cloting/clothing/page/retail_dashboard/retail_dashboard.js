frappe.pages["retail-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Mr Black Retail Dashboard"),
		single_column: true,
	});

	frappe.require("/assets/cloting/css/retail_dashboard.css");
	wrapper.retail_dashboard = new RetailDashboard(wrapper, page);
};

class RetailDashboard {
	constructor(wrapper, page) {
		this.wrapper = wrapper;
		this.page = page;
		this.charts = {};
		this.setup_controls();
		this.render_shell();
		this.refresh();
	}

	setup_controls() {
		this.period = this.page.add_field({
			fieldname: "period",
			label: __("Period"),
			fieldtype: "Select",
			options: [
				{ label: __("Today"), value: "today" },
				{ label: __("This Week"), value: "week" },
				{ label: __("This Month"), value: "month" },
				{ label: __("This Year"), value: "year" },
				{ label: __("Custom Date Range"), value: "custom" },
			],
			default: "month",
			change: () => this.period_changed(),
		});
		this.from_date = this.page.add_field({
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			hidden: 1,
			change: () => this.refresh(),
		});
		this.to_date = this.page.add_field({
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			hidden: 1,
			change: () => this.refresh(),
		});
		this.company = this.page.add_field({
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company") || "MrBlack",
			change: () => this.refresh(),
		});
		this.warehouse = this.page.add_field({
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: () => ({ filters: { company: this.company.get_value(), disabled: 0 } }),
			change: () => this.refresh(),
		});
		this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh-cw");
		this.period.set_value("month");
		this.period_changed(false);
	}

	period_changed(refresh = true) {
		const today = frappe.datetime.get_today();
		const period = this.period.get_value();
		let from = today;
		if (period === "week") from = frappe.datetime.add_days(today, -6);
		if (period === "month") from = frappe.datetime.month_start(today);
		if (period === "year") from = frappe.datetime.year_start(today);
		const custom = period === "custom";
		$(this.from_date.wrapper).toggle(custom);
		$(this.to_date.wrapper).toggle(custom);
		if (!custom) {
			this.from_date.set_value(from);
			this.to_date.set_value(today);
		}
		if (refresh) this.refresh();
	}

	render_shell() {
		$(this.page.main).html(`
			<div class="mr-dashboard">
				<header class="mr-dashboard-header">
					<div>
						<div class="mr-dashboard-kicker">MR. BLACK / RETAIL OPERATIONS</div>
						<h1>Mr Black <span>Retail Management Dashboard</span></h1>
						<p>Business performance overview</p>
					</div>
					<div class="mr-dashboard-updated" data-updated></div>
				</header>
				<div class="mr-dashboard-loading" data-loading>Loading dashboard...</div>
				<div data-dashboard-content></div>
			</div>
		`);
	}

	refresh() {
		if (this.period.get_value() === "custom" && (!this.from_date.get_value() || !this.to_date.get_value())) return;
		$(this.wrapper).find("[data-loading]").show();
		frappe.call({
			method: "cloting.clothing.page.retail_dashboard.retail_dashboard.get_dashboard_data",
			args: {
				from_date: this.from_date.get_value(),
				to_date: this.to_date.get_value(),
				company: this.company.get_value(),
				warehouse: this.warehouse.get_value(),
			},
		}).then((response) => {
			this.data = response.message;
			this.render_dashboard();
		}).catch(() => {
			frappe.msgprint(__("Unable to load dashboard data."));
		}).finally(() => $(this.wrapper).find("[data-loading]").hide());
	}

	render_dashboard() {
		const d = this.data;
		$(this.wrapper).find("[data-updated]").text(__("Updated {0}", [d.updated_at]));
		$(this.wrapper).find("[data-dashboard-content]").html(`
			<section class="mr-kpi-grid">${this.kpi("Total Sales", d.kpis.total_sales, "currency")}
				${this.kpi("Sales Invoices", d.kpis.invoice_count, "number")}
				${this.kpi("Average Order Value", d.kpis.average_order_value, "currency")}
				${this.kpi("Purchase Value", d.kpis.purchase_value, "currency")}
				${this.kpi("Customers", d.kpis.customers, "number")}
				${this.kpi("Outstanding Payments", d.kpis.outstanding, "currency")}
				${this.kpi("Total Stock Value", d.kpis.stock_value, "currency")}
				${this.kpi("Low Stock Items", d.kpis.low_stock_count, "number")}
			</section>
			<section class="mr-section">
				<div class="mr-section-title"><span>Sales Analytics</span><small>${d.filters.from_date} — ${d.filters.to_date}</small></div>
				<div class="mr-chart-grid">
					${this.chart_card("Daily Sales Trend", "daily", "line")}
					${this.chart_card("Monthly Sales Trend", "monthly", "line")}
					${this.chart_card("Sales by Item Group", "item_groups", "bar")}
					${this.chart_card("Top 10 Selling Products", "products", "bar")}
					${this.chart_card("Payment Mode Distribution", "payments", "donut")}
				</div>
			</section>
			<section class="mr-section">
				<div class="mr-section-title"><span>Inventory Analytics</span><small>${d.inventory.stock_qty.toLocaleString()} units available</small></div>
				<div class="mr-stat-strip"><b>${d.inventory.stock_value.toLocaleString()}</b><span>Stock value</span><b>${d.inventory.low_stock_count}</b><span>Low stock</span><b>${d.inventory.out_of_stock_count}</b><span>Out of stock</span></div>
				<div class="mr-chart-grid">${this.chart_card("Top Items by Stock Value", "inventory_top", "bar")}${this.chart_card("Warehouse Stock Distribution", "warehouses", "donut")}</div>
			</section>
			<section class="mr-section">
				<div class="mr-section-title"><span>Customers & Buying</span></div>
				<div class="mr-two-column">
					<div class="mr-panel"><h3>Customer Analytics</h3>${this.chart_card("Top Customers by Sales", "top_customers", "bar", true)}${this.chart_card("Customer Group Sales", "customer_groups", "bar", true)}${this.chart_card("Individual vs Company", "customer_types", "donut", true)}</div>
					<div class="mr-panel"><h3>Buying & Suppliers</h3><div class="mr-mini-stats"><div><b>${d.buying.pending_po}</b><span>Pending purchase orders</span></div><div><b>${d.buying.pending_pr}</b><span>Pending receipts</span></div></div>${this.chart_card("Top Suppliers by Purchase Value", "supplier_purchase", "bar", true)}</div>
				</div>
			</section>
			<section class="mr-section">
				<div class="mr-section-title"><span>Mr Black Custom Analytics</span></div>
				<div class="mr-custom-grid">
					<div class="mr-custom-card"><b>${d.custom.feedback.count}</b><span>Feedback entries</span><strong>${d.custom.feedback.average_rating.toFixed(1)} / 5 average rating</strong></div>
					<div class="mr-custom-card"><b>${d.custom.supplier_quality.count}</b><span>Supplier quality evaluations</span><strong>${d.custom.supplier_quality.average_rating.toFixed(1)} / 5 average rating</strong></div>
					${this.chart_card("Product Launch Status", "launches", "donut", true)}
				</div>
				<div class="mr-omitted">${d.custom.omitted.join(" ")}</div>
			</section>
		`);
		this.render_charts();
	}

	kpi(label, value, type) {
		const formatted = type === "currency" ? format_currency(value) : Number(value || 0).toLocaleString();
		return `<div class="mr-kpi-card"><span>${label}</span><b>${formatted}</b></div>`;
	}

	chart_card(title, key, type, compact = false) {
		return `<div class="mr-chart-card ${compact ? "compact" : ""}"><h3>${title}</h3><div class="mr-chart" data-chart="${key}" data-chart-type="${type}"></div></div>`;
	}

	render_charts() {
		const map = {
			daily: this.data.sales.daily, monthly: this.data.sales.monthly,
			item_groups: this.data.sales.item_groups, products: this.data.sales.products,
			payments: this.data.sales.payments, inventory_top: this.data.inventory.top_items,
			warehouses: this.data.inventory.warehouses, top_customers: this.data.customers.top_customers,
			customer_groups: this.data.customers.groups, customer_types: this.data.customers.types,
			supplier_purchase: this.data.buying.supplier_purchase,
			launches: this.data.custom.launches,
		};
		$(this.wrapper).find("[data-chart]").each((_, node) => {
			const key = $(node).data("chart");
			const rows = map[key] || [];
			if (!rows.length) {
				$(node).html('<div class="mr-empty">No data for this period</div>');
				return;
			}
			const type = $(node).data("chart-type");
			const options = {
				data: { labels: rows.map((r) => r.label), datasets: [{ values: rows.map((r) => r.value) }] },
				type: type === "donut" ? "donut" : type,
				height: 220,
				colors: ["#111827", "#6b7280", "#b8a06a"],
				axisOptions: { xIsSeries: true, xAxisMode: "tick" },
				tooltipOptions: { formatTooltipX: (d) => d, formatTooltipY: (d) => format_currency(d) },
			};
			new frappe.Chart(node, options);
		});
	}
}

function format_currency(value) {
	return frappe.format(value || 0, { fieldtype: "Currency", options: "INR" });
}

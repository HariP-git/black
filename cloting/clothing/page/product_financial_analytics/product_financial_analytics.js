frappe.pages["product-financial-analytics"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Product & Financial Analytics"),
		single_column: true,
	});

	wrapper.product_financial_analytics = new ProductFinancialAnalytics(wrapper, page);
};

class ProductFinancialAnalytics {
	constructor(wrapper, page) {
		this.wrapper = wrapper;
		this.page = page;
		this.charts = [];
		this.setup_filters();
		this.render_shell();
		this.refresh();
	}

	setup_filters() {
		const today = frappe.datetime.get_today();
		this.from_date = this.page.add_field({
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(today),
			change: () => this.refresh(),
		});
		this.to_date = this.page.add_field({
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: today,
			change: () => this.refresh(),
		});
		this.company = this.page.add_field({
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
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
		this.item_group = this.page.add_field({
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
			change: () => this.refresh(),
		});
		this.item_code = this.page.add_field({
			fieldname: "item_code",
			label: __("Product"),
			fieldtype: "Link",
			options: "Item",
			change: () => this.refresh(),
		});
		this.transaction_type = this.page.add_field({
			fieldname: "transaction_type",
			label: __("Transaction Type"),
			fieldtype: "Select",
			options: ["All", "Retail", "Rental"],
			default: "All",
			change: () => this.refresh(),
		});
		this.supplier = this.page.add_field({
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
			change: () => this.refresh(),
		});
		this.customer = this.page.add_field({
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
			change: () => this.refresh(),
		});
		this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh-cw");
		this.page.add_inner_button(__("Export Products"), () => this.export_products());
		this.page.add_inner_button(__("Print"), () => window.print());
	}

	render_shell() {
		$(this.page.main).html(`
			<style>
				.pfa-page { padding: 18px; background: #f8fafc; min-height: 100vh; }
				.pfa-header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:18px; }
				.pfa-header h1 { margin:0; font-size:26px; color:#111827; }
				.pfa-header p { color:#6b7280; margin:5px 0 0; }
				.pfa-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }
				.pfa-card,.pfa-panel { background:white; border:1px solid #e5e7eb; border-radius:8px; padding:16px; }
				.pfa-card span,.pfa-card small { display:block; color:#6b7280; }
				.pfa-card b { display:block; margin-top:8px; font-size:21px; color:#111827; }
				.pfa-section { margin-top:20px; }
				.pfa-section h2 { font-size:18px; margin:0 0 10px; color:#111827; }
				.pfa-two { display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:14px; }
				.pfa-chart { min-height:260px; }
				.pfa-table { width:100%; border-collapse:collapse; font-size:12px; }
				.pfa-table th,.pfa-table td { border-bottom:1px solid #eef0f2; padding:8px; text-align:right; white-space:nowrap; }
				.pfa-table th:first-child,.pfa-table td:first-child { text-align:left; }
				.pfa-table-wrap { overflow:auto; }
				.pfa-muted { color:#6b7280; font-size:12px; }
				.pfa-note { background:#fffbeb; border:1px solid #fde68a; padding:10px 14px; border-radius:6px; margin-top:14px; color:#78350f; }
			</style>
			<div class="pfa-page">
				<div class="pfa-header">
					<div><h1>${__("Product & Financial Analytics")}</h1><p>${__("Traceable product, inventory, sales, rental, and accounting performance")}</p></div>
					<div class="pfa-muted" data-updated></div>
				</div>
				<div data-loading class="pfa-note">${__("Loading analytics...")}</div>
				<div data-content></div>
			</div>
		`);
	}

	refresh() {
		const args = {
			from_date: this.from_date.get_value(),
			to_date: this.to_date.get_value(),
			company: this.company.get_value(),
			warehouse: this.warehouse.get_value(),
			item_group: this.item_group.get_value(),
			item_code: this.item_code.get_value(),
			transaction_type: this.transaction_type.get_value(),
			supplier: this.supplier.get_value(),
			customer: this.customer.get_value(),
		};
		$(this.wrapper).find("[data-loading]").show();
		frappe.call({
			method: "cloting.clothing.page.product_financial_analytics.product_financial_analytics.get_dashboard_data",
			args,
		}).then((response) => {
			this.data = response.message;
			this.render();
		}).catch(() => {
			frappe.msgprint(__("Unable to load Product & Financial Analytics."));
		}).finally(() => $(this.wrapper).find("[data-loading]").hide());
	}

	render() {
		const d = this.data;
		$(this.wrapper).find("[data-updated]").text(__("Updated {0}", [d.updated_at]));
		$(this.wrapper).find("[data-content]").html(`
			<section class="pfa-grid">${[
				["Total Sales Revenue", d.kpis.total_sales_revenue],
				["Net Sales", d.kpis.net_sales],
				["Gross Profit", d.kpis.gross_profit],
				["Net Profit", d.kpis.net_profit],
				["Total Expenses", d.kpis.total_expenses],
				["COGS", d.kpis.total_cogs],
				["Current Stock Value", d.kpis.current_stock_value],
				["Receivables", d.kpis.outstanding_receivables],
				["Payables", d.kpis.outstanding_payables],
				["Customer Advances", d.kpis.customer_advances],
				["Supplier Advances", d.kpis.supplier_advances],
				["Rental Revenue", d.kpis.rental_revenue],
				["Discounts", d.kpis.total_discounts],
			].map(([label, value]) => this.card(label, format_currency(value, d.currency))).join("")}</section>

			<section class="pfa-section">
				<h2>${__("Profit & Loss Analysis")}</h2>
				<div class="pfa-grid">${[
					["Gross Sales", d.pnl.gross_sales],
					["Sales Returns", d.pnl.sales_returns],
					["Sales Discounts", d.pnl.discounts],
					["Net Sales", d.pnl.net_sales],
					["COGS", d.pnl.cogs],
					["Gross Profit", d.pnl.gross_profit],
					["Operating Expenses", d.pnl.operating_expenses],
					["Net Profit / Loss", d.pnl.net_profit],
				].map(([label, value]) => this.card(label, format_currency(value, d.currency))).join("")}</div>
			</section>

			<section class="pfa-section pfa-two">
				<div class="pfa-panel"><h2>${__("Monthly Revenue vs Expenses")}</h2><div class="pfa-chart" data-chart="income-expense"></div></div>
				<div class="pfa-panel"><h2>${__("Top Products by Profit")}</h2><div class="pfa-chart" data-chart="top-profit"></div></div>
				<div class="pfa-panel"><h2>${__("Top Products by Revenue")}</h2><div class="pfa-chart" data-chart="top-revenue"></div></div>
				<div class="pfa-panel"><h2>${__("Warehouse Stock Value")}</h2><div class="pfa-chart" data-chart="warehouse-stock"></div></div>
			</section>

			<section class="pfa-section pfa-panel">
				<h2>${__("Product Performance")}</h2>
				<div class="pfa-table-wrap">${this.product_table(d.products, d.currency)}</div>
			</section>

			<section class="pfa-section pfa-panel">
				<h2>${__("Products with No Sales in Period")}</h2>
				<div class="pfa-table-wrap">${this.no_sales_table(d.no_sales_products)}</div>
			</section>

			<section class="pfa-section pfa-two">
				<div class="pfa-panel"><h2>${__("Purchase & Supplier Analysis")}</h2><div class="pfa-table-wrap">${this.simple_table(d.purchases.supplier_values, ["label", "value"], d.currency)}</div></div>
				<div class="pfa-panel"><h2>${__("Sales by Category")}</h2><div class="pfa-table-wrap">${this.simple_table(d.sales.category_values, ["label", "value"], d.currency)}</div></div>
			</section>

			<section class="pfa-section pfa-panel">
				<h2>${__("Rental Business Analysis")}</h2>
				<div class="pfa-grid">${[
					["Rental Revenue", d.rental.revenue],
					["Booking Count", d.rental.booking_count, true],
					["Utilization Days", d.rental.utilization_days, true],
					["Late Return Charges", d.rental.late_fee],
					["Damage Recovery", d.rental.damage_recovery],
				].map(([label, value, number]) => this.card(label, number ? Number(value || 0).toLocaleString() : format_currency(value, d.currency))).join("")}</div>
				<div class="pfa-note">${esc(d.rental.profitability_note)}</div>
			</section>

			<section class="pfa-section pfa-panel"><h2>${__("Data Definitions & Limitations")}</h2><ul>${d.limitations.map((text) => `<li>${esc(text)}</li>`).join("")}</ul></section>
		`);
		$(this.wrapper).find("[data-product-detail]").on("click", (event) => {
			event.preventDefault();
			this.show_product_detail($(event.currentTarget).data("item-code"));
		});
		this.render_charts();
	}

	card(label, value) {
		return `<div class="pfa-card"><span>${esc(label)}</span><b>${value}</b></div>`;
	}

	product_table(rows, currency) {
		if (!rows.length) return `<div class="pfa-muted">${__("No product transactions found for the selected filters.")}</div>`;
		const headers = ["Product", "Group", "Qty Sold", "Net Sales", "COGS", "Gross Profit", "Margin", "Stock Qty", "Stock Value"];
		return `<table class="pfa-table"><thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `
			<tr>
				<td><a href="#" data-product-detail data-item-code="${esc(row.item_code)}">${esc(row.item_code)}</a><br><span class="pfa-muted">${esc(row.item_name || "")}</span></td>
				<td>${esc(row.item_group || "")}</td><td>${Number(row.qty_sold || 0).toLocaleString()}</td>
				<td>${format_currency(row.net_sales, currency)}</td><td>${format_currency(row.cogs, currency)}</td>
				<td>${format_currency(row.gross_profit, currency)}</td><td>${Number(row.profit_margin || 0).toFixed(1)}%</td>
				<td>${Number(row.stock_qty || 0).toLocaleString()}</td><td>${format_currency(row.stock_value, currency)}</td>
			</tr>`).join("")}</tbody></table>`;
	}

	no_sales_table(rows) {
			if (!rows.length) return `<div class="pfa-muted">${__("No stock products without sales were found for the selected filters.")}</div>`;
			return `<table class="pfa-table"><thead><tr><th>${__("Item")}</th><th>${__("Item Group")}</th><th>${__("Brand")}</th></tr></thead><tbody>${rows.map((row) => `
				<tr><td><a href="#" data-product-detail data-item-code="${esc(row.item_code)}">${esc(row.item_code)}</a><br><span class="pfa-muted">${esc(row.item_name || "")}</span></td>
				<td>${esc(row.item_group || "")}</td><td>${esc(row.brand || "")}</td></tr>`).join("")}</tbody></table>`;
	}

	export_products() {
			const rows = this.data && this.data.products;
			if (!rows || !rows.length) {
				frappe.msgprint(__("There are no product rows to export."));
				return;
			}
			const headers = ["Item Code", "Item Name", "Item Group", "Qty Sold", "Net Sales", "COGS", "Gross Profit", "Margin %", "Stock Qty", "Stock Value"];
			const values = rows.map((row) => [
				row.item_code, row.item_name, row.item_group, row.qty_sold, row.net_sales,
				row.cogs, row.gross_profit, row.profit_margin, row.stock_qty, row.stock_value,
			]);
			const csv = [headers, ...values].map((line) => line.map((value) => `"${String(value == null ? "" : value).replace(/"/g, '""')}"`).join(",")).join("\n");
			const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
			const link = document.createElement("a");
			link.href = URL.createObjectURL(blob);
			link.download = "product-performance.csv";
			link.click();
			URL.revokeObjectURL(link.href);
	}

	show_product_detail(item_code) {
			const dialog = new frappe.ui.Dialog({
				title: __("Product Analysis: {0}", [item_code]),
				size: "extra-large",
				fields: [{ fieldname: "body", fieldtype: "HTML" }],
			});
			dialog.fields_dict.body.$wrapper.html(__("Loading product analysis..."));
			dialog.show();
			frappe.call({
				method: "cloting.clothing.page.product_financial_analytics.product_financial_analytics.get_product_detail",
				args: {
					item_code,
					from_date: this.from_date.get_value(),
					to_date: this.to_date.get_value(),
					company: this.company.get_value(),
				},
			}).then((response) => {
				const d = response.message;
				dialog.fields_dict.body.$wrapper.html(`
					<div class="pfa-grid">
						${this.card(__("Item"), esc(d.item.item_code))}
						${this.card(__("Name"), esc(d.item.item_name))}
						${this.card(__("Item Group"), esc(d.item.item_group))}
						${this.card(__("Standard Rate"), format_currency(d.item.standard_rate, this.data.currency))}
					</div>
					<h4>${__("Stock by Warehouse")}</h4>${this.simple_table(d.stock.map((row) => ({ label: row.warehouse, value: row.stock_value })), ["label", "value"], this.data.currency)}
					<h4>${__("Sales History")}</h4>${this.history_table(d.sales, "name", "posting_date", "customer", "base_net_amount", this.data.currency)}
					<h4>${__("Purchase History")}</h4>${this.history_table(d.purchases, "name", "posting_date", "supplier", "base_net_amount", this.data.currency)}
				`);
			}).catch(() => {
				dialog.fields_dict.body.$wrapper.html(`<div class="pfa-note">${__("Unable to load product analysis.")}</div>`);
			});
	}

	history_table(rows, document_key, date_key, party_key, amount_key, currency) {
			if (!rows.length) return `<div class="pfa-muted">${__("No history for the selected period.")}</div>`;
			return `<table class="pfa-table"><thead><tr><th>${__("Document")}</th><th>${__("Date")}</th><th>${__("Party")}</th><th>${__("Amount")}</th></tr></thead><tbody>${rows.map((row) => `
				<tr><td>${esc(row[document_key])}</td><td>${esc(row[date_key])}</td><td>${esc(row[party_key])}</td><td>${format_currency(row[amount_key], currency)}</td></tr>`).join("")}</tbody></table>`;
	}

	simple_table(rows, keys, currency) {
		if (!rows.length) return `<div class="pfa-muted">${__("No data for the selected filters.")}</div>`;
		return `<table class="pfa-table"><thead><tr><th>${__("Name")}</th><th>${__("Amount")}</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${esc(row[keys[0]] || "")}</td><td>${format_currency(row[keys[1]], currency)}</td></tr>`).join("")}</tbody></table>`;
	}

	render_charts() {
		this.charts.forEach((chart) => chart && chart.destroy && chart.destroy());
		this.charts = [];
		const charts = this.data.charts;
		const defs = {
			"income-expense": { rows: charts.monthly_income_expense, datasets: ["income", "expense"], names: [__("Income"), __("Expenses")] },
			"top-profit": { rows: charts.top_profit, datasets: ["value"], names: [__("Gross Profit")] },
			"top-revenue": { rows: charts.top_revenue, datasets: ["value"], names: [__("Net Sales")] },
			"warehouse-stock": { rows: this.data.inventory.warehouse_values, datasets: ["value"], names: [__("Stock Value")] },
		};
		$(this.wrapper).find("[data-chart]").each((_, node) => {
			const definition = defs[$(node).data("chart")];
			if (!definition || !definition.rows.length) {
				$(node).html(`<div class="pfa-muted">${__("No data for this period.")}</div>`);
				return;
			}
			const datasets = definition.datasets.map((key, index) => ({
				name: definition.names[index],
				values: definition.rows.map((row) => Number(row[key] || 0)),
			}));
			this.charts.push(new frappe.Chart(node, {
				data: { labels: definition.rows.map((row) => row.label), datasets },
				type: definition.datasets.length > 1 ? "bar" : "bar",
				height: 240,
				colors: ["#111827", "#b8a06a"],
				axisOptions: { xIsSeries: true },
			}));
		});
	}
}

function format_currency(value, currency) {
	return frappe.format(value || 0, { fieldtype: "Currency", options: currency });
}

function esc(value) {
	return frappe.utils.escape_html(String(value == null ? "" : value));
}

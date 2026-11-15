frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        if (
            frm.doc.docstatus === 1 &&
            frm.doc.custom_is_customized
        ) {
            frm.add_custom_button(
                ("Advance Payment"),
                () => mr_black_open_advance_payment(frm)
            );
        }
    },

});

function mr_black_open_advance_payment(frm) {
    const dialog = new frappe.ui.Dialog({
        title: ("Advance Payment"),

        fields: [
            {
                label: ("Customer"),
                fieldname: "customer",
                fieldtype: "Link",
                options: "Customer",
                default: frm.doc.customer,
                read_only: 1
            },
            {
                label: ("Sales Order"),
                fieldname: "sales_order",
                fieldtype: "Link",
                options: "Sales Order",
                default: frm.doc.name,
                read_only: 1
            },
            {
                label: ("Order Amount"),
                fieldname: "order_amount",
                fieldtype: "Currency",
                default: frm.doc.grand_total,
                read_only: 1
            },
            {
                label: ("Amount Collected"),
                fieldname: "paid_amount",
                fieldtype: "Currency",
                reqd: 1
            },
            {
                label: ("Posting Date"),
                fieldname: "posting_date",
                fieldtype: "Date",
                default: frappe.datetime.get_today(),
                reqd: 1
            },
            {
                label: ("Mode of Payment"),
                fieldname: "mode_of_payment",
                fieldtype: "Link",
                options: "Mode of Payment",
                reqd: 1
            },
            {
                label: ("Paid To Account"),
                fieldname: "paid_to",
                fieldtype: "Link",
                options: "Account",
                reqd: 1,
                get_query() {
                    return {
                        filters: {
                            company: frm.doc.company,
                            is_group: 0,
                            disabled: 0
                        }
                    };
                }
            }
        ],

        primary_action_label: ("Create Payment Entry"),
        primary_action(values) {

            frappe.call({
                method: "cloting.overrides.sales_order.create_advance_payment",

                args: {
                    sales_order: frm.doc.name,
                    paid_amount: values.paid_amount,
                    posting_date: values.posting_date,
                    mode_of_payment: values.mode_of_payment,
                    paid_to: values.paid_to
                },

                freeze: true,
                callback(r) {
                    if (r.message) {
                        dialog.hide();

                        frappe.msgprint(
                            ("Payment Entry created successfully.", [
                                r.message
                            ])
                        );

                        frm.reload_doc();
                    }
                }
            });
        }
    });

    dialog.show();
}

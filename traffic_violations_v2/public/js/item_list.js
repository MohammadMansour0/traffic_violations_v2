frappe.listview_settings['Item'] = {

    onload: function(listview) {

        listview.page.add_inner_button('MOI Violation Lookup', function() {

            let d = new frappe.ui.Dialog({
                title: 'Violation Lookup',

                fields: [

                    {
                        label: 'Plate Number',
                        fieldname: 'plate',
                        fieldtype: 'Data',
                        reqd: 1
                    },

                    {
                        label: 'Vehicle Type',
                        fieldname: 'vehicle_type',
                        fieldtype: 'Select',
                        options: [
                            { label: "PRIVATE VEHICLE", value: "PRV" },
                            { label: "GOVERNMENT VEHICLE", value: "G-Q" },
                            { label: "DIPLOMATIC VEHICLE", value: "DIP" },
                            { label: "PRIVATE MOTORCYCLE", value: "PRM" },
                            { label: "TAXI", value: "TXI" },
                            { label: "COMMERCIAL VEHICLE", value: "COM" },
                            { label: "PRIVATE TRANSPORTATION", value: "PRT" },
                            { label: "HEAVY EQUIPMENT", value: "HEQ" },
                            { label: "TRAILERS", value: "TLR" },
                            { label: "PUBLIC TRANSPORTATION", value: "PUT" },
                            { label: "UNITED NATIONS", value: "U-N" },
                            { label: "EXPORT PLATE", value: "XPO" },
                            { label: "GOVERNMENT MECHANICAL", value: "GMQ" },
                            { label: "TESTING PLATE", value: "TMP" },
                            { label: "GOVERMENT TRAILERS", value: "GTR" },
                            { label: "LIMOUSINE", value: "LMS" },
                            { label: "TEMPORARY ENTRY", value: "TME" },
                            { label: "EQUIPMENT", value: "EQP" }
                        ],
                        reqd: 1
                    },

                    {
                        label: 'Owner Type',
                        fieldname: 'owner_type',
                        fieldtype: 'Select',
                        options: ['Individual', 'Company'],
                        default: 'Individual',
                        reqd: 1
                    },

                    {
                        label: 'QID',
                        fieldname: 'qid',
                        fieldtype: 'Data'
                    },

                    {
                        label: 'Company ID',
                        fieldname: 'company_id',
                        fieldtype: 'Data',
                        hidden: 1
                    }
                ],

                primary_action_label: 'Search',

                primary_action(values) {

                    // 🔒 Validations
                    if (!values.plate) {
                        frappe.msgprint("Plate number is required");
                        return;
                    }

                    if (!values.vehicle_type) {
                        frappe.msgprint("Vehicle type is required");
                        return;
                    }

                    if (values.owner_type === "Individual" && !values.qid) {
                        frappe.msgprint("QID is required for Individual");
                        return;
                    }

                    if (values.owner_type === "Company" && !values.company_id) {
                        frappe.msgprint("Company ID is required for Company");
                        return;
                    }

                    // 🚀 Call backend
                    frappe.call({
                        method: "traffic_violations_v2.api.lookup.lookup_violations",

                        args: {
                            plate: values.plate,
                            vehicle_type: values.vehicle_type,
                            qid: values.owner_type === "Individual" ? values.qid : null,
                            company_id: values.owner_type === "Company" ? values.company_id : null
                        },

                        freeze: true,
                        freeze_message: "Checking MOI Violations...",

                        callback(r) {
                            if (!r.message) return;

                            const res = r.message;

                            // 🔴 Invalid ID
                            if (res.status === "invalid_id") {
                                frappe.msgprint({
                                    title: "Invalid ID",
                                    message: "The entered ID is invalid.",
                                    indicator: "red"
                                });
                                return;
                            }

                            // 🔴 Invalid Plate
                            if (res.status === "invalid_plate") {
                                frappe.msgprint({
                                    title: "Invalid Plate",
                                    message: "Type of Vehicle / Plate Number is invalid.",
                                    indicator: "red"
                                });
                                return;
                            }

                            // 🟢 Clean vehicle
                            if (res.status === "clean") {
                                frappe.msgprint({
                                    title: "MOI Result",
                                    message: "✅ No traffic violations found.",
                                    indicator: "green"
                                });
                                return;
                            }

                            // 🟠 Violations found (⭐ USER-FRIENDLY)
                            if (res.status === "violations found") {

                                let html = `
                                    <div>
                                        <p><b>Total Violations:</b> ${res.violations.length}</p>
                                        <hr>
                                `;

                                res.violations.forEach(v => {
                                    html += `
                                        <div style="margin-bottom:12px;">
                                            <b>#${v.violation_no}</b><br>
                                            📅 ${v.date}<br>
                                            📝 ${v.description}<br>
                                            💰 <b>${v.amount}</b>
                                        </div>
                                        <hr>
                                    `;
                                });

                                html += `</div>`;

                                frappe.msgprint({
                                    title: "Traffic Violations",
                                    message: html,
                                    indicator: "orange",
                                    wide: true
                                });

                                return;
                            }

                            // ⚠️ Fallback
                            frappe.msgprint({
                                title: "MOI Error",
                                message: "An unknown error occurred during lookup.",
                                indicator: "orange"
                            });
                        }
                    });

                    d.hide();
                }
            });

            // 🔥 Dynamic switching between QID and Company ID
            d.fields_dict.owner_type.$input.on("change", function() {

                let type = d.get_value("owner_type");

                if (type === "Individual") {
                    d.set_df_property('qid', 'hidden', 0);
                    d.set_df_property('company_id', 'hidden', 1);
                } else {
                    d.set_df_property('qid', 'hidden', 1);
                    d.set_df_property('company_id', 'hidden', 0);
                }

                d.refresh();
            });

            d.show();
        });

    }
};
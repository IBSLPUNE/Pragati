# import frappe


# def set_missing_values(source, target, *args, **kwargs):
#     target.stock_entry_type = target.stock_entry_type or "Material Transfer"


# def update_item(source_doc, target_doc, source_parent, *args, **kwargs):
#     qty = frappe.utils.flt(source_doc.qty) - frappe.utils.flt(source_doc.delivered_qty)
#     target_doc.qty = qty if qty > 0 else frappe.utils.flt(source_doc.qty)
#     target_doc.uom = source_doc.uom
#     target_doc.stock_uom = source_doc.stock_uom
#     target_doc.conversion_factor = source_doc.conversion_factor or 1
#     target_doc.basic_rate = source_doc.rate
#     target_doc.rate = source_doc.rate
#     target_doc.amount = source_doc.amount
#     target_doc.custom_customer_name = source_parent.customer

#     if source_doc.warehouse:
#         target_doc.s_warehouse = source_doc.warehouse

#     custom_fields = [
#         "custom_project_code",
#         "custom_finish_length",
#         "custom_finish_width",
#         "custom_finish_thickness",
#         "custom_raw_length",
#         "custom_raw_width",
#         "custom_raw_thickness",
#         "custom_material_rate",
#         "custom_weight",
#         "custom_batch_no"
#     ]
#     for field in custom_fields:
#         value = source_doc.get(field)
#         if value is not None:
#             target_doc.set(field, value)


# @frappe.whitelist()
# def make_stock_entry_from_sales_order(source_name, target_doc=None, args=None, **kwargs):
#     # map_docs (allow_child_item_selection wale flow mein) is function ko
#     # positionally call karta hai: method(source_name, target_doc, args)
#     # jaha "args" ek poora dict hota hai:
#     #   {"customer": ..., "allow_child_item_selection": 1,
#     #    "filtered_children": [<selected Sales Order Item row names>]}
#     # Isliye humein khud dict ke andar se "filtered_children" nikaalna hoga.
#     args = args or {}
#     filtered_children = args.get("filtered_children")

#     def item_condition(source_doc):
#         if not filtered_children:
#             return True  # koi selection nahi -> sab allow (safe fallback)
#         return source_doc.name in filtered_children

#     doc = frappe.model.mapper.get_mapped_doc(
#         "Sales Order",
#         source_name,
#         {
#             "Sales Order": {
#                 "doctype": "Stock Entry",
#                 "validation": {
#                     "docstatus": ["=", 1]
#                 },
#                 "postprocess": set_missing_values
#             },
#             "Sales Order Item": {
#                 "doctype": "Stock Entry Detail",
#                 "condition": item_condition,
#                 "postprocess": update_item
#             }
#         },
#         target_doc
#     )

#     return doc






import frappe
from frappe.query_builder.functions import Sum


def get_sales_order_link_fieldname():
    """
    Dynamically find the Stock Entry Detail field that links back to
    Sales Order - mirrors the same lookup the client-side duplicate-fetch
    guard already does, so this keeps working even if that field is
    ever renamed.
    """

    meta = frappe.get_meta("Stock Entry Detail")

    for df in meta.fields:
        if df.fieldtype == "Link" and df.options == "Sales Order":
            return df.fieldname

    return None


def get_already_consumed_qty(sales_order, item_code, link_fieldname):
    """
    Sum of custom_weight ("Qty") already pulled into any non-cancelled
    Stock Entry (Draft or Submitted, any customer) for this Sales Order +
    Item Code combination. This is what makes the "remaining" balance
    correct across customers and across drafts, not just within the
    Stock Entry currently open.
    """

    if not link_fieldname:
        return 0

    sed = frappe.qb.DocType("Stock Entry Detail")
    link_field = getattr(sed, link_fieldname)

    result = (
        frappe.qb.from_(sed)
        .select(Sum(sed.custom_weight).as_("total"))
        .where(link_field == sales_order)
        .where(sed.item_code == item_code)
        .where(sed.docstatus != 2)
        .run(as_dict=True)
    )

    return frappe.utils.flt(result[0].total) if result and result[0].total else 0


def set_missing_values(source, target, *args, **kwargs):
    """
    Set default Stock Entry values and fetch Project Title
    from the source Sales Order.
    """

    target.stock_entry_type = (
        target.stock_entry_type or "Material Transfer"
    )

    # Fetch Project Title from Sales Order
    # Only set if Stock Entry Project Title is currently empty
    project_title = source.get("custom_project_title")

    if project_title and not target.get("custom_project_title"):
        target.custom_project_title = project_title


def update_item(source_doc, target_doc, source_parent, *args, **kwargs):
    """
    Map Sales Order Item fields into Stock Entry Detail.
    """

    qty = (
        frappe.utils.flt(source_doc.qty)
        - frappe.utils.flt(source_doc.delivered_qty)
    )

    target_doc.qty = (
        qty if qty > 0 else frappe.utils.flt(source_doc.qty)
    )

    target_doc.uom = source_doc.uom
    target_doc.stock_uom = source_doc.stock_uom

    target_doc.conversion_factor = (
        source_doc.conversion_factor or 1
    )

    target_doc.basic_rate = source_doc.rate
    target_doc.rate = source_doc.rate
    target_doc.amount = source_doc.amount

    target_doc.custom_customer_name = source_parent.customer

    # Source Warehouse
    if source_doc.warehouse:
        target_doc.s_warehouse = source_doc.warehouse

    # Custom fields to be fetched from Sales Order Item
    custom_fields = [
        "custom_project_code",
        "custom_finish_length",
        "custom_finish_width",
        "custom_finish_thickness",
        "custom_raw_length",
        "custom_raw_width",
        "custom_raw_thickness",
        "custom_material_rate",
        "custom_weight",
        "custom_batch_no"
    ]

    for field in custom_fields:
        value = source_doc.get(field)

        if value is not None:
            target_doc.set(field, value)

    # Default "Qty" (custom_weight) to the REMAINING balance instead of
    # always copying the Sales Order Item's full original quantity -
    # subtract whatever has already been pulled into any other Stock
    # Entry (any customer, Draft or Submitted) for this same Sales
    # Order + Item Code.
    link_fieldname = get_sales_order_link_fieldname()

    if link_fieldname:
        already_consumed = get_already_consumed_qty(
            source_parent.name, source_doc.item_code, link_fieldname
        )

        remaining = (
            frappe.utils.flt(source_doc.custom_weight) - already_consumed
        )

        target_doc.custom_weight = remaining if remaining > 0 else 0

        # Keep the link back to the Sales Order populated so future
        # fetches - for this or any other customer - can see this
        # quantity was already allocated here.
        target_doc.set(link_fieldname, source_parent.name)


@frappe.whitelist()
def make_stock_entry_from_sales_order(
    source_name,
    target_doc=None,
    args=None,
    **kwargs
):
    """
    Map Draft or Submitted Sales Order into Stock Entry.

    Allowed:
        Draft SO       (docstatus = 0)
        Submitted SO   (docstatus = 1)

    Not Allowed:
        Cancelled SO   (docstatus = 2)
    """


    so = frappe.get_doc("Sales Order", source_name)


    if so.docstatus == 2:
        frappe.throw(
            "Cancelled Sales Order {0} cannot be mapped.".format(
                so.name
            )
        )

    args = args or {}

    filtered_children = args.get("filtered_children")

    link_fieldname = get_sales_order_link_fieldname()
    skipped_items = []

    def item_condition(source_doc):

        if filtered_children and source_doc.name not in filtered_children:
            return False

        # Exclude items that are already fully allocated - whether that
        # happened on this same Sales Order for another customer, or on
        # an earlier Draft Stock Entry that hasn't even been submitted yet.
        if link_fieldname:
            already_consumed = get_already_consumed_qty(
                source_name, source_doc.item_code, link_fieldname
            )

            remaining = (
                frappe.utils.flt(source_doc.custom_weight) - already_consumed
            )

            if remaining <= 0:
                if source_doc.item_code not in skipped_items:
                    skipped_items.append(source_doc.item_code)
                return False

        return True


    doc = frappe.model.mapper.get_mapped_doc(
        "Sales Order",
        source_name,
        {
            "Sales Order": {
                "doctype": "Stock Entry",

                "postprocess": set_missing_values
            },

            "Sales Order Item": {
                "doctype": "Stock Entry Detail",
                "condition": item_condition,
                "postprocess": update_item
            }
        },
        target_doc
    )

    if skipped_items:
        frappe.msgprint(
            "Skipped {0} - already fully allocated to another Stock Entry.".format(
                ", ".join(skipped_items)
            ),
            indicator="orange",
            alert=True
        )

    return doc
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

    # ------------------------------------------------------------
    # STEP 1: LOAD SALES ORDER
    # ------------------------------------------------------------

    so = frappe.get_doc("Sales Order", source_name)

    # ------------------------------------------------------------
    # STEP 2: BLOCK CANCELLED SALES ORDER
    # ------------------------------------------------------------

    if so.docstatus == 2:
        frappe.throw(
            "Cancelled Sales Order {0} cannot be mapped.".format(
                so.name
            )
        )

    # Draft (0) and Submitted (1) are allowed
    # No docstatus=1 restriction here

    # ------------------------------------------------------------
    # STEP 3: GET SELECTED SALES ORDER ITEMS
    # ------------------------------------------------------------

    args = args or {}

    filtered_children = args.get("filtered_children")

    def item_condition(source_doc):

        # If child rows are selected in the dialog,
        # map only those selected rows
        if not filtered_children:
            return True

        return source_doc.name in filtered_children

    # ------------------------------------------------------------
    # STEP 4: MAP SALES ORDER TO STOCK ENTRY
    # ------------------------------------------------------------

    doc = frappe.model.mapper.get_mapped_doc(
        "Sales Order",
        source_name,
        {
            "Sales Order": {
                "doctype": "Stock Entry",

                # IMPORTANT:
                # Removed docstatus=1 validation.
                # Draft and Submitted SOs can now be mapped.

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

    return doc
# import frappe
# from frappe.query_builder.functions import Sum


# def get_sales_order_link_fieldname():
#     """
#     Dynamically find the Stock Entry Detail field that links back to
#     Sales Order - mirrors the same lookup the client-side duplicate-fetch
#     guard already does, so this keeps working even if that field is
#     ever renamed.
#     """

#     meta = frappe.get_meta("Stock Entry Detail")

#     for df in meta.fields:
#         if df.fieldtype == "Link" and df.options == "Sales Order":
#             return df.fieldname

#     return None


# def get_already_consumed_qty(sales_order, item_code, link_fieldname):
#     """
#     Sum of custom_weight ("Qty") already pulled into any non-cancelled
#     Stock Entry (Draft or Submitted, any customer) for this Sales Order +
#     Item Code combination. This is what makes the "remaining" balance
#     correct across customers and across drafts, not just within the
#     Stock Entry currently open.
#     """

#     if not link_fieldname:
#         return 0

#     sed = frappe.qb.DocType("Stock Entry Detail")
#     link_field = getattr(sed, link_fieldname)

#     result = (
#         frappe.qb.from_(sed)
#         .select(Sum(sed.custom_weight).as_("total"))
#         .where(link_field == sales_order)
#         .where(sed.item_code == item_code)
#         .where(sed.docstatus != 2)
#         .run(as_dict=True)
#     )

#     return frappe.utils.flt(result[0].total) if result and result[0].total else 0


# def set_missing_values(source, target, *args, **kwargs):
#     """
#     Set default Stock Entry values and fetch Project Title
#     from the source Sales Order.
#     """

#     target.stock_entry_type = (
#         target.stock_entry_type or "Material Transfer"
#     )

#     # Fetch Project Title from Sales Order
#     # Only set if Stock Entry Project Title is currently empty
#     project_title = source.get("custom_project_title")

#     if project_title and not target.get("custom_project_title"):
#         target.custom_project_title = project_title


# def update_item(source_doc, target_doc, source_parent, *args, **kwargs):
#     """
#     Map Sales Order Item fields into Stock Entry Detail.
#     """

#     qty = (
#         frappe.utils.flt(source_doc.qty)
#         - frappe.utils.flt(source_doc.delivered_qty)
#     )

#     target_doc.qty = (
#         qty if qty > 0 else frappe.utils.flt(source_doc.qty)
#     )

#     target_doc.uom = source_doc.uom
#     target_doc.stock_uom = source_doc.stock_uom

#     target_doc.conversion_factor = (
#         source_doc.conversion_factor or 1
#     )

#     target_doc.basic_rate = source_doc.rate
#     target_doc.rate = source_doc.rate
#     target_doc.amount = source_doc.amount

#     target_doc.custom_customer_name = source_parent.customer

#     # Source Warehouse
#     if source_doc.warehouse:
#         target_doc.s_warehouse = source_doc.warehouse

#     # Custom fields to be fetched from Sales Order Item
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

#     # Default "Qty" (custom_weight) to the REMAINING balance instead of
#     # always copying the Sales Order Item's full original quantity -
#     # subtract whatever has already been pulled into any other Stock
#     # Entry (any customer, Draft or Submitted) for this same Sales
#     # Order + Item Code.
#     link_fieldname = get_sales_order_link_fieldname()

#     if link_fieldname:
#         already_consumed = get_already_consumed_qty(
#             source_parent.name, source_doc.item_code, link_fieldname
#         )

#         remaining = (
#             frappe.utils.flt(source_doc.custom_weight) - already_consumed
#         )

#         target_doc.custom_weight = remaining if remaining > 0 else 0

#         # Keep the link back to the Sales Order populated so future
#         # fetches - for this or any other customer - can see this
#         # quantity was already allocated here.
#         target_doc.set(link_fieldname, source_parent.name)


# @frappe.whitelist()
# def make_stock_entry_from_sales_order(
#     source_name,
#     target_doc=None,
#     args=None,
#     **kwargs
# ):
#     """
#     Map Draft or Submitted Sales Order into Stock Entry.

#     Allowed:
#         Draft SO       (docstatus = 0)
#         Submitted SO   (docstatus = 1)

#     Not Allowed:
#         Cancelled SO   (docstatus = 2)
#     """


#     so = frappe.get_doc("Sales Order", source_name)


#     if so.docstatus == 2:
#         frappe.throw(
#             "Cancelled Sales Order {0} cannot be mapped.".format(
#                 so.name
#             )
#         )

#     args = args or {}

#     filtered_children = args.get("filtered_children")

#     link_fieldname = get_sales_order_link_fieldname()
#     skipped_items = []

#     def item_condition(source_doc):

#         if filtered_children and source_doc.name not in filtered_children:
#             return False

#         # Exclude items that are already fully allocated - whether that
#         # happened on this same Sales Order for another customer, or on
#         # an earlier Draft Stock Entry that hasn't even been submitted yet.
#         if link_fieldname:
#             already_consumed = get_already_consumed_qty(
#                 source_name, source_doc.item_code, link_fieldname
#             )

#             remaining = (
#                 frappe.utils.flt(source_doc.custom_weight) - already_consumed
#             )

#             if remaining <= 0:
#                 if source_doc.item_code not in skipped_items:
#                     skipped_items.append(source_doc.item_code)
#                 return False

#         return True


#     doc = frappe.model.mapper.get_mapped_doc(
#         "Sales Order",
#         source_name,
#         {
#             "Sales Order": {
#                 "doctype": "Stock Entry",

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

#     if skipped_items:
#         frappe.msgprint(
#             "Skipped {0} - already fully allocated to another Stock Entry.".format(
#                 ", ".join(skipped_items)
#             ),
#             indicator="orange",
#             alert=True
#         )

#     return doc





# import frappe
# from frappe.query_builder.functions import Sum


# # ============================================================
# # GET SALES ORDER LINK FIELDNAME
# # ============================================================

# def get_sales_order_link_fieldname():
#     """
#     Dynamically find the Stock Entry Detail field
#     that links back to Sales Order.
#     """

#     meta = frappe.get_meta("Stock Entry Detail")

#     for df in meta.fields:
#         if df.fieldtype == "Link" and df.options == "Sales Order":
#             return df.fieldname

#     return None


# # ============================================================
# # GET ALREADY ALLOCATED QTY FOR EXACT SALES ORDER ITEM ROW
# # ============================================================

# def get_already_consumed_qty(sales_order_item):
#     """
#     Sum custom_weight already allocated against this exact
#     Sales Order Item row.

#     Count:
#         Draft + Submitted Stock Entries

#     Ignore:
#         Cancelled Stock Entries

#     IMPORTANT:
#         Allocation is based on custom_sales_order_detail,
#         NOT Item Code. Different SO Item rows with the same
#         Item Code will not consume each other's Qty.
#     """

#     if not sales_order_item:
#         return 0

#     sed = frappe.qb.DocType("Stock Entry Detail")

#     result = (
#         frappe.qb.from_(sed)
#         .select(Sum(sed.custom_weight).as_("total"))
#         .where(
#             sed.custom_sales_order_detail == sales_order_item
#         )
#         .where(sed.docstatus != 2)
#         .run(as_dict=True)
#     )

#     return (
#         frappe.utils.flt(result[0].total)
#         if result and result[0].total
#         else 0
#     )


# # ============================================================
# # SET MISSING VALUES
# # ============================================================

# def set_missing_values(source, target, *args, **kwargs):
#     """
#     Set default Stock Entry values and fetch Project Title
#     from the source Sales Order.
#     """

#     target.stock_entry_type = (
#         target.stock_entry_type or "Material Transfer"
#     )

#     project_title = source.get("custom_project_title")

#     if project_title and not target.get("custom_project_title"):
#         target.custom_project_title = project_title


# # ============================================================
# # UPDATE MAPPED STOCK ENTRY ITEM
# # ============================================================

# def update_item(source_doc, target_doc, source_parent, *args, **kwargs):
#     """
#     Map Sales Order Item fields into Stock Entry Detail.

#     Only the remaining custom_weight Qty is allocated
#     for this exact Sales Order Item row.
#     """

#     # --------------------------------------------------------
#     # STANDARD QTY LOGIC - PRESERVED
#     # --------------------------------------------------------

#     qty = (
#         frappe.utils.flt(source_doc.qty)
#         - frappe.utils.flt(source_doc.delivered_qty)
#     )

#     target_doc.qty = (
#         qty if qty > 0
#         else frappe.utils.flt(source_doc.qty)
#     )

#     target_doc.uom = source_doc.uom
#     target_doc.stock_uom = source_doc.stock_uom

#     target_doc.conversion_factor = (
#         source_doc.conversion_factor or 1
#     )

#     target_doc.basic_rate = source_doc.rate
#     target_doc.rate = source_doc.rate
#     target_doc.amount = source_doc.amount

#     target_doc.custom_customer_name = source_parent.customer

#     # --------------------------------------------------------
#     # SOURCE WAREHOUSE - PRESERVED
#     # --------------------------------------------------------

#     if source_doc.warehouse:
#         target_doc.s_warehouse = source_doc.warehouse

#     # --------------------------------------------------------
#     # CUSTOM FIELD MAPPING - PRESERVED
#     # --------------------------------------------------------

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

#     # --------------------------------------------------------
#     # SALES ORDER LINK - PRESERVED
#     # --------------------------------------------------------

#     link_fieldname = get_sales_order_link_fieldname()

#     if link_fieldname:
#         target_doc.set(link_fieldname, source_parent.name)

#     # --------------------------------------------------------
#     # EXACT SALES ORDER ITEM LINK
#     # --------------------------------------------------------

#     target_doc.custom_sales_order_detail = source_doc.name

#     # --------------------------------------------------------
#     # REMAINING CUSTOM WEIGHT QTY
#     # --------------------------------------------------------

#     already_consumed = get_already_consumed_qty(
#         source_doc.name
#     )

#     remaining = (
#         frappe.utils.flt(source_doc.custom_weight)
#         - already_consumed
#     )

#     target_doc.custom_weight = max(0, remaining)


# # ============================================================
# # MAIN SALES ORDER MAPPER
# # ============================================================

# @frappe.whitelist()
# def make_stock_entry_from_sales_order(
#     source_name,
#     target_doc=None,
#     args=None,
#     **kwargs
# ):
#     """
#     Map Draft or Submitted Sales Order into Stock Entry.

#     Allowed:
#         Draft SO       (docstatus = 0)
#         Submitted SO   (docstatus = 1)

#     Not Allowed:
#         Cancelled SO   (docstatus = 2)
#     """

#     so = frappe.get_doc("Sales Order", source_name)

#     if so.docstatus == 2:
#         frappe.throw(
#             "Cancelled Sales Order {0} cannot be mapped.".format(
#                 so.name
#             )
#         )

#     args = args or {}

#     filtered_children = args.get("filtered_children")

#     skipped_items = []

#     # --------------------------------------------------------
#     # ITEM CONDITION
#     # --------------------------------------------------------

#     def item_condition(source_doc):
#         if (
#             filtered_children
#             and source_doc.name not in filtered_children
#         ):
#             return False

#         already_consumed = get_already_consumed_qty(
#             source_doc.name
#         )

#         remaining = (
#             frappe.utils.flt(source_doc.custom_weight)
#             - already_consumed
#         )
#         if remaining <= 0:

#             if source_doc.item_code not in skipped_items:
#                 skipped_items.append(source_doc.item_code)

#             return False

#         return True

#     # --------------------------------------------------------
#     # GET MAPPED DOCUMENT - EXISTING MAPPING PRESERVED
#     # --------------------------------------------------------

#     doc = frappe.model.mapper.get_mapped_doc(
#         "Sales Order",
#         source_name,
#         {
#             "Sales Order": {
#                 "doctype": "Stock Entry",
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

#     # --------------------------------------------------------
#     # SKIPPED ITEM MESSAGE - PRESERVED
#     # --------------------------------------------------------

#     if skipped_items:
#         frappe.msgprint(
#             "Skipped {0} - already fully allocated to another Stock Entry.".format(
#                 ", ".join(skipped_items)
#             ),
#             indicator="orange",
#             alert=True
#         )

#     return doc














import json
import frappe
from frappe.query_builder.functions import Sum


def get_sales_order_link_fieldname():
    """
    Dynamically find the Stock Entry Detail field
    that links back to Sales Order.
    """

    meta = frappe.get_meta("Stock Entry Detail")

    for df in meta.fields:
        if df.fieldtype == "Link" and df.options == "Sales Order":
            return df.fieldname

    return None


def get_already_consumed_qty(sales_order_item):
    """
    Sum custom_weight already allocated against this exact
    Sales Order Item row.

    Count:
        Draft + Submitted Stock Entries

    Ignore:
        Cancelled Stock Entries
    """

    if not sales_order_item:
        return 0

    sed = frappe.qb.DocType("Stock Entry Detail")

    result = (
        frappe.qb.from_(sed)
        .select(Sum(sed.custom_weight).as_("total"))
        .where(
            sed.custom_sales_order_detail == sales_order_item
        )
        .where(sed.docstatus != 2)
        .run(as_dict=True)
    )

    return (
        frappe.utils.flt(result[0].total)
        if result and result[0].total
        else 0
    )


def get_current_doc_qty(target_doc, sales_order_item):
    """
    Get Qty already present in the current unsaved Stock Entry
    for the exact Sales Order Item.

    This is used when the user fetches the same SO item again
    WITHOUT saving the Stock Entry.
    """

    if not target_doc or not sales_order_item:
        return 0

    total_qty = 0

    items = []

    # target_doc can be a Frappe Document
    if hasattr(target_doc, "get"):
        items = target_doc.get("items") or []

    # target_doc can also be a dictionary
    elif isinstance(target_doc, dict):
        items = target_doc.get("items") or []

    for row in items:

        if isinstance(row, dict):
            row_so_item = row.get("custom_sales_order_detail")
            row_qty = row.get("qty")

        else:
            row_so_item = row.get("custom_sales_order_detail")
            row_qty = row.get("qty")

        if row_so_item == sales_order_item:
            total_qty += frappe.utils.flt(row_qty)

    return total_qty


def get_current_doc_weight(target_doc, sales_order_item):
    """
    Get custom_weight already present in the current unsaved
    Stock Entry for the exact Sales Order Item.
    """

    if not target_doc or not sales_order_item:
        return 0

    total_weight = 0

    items = []

    if hasattr(target_doc, "get"):
        items = target_doc.get("items") or []

    elif isinstance(target_doc, dict):
        items = target_doc.get("items") or []

    for row in items:

        if isinstance(row, dict):
            row_so_item = row.get("custom_sales_order_detail")
            row_weight = row.get("custom_weight")

        else:
            row_so_item = row.get("custom_sales_order_detail")
            row_weight = row.get("custom_weight")

        if row_so_item == sales_order_item:
            total_weight += frappe.utils.flt(row_weight)

    return total_weight


# ============================================================
# SET MISSING VALUES
# ============================================================

def set_missing_values(source, target, *args, **kwargs):
    """
    Set default Stock Entry values and fetch Project Title
    from the source Sales Order.
    """

    target.stock_entry_type = (
        target.stock_entry_type or "Material Transfer"
    )

    project_title = source.get("custom_project_title")

    if project_title and not target.get("custom_project_title"):
        target.custom_project_title = project_title


# ============================================================
# UPDATE MAPPED STOCK ENTRY ITEM
# ============================================================

def update_item(
    source_doc,
    target_doc,
    source_parent,
    *args,
    **kwargs
):
    """
    Map Sales Order Item fields into Stock Entry Detail.
    """

    target_doc.uom = source_doc.uom
    target_doc.stock_uom = source_doc.stock_uom

    target_doc.conversion_factor = (
        source_doc.conversion_factor or 1
    )

    target_doc.basic_rate = source_doc.rate
    target_doc.rate = source_doc.rate

    target_doc.custom_customer_name = source_parent.customer

    if source_doc.warehouse:
        target_doc.s_warehouse = source_doc.warehouse


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

    link_fieldname = get_sales_order_link_fieldname()

    if link_fieldname:
        target_doc.set(
            link_fieldname,
            source_parent.name
        )

    target_doc.custom_sales_order_detail = source_doc.name

    current_doc_qty_map = kwargs.get(
        "current_doc_qty_map",
        {}
    )

    current_doc_weight_map = kwargs.get(
        "current_doc_weight_map",
        {}
    )

    saved_qty = 0

    saved_weight = get_already_consumed_qty(
        source_doc.name
    )

    current_qty = frappe.utils.flt(
        current_doc_qty_map.get(
            source_doc.name,
            0
        )
    )

    current_weight = frappe.utils.flt(
        current_doc_weight_map.get(
            source_doc.name,
            0
        )
    )


    original_qty = (
        frappe.utils.flt(source_doc.qty)
        - frappe.utils.flt(source_doc.delivered_qty)
    )

    if original_qty < 0:
        original_qty = 0

    remaining_qty = (
        original_qty
        - saved_qty
        - current_qty
    )

    target_doc.qty = max(
        0,
        remaining_qty
    )


    original_weight = frappe.utils.flt(
        source_doc.custom_weight
    )

    remaining_weight = (
        original_weight
        - saved_weight
        - current_weight
    )

    target_doc.custom_weight = max(
        0,
        remaining_weight
    )


    target_doc.amount = (
        frappe.utils.flt(target_doc.qty)
        * frappe.utils.flt(source_doc.rate)
    )


@frappe.whitelist()
def make_stock_entry_from_sales_order(
    source_name,
    target_doc=None,
    args=None,
    **kwargs
):
    """
    Map Draft or Submitted Sales Order into Stock Entry.

    Existing functionality preserved.
    """

    so = frappe.get_doc(
        "Sales Order",
        source_name
    )

    if so.docstatus == 2:
        frappe.throw(
            "Cancelled Sales Order {0} cannot be mapped.".format(
                so.name
            )
        )


    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}

    args = args or {}

    filtered_children = args.get(
        "filtered_children"
    )

    if isinstance(filtered_children, str):

        try:
            filtered_children = json.loads(
                filtered_children
            )
        except Exception:
            filtered_children = []


    current_doc_qty_map = {}
    current_doc_weight_map = {}

    current_target = target_doc

    # target_doc can be JSON string
    if isinstance(current_target, str):

        try:
            current_target = json.loads(
                current_target
            )
        except Exception:
            current_target = None

    if current_target:

        if isinstance(current_target, dict):

            current_items = (
                current_target.get("items") or []
            )

        elif hasattr(current_target, "get"):

            current_items = (
                current_target.get("items") or []
            )

        else:
            current_items = []

        for row in current_items:

            if isinstance(row, dict):

                so_item = row.get(
                    "custom_sales_order_detail"
                )

                row_qty = frappe.utils.flt(
                    row.get("qty")
                )

                row_weight = frappe.utils.flt(
                    row.get("custom_weight")
                )

            else:

                so_item = row.get(
                    "custom_sales_order_detail"
                )

                row_qty = frappe.utils.flt(
                    row.get("qty")
                )

                row_weight = frappe.utils.flt(
                    row.get("custom_weight")
                )

            if so_item:

                current_doc_qty_map[so_item] = (
                    current_doc_qty_map.get(
                        so_item,
                        0
                    )
                    + row_qty
                )

                current_doc_weight_map[so_item] = (
                    current_doc_weight_map.get(
                        so_item,
                        0
                    )
                    + row_weight
                )


    skipped_items = []


    def item_condition(source_doc):

        # ----------------------------------------------------
        # PRESERVE CHILD SELECTION
        # ----------------------------------------------------

        if (
            filtered_children
            and source_doc.name not in filtered_children
        ):
            return False

        # ----------------------------------------------------
        # SAVED CUSTOM WEIGHT
        # ----------------------------------------------------

        saved_weight = get_already_consumed_qty(
            source_doc.name
        )

        # ----------------------------------------------------
        # CURRENT UNSAVED CUSTOM WEIGHT
        # ----------------------------------------------------

        current_weight = frappe.utils.flt(
            current_doc_weight_map.get(
                source_doc.name,
                0
            )
        )

        # ----------------------------------------------------
        # REMAINING CUSTOM WEIGHT
        # ----------------------------------------------------

        remaining_weight = (
            frappe.utils.flt(
                source_doc.custom_weight
            )
            - saved_weight
            - current_weight
        )

        # ----------------------------------------------------
        # STANDARD QTY
        # ----------------------------------------------------

        original_qty = (
            frappe.utils.flt(source_doc.qty)
            - frappe.utils.flt(
                source_doc.delivered_qty
            )
        )

        if original_qty < 0:
            original_qty = 0

        current_qty = frappe.utils.flt(
            current_doc_qty_map.get(
                source_doc.name,
                0
            )
        )

        # ----------------------------------------------------
        # CHECK BOTH
        # ----------------------------------------------------

        remaining_qty = (
            original_qty
            - current_qty
        )

        if (
            remaining_qty <= 0
            and remaining_weight <= 0
        ):

            if (
                source_doc.item_code
                not in skipped_items
            ):
                skipped_items.append(
                    source_doc.item_code
                )

            return False

        return True

    # ========================================================
    # GET MAPPED DOCUMENT
    # ========================================================

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
                "postprocess": lambda source, target, parent, *a, **k:
                    update_item(
                        source,
                        target,
                        parent,
                        current_doc_qty_map=current_doc_qty_map,
                        current_doc_weight_map=current_doc_weight_map
                    )
            }
        },
        target_doc
    )

    # ========================================================
    # SKIPPED ITEM MESSAGE
    # ========================================================

    if skipped_items:

        frappe.msgprint(
            "Skipped {0} - already fully allocated to another Stock Entry.".format(
                ", ".join(skipped_items)
            ),
            indicator="orange",
            alert=True
        )

    return doc
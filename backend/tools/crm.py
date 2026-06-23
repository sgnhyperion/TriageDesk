"""CRM lookup tools. Owner: Member B. Back these with the Supabase tables."""
from contracts.schemas import SupportState, ToolName, ToolResult


def lookup_customer(args: dict, state: SupportState) -> ToolResult:
    """TODO(Member B): query `customers` by state.customer_id / args['customer_id']."""
    return ToolResult(tool=ToolName.LOOKUP_CUSTOMER, ok=True,
                      output={"stub": True, "customer_id": state.customer_id})


def lookup_order(args: dict, state: SupportState) -> ToolResult:
    """TODO(Member B): query `orders`; detect duplicate charges, refundable amounts."""
    return ToolResult(tool=ToolName.LOOKUP_ORDER, ok=True,
                      output={"stub": True, "duplicate_charge": False})


def check_subscription_status(args: dict, state: SupportState) -> ToolResult:
    """TODO(Member B): query `subscriptions` for plan/status/renewal."""
    return ToolResult(tool=ToolName.CHECK_SUBSCRIPTION_STATUS, ok=True,
                      output={"stub": True, "status": "active"})

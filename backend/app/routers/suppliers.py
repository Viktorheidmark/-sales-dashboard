from fastapi import APIRouter
from app.schemas.dashboard import SuppliersResponse, SupplierItem
from app.services import analytics

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("", response_model=SuppliersResponse)
def list_suppliers():
    """Return all available demo suppliers with id and name."""
    rows = analytics.get_supplier_list()
    return SuppliersResponse(suppliers=[SupplierItem(**r) for r in rows])

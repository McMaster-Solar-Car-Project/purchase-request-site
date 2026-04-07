from pydantic import BaseModel


class ReceiptItem(BaseModel):
    name: str
    quantity: float
    unit_price: float
    total_price: float


class ReceiptSummary(BaseModel):
    number_of_items: int
    subtotal: float
    discount: float
    delivery_fee: float
    service_fee: float
    tax: float
    tip: float
    total: float


class ReceiptData(BaseModel):
    store: str
    order_number: str | None = None
    date: str | None = None
    currency: str
    items: list[ReceiptItem]
    summary: ReceiptSummary

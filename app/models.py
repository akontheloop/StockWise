from datetime import datetime
from app import db


class Business(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150), nullable=False)
    business_type = db.Column(db.String(50), default="retail")
    currency = db.Column(db.String(10), default="INR")

    low_stock_threshold = db.Column(db.Integer, default=10)
    expiry_tracking = db.Column(db.Boolean, default=False)
    variant_tracking = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship(
        "Product",
        backref="business",
        lazy=True
    )


class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False
    )

    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150))
    phone = db.Column(db.String(50))
    lead_time_days = db.Column(db.Integer, default=7)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False
    )

    supplier_id = db.Column(
        db.Integer,
        db.ForeignKey("supplier.id"),
        nullable=True
    )

    name = db.Column(db.String(150), nullable=False)
    sku = db.Column(db.String(100))
    category = db.Column(db.String(100))
    description = db.Column(db.Text)

    price = db.Column(db.Float, default=0)
    cost_price = db.Column(db.Float, default=0)

    quantity = db.Column(db.Integer, default=0)
    reorder_level = db.Column(db.Integer, default=10)

    variant = db.Column(db.String(100))
    expiry_date = db.Column(db.Date)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StockMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    product = db.relationship("Product")
    movement_type = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(250))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

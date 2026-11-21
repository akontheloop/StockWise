from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash

from datetime import datetime
import csv
import io

from app.models import Product, Business, StockMovement, Supplier
from app import db
main = Blueprint("main", __name__)


def get_business():
    return Business.query.first()


@main.route("/")
def dashboard():
    business = get_business()

    if not business:
        return redirect(url_for("main.setup"))

    products = Product.query.filter_by(
        business_id=business.id
    ).all()

    total_products = len(products)
    total_stock = sum(p.quantity for p in products)

    inventory_value = sum(
        p.quantity * p.cost_price for p in products
    )

    low_stock = [
        p for p in products
        if p.quantity <= p.reorder_level
    ]

    out_of_stock = [
        p for p in products
        if p.quantity == 0
    ]

    return render_template(
        "dashboard.html",
        business=business,
        total_products=total_products,
        total_stock=total_stock,
        inventory_value=inventory_value,
        low_stock=low_stock,
        out_of_stock=out_of_stock,
        products=products
    )

@main.route("/inventory/import", methods=["GET", "POST"])
def import_inventory():
    business = get_business()

    if not business:
        return redirect(url_for("main.setup"))

    if request.method == "POST":
        file = request.files.get("file")

        if not file or not file.filename:
            flash("Please select a CSV file.", "error")
            return redirect(url_for("main.import_inventory"))

        if not file.filename.lower().endswith(".csv"):
            flash("Please upload a CSV file.", "error")
            return redirect(url_for("main.import_inventory"))

        try:
            content = file.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(content))

            if not reader.fieldnames:
                flash("The CSV file is empty.", "error")
                return redirect(url_for("main.import_inventory"))

            headers = {
                h.strip().lower(): h
                for h in reader.fieldnames
                if h
            }

            if "name" not in headers:
                flash("CSV must contain a 'name' column.", "error")
                return redirect(url_for("main.import_inventory"))

            imported = 0
            skipped = 0

            for row in reader:
                name = (row.get(headers["name"]) or "").strip()

                if not name:
                    skipped += 1
                    continue

                def get_value(column, default=""):
                    original = headers.get(column)
                    return (row.get(original) or default).strip() if original else default

                sku = get_value("sku")

                if sku:
                    existing = Product.query.filter_by(
                        business_id=business.id,
                        sku=sku
                    ).first()

                    if existing:
                        skipped += 1
                        continue

                try:
                    quantity = int(get_value("quantity", "0"))
                    price = float(get_value("price", "0"))
                    cost_price = float(get_value("cost_price", "0"))
                    reorder_level = int(
                        get_value(
                            "reorder_level",
                            str(business.low_stock_threshold)
                        )
                    )

                    if quantity < 0 or price < 0 or cost_price < 0:
                        skipped += 1
                        continue

                    expiry_date = None
                    expiry_value = get_value("expiry_date")

                    if expiry_value:
                        expiry_date = datetime.strptime(
                            expiry_value, "%Y-%m-%d"
                        ).date()

                except (ValueError, TypeError):
                    skipped += 1
                    continue

                product = Product(
                    business_id=business.id,
                    name=name,
                    sku=sku or None,
                    category=get_value("category") or None,
                    description=get_value("description") or None,
                    price=price,
                    cost_price=cost_price,
                    quantity=quantity,
                    reorder_level=reorder_level,
                    variant=get_value("variant") or None,
                    expiry_date=expiry_date
                )

                db.session.add(product)
                imported += 1

            db.session.commit()

            flash(
                f"Import complete: {imported} products imported, "
                f"{skipped} rows skipped.",
                "success"
            )

            return redirect(url_for("main.inventory"))

        except Exception as e:
            db.session.rollback()
            flash(f"Import failed: {str(e)}", "error")
            return redirect(url_for("main.import_inventory"))

    return render_template("import_inventory.html", business=business)
@main.route("/search")
def global_search():
    business = get_business()

    if not business:
        return redirect(url_for("main.setup"))

    query = request.args.get("q", "").strip()

    products = []
    suppliers = []

    if query:
        products = Product.query.filter(
            Product.business_id == business.id,
            db.or_(
                Product.name.ilike(f"%{query}%"),
                Product.sku.ilike(f"%{query}%"),
                Product.category.ilike(f"%{query}%")
            )
        ).all()

        suppliers = Supplier.query.filter(
            Supplier.business_id == business.id,
            Supplier.name.ilike(f"%{query}%")
        ).all()

    return render_template(
        "search_results.html",
        business=business,
        query=query,
        products=products,
        suppliers=suppliers
    )

@main.route("/setup", methods=["GET", "POST"])
def setup():
    business = get_business()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        business_type = request.form.get("business_type")
        currency = request.form.get("currency")
        low_stock_threshold = request.form.get(
            "low_stock_threshold", 10
        )

        if not name:
            flash("Business name is required.", "error")
            return redirect(url_for("main.setup"))

        if business:
            business.name = name
            business.business_type = business_type
            business.currency = currency
            business.low_stock_threshold = int(
                low_stock_threshold
            )
            business.expiry_tracking = (
                "expiry_tracking" in request.form
            )
            business.variant_tracking = (
                "variant_tracking" in request.form
            )
        else:
            business = Business(
                name=name,
                business_type=business_type,
                currency=currency,
                low_stock_threshold=int(
                    low_stock_threshold
                ),
                expiry_tracking=(
                    "expiry_tracking" in request.form
                ),
                variant_tracking=(
                    "variant_tracking" in request.form
                )
            )
            db.session.add(business)

        db.session.commit()

        return redirect(url_for("main.dashboard"))

    return render_template(
        "setup.html",
        business=business
    )


@main.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "application": "StockWise",
        "timestamp": datetime.utcnow().isoformat()
    }), 200


@main.route("/api/status")
def status():
    return jsonify({
        "application": "StockWise",
        "version": "1.0.0",
        "status": "running"
    })
@main.route("/products/add", methods=["GET", "POST"])
def add_product():
    business = Business.query.first()

    if not business:
        return redirect(url_for("main.setup"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sku = request.form.get("sku", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", 0)
        cost_price = request.form.get("cost_price", 0)
        quantity = request.form.get("quantity", 0)
        reorder_level = request.form.get("reorder_level", 5)
        variant = request.form.get("variant", "").strip()

        if not name:
            flash("Product name is required.", "error")
            return redirect(url_for("main.add_product"))

        product = Product(
            business_id=business.id,
            name=name,
            sku=sku or None,
            category=category or None,
            description=description or None,
            price=float(price or 0),
            cost_price=float(cost_price or 0),
            quantity=int(quantity or 0),
            reorder_level=int(reorder_level or 5),
            variant=variant or None
        )

        db.session.add(product)
        db.session.commit()

        flash(f"{name} added successfully!", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("add_product.html", business=business)
@main.route("/inventory")
def inventory():
    business = get_business()

    if not business:
        return redirect(url_for("main.setup"))

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "")
    category_filter = request.args.get("category", "")

    query = Product.query.filter_by(business_id=business.id)

    if search:
        query = query.filter(
            db.or_(
                Product.name.ilike(f"%{search}%"),
                Product.sku.ilike(f"%{search}%"),
                Product.category.ilike(f"%{search}%")
            )
        )

    if category_filter:
        query = query.filter_by(category=category_filter)

    products = query.order_by(Product.created_at.desc()).all()

    if status_filter == "out":
        products = [p for p in products if p.quantity <= 0]

    elif status_filter == "low":
        products = [
            p for p in products
            if 0 < p.quantity <= p.reorder_level
        ]

    elif status_filter == "healthy":
        products = [
            p for p in products
            if p.quantity > p.reorder_level
        ]

    all_products = Product.query.filter_by(
        business_id=business.id
    ).all()

    categories = sorted(set(
        p.category for p in all_products
        if p.category
    ))

    total_products = len(all_products)

    total_units = sum(p.quantity for p in all_products)

    inventory_value = sum(
        p.quantity * p.cost_price for p in all_products
    )

    low_stock_count = sum(
        1 for p in all_products
        if 0 < p.quantity <= p.reorder_level
    )

    out_of_stock_count = sum(
        1 for p in all_products
        if p.quantity <= 0
    )

    return render_template(
        "inventory.html",
        business=business,
        products=products,
        categories=categories,
        search=search,
        status_filter=status_filter,
        category_filter=category_filter,
        total_products=total_products,
        total_units=total_units,
        inventory_value=inventory_value,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count
    )


@main.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    business = get_business()

    if not business:
        return redirect(url_for("main.setup"))

    product = Product.query.filter_by(
        id=product_id,
        business_id=business.id
    ).first_or_404()

    if request.method == "POST":
        product.name = request.form.get("name", "").strip()
        product.sku = request.form.get("sku", "").strip() or None
        product.category = request.form.get("category", "").strip() or None
        product.description = request.form.get("description", "").strip() or None
        product.price = float(request.form.get("price") or 0)
        product.cost_price = float(request.form.get("cost_price") or 0)
        product.quantity = int(request.form.get("quantity") or 0)
        product.reorder_level = int(request.form.get("reorder_level") or 5)
        product.variant = request.form.get("variant", "").strip() or None

        db.session.commit()

        flash("Product updated successfully!", "success")
        return redirect(url_for("main.inventory"))

    return render_template(
        "edit_product.html",
        product=product,
        business=business
    )


@main.route("/products/<int:product_id>/delete", methods=["POST"])
def delete_product(product_id):
    business = get_business()

    if not business:
        return redirect(url_for("main.setup"))

    product = Product.query.filter_by(
        id=product_id,
        business_id=business.id
    ).first_or_404()

    name = product.name

    db.session.delete(product)
    db.session.commit()

    flash(f"{name} deleted successfully.", "success")
    return redirect(url_for("main.inventory"))


@main.route("/movements", methods=["GET", "POST"])
def movements():

    business = get_business()

    if not business:
        return redirect(url_for("main.setup"))

    products = Product.query.filter_by(
        business_id=business.id
    ).all()

    if request.method == "POST":

        product_id = request.form.get("product_id")
        movement_type = request.form.get("movement_type")
        quantity = int(request.form.get("quantity", 0))
        note = request.form.get("note", "").strip()

        product = Product.query.filter_by(
            id=product_id,
            business_id=business.id
        ).first()

        if not product or quantity <= 0:
            flash("Invalid product or quantity.", "error")
            return redirect(url_for("main.movements"))

        if movement_type == "OUT" and quantity > product.quantity:
            flash("Not enough stock available.", "error")
            return redirect(url_for("main.movements"))

        if movement_type == "IN":
            product.quantity += quantity

        elif movement_type == "OUT":
            product.quantity -= quantity

        else:
            flash("Invalid movement type.", "error")
            return redirect(url_for("main.movements"))

        movement = StockMovement(
            business_id=business.id,
            product_id=product.id,
            movement_type=movement_type,
            quantity=quantity,
            note=note or None
        )

        db.session.add(movement)
        db.session.commit()

        flash("Stock movement recorded successfully!", "success")

        return redirect(url_for("main.movements"))

    movements_list = StockMovement.query.filter_by(
        business_id=business.id
    ).order_by(
        StockMovement.created_at.desc()
    ).all()

    return render_template(
        "movements.html",
        business=business,
        products=products,
        movements=movements_list
    )


@main.route("/suppliers", methods=["GET", "POST"])
def suppliers():
    business = get_business()

    if not business:
        return redirect(url_for("main.setup"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()

        if not name:
            flash("Supplier name is required.", "error")
            return redirect(url_for("main.suppliers"))

        supplier = Supplier(
            business_id=business.id,
            name=name,
            email=request.form.get("email", "").strip() or None,
            phone=request.form.get("phone", "").strip() or None,
            lead_time_days=int(request.form.get("lead_time_days") or 7)
        )

        db.session.add(supplier)
        db.session.commit()

        flash("Supplier added successfully!", "success")
        return redirect(url_for("main.suppliers"))

    suppliers_list = Supplier.query.filter_by(
        business_id=business.id
    ).order_by(Supplier.name.asc()).all()

    return render_template(
        "suppliers.html",
        business=business,
        suppliers=suppliers_list
    )


@main.route("/suppliers/<int:supplier_id>/edit", methods=["GET", "POST"])
def edit_supplier(supplier_id):
    business = get_business()

    if not business:
        return redirect(url_for("main.setup"))

    supplier = Supplier.query.filter_by(
        id=supplier_id,
        business_id=business.id
    ).first_or_404()

    if request.method == "POST":
        supplier.name = request.form.get("name", "").strip()
        supplier.email = request.form.get("email", "").strip() or None
        supplier.phone = request.form.get("phone", "").strip() or None
        supplier.lead_time_days = int(
            request.form.get("lead_time_days") or 7
        )

        db.session.commit()

        flash("Supplier updated successfully!", "success")
        return redirect(url_for("main.suppliers"))

    return render_template(
        "edit_supplier.html",
        supplier=supplier,
        business=business
    )


@main.route("/suppliers/<int:supplier_id>/delete", methods=["POST"])
def delete_supplier(supplier_id):
    business = get_business()

    if not business:
        return redirect(url_for("main.setup"))

    supplier = Supplier.query.filter_by(
        id=supplier_id,
        business_id=business.id
    ).first_or_404()

    # Remove supplier association from products before deletion
    Product.query.filter_by(
        supplier_id=supplier.id,
        business_id=business.id
    ).update({"supplier_id": None})

    db.session.delete(supplier)
    db.session.commit()

    flash("Supplier deleted successfully!", "success")
    return redirect(url_for("main.suppliers"))


@main.route("/intelligence")
def intelligence():
    business = get_business()

    if not business:
        return redirect(url_for("main.setup"))

    products = Product.query.filter_by(
        business_id=business.id
    ).all()

    total_products = len(products)

    total_units = sum(p.quantity for p in products)

    inventory_cost = sum(
        p.quantity * (p.cost_price or 0)
        for p in products
    )

    retail_value = sum(
        p.quantity * (p.price or 0)
        for p in products
    )

    potential_profit = retail_value - inventory_cost

    low_stock = [
        p for p in products
        if 0 < p.quantity <= p.reorder_level
    ]

    out_of_stock = [
        p for p in products
        if p.quantity <= 0
    ]

    healthy_stock = [
        p for p in products
        if p.quantity > p.reorder_level
    ]

    categories = {}

    for product in products:
        category = product.category or "Uncategorized"

        if category not in categories:
            categories[category] = {
                "products": 0,
                "units": 0,
                "value": 0
            }

        categories[category]["products"] += 1
        categories[category]["units"] += product.quantity
        categories[category]["value"] += (
            product.quantity * (product.cost_price or 0)
        )

    category_list = sorted(
        categories.items(),
        key=lambda x: x[1]["value"],
        reverse=True
    )

    top_products = sorted(
        products,
        key=lambda p: p.quantity * (p.cost_price or 0),
        reverse=True
    )[:5]

    stock_health = (
        round((len(healthy_stock) / total_products) * 100)
        if total_products else 0
    )

    return render_template(
        "intelligence.html",
        business=business,
        products=products,
        total_products=total_products,
        total_units=total_units,
        inventory_cost=inventory_cost,
        retail_value=retail_value,
        potential_profit=potential_profit,
        low_stock=low_stock,
        out_of_stock=out_of_stock,
        healthy_stock=healthy_stock,
        categories=category_list,
        top_products=top_products,
        stock_health=stock_health
    )


@main.route("/alerts")
def alerts():
    business = get_business()

    if not business:
        return redirect(url_for("main.setup"))

    from datetime import date, timedelta

    products = Product.query.filter_by(
        business_id=business.id
    ).all()

    today = date.today()
    expiry_window = today + timedelta(days=30)

    alert_list = []

    for product in products:

        # Out of stock
        if product.quantity <= 0:
            alert_list.append({
                "type": "out_of_stock",
                "severity": "critical",
                "title": "Out of stock",
                "product": product,
                "message": "This product has no available inventory.",
                "recommended_quantity": max(product.reorder_level, 1)
            })

        # Low stock
        elif product.quantity <= product.reorder_level:
            alert_list.append({
                "type": "low_stock",
                "severity": "warning",
                "title": "Low stock",
                "product": product,
                "message": "Inventory is at or below the reorder threshold.",
                "recommended_quantity": product.reorder_level - product.quantity
            })

        # Expiry alerts
        if business.expiry_tracking and product.expiry_date:

            if product.expiry_date < today:
                alert_list.append({
                    "type": "expired",
                    "severity": "critical",
                    "title": "Expired product",
                    "product": product,
                    "message": "This product has passed its expiry date.",
                    "recommended_quantity": 0
                })

            elif product.expiry_date <= expiry_window:
                alert_list.append({
                    "type": "expiry",
                    "severity": "warning",
                    "title": "Expiring soon",
                    "product": product,
                    "message": "This product expires within the next 30 days.",
                    "recommended_quantity": 0
                })

    critical_count = sum(
        1 for alert in alert_list
        if alert["severity"] == "critical"
    )

    warning_count = sum(
        1 for alert in alert_list
        if alert["severity"] == "warning"
    )

    return render_template(
        "alerts.html",
        business=business,
        alerts=alert_list,
        critical_count=critical_count,
        warning_count=warning_count,
        total_alerts=len(alert_list)
    )


@main.route("/settings", methods=["GET", "POST"])
def settings():
    business = get_business()

    if not business:
        return redirect(url_for("main.setup"))

    if request.method == "POST":

        business.name = request.form.get("name", "").strip()
        business.business_type = request.form.get("business_type", "retail")
        business.currency = request.form.get("currency", "INR")

        business.low_stock_threshold = int(
            request.form.get("low_stock_threshold") or 10
        )

        business.expiry_tracking = (
            request.form.get("expiry_tracking") == "on"
        )

        business.variant_tracking = (
            request.form.get("variant_tracking") == "on"
        )

        db.session.commit()

        flash("Business settings updated successfully!", "success")

        return redirect(url_for("main.settings"))

    return render_template(
        "settings.html",
        business=business
    )

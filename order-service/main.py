import mimetypes
import os
import json
import httpx
import threading
import pika
import time
import datetime
from fastapi import FastAPI, Request, HTTPException, status, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List, Dict, Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

# Prevent browsers from loading JavaScript/CSS files as unstyled plain text
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/javascript', '.js')

app = FastAPI(title="Order Microservice")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# =====================================================================
# 🗄️ POSTGRESQL RELATIONAL ENGINE CONFIGURATION
# =====================================================================
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@postgres_db:5432/orders_db")

# echo=True prints all running SQL queries to your terminal console for easy debugging
engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class DBOrder(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="Bulk Order Placed Successfully")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    items = relationship("DBOrderItem", back_populates="order", cascade="all, delete-orphan")


class DBOrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    order = relationship("DBOrder", back_populates="items")


# Automatically generate database tables if they do not exist on launch
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# In-memory synchronized maps mirroring data pulled from your product microservice
LOCAL_PRODUCT_DATABASE: Dict[int, dict] = {}
LOCAL_INVENTORY_CACHE: Dict[int, bool] = {}


@app.post("/orders/sync-inventory/")
async def sync_inventory():
    try:
        async with httpx.AsyncClient() as client:
            # Connect to your product service to grab database rows
            response = await client.get("http://product-service:8001/debug/db-entries", timeout=3.0)

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch product catalog")

        catalog = response.json()
        records = catalog.get("records", [])

        LOCAL_PRODUCT_DATABASE.clear()
        LOCAL_INVENTORY_CACHE.clear()

        for item in records:
            p_id = int(item["id"])
            LOCAL_PRODUCT_DATABASE[p_id] = item
            LOCAL_INVENTORY_CACHE[p_id] = item.get("in_stock", True)

        return {"status": "Sync complete", "synced_products_count": len(records)}
    except Exception as e:
        # Fallback Seed Injector: If product-service container is completely offline or blank,
        # we populate the local map so your layout still works during localized frontend R&D
        print(f"⚠️ product-service database fetch failed ({str(e)}). Applying local layout seed fallbacks.")
        fallback_seeds = [
            {"id": 101, "layer_id": 1, "name": "Compute Server Unit Node", "price": 15.00, "in_stock": True},
            {"id": 102, "layer_id": 1, "name": "Distributed Micro-Cluster Node", "price": 45.00, "in_stock": True},
            {"id": 201, "layer_id": 2, "name": "Managed HA Database Instance", "price": 30.00, "in_stock": True},
            {"id": 202, "layer_id": 2, "name": "Redis In-Memory Cache Store", "price": 12.50, "in_stock": True},
            {"id": 301, "layer_id": 3, "name": "Web Application Firewall (WAF)", "price": 25.00, "in_stock": True},
            {"id": 401, "layer_id": 4, "name": "Prometheus Central Metric Node", "price": 18.00, "in_stock": True}
        ]
        for item in fallback_seeds:
            p_id = item["id"]
            LOCAL_PRODUCT_DATABASE[p_id] = item
            LOCAL_INVENTORY_CACHE[p_id] = item["in_stock"]
        return {"status": "Fallback Sync Complete", "synced_products_count": len(fallback_seeds)}


@app.get("/api/products")
async def get_db_products(layer_id: Optional[int] = None):
    """
    Exposes database objects filtered by active layout layers directly to script.js
    """
    response_items = []
    for p_id, product in LOCAL_PRODUCT_DATABASE.items():
        item_layer = product.get("layer_id")
        if item_layer is None:
            if 100 <= p_id < 200 or p_id == 1:
                item_layer = 1
            elif 200 <= p_id < 300 or p_id == 2:
                item_layer = 2
            elif 300 <= p_id < 400 or p_id == 3:
                item_layer = 3
            else:
                item_layer = 4

        in_stock = LOCAL_INVENTORY_CACHE.get(p_id, product.get("in_stock", True))

        if layer_id is None or int(item_layer) == int(layer_id):
            response_items.append({
                "id": p_id,
                "name": product.get("name", f"Resource Object {p_id}"),
                "price": float(product.get("price", 0.00)),
                "in_stock": in_stock
            })
    return response_items


class CartItem(BaseModel):
    product_id: int
    quantity: int


class OrderCreate(BaseModel):
    items: List[CartItem]


@app.post("/orders/", status_code=201)
def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    if not order.items:
        raise HTTPException(status_code=400, detail="Cart cannot be empty for checkout validation.")

    # 1. Enforce validation boundaries against stock caches
    for item in order.items:
        in_stock = LOCAL_INVENTORY_CACHE.get(item.product_id, False)
        if not in_stock:
            raise HTTPException(
                status_code=400,
                detail=f"Checkout failed: Product #{item.product_id} is unavailable or out of stock."
            )

    try:
        # 2. Write Order entry header into PostgreSQL
        new_order = DBOrder()
        db.add(new_order)
        db.flush()  # Populates relational index serial primary key id instantly

        # 3. Add transactional child records mapped to our relational order
        for item in order.items:
            order_item = DBOrderItem(
                order_id=new_order.id,
                product_id=item.product_id,
                quantity=item.quantity
            )
            db.add(order_item)

        db.commit()
        db.refresh(new_order)
        return {
            "status": "Order saved to PostgreSQL relational store",
            "order_id": new_order.id,
            "processed_items_count": len(order.items)
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database persistent log save failure: {str(e)}")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# Background RabbitMQ consumer listening for system-wide creation events
def start_rabbitmq_consumer():
    def callback(ch, method, properties, body):
        try:
            payload = json.loads(body)
            if payload.get("event") == "PRODUCT_CREATED":
                data = payload.get("data", {})
                p_id = int(data["id"])
                LOCAL_PRODUCT_DATABASE[p_id] = data
                LOCAL_INVENTORY_CACHE[p_id] = data.get("in_stock", True)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            print(f"Broker parsing error: {e}")

    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
            channel = connection.channel()
            channel.queue_declare(queue='inventory_events', durable=True)
            channel.basic_consume(queue='inventory_events', on_message_callback=callback)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            time.sleep(2)


threading.Thread(target=start_rabbitmq_consumer, daemon=True).start()

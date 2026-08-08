import time
import json
import pika
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# 1. Database Setup (Points to the postgres container defined in docker-compose)
DATABASE_URL = "postgresql://user:password@db:5432/microservices_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# This loop forces the service to wait for the database engine to wake up
for attempt in range(10):
    try:
        # Try to establish a dummy connection
        with engine.connect() as connection:
            print("Successfully connected to the database!")
            break
    except OperationalError:
        print(f"Database not ready yet (attempt {attempt + 1}/10). Retrying in 2 seconds...")
        time.sleep(2)
else:
    raise RuntimeError("Could not connect to the database after multiple attempts.")
# --- REPLACEMENT END ---

class ProductModel(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    price = Column(Float)
    in_stock = Column(Boolean, default=True)


Base.metadata.create_all(bind=engine)


# 2. RabbitMQ Event Publisher Utility
def publish_event(event_type: str, data: dict):
    try:
        # Connects to the rabbitmq container defined in docker-compose
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
        channel = connection.channel()
        channel.queue_declare(queue='inventory_events', durable=True)

        payload = {"event": event_type, "data": data}
        channel.basic_publish(
            exchange='',
            routing_key='inventory_events',
            body=json.dumps(payload),
            properties=pika.BasicProperties(delivery_mode=2)  # Persistent message
        )
        connection.close()
    except Exception as e:
        print(f"Failed to publish event to RabbitMQ: {e}")


# 3. FastAPI Application
app = FastAPI(title="Product Microservice")

# --- CORS CONFIGURATION BLOCK TO PRODUCT SERVICE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permits cross-origin resource extraction straight to your Web UI
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProductCreate(BaseModel):
    name: str
    price: float
    in_stock: bool


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/products/", status_code=201)
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    db_product = ProductModel(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    # Broadcast event asynchronously to other services via message broker
    product_data = {"id": db_product.id, "name": db_product.name, "in_stock": db_product.in_stock}
    publish_event("PRODUCT_CREATED", product_data)

    return db_product


@app.get("/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    db_product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product

@app.get("/debug/db-entries")
def dump_database_entries(db: Session = Depends(get_db)):
    # This queries the PostgreSQL database for all products
    results = db.query(ProductModel).all()
    # It must return a dictionary with the key "records"
    return {"total_records": len(results), "records": results}

from sqlalchemy import Column, Integer, String
from .database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    required_features = Column(String)  # 필수 특징
    optional_features = Column(String)  # 보조 특징

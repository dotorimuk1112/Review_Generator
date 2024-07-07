from pydantic import BaseModel

class ProductBase(BaseModel):
    name: str
    required_features: str
    optional_features: str

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: int

    class Config:
        from_attributes = True

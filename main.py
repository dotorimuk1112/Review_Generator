import csv
import random
from fastapi import FastAPI, HTTPException, Depends, Request, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List
import os
import getpass
from langchain_google_genai import ChatGoogleGenerativeAI
from io import StringIO

from app import crud, models, schemas
from app.database import SessionLocal, engine, get_db

# FastAPI 애플리케이션 생성
app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 모델 생성
models.Base.metadata.create_all(bind=engine)

# Google API 키 설정
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = getpass.getpass("Provide your Google API Key")

# Google Gemini 모델 설정
llm = ChatGoogleGenerativeAI(model="gemini-pro")

# 정적 파일 서비스 설정
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Jinja2 템플릿 설정
templates = Jinja2Templates(directory="app/templates")

# 루트 경로 정의
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/products/", response_model=schemas.Product)
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    db_product = crud.get_product_by_name(db, name=product.name)
    if db_product:
        raise HTTPException(status_code=400, detail="Product with this name already exists")
    return crud.create_product(db=db, product=product)

@app.get("/products/", response_model=List[schemas.Product])
def read_products(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    products = crud.get_products(db, skip=skip, limit=limit)
    return products

@app.get("/products/view", response_class=HTMLResponse)
async def view_products(
    request: Request,
    db: Session = Depends(get_db),
    skip: int = Query(0, alias="page", ge=0),
    limit: int = Query(10, ge=1)
):
    products = crud.get_products(db, skip=skip * limit, limit=limit)
    total_count = db.query(models.Product).count()

    return templates.TemplateResponse("view_products.html", {
        "request": request,
        "products": products,
        "total_count": total_count,
        "skip": skip,
        "limit": limit
    })

@app.get("/reviews", response_class=HTMLResponse)
def get_reviews_page(request: Request):
    return templates.TemplateResponse("review.html", {"request": request})

@app.post("/reviews/download", response_class=StreamingResponse)
async def create_reviews_and_download(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    product_id = int(data.get("product_id"))
    review_count = int(data.get("review_count"))
    min_number_of_sentence = int(data.get("min_number_of_sentence"))
    max_number_of_sentence = int(data.get("max_number_of_sentence"))
    way_of_speaking = data.get("way_of_speaking")
    exception_words = data.get("exception_words")


    product = crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    required_features = product.required_features.split('\n')
    required_features = [feature.strip() for feature in required_features if feature.strip()]
    
    optional_features = product.optional_features.split('\n')
    optional_features = [feature.strip() for feature in optional_features if feature.strip()]
    product_name = product.name

    reviews = []
    for _ in range(review_count):
        selected_optional_features = random.sample(optional_features, min(1, len(optional_features)))
        selected_description = ". ".join(required_features + selected_optional_features)

        prompt = f"""다음 제품에 대한 상세하고 독특한 리뷰를 생성해 주세요:\n\n
                     이 제품은 {product_name}입니다.
                     제품 설명: "{selected_description}"를 기반으로 리뷰를 생성해주세요.\n\n
                     리뷰는 최소 {min_number_of_sentence}문장에서 최대 {max_number_of_sentence}문장이어야 합니다.\n\n
                     리뷰는 최대한 사람이 작성한 것처럼 생생하고 자연스러워야 합니다.\n
                     리뷰는 한국어로 작성해 주세요.
                  """

        if way_of_speaking:
            prompt += f"말투는 {way_of_speaking} 말투로 작성해주세요.\n"

        if exception_words:
            prompt += f"{exception_words} 이 단어들은 리뷰에 포함되지 않아야만 합니다."

        response = llm.invoke(prompt)
        print(response)
        review = response.content.strip()

        if review:
            reviews.append(review)

    # CSV 생성
    def generate_csv():
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['번호', '리뷰 내용'])

        for i, review in enumerate(reviews, 1):
            writer.writerow([i, review])

        output.seek(0)
        yield output.read()

    return StreamingResponse(generate_csv(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=reviews.csv"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

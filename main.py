# main.py
from datetime import timedelta
from typing import List
import math
import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import google.generativeai as genai
from config import API_KEY_GEMINI
from dotenv import load_dotenv
import os

from auth import (
    get_db,
    get_current_active_user,
    authenticate_user,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_password_hash,
    get_user_by_username,
    get_user_by_email,
    create_email_verification_token,
    decode_email_verification_token,
)
from email_utils import send_verification_email
from database import Base, engine
from finance import (
    fetch_price_history,
    fetch_fundamentals,
    compute_ratios,
    dataframe_to_statement,
)
from models import User, Company
from schemas import (
    UserCreate,
    UserOut,
    Token,
    CompanyCreate,
    CompanyOut,
    DashboardResponse,
    CompanyMetrics,
    CompanyDetailResponse,
    StatementResponse,
)

# ================== GEMINI CONFIG ==================

load_dotenv()  # Load environment variables from .env file
my_key = os.getenv(API_KEY_GEMINI)
GEMINI_API_KEY = API_KEY_GEMINI  # Keeping your original logic

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.5-flash")
else:
    gemini_model = None  # we'll handle missing key gracefully


def generate_gemini_text(prompt: str, max_words: int) -> str:
    """
    Use Gemini to generate text with an explicit word limit.
    If Gemini is not configured, return a fallback message.
    """
    if gemini_model is None:
        return "[Gemini API key not configured. Please set GEMINI_API_KEY.]"

    try:
        response = gemini_model.generate_content(prompt)
        text = (response.text or "").strip()
    except Exception as e:
        return f"[Gemini error: {e}]"

    # Hard word cap
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words])
    return text


# ================== APP & DB SETUP ==================

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Logistics Financial Analytics Web App",
    description="FastAPI + OAuth2 + SQLite + yfinance",
    version="0.1.0",
)

# Serve static front-end
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse("static/index.html")


# ================== AUTH ROUTES ==================

@app.post("/register", response_model=UserOut)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    # Check duplicates
    if get_user_by_username(db, user_in.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    if get_user_by_email(db, user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = get_password_hash(user_in.password)
    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed_pw,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create verification token and link
    token = create_email_verification_token(user.email)
    # Adjust host/port if deploying elsewhere
    verify_link = f"http://127.0.0.1:8000/verify-email?token={token}"

    # Send email (log if not configured)
    send_verification_email(user.email, verify_link)

    return user


@app.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # authenticate_user can be updated in auth.py to accept username OR email
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your inbox."
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


@app.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    email = decode_email_verification_token(token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        return {"message": "Email already verified."}

    user.is_verified = True
    db.commit()
    return {"message": "Email verified successfully. You can now log in."}


# ================== COMPANY CRUD ==================

@app.get("/companies", response_model=List[CompanyOut])
def list_companies(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    return (
        db.query(Company)
        .filter(Company.owner_id == current_user.id)
        .order_by(Company.segment, Company.name)
        .all()
    )


@app.post("/companies", response_model=CompanyOut, status_code=201)
def create_company(
    company_in: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    company = Company(
        name=company_in.name,
        ticker=company_in.ticker,
        segment=company_in.segment,
        owner_id=current_user.id,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@app.delete("/companies/{company_id}", status_code=204)
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    company = (
        db.query(Company)
        .filter(Company.id == company_id, Company.owner_id == current_user.id)
        .first()
    )
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    db.delete(company)
    db.commit()
    return


# ================== DASHBOARD & DETAIL ==================

@app.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    companies = (
        db.query(Company)
        .filter(Company.owner_id == current_user.id)
        .order_by(Company.segment, Company.name)
        .all()
    )
    if not companies:
        return DashboardResponse(companies=[])

    metrics_list: List[CompanyMetrics] = []

    for c in companies:
        price_hist = fetch_price_history(c.ticker, period="5y")
        fundamentals = fetch_fundamentals(c.ticker)
        ratios = compute_ratios(
            fundamentals["income"],
            fundamentals["balance"],
            fundamentals["cashflow"],
            price_hist,
            info_df=fundamentals["info"],   # make sure finance.compute_ratios accepts info_df
        )

        metrics_list.append(
            CompanyMetrics(
                id=c.id,
                name=c.name,
                ticker=c.ticker,
                segment=c.segment,
                price=ratios["price"],
                revenue=ratios["revenue"],
                net_income=ratios["net_income"],
                net_margin=ratios["net_margin"],
                roe=ratios["roe"],
                debt_to_equity=ratios["debt_to_equity"],
                current_ratio=ratios["current_ratio"],
                one_year_return=ratios["one_year_return"],
                pe=ratios.get("pe"),                    # NEW
                pb=ratios.get("pb"),                    # NEW
                ev_to_ebitda=ratios.get("ev_to_ebitda") # NEW
            )
        )

    return DashboardResponse(companies=metrics_list)


@app.get("/analytics/sector")
def sector_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Reuse the dashboard metrics
    companies = db.query(Company).filter(Company.owner_id == current_user.id).all()
    if not companies:
        return {"text": "No companies added yet. Please add logistics companies to view sector analysis."}

    metrics_list = []

    for c in companies:
        price_hist = fetch_price_history(c.ticker, period="5y")
        fundamentals = fetch_fundamentals(c.ticker)
        ratios = compute_ratios(
            income=fundamentals["income"],
            balance=fundamentals["balance"],
            cashflow=fundamentals["cashflow"],
            price_hist=price_hist,
            info_df=fundamentals["info"],
        )
        metrics_list.append(
            {
                "name": c.name,
                "ticker": c.ticker,
                "segment": c.segment,
                "revenue": ratios.get("revenue"),
                "net_income": ratios.get("net_income"),
                "net_margin": ratios.get("net_margin"),
                "roe": ratios.get("roe"),
                "debt_to_equity": ratios.get("debt_to_equity"),
                "current_ratio": ratios.get("current_ratio"),
                "one_year_return": ratios.get("one_year_return"),
                # include market-based multiples in the JSON sent to Gemini
                "pe": ratios.get("pe"),
                "pb": ratios.get("pb"),
                "ev_to_ebitda": ratios.get("ev_to_ebitda"),
            }
        )

    # Build prompt for Gemini
    prompt = (
        "You are a financial analyst specialising in logistics, ports and warehousing.\n"
        "You are given a portfolio of listed companies with some key metrics.\n"
        "Provide a concise sector-level commentary in at most 150 words.\n"
        "Highlight broad themes: beta (calculate or research), risk adjusted portfolio returns, "
        "growth/profitability, leverage, liquidity and recent price momentum.\n"
        "Avoid any investment recommendation language like 'buy/sell/hold'.\n\n"
        f"Metrics JSON:\n{metrics_list}\n\n"
        "Now write the 150-word commentary:"
    )

    text = generate_gemini_text(prompt, max_words=150)
    return {"text": text}


@app.get("/analytics/company/{company_id}")
def company_analytics(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    c = (
        db.query(Company)
        .filter(Company.id == company_id, Company.owner_id == current_user.id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")

    price_hist = fetch_price_history(c.ticker, period="5y")
    fundamentals = fetch_fundamentals(c.ticker)
    ratios = compute_ratios(
        income=fundamentals["income"],
        balance=fundamentals["balance"],
        cashflow=fundamentals["cashflow"],
        price_hist=price_hist,
        info_df=fundamentals["info"],
    )

    prompt = (
        "You are a financial analyst specialising in logistics, ports and warehousing.\n"
        "Provide a focused company-level commentary with brief background on the business it does (max 150 words).\n"
        "Comment briefly on size (revenue), profitability, leverage, liquidity and recent price performance.\n"
        "Avoid the words 'buy', 'sell', 'hold', 'recommend', 'target price'.\n\n"
        f"Company name: {c.name}\n"
        f"Ticker: {c.ticker}\n"
        f"Segment: {c.segment}\n"
        f"Ratios JSON: {ratios}\n\n"
        "Now write the 100-word commentary:"
    )

    text = generate_gemini_text(prompt, max_words=100)
    return {"text": text}


@app.get("/companies/{company_id}/detail", response_model=CompanyDetailResponse)
def company_detail(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # ---------- 1. Fetch company ----------
    c = (
        db.query(Company)
        .filter(Company.id == company_id, Company.owner_id == current_user.id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")

    # ---------- 2. Fetch fundamentals ----------
    fundamentals = fetch_fundamentals(c.ticker)
    income_df = fundamentals.get("income")
    balance_df = fundamentals.get("balance")
    cashflow_df = fundamentals.get("cashflow")
    # IMPORTANT: remove the trailing comma so this is a DataFrame, not a tuple
    info_df = fundamentals.get("info")

    # ---------- 3. Price history ----------
    price_hist = fetch_price_history(c.ticker, period="5y")

    # ---------- 4. Compute ratios (include info_df for market multiples) ----------
    ratios = compute_ratios(
        income=income_df,
        balance=balance_df,
        cashflow=cashflow_df,
        price_hist=price_hist,
        info_df=info_df,
    )

    # ---------- 5. Build safe info_dict ----------
    info_dict = {}

    if info_df is not None and not info_df.empty:
        for idx, row in info_df.iterrows():
            val = row["value"]

            # -- Arrays / lists / Series first --
            if isinstance(val, (np.ndarray, pd.Series, list, tuple)):
                arr = np.array(val).flatten()
                if arr.size == 0 or np.all(pd.isna(arr)):
                    continue
                mask = ~pd.isna(arr)
                if not mask.any():
                    continue
                val = arr[mask][0]

            # -- Now scalar --
            if pd.isna(val):
                continue

            # Numeric
            if isinstance(val, (int, float, np.integer, np.floating)):
                try:
                    v = float(val)
                    if math.isnan(v) or math.isinf(v):
                        continue
                    val = v
                except Exception:
                    continue

            # All remaining types (str, bool, etc.) are JSON-safe
            info_dict[idx] = val

    # ---------- 6. Statements (Income, Balance, Cash Flow) ----------
    income_json = dataframe_to_statement(income_df, max_cols=3)
    balance_json = dataframe_to_statement(balance_df, max_cols=3)
    cf_json = dataframe_to_statement(cashflow_df, max_cols=3)

    def to_statement(obj):
        if obj is None:
            return None
        return StatementResponse(
            columns=obj["columns"],
            index=obj["index"],
            data=obj["data"],
        )

    # ---------- 7. Final JSON-safe response ----------
    return CompanyDetailResponse(
        info=info_dict,
        ratios=ratios,
        income_statement=to_statement(income_json),
        balance_sheet=to_statement(balance_json),
        cash_flow=to_statement(cf_json),
    )
# ================== END OF FILE ==================
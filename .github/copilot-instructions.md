# FinApp Copilot Instructions

## Project Overview
FinApp is a FastAPI-based financial analytics web application for tracking and analyzing logistics company financials using yfinance data.

**Architecture**: Multi-tier FastAPI app with OAuth2 authentication, SQLite persistence, and real-time financial data fetching.

---

## Core Architecture

### Layering Pattern
- **API Layer** (`main.py`): FastAPI routes organized by feature (auth, company CRUD, dashboard, detail)
- **Schema Layer** (`schemas.py`): Pydantic models for request/response validation with `orm_mode` enabled
- **Data Layer** (`models.py`, `database.py`): SQLAlchemy ORM with SQLite backend
- **Auth Layer** (`auth.py`): Stateless JWT-based OAuth2 with passlib/bcrypt
- **Business Logic** (`finance.py`): External data fetching (yfinance) + financial ratio calculations

### Data Flow
1. User submits request → FastAPI validates via Pydantic schema
2. `get_current_active_user` dependency validates JWT token
3. Query filters by `owner_id` for multi-tenancy
4. Finance module fetches/computes metrics from yfinance API
5. Response serialized via schema model

### Key Design Decisions
- **Session management**: Session-per-request pattern via `get_db()` dependency
- **Data isolation**: Companies filtered by `owner_id` at database query level
- **Error handling in finance**: Graceful null returns on yfinance fetch failures (e.g., `pd.DataFrame()` returns)
- **NaN/Inf sanitization**: `compute_ratios()` converts invalid floats to `None` for JSON serialization

---

## Critical Patterns

### Adding Company Routes
Follow the pattern in `/companies` endpoints:
1. Query with `Company.owner_id == current_user.id` filter
2. Return Pydantic model (`CompanyOut`) with `orm_mode=True` config
3. Use status codes: `201` for create, `204` for delete

Example:
```python
@app.get("/companies/{company_id}/detail")
def company_detail(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    c = db.query(Company).filter(
        Company.id == company_id, 
        Company.owner_id == current_user.id  # CRITICAL: Always filter by owner
    ).first()
```

### Financial Data Fetching
The `finance.py` module tolerates incomplete data:
- **`_get_item()`**: Uses fallback label candidates (e.g., "Total Revenue" → "TotalRevenue" → "Revenue")
- **DataFrame handling**: Returns empty `pd.DataFrame()` on yfinance failures, not exceptions
- **NaN/Inf conversion**: Loop at end of `compute_ratios()` converts invalid floats to `None`

When adding new metrics, add fallback labels to the candidates list:
```python
revenue = _get_item(income, ["Total Revenue", "TotalRevenue", "Revenue"])
```

### Authentication Flow
- Token created with `{"sub": username}` payload only
- `get_current_user()` decodes JWT, re-fetches user from DB for each request
- `get_current_active_user()` adds `is_active` check (allows soft-deletion)
- **Note**: `SECRET_KEY = ""` in auth.py—this must be set to a real secret before production

---

## Development Workflow

### Running the App
```powershell
# Activate venv
.\finapp\Scripts\Activate.ps1

# Start dev server (watch mode)
uvicorn main:app --reload
```
Server runs on `http://localhost:8000`; frontend served from `/static/index.html`

### Dependencies
Key packages in `requirements.txt`:
- **FastAPI + Uvicorn**: Web framework + ASGI server
- **SQLAlchemy + Pydantic**: ORM + validation
- **yfinance**: Real-time stock data
- **passlib + python-jose**: Auth (passwords + JWT tokens)
- **pandas + numpy**: Data manipulation (fundamentals, calculations)

---

## Testing & Validation Considerations

- **Auth testing**: Include token in `Authorization: Bearer {token}` header
- **Company isolation**: Verify users cannot access peers' companies (test with multiple users)
- **Finance data edge cases**: Test with tickers that return sparse/missing statements (yfinance inconsistency)
- **Float sanitization**: Verify NaN/Inf values in responses are `None`, not strings/zeroes

---

## File Responsibilities

| File | Purpose |
|------|---------|
| `main.py` | All route handlers, response serialization |
| `models.py` | SQLAlchemy table definitions + relationships |
| `schemas.py` | Pydantic models for validation (input + output) |
| `auth.py` | JWT tokens, password hashing, dependency injection |
| `finance.py` | yfinance API integration + financial calculations |
| `database.py` | SQLite engine + session factory |
| `static/` | HTML/CSS/JS frontend |

---

## Common Modifications

- **Add new financial metric**: Add candidate labels to `compute_ratios()`, add field to `CompanyMetrics`, add column to dashboard
- **Extend user profile**: Add columns to `User` model, update `UserOut` schema, update `/register` handler
- **Add filtering to dashboard**: Modify the company list query in `get_dashboard()` before metrics computation loop

Expense Management Prototype

This is a small FastAPI prototype implementing core flows for an expense management system.

Quick start (Windows PowerShell):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Notes:
- By default the app uses mocked country/currency and exchange-rate lookups to avoid external API calls during initial testing. Set environment variable USE_EXTERNAL=1 to enable real API calls.
- Endpoints:
  - POST /signup -> create company + admin
  - POST /users -> create users
  - POST /expenses -> submit expense
  - POST /approvals/{expense_id}/decision -> approve/reject
  - GET /expenses/user/{user_id} -> list user's expenses
  - GET /approvals/user/{user_id}/pending -> approvals waiting for user

  Developer helpers
   - A PowerShell dev script is included at `scripts\dev.ps1` to create a Python 3.11 venv, install deps, run tests, or start the server. Example:

  ```powershell
  # create venv and start server (uses py -3.11)
  .\scripts\dev.ps1

  # run tests
  .\scripts\dev.ps1 test

  # clean artifacts
  .\scripts\dev.ps1 clean
  ```

  Docker
   - Build and run with Docker (uses Python 3.11 image):

  ```powershell
  docker build -t expense-app .
  docker run -p 8000:8000 expense-app
  ```

  OCR
   - There's a stub endpoint `POST /ocr/receipt` which returns a mocked parsed receipt. To enable real OCR, install Tesseract OCR on your machine and add `pytesseract` to `requirements.txt`, then implement parsing in `main.py`.

Next steps:
- Add frontend or integrate with real OCR service.
- Add auth (JWT) and pagination.

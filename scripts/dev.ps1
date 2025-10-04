param(
    [string]$action = "run"  # run | test | clean
)

Write-Host "Using Python 3.11 venv if available..."
if (-not (Test-Path -Path .venv)) {
    py -3.11 -m venv .venv
}
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

switch ($action) {
    "test" { pytest -q; break }
    "clean" { Remove-Item -Recurse -Force .venv, __pycache__, *.db -ErrorAction SilentlyContinue; break }
    default { uvicorn main:app --reload }
}

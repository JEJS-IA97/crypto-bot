# Apply this stage

From the repository root:

```powershell
git checkout master
git pull origin master
git checkout -b feature/okx-demo-execution
```

Extract this bundle into the repository root, preserving paths. It contains complete replacement files for `backend/app/config.py` and `backend/.env.example`, plus the new OKX/execution files.

From `backend` run:

```powershell
python -m unittest tests/test_okx_demo_client.py
python -m unittest discover -s tests -p "test_*.py"
python -m compileall app tests
```

Do not put API keys or secrets into Git or into this bundle.

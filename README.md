# ForgeMind X

ForgeMind X is a local project workflow demonstration. By default, the six agents use rules-based outputs. If `backend/.env` contains a valid `GEMINI_API_KEY`, they request contextual suggestions from Gemini; API failure automatically uses the local fallback. Outputs do not include actual FEA, validated engineering results, or G-code. Cost figures are illustrative estimates.

## Windows setup

Open two PowerShell windows in the project folder.

### Backend

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

FastAPI docs: <http://localhost:8000/docs>. Local SQLite data is stored at `backend/forgemind.db`. No MongoDB or API key is needed.

For optional Gemini-generated suggestions, place `GEMINI_API_KEY=your-key` in `backend/.env` before starting the backend. Keep the key private. If it is missing, invalid, or rate-limited, the rules-based demo remains available.

For optional NVIDIA TRELLIS visual concepts, place `NVIDIA_API_KEY=your-key` in `backend/.env`. In the workspace, select **Generate 3D concept (.glb)** on a project and enter a text prompt of at most 77 characters. The API returns a downloadable GLB visual asset; it is not dimensionally accurate CAD or a validated engineering design. NVIDIA's hosted TRELLIS API is a trial service and may be rate limited or unavailable.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. Register an account with any valid email and a password of at least eight characters.

## Review demonstration

1. Register and open the workspace.
2. Select **Fill sample project**, then save it.
3. Select **Run six-agent demo**.
4. Review the requirements, design, simulation limitations, manufacturing steps, estimated BOM, and report summary.
5. Select **Download PDF report**.

The simulation output explicitly states that it is not an FEA result. Manufacturing output does not provide validated CNC code. Use this as an educational concept workflow only.

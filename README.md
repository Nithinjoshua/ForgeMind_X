# ForgeMind X

ForgeMind X is a local engineering concept-review workspace. Create projects, run a six-agent review, and browse the results in separate sections for Requirements, Design, Simulation, Manufacturing, Cost, and Report.

The app works without external AI keys. It uses a local rules-based fallback when Gemini is not configured or unavailable. Gemini can provide contextual suggestions when configured. The optional NVIDIA TRELLIS integration generates a downloadable visual GLB concept from a text prompt.

> **Important:** Outputs are concept-stage suggestions. They are not validated engineering, a real FEA simulation, certified designs, supplier quotations, or validated manufacturing instructions. The 3D file is a visual concept, not dimensionally accurate CAD. Cost estimates and the USD-to-INR conversion are illustrative.

## Features

- Email/password registration and sign-in for a local demo workspace.
- Create and manage product projects with a description and requirements list.
- Run a six-agent workflow covering requirements, design, simulation planning, manufacturing, cost, and report summary.
- View detailed assumptions, missing information, review checks, manufacturing considerations, and cost drivers.
- Estimate a prototype bill of materials in USD, convert it to INR using an editable sample exchange rate, and calculate a suggested price using an editable markup.
- Optionally generate a TRELLIS visual concept as a `.glb` file.
- Download a PDF containing the project and agent results.
- Store users, projects, and executions locally in SQLite.

## Requirements

- Windows with **Command Prompt** (`cmd.exe`)
- Python 3.10 or later
- Node.js and npm

## Run locally on Windows

Start the backend and frontend in two separate Command Prompt windows. Run these commands from the project directory.

### 1. Backend

```bat
cd /d D:\DLCV_Project\ForgeMind-X-main\backend
py -m venv venv
venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The API will normally be available at <http://localhost:8000>. Interactive API documentation is at <http://localhost:8000/docs>, and the health endpoint is <http://localhost:8000/api/health>.

The SQLite database is created automatically at `backend/forgemind.db`. No database server or API key is required for local fallback mode.

### 2. Frontend

In a second Command Prompt window:

```bat
cd /d D:\DLCV_Project\ForgeMind-X-main\frontend
npm install
npm run dev
```

Open <http://localhost:3000>. If port 3000 is already in use, Next.js may start on port 3001 or another available port and will print the correct address in the terminal.

The frontend uses `http://localhost:8000/api` by default. If the backend uses another port, create `frontend/.env.local` with the matching API URL, for example:

```env
NEXT_PUBLIC_API_URL=http://localhost:8080/api
```

Restart the frontend after changing `.env.local`.

## Optional AI services

Create `backend/.env` if you want to configure hosted AI integrations. Keep API keys private; do not commit this file or paste keys into source code.

```env
GEMINI_API_KEY=your-gemini-key
NVIDIA_API_KEY=your-nvidia-key
```

An example file is provided at `backend/.env.example`. Restart the backend after changing environment variables.

- **Gemini:** The six-agent workflow attempts Gemini when a key is configured. If the request fails or the service is unavailable, ForgeMind X returns the local rules-based output and includes a provider message.
- **NVIDIA TRELLIS:** In the Simulation section, create a 3D concept by entering a prompt of up to 77 characters. The result is a downloadable GLB concept and is not CAD or a simulation result. Hosted API availability, limits, and charges are determined by NVIDIA.

## Try the workflow

1. Open the frontend and register using a valid email address and a password of at least eight characters.
2. On Home, enter a project name, description, and requirements. **Fill sample project** can populate an example.
3. Save the project, then select **Run workflow**.
4. Browse each section using the left navigation menu. Review open questions and assumptions before relying on suggestions.
5. Optionally create a visual model from Simulation, or download the full PDF from Report.

To see the expanded agent output, run the workflow again after changing backend code. Existing executions keep the results saved at the time they were created.

## API overview

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Check API status and configured integrations |
| `POST /api/auth/register` / `POST /api/auth/login` | Create an account or sign in |
| `GET, POST /api/projects` | List or create projects |
| `GET, PUT, DELETE /api/projects/{project_id}` | Read, update, or remove a project |
| `POST /api/projects/{project_id}/executions` | Run the six-agent workflow |
| `GET /api/executions/{execution_id}` | Read a saved execution |
| `POST /api/projects/{project_id}/model3d` | Request a TRELLIS visual concept |
| `GET /api/executions/{execution_id}/report.pdf` | Download an execution PDF |

Protected project and execution endpoints require a bearer token returned by registration or login. See the interactive docs at `/docs` for request schemas.

## Local data and configuration

- Default database: `backend/forgemind.db` (SQLite).
- Set `FORGEMIND_DB` in `backend/.env` to use a different SQLite file path.
- Set `JWT_SECRET` in `backend/.env` to replace the local demo signing secret. The default is intended only for local demonstration; do not deploy it publicly.
- Authentication tokens expire after 12 hours.

## Troubleshooting

- **Frontend says “Failed to fetch”:** Confirm the backend is running, check `/api/health`, and make sure `NEXT_PUBLIC_API_URL` points to the backend address. Restart Next.js after editing `.env.local`.
- **Port is busy:** Use the port printed by Next.js. If you change the backend port, also update `NEXT_PUBLIC_API_URL`.
- **Gemini timeout or service error:** The workflow can still use the local fallback. Retry later or continue in rules-based mode.
- **3D generation fails:** Confirm `NVIDIA_API_KEY` is present in `backend/.env`, restart Uvicorn, and check whether the hosted service is available to your account.

## Build checks

```bat
cd /d D:\DLCV_Project\ForgeMind-X-main\frontend
npm run build
```

For Python syntax validation from the backend directory:

```bat
venv\Scripts\python.exe -m py_compile app\main.py
```

"""ForgeMind X local demo API. Outputs are rules-based and are not validated engineering."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DB_PATH = Path(os.getenv("FORGEMIND_DB", ROOT / "forgemind.db"))
SECRET = os.getenv("JWT_SECRET", "local-demo-secret-change-before-deployment")
ALGORITHM = "HS256"
app = FastAPI(title="ForgeMind X", version="1.0.0", description="Local, rules-based engineering workflow demo")
# Next.js may choose 3001 (or another port) when the default dev port is busy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):[0-9]+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
bearer = HTTPBearer(auto_error=False)

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db() -> None:
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, name TEXT NOT NULL, description TEXT NOT NULL, requirements TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS executions(id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE, status TEXT NOT NULL, outputs TEXT NOT NULL, created_at TEXT NOT NULL);
        """)

@app.on_event("startup")
def startup() -> None: init_db()

class Credentials(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value): raise ValueError("Enter a valid email address")
        return value
class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=5, max_length=5000)
    requirements: list[str] = Field(default_factory=list)
class Model3DIn(BaseModel):
    prompt: str = Field(min_length=3, max_length=77)
    seed: int = Field(default=0, ge=0)

def token_for(uid: int) -> str:
    return jwt.encode({"sub": str(uid), "exp": datetime.now(timezone.utc) + timedelta(hours=12)}, SECRET, algorithm=ALGORITHM)
def user_id(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> int:
    if not creds: raise HTTPException(401, "Sign in to continue")
    try: return int(jwt.decode(creds.credentials, SECRET, algorithms=[ALGORITHM])["sub"])
    except Exception: raise HTTPException(401, "Session expired; please sign in again")

@app.get("/api/health")
def health() -> dict[str, Any]: return {"status": "ok", "mode": "local-demo", "database": "sqlite", "gemini_key_loaded": bool(os.getenv("GEMINI_API_KEY", "").strip()), "nvidia_trellis_key_loaded": bool(os.getenv("NVIDIA_API_KEY", "").strip())}

@app.post("/api/auth/register")
def register(body: Credentials) -> dict[str, str]:
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", body.password.encode(), salt.encode(), 240000).hex()
    try:
        with db() as c: cur = c.execute("INSERT INTO users(email,salt,password_hash) VALUES(?,?,?)", (body.email.lower(), salt, hashed)); uid = cur.lastrowid
    except sqlite3.IntegrityError: raise HTTPException(409, "An account with this email already exists")
    return {"access_token": token_for(uid), "token_type": "bearer", "email": body.email.lower()}

@app.post("/api/auth/login")
def login(body: Credentials) -> dict[str, str]:
    with db() as c: row = c.execute("SELECT * FROM users WHERE email=?", (body.email.lower(),)).fetchone()
    if not row: raise HTTPException(401, "Incorrect email or password")
    check = hashlib.pbkdf2_hmac("sha256", body.password.encode(), row["salt"].encode(), 240000).hex()
    if not hmac.compare_digest(check, row["password_hash"]): raise HTTPException(401, "Incorrect email or password")
    return {"access_token": token_for(row["id"]), "token_type": "bearer", "email": row["email"]}

@app.get("/api/projects")
def projects(uid: int = Depends(user_id)) -> list[dict[str, Any]]:
    with db() as c: rows = c.execute("SELECT * FROM projects WHERE owner_id=? ORDER BY id DESC", (uid,)).fetchall()
    return [{**dict(r), "requirements": json.loads(r["requirements"])} for r in rows]

@app.get("/api/projects/{project_id}")
def get_project(project_id: int, uid: int = Depends(user_id)) -> dict[str, Any]:
    with db() as c: row = c.execute("SELECT * FROM projects WHERE id=? AND owner_id=?", (project_id,uid)).fetchone()
    if not row: raise HTTPException(404,"Project not found")
    return {**dict(row),"requirements":json.loads(row["requirements"])}

@app.post("/api/projects")
def create_project(body: ProjectIn, uid: int = Depends(user_id)) -> dict[str, Any]:
    with db() as c:
        cur = c.execute("INSERT INTO projects(owner_id,name,description,requirements,created_at) VALUES(?,?,?,?,?)", (uid, body.name, body.description, json.dumps(body.requirements), datetime.now(timezone.utc).isoformat()))
        row = c.execute("SELECT * FROM projects WHERE id=?", (cur.lastrowid,)).fetchone()
    return {**dict(row), "requirements": json.loads(row["requirements"])}

@app.put("/api/projects/{project_id}")
def update_project(project_id: int, body: ProjectIn, uid: int = Depends(user_id)) -> dict[str, Any]:
    with db() as c:
        cur=c.execute("UPDATE projects SET name=?,description=?,requirements=? WHERE id=? AND owner_id=?",(body.name,body.description,json.dumps(body.requirements),project_id,uid))
        if not cur.rowcount: raise HTTPException(404,"Project not found")
        row=c.execute("SELECT * FROM projects WHERE id=?",(project_id,)).fetchone()
    return {**dict(row),"requirements":json.loads(row["requirements"])}

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int, uid: int = Depends(user_id)) -> dict[str, bool]:
    with db() as c: cur=c.execute("DELETE FROM projects WHERE id=? AND owner_id=?",(project_id,uid))
    if not cur.rowcount: raise HTTPException(404,"Project not found")
    return {"deleted":True}

def run_agents(p: dict[str, Any]) -> dict[str, Any]:
    text = (p["name"] + " " + p["description"] + " " + " ".join(p["requirements"])).lower()
    lightweight = "lightweight" in text or "drone" in text or "portable" in text
    water = any(word in text for word in ("water", "purifier", "filtration", "filter"))
    solar = "solar" in text
    if water:
        material = "Food-contact-rated polypropylene or 304 stainless steel (verify certification and compatibility)"
        components = ["Food-safe inlet and outlet fittings", "Replaceable filter cartridge and sealed housing", "Pump or gravity-feed path, selected for the required flow", "Serviceable enclosure and mounting points"]
        approach = "A serviceable, sealed filter housing with replaceable cartridge; choose pump or gravity feed after the target flow and pressure are known."
        process = "Prototype with off-the-shelf food-contact fittings and a machined or molded housing; select production process after volume and pressure requirements are known."
        bom = [{"item":"Filter cartridge and fittings", "detail":"Food-contact-rated components; confirm supplier certificates", "estimated_cost_usd":55.0}, {"item":"Housing and seals", "detail":material, "estimated_cost_usd":65.0}, {"item":"Assembly and leak-check allowance", "detail":"One-off prototype estimate", "estimated_cost_usd":45.0}]
    else:
        material = "6061-T6 aluminum (initial option; confirm load, corrosion, and joining requirements)" if ("aluminum" in text or lightweight) else "304 stainless steel (initial option; confirm load and environment)"
        components = ["Primary product structure or enclosure", "Interfaces for payloads, controls, or adjacent modules", "Fasteners, seals, and vibration isolation where needed", "Access features for assembly and service"]
        approach = f"Use a modular structure tailored to {p['name']}; select section sizes and joints after loads, packaging, and service access are defined."
        process = "Prototype by CNC machining or cut-and-join fabrication after reviewing the geometry; compare with formed sheet or extrusion for larger batches."
        bom = [{"item":"Primary structure / enclosure", "detail":material, "estimated_cost_usd":85.0 if lightweight else 120.0}, {"item":"Fasteners, seals, and inserts", "detail":"Choose grade and finish for the real environment", "estimated_cost_usd":24.0}, {"item":"Prototype fabrication and finishing", "detail":"Illustrative one-off allowance; depends on geometry", "estimated_cost_usd":110.0}]
    if solar:
        components.append("Solar panel mounting and cable strain relief; size only after power demand is known")
    total = round(sum(x["estimated_cost_usd"] for x in bom), 2)
    agents = [
      ("Requirements", {"functional":p["requirements"] or ["Design and document the requested product", "Support intended use described in project brief"], "non_functional":["Review durability, weight, serviceability, and manufacturability constraints", "Define measurable acceptance limits before detailed design"], "missing_information":["Overall dimensions and packaging envelope", "Loads, duty cycle, and operating environment", "Target service life and maintenance interval", "Target production quantity and applicable standards"], "acceptance_checks":["Each requirement has a measurable pass/fail check", "Critical interfaces and user actions are defined", "Open questions are resolved before release for fabrication"]}),
      ("Design", {"recommendation":approach, "components":components, "material_and_tradeoffs":[f"Starting material: {material}.", "Compare mass, strength, corrosion/chemical exposure, joining method, availability, and end-of-life needs before selection."], "specification":"Create a dimensioned layout, define interfaces and tolerances, document fastener/seal details, and identify inspection points before fabrication.", "design_review_checklist":["Confirm envelope, access, assembly sequence, and replacement of service parts", "Check sharp edges, pinch points, water ingress or contamination paths as applicable", "Record assumptions and unresolved decisions on the drawing"]}),
      ("Simulation", {"estimate":"Qualitative screening only. No numerical stress, flow, thermal result, safety factor, or performance prediction is asserted.", "assumptions":["No CAD geometry, material certificate, boundary conditions, or measured loads/flow data were supplied.", "Results must not be used as evidence of safety or performance."], "load_cases_to_define":["Normal operating condition and peak expected load", "Handling, transport, vibration, and misuse cases relevant to the product", "Environmental exposure such as temperature, moisture, or chemical contact"], "checks_to_plan":["Geometry and mesh convergence", "Material properties and realistic constraints", "Compare predicted results with a physical prototype measurement"], "next_step":"Prepare a documented model with geometry, mesh, material data, loads, constraints, and acceptance criteria in a suitable validated solver; review it with a qualified engineer."}),
      ("Manufacturing", {"process":process, "steps":["Freeze a reviewed, dimensioned drawing and bill of materials", "Confirm material grade, certificates, and supplier availability", "Review tooling, joining, sealing, and assembly access", "Build a prototype and record deviations", "Inspect critical dimensions and perform product-specific functional checks"], "quality_checks":["Incoming material and component identification", "Critical interface dimensions and joint/seal inspection", "Functional test appropriate to product (for example leak/flow test for water equipment)"], "production_considerations":["Compare one-off machining with formed, molded, or extruded options at the intended batch size", "Plan replacement parts and avoid special tooling until demand is established"], "notice":"No CNC/G-code is generated or validated; process choice requires drawing and supplier review."}),
      ("Cost", {"currency":"USD", "basis":"Illustrative one-off prototype allowances only; excludes tax, shipping, certification, and supplier-specific minimums unless listed. Replace with current quotes.", "items":bom, "cost_drivers":["Geometry, tolerances, finish, and material availability", "Batch quantity, setup/tooling, assembly, and testing", "Certification, packaging, freight, and taxes are not included"], "total_estimated_usd":total}),
      ("Report", {"title":p["name"], "overview":p["description"], "executive_summary":f"This concept review organizes the supplied brief for {p['name']} into requirements, design, simulation planning, manufacturing, and illustrative prototype cost.", "design_basis":[f"User requirements: {', '.join(p['requirements']) if p['requirements'] else 'No explicit requirements supplied.'}", "Unspecified geometry and operating conditions remain open design inputs."], "recommended_actions":["Confirm missing dimensions, loads, environment, and production quantity", "Review material and component choices against actual use and applicable standards", "Develop drawings and obtain supplier quotes before build or pricing"], "conclusion":"Use this package to plan engineering review and prototype definition.", "limitations":["Rules-based concept guidance, not a validated design or real AI analysis", "No FEA, certification, supplier quotation, or manufacturing validation was performed"]})]
    return {"mode":"rules-based demo", "disclaimer":"Generated locally from project inputs. Estimates are illustrative and are not validated engineering results.", "agents":[{"name":n,"status":"completed","output":o} for n,o in agents]}

AGENT_NAMES = ["Requirements", "Design", "Simulation", "Manufacturing", "Cost", "Report"]

def run_gemini_agents(project: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Request six contextual outputs in one Gemini call and return a safe fallback reason."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None, "Backend did not load GEMINI_API_KEY from backend/.env. Restart Uvicorn after saving the key."
    prompt = """Create useful, detailed, product-specific engineering concept-review outputs using the project input. Return ONLY JSON with exactly six agents: Requirements output keys functional (specific requirements), non_functional, missing_information (dimensions, loads/environment, duty life/quantity/standards as relevant), acceptance_checks; Design keys recommendation, components, material_and_tradeoffs, specification, design_review_checklist; Simulation keys estimate, assumptions, load_cases_to_define, checks_to_plan, next_step; Manufacturing keys process, steps, quality_checks, production_considerations, notice; Cost keys currency, basis, items (item/detail/estimated_cost_usd), cost_drivers, total_estimated_usd; Report keys title, overview, executive_summary, design_basis, recommended_actions, conclusion, limitations. Use all six names exactly once. Give several concrete, relevant points per list and complete sentences where useful. Tailor recommendations to the actual product; do not assume a frame or drone unless the brief says so. Clearly state simulation is planning only and is not FEA or a validated result. Never claim certification, supplier quotes, or generate G-code. Cost figures are rough one-off prototype allowances in USD, state exclusions, and ensure total equals line items. Keep the entire response within the requested JSON format.
""" + json.dumps({"name": project["name"], "description": project["description"], "requirements": project["requirements"]}, ensure_ascii=False)
    request_body = json.dumps({"contents":[{"parts":[{"text":prompt}]}], "generationConfig":{"responseMimeType":"application/json","temperature":0.2,"maxOutputTokens":5000,"thinkingConfig":{"thinkingLevel":"MINIMAL"}}}).encode("utf-8")
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    backup_model = os.getenv("GEMINI_BACKUP_MODEL", "gemini-3.6-flash").strip()
    models = [model] + ([backup_model] if backup_model and backup_model != model else [])
    payload = None
    last_503: str | None = None
    try:
        for index, selected_model in enumerate(models):
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent",
                data=request_body,
                headers={"Content-Type":"application/json", "x-goog-api-key":api_key},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=25) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 503 and index < len(models) - 1:
                    last_503 = f"{selected_model} is temporarily at capacity; retrying with {backup_model}."
                    time.sleep(1)
                    continue
                raise
        if payload is None:
            return None, last_503 or "Gemini models did not return a response."
        raw = payload["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(raw)
        mapped = {item["name"]: item["output"] for item in data["agents"]}
        if set(mapped) != set(AGENT_NAMES) or not all(isinstance(mapped[n], dict) for n in AGENT_NAMES):
            return None, "Gemini responded, but its output did not match the six-agent format."
        cost = mapped["Cost"]
        if isinstance(cost.get("items"), list):
            total = round(sum(float(item.get("estimated_cost_usd", 0)) for item in cost["items"]), 2)
            cost["total_estimated_usd"] = total
        return {"mode":"Gemini AI", "disclaimer":"AI-generated concept suggestions based on your inputs. Cost figures are illustrative. This is not validated engineering, FEA, certification, or a supplier quote.", "agents":[{"name":name,"status":"completed","output":mapped[name]} for name in AGENT_NAMES]}, None
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            detail = ""
        reason = f"Gemini API returned HTTP {exc.code}" + (f": {detail[:350]}" if detail else ".")
        return None, reason
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, TypeError, ValueError) as exc:
        if isinstance(exc, urllib.error.URLError):
            detail = str(exc.reason)
        else:
            detail = str(exc) or type(exc).__name__
        return None, f"Gemini request failed ({type(exc).__name__}): {detail[:250]}"

@app.post("/api/projects/{project_id}/executions")
def execute(project_id: int, uid: int = Depends(user_id)) -> dict[str, Any]:
    with db() as c:
        p = c.execute("SELECT * FROM projects WHERE id=? AND owner_id=?", (project_id,uid)).fetchone()
        if not p: raise HTTPException(404, "Project not found")
        project = {**dict(p), "requirements":json.loads(p["requirements"])}
        outputs, fallback_reason = run_gemini_agents(project)
        if outputs is None:
            outputs = run_agents(project)
            outputs["mode"] = "rules-based demo (Gemini unavailable)"
            outputs["provider_message"] = fallback_reason or "Gemini was unavailable; using the local rules-based fallback."
        cur = c.execute("INSERT INTO executions(project_id,status,outputs,created_at) VALUES(?,?,?,?)", (project_id,"completed",json.dumps(outputs),datetime.now(timezone.utc).isoformat()))
        eid = cur.lastrowid
    return {"id":eid,"project_id":project_id,"status":"completed",**outputs}

@app.get("/api/executions/{execution_id}")
def get_execution(execution_id: int, uid: int = Depends(user_id)) -> dict[str, Any]:
    with db() as c:
        row = c.execute("SELECT e.* FROM executions e JOIN projects p ON p.id=e.project_id WHERE e.id=? AND p.owner_id=?",(execution_id,uid)).fetchone()
    if not row: raise HTTPException(404,"Execution not found")
    return {"id":row["id"],"project_id":row["project_id"],"status":row["status"],**json.loads(row["outputs"])}

@app.post("/api/projects/{project_id}/model3d")
def generate_project_model(project_id: int, body: Model3DIn, uid: int = Depends(user_id)) -> Response:
    """Generate a concept GLB through NVIDIA TRELLIS; never treat it as CAD."""
    api_key = os.getenv("NVIDIA_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(503, "NVIDIA TRELLIS is not configured. Add NVIDIA_API_KEY to backend/.env and restart the backend.")
    with db() as c:
        project = c.execute("SELECT name FROM projects WHERE id=? AND owner_id=?", (project_id,uid)).fetchone()
    if not project: raise HTTPException(404,"Project not found")
    request_body = json.dumps({
        "mode":"text", "prompt":body.prompt, "seed":body.seed,
        "output_format":"glb", "samples":1,
        "slat_sampling_steps":25, "ss_sampling_steps":25,
        "slat_cfg_scale":3.0, "ss_cfg_scale":7.5,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://ai.api.nvidia.com/v1/genai/microsoft/trellis",
        data=request_body,
        headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json","Accept":"application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req,timeout=240) as response:
            content_type=response.headers.get("Content-Type","")
            result=response.read()
        if "model/gltf-binary" in content_type or result[:4] == b"glTF":
            glb=result
        else:
            payload=json.loads(result.decode("utf-8"))
            encoded=(payload.get("artifacts") or [{}])[0].get("base64") or payload.get("output",{}).get("glb")
            if not encoded: raise ValueError("NVIDIA response did not contain a GLB artifact")
            glb=__import__("base64").b64decode(encoded)
        if not glb.startswith(b"glTF"): raise ValueError("NVIDIA response was not a valid GLB file")
    except urllib.error.HTTPError as exc:
        try:
            error_body=json.loads(exc.read().decode("utf-8"))
            detail=error_body.get("detail") or error_body.get("error",{}).get("message","")
        except Exception: detail=""
        raise HTTPException(502,f"NVIDIA TRELLIS returned HTTP {exc.code}"+(f": {str(detail)[:300]}" if detail else "."))
    except (urllib.error.URLError,TimeoutError) as exc:
        raise HTTPException(504,f"NVIDIA TRELLIS request timed out or could not connect: {str(getattr(exc,'reason',exc))[:200]}")
    except (ValueError,KeyError,TypeError) as exc:
        raise HTTPException(502,f"Could not read NVIDIA TRELLIS output: {str(exc)[:200]}")
    safe_name=re.sub(r"[^A-Za-z0-9_-]+","-",project["name"]).strip("-")[:60] or "project"
    return Response(glb,media_type="model/gltf-binary",headers={"Content-Disposition":f'attachment; filename="{safe_name}-concept.glb"',"X-Model-Notice":"AI-generated visual concept only; not CAD, dimensionally accurate, or validated."})

@app.get("/api/executions/{execution_id}/report.pdf")
def report_pdf(execution_id: int, uid: int = Depends(user_id)) -> Response:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from xml.sax.saxutils import escape
        from io import BytesIO
    except ImportError: raise HTTPException(503,"PDF support is unavailable; install backend requirements")
    with db() as c:
        row = c.execute("SELECT e.*,p.name,p.description,p.requirements FROM executions e JOIN projects p ON p.id=e.project_id WHERE e.id=? AND p.owner_id=?",(execution_id,uid)).fetchone()
    if not row: raise HTTPException(404,"Execution not found")
    payload=json.loads(row["outputs"]); agents={a["name"]:a["output"] for a in payload["agents"]}; buf=BytesIO()
    def page(canvas, doc):
        canvas.saveState(); canvas.setFont("Helvetica",9); canvas.setFillColor(colors.grey); canvas.drawString(42,25,"ForgeMind X • Concept report • Not validated engineering"); canvas.drawRightString(570,25,f"Page {doc.page}"); canvas.restoreState()
    doc=SimpleDocTemplate(buf,pagesize=letter,rightMargin=42,leftMargin=42,topMargin=42,bottomMargin=42); styles=getSampleStyleSheet(); story=[Paragraph("ForgeMind X Engineering Concept Report",styles["Title"]),Paragraph(row["name"],styles["Heading1"]),Paragraph(row["description"],styles["BodyText"]),Spacer(1,14)]
    for title,key in [("Requirements analysis","Requirements"),("Design recommendations","Design"),("Simulation planning","Simulation"),("Manufacturing recommendations","Manufacturing"),("Bill of materials and cost","Cost"),("Summary and next steps","Report")]:
        story.append(Paragraph(title,styles["Heading2"]))
        for field,value in agents[key].items():
            story.append(Paragraph(escape(field.replace("_"," ").title()),styles["Heading3"]))
            if isinstance(value,list):
                for item in value:
                    if isinstance(item,dict):
                        line="; ".join(f"{name.replace('_',' ').title()}: {detail}" for name,detail in item.items())
                    else: line=str(item)
                    story.append(Paragraph("• " + escape(line),styles["BodyText"]))
            elif isinstance(value,dict):
                for name,detail in value.items(): story.append(Paragraph(f"<b>{escape(name.replace('_',' ').title())}:</b> {escape(str(detail))}",styles["BodyText"]))
            else: story.append(Paragraph(escape(str(value)),styles["BodyText"]))
            story.append(Spacer(1,5))
        story.append(Spacer(1,8))
    cost=agents["Cost"]; data=[["Item","Details","Estimated USD"]]+[[x["item"],x["detail"],f"${x['estimated_cost_usd']:.2f}"] for x in cost["items"]]+[["Total","Illustrative prototype allowance",f"${cost['total_estimated_usd']:.2f}"]]
    story.extend([Table(data,colWidths=[135,280,90],repeatRows=1,style=TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#17324d")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.4,colors.lightgrey),("VALIGN",(0,0),(-1,-1),"TOP")])),Spacer(1,16),Paragraph(payload["disclaimer"],styles["Italic"])])
    doc.build(story,onFirstPage=page,onLaterPages=page); return Response(buf.getvalue(),media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="forgemind-report-{execution_id}.pdf"'})

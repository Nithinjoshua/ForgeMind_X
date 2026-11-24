"use client";

import { useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
type Project = { id: number; name: string; description: string; requirements: string[] };
type Agent = { name: string; status: string; output: Record<string, unknown> };
type Execution = { id: number; project_id: number; status: string; mode: string; disclaimer: string; provider_message?: string; agents: Agent[] };
type Section = "home" | "requirements" | "design" | "simulation" | "manufacturing" | "cost" | "report";
const sections: { id: Section; label: string; icon: string }[] = [
  { id: "home", label: "Home", icon: "⌂" },
  { id: "requirements", label: "Requirements", icon: "☷" },
  { id: "design", label: "Design", icon: "◇" },
  { id: "simulation", label: "Simulation", icon: "◉" },
  { id: "manufacturing", label: "Manufacturing", icon: "⚙" },
  { id: "cost", label: "Cost", icon: "₹" },
  { id: "report", label: "Report", icon: "▤" },
];
const agentBySection: Partial<Record<Section, string>> = {
  requirements: "Requirements", design: "Design", simulation: "Simulation", manufacturing: "Manufacturing",
};

async function request(path: string, token: string, init: RequestInit = {}) {
  const response = await fetch(API + path, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...init.headers },
  });
  if (!response.ok) {
    let detail: string | undefined;
    try { detail = (await response.json()).detail; } catch { /* Keep the status fallback. */ }
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return response;
}

function AgentDetails({ agent }: { agent: Agent }) {
  const label = (key: string) => key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  const renderValue = (value: unknown) => {
    if (Array.isArray(value)) return <ul>{value.map((item, index) => <li key={index}>{typeof item === "object" && item !== null ? <div className="detail-object">{Object.entries(item).map(([key, nested]) => <p key={key}><strong>{label(key)}:</strong> {String(nested)}</p>)}</div> : String(item)}</li>)}</ul>;
    if (typeof value === "object" && value !== null) return <div className="detail-object">{Object.entries(value).map(([key, nested]) => <p key={key}><strong>{label(key)}:</strong> {String(nested)}</p>)}</div>;
    return <p>{String(value)}</p>;
  };
  return <div className="agent-details">
    {Object.entries(agent.output).map(([key, value]) => <section className="agent-detail" key={key}>
      <h3>{label(key)}</h3>
      {renderValue(value)}
    </section>)}
  </div>;
}

export default function Portal({ initial }: { initial: "login" | "register" | "dashboard" }) {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<number | null>(null);
  const [execution, setExecution] = useState<Execution | null>(null);
  const [section, setSection] = useState<Section>("home");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [requirements, setRequirements] = useState("Lightweight construction\nDurable frame\nSuitable material selection\nManufacturability\nEstimated production cost\nClear engineering documentation");
  const [exchangeRate, setExchangeRate] = useState(86);
  const [margin, setMargin] = useState(25);

  useEffect(() => {
    const storedToken = localStorage.getItem("fm_token");
    if (storedToken) { setToken(storedToken); setEmail(localStorage.getItem("fm_email") || ""); }
  }, []);
  useEffect(() => {
    if (!token) return;
    request("/projects", token).then((r) => r.json()).then((list: Project[]) => {
      setProjects(list);
      if (list.length) setActiveProjectId((current) => current ?? list[0].id);
    }).catch((e) => setError(e.message));
  }, [token]);

  const activeProject = projects.find((project) => project.id === activeProjectId) || projects[0] || null;
  const getAgent = (agentName: string) => execution?.agents.find((agent) => agent.name === agentName);
  const costOutput = getAgent("Cost")?.output;
  const costItems = useMemo(() => Array.isArray(costOutput?.items) ? costOutput.items as { item?: string; detail?: string; estimated_cost_usd?: number }[] : [], [costOutput]);
  const productionCostInr = costItems.reduce((total, item) => total + (Number(item.estimated_cost_usd) || 0) * exchangeRate, 0);
  const suggestedPriceInr = productionCostInr * (1 + margin / 100);

  async function auth(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const response = await fetch(`${API}/auth/${initial}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password: (document.getElementById("password") as HTMLInputElement).value }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Authentication failed");
      localStorage.setItem("fm_token", data.access_token); localStorage.setItem("fm_email", data.email);
      setToken(data.access_token); location.href = "/dashboard";
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function createProject(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const response = await request("/projects", token, { method: "POST", body: JSON.stringify({ name, description, requirements: requirements.split("\n").map((item) => item.trim()).filter(Boolean) }) });
      const project: Project = await response.json();
      setProjects((current) => [project, ...current]); setActiveProjectId(project.id); setName(""); setDescription("");
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function runProject(project: Project) {
    setBusy(true); setError(""); setActiveProjectId(project.id);
    try {
      const response = await request(`/projects/${project.id}/executions`, token, { method: "POST" });
      const result: Execution = await response.json(); setExecution(result); setSection("requirements");
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function generate3d() {
    if (!activeProject) return;
    const suggestion = `${activeProject.name}, isolated product concept`.slice(0, 77);
    const prompt = window.prompt("Describe the visual 3D concept (77 characters maximum). This is an illustrative mesh, not CAD.", suggestion);
    if (!prompt) return;
    if (prompt.trim().length > 77) { setError("TRELLIS prompts must be 77 characters or fewer."); return; }
    setBusy(true); setError("");
    try {
      const response = await request(`/projects/${activeProject.id}/model3d`, token, { method: "POST", body: JSON.stringify({ prompt: prompt.trim(), seed: 0 }) });
      const url = URL.createObjectURL(await response.blob()); const anchor = document.createElement("a");
      anchor.href = url; anchor.download = `${activeProject.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-concept.glb`; anchor.click(); URL.revokeObjectURL(url);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function downloadReport() {
    if (!execution) return;
    setBusy(true); setError("");
    try {
      const response = await request(`/executions/${execution.id}/report.pdf`, token);
      const url = URL.createObjectURL(await response.blob()); const anchor = document.createElement("a");
      anchor.href = url; anchor.download = `forgemind-report-${execution.id}.pdf`; anchor.click(); URL.revokeObjectURL(url);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  function selectSection(next: Section) { setSection(next); setMobileSidebarOpen(false); setError(""); }
  function renderAgent(sectionName: string) {
    const agent = getAgent(sectionName);
    if (!agent) return <EmptyState text="Run the six-agent workflow from Home to generate this section." onHome={() => selectSection("home")} />;
    return <div className="content-card"><AgentDetails agent={agent} /></div>;
  }

  if (!token && initial !== "login" && initial !== "register") return <main className="auth-main"><section className="auth-card"><h1>ForgeMind X</h1><p>Sign in to open your Engineering Workspace.</p><div className="auth-link-row"><a href="/login">Sign in</a><a href="/register">Create account</a></div></section></main>;
  if (initial === "login" || initial === "register") return <>
    <nav className="auth-nav"><a className="site-brand" href="/">ForgeMind X</a><a className="auth-home" href="/">Back to home</a></nav>
    <main className="auth-main"><section className="auth-card">
      <div className="auth-heading"><p className="auth-eyebrow">ENGINEERING CONCEPT WORKSPACE</p><h1>{initial === "login" ? "Welcome back" : "Create your account"}</h1><p className="muted">{initial === "login" ? "Sign in to continue to your projects." : "Set up your workspace to get started."}</p></div>
      <form className="auth-form" onSubmit={auth}><label htmlFor="email">Email address</label><input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /><label htmlFor="password">Password</label><input id="password" type="password" autoComplete={initial === "login" ? "current-password" : "new-password"} minLength={8} required /><button className="auth-submit" disabled={busy}>{busy ? "Please wait…" : initial === "login" ? "Sign in" : "Create account"}</button></form>
      {error && <p className="error auth-error" role="alert">{error}</p>}<p className="auth-switch"><span>{initial === "login" ? "New to ForgeMind X?" : "Already have an account?"}</span> <a href={initial === "login" ? "/register" : "/login"}>{initial === "login" ? "Create an account" : "Sign in"}</a></p>
    </section></main>
  </>;

  const currentSection = sections.find((item) => item.id === section)!;
  const content = section === "home" ? <>
    <section className="workspace-intro"><div><p className="auth-eyebrow">ENGINEERING WORKSPACE</p><h1>Home</h1><p className="muted">Build a project brief, then review its requirements, design options, simulation plan, manufacturing path, cost assumptions, and report in separate sections.</p></div></section>
    <section className="content-card"><h2>Create project</h2><form className="project-form" onSubmit={createProject}><label htmlFor="project-name">Project name</label><input id="project-name" required minLength={2} value={name} onChange={(e) => setName(e.target.value)} placeholder="Smart Agricultural Drone Frame" /><label htmlFor="project-description">Description</label><textarea id="project-description" required minLength={5} rows={3} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Describe the product and its intended use." /><label htmlFor="project-requirements">Requirements (one per line)</label><textarea id="project-requirements" rows={5} value={requirements} onChange={(e) => setRequirements(e.target.value)} /><div className="row"><button disabled={busy}>{busy ? "Please wait…" : "Save project"}</button><button type="button" className="button-secondary" onClick={() => { setName("Smart Agricultural Drone Frame"); setDescription("Design a lightweight agricultural drone frame suitable for crop monitoring and precision agriculture."); }}>Fill sample project</button></div></form></section>
    <section className="content-card"><div className="section-heading"><div><h2>Your projects</h2><p className="muted">Select a project, then run the six-agent workflow.</p></div></div>
      {projects.length === 0 ? <p className="empty-message">No projects yet. Create a project above to get started.</p> : <div className="project-list">{projects.map((project) => <article className={`project-row ${activeProject?.id === project.id ? "project-row-active" : ""}`} key={project.id}><div><h3>{project.name}</h3><p className="muted">{project.description}</p></div><div className="project-actions"><button type="button" className="button-secondary" onClick={() => setActiveProjectId(project.id)}>Select</button><button type="button" disabled={busy} onClick={() => runProject(project)}>{busy && activeProjectId === project.id ? "Running…" : "Run workflow"}</button></div></article>)}</div>}
    </section>
    <section className="content-card workflow-guide"><h2>How the review works</h2><div className="workflow-steps"><article><span>01</span><div><h3>Describe the product</h3><p>Add its intended use and the requirements that matter. Specific dimensions, loads, environment, service life, and production quantity make the review more useful.</p></div></article><article><span>02</span><div><h3>Run the six agents</h3><p>The workflow organizes your brief into requirements, design, simulation planning, manufacturing, cost, and a report. AI availability can affect whether the local rules-based mode is used.</p></div></article><article><span>03</span><div><h3>Review assumptions and gaps</h3><p>Use the open questions and checks in each section to decide what needs measurement, supplier confirmation, or qualified engineering review.</p></div></article></div></section>
  </> : section === "requirements" ? <SectionPanel title="Requirements" intro="Functional and non-functional requirements, plus open questions." >{renderAgent("Requirements")}</SectionPanel>
    : section === "design" ? <SectionPanel title="Design" intro="Product-specific design recommendations and component concepts." >{renderAgent("Design")}</SectionPanel>
    : section === "simulation" ? <SectionPanel title="Simulation" intro="Review the screening assumptions. Generate an optional visual 3D concept mesh for the selected project." >{<>{renderAgent("Simulation")}<div className="content-card simulation-action"><div><h2>3D concept model</h2><p className="muted">Creates a downloadable TRELLIS GLB visual concept. It is not CAD or a validated simulation.</p><p className="muted">Selected project: <strong>{activeProject?.name || "None"}</strong></p></div><button type="button" disabled={busy || !activeProject} onClick={generate3d}>{busy ? "Generating…" : "Create 3D model (.glb)"}</button></div></>}</SectionPanel>
    : section === "manufacturing" ? <SectionPanel title="Manufacturing" intro="Suggested production approach and review steps." >{renderAgent("Manufacturing")}</SectionPanel>
    : section === "cost" ? <SectionPanel title="Cost" intro="Review the estimated prototype bill of materials in rupees, understand the main cost drivers, and adjust the assumptions behind a suggested product price." >{!execution || !costOutput ? <EmptyState text="Run the six-agent workflow from Home to generate a cost breakdown." onHome={() => selectSection("home")} /> : <><div className="content-card"><div className="cost-controls"><label>Illustrative USD → INR rate<input type="number" min="0.01" step="0.01" value={exchangeRate} onChange={(e) => setExchangeRate(Number(e.target.value) || 0)} /></label><label>Target markup (%)<input type="number" min="0" max="500" step="1" value={margin} onChange={(e) => setMargin(Number(e.target.value) || 0)} /></label></div><p className="cost-note">The exchange rate is editable and illustrative, not live. Markup is applied to the estimated cost (cost × (1 + markup)); it is not the same as gross margin.</p><div className="cost-table-wrap"><table className="cost-table"><thead><tr><th>Component / cost</th><th>Details</th><th>Estimated price (₹)</th></tr></thead><tbody>{costItems.map((item, index) => <tr key={`${item.item}-${index}`}><td>{item.item || `Item ${index + 1}`}</td><td>{item.detail || ""}</td><td>₹{((Number(item.estimated_cost_usd) || 0) * exchangeRate).toLocaleString("en-IN", { maximumFractionDigits: 2 })}</td></tr>)}<tr className="cost-total"><td colSpan={2}>Estimated prototype production cost</td><td>₹{productionCostInr.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</td></tr></tbody></table></div><div className="selling-price"><div><p className="muted">Suggested product price</p><strong>₹{suggestedPriceInr.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</strong></div><p className="muted">Estimated prototype cost plus {margin}% markup. This is a planning figure, not a market price or validated quote.</p></div><p className="cost-note">{String(costOutput.basis || "Illustrative estimate")}. Confirm costs with suppliers before making pricing decisions.</p></div>{Array.isArray(costOutput.cost_drivers) && <div className="content-card"><h2>What can change this estimate?</h2><ul className="detail-list">{(costOutput.cost_drivers as unknown[]).map((driver, index) => <li key={index}>{String(driver)}</li>)}</ul></div>}</>}</SectionPanel>
    : <SectionPanel title="Report" intro="Review the executive summary and recommended next steps, then download the complete report containing all six agent outputs." >{!execution ? <EmptyState text="Run the six-agent workflow from Home before downloading the report." onHome={() => selectSection("home")} /> : <>{getAgent("Report") && <div className="content-card"><AgentDetails agent={getAgent("Report")!} /></div>}<div className="content-card report-card"><div><p className="auth-eyebrow">COMPLETED EXECUTION</p><h2>{activeProject?.name || "Engineering concept report"}</h2><p className="muted">Execution #{execution.id} · {execution.status} · {execution.mode}</p><p>{execution.disclaimer}</p>{execution.provider_message && <p className="error">{execution.provider_message}</p>}</div><button type="button" disabled={busy} onClick={downloadReport}>{busy ? "Preparing…" : "Download full PDF report"}</button></div></>}</SectionPanel>;

  return <div className={`workspace-layout ${sidebarCollapsed ? "sidebar-collapsed" : ""} ${mobileSidebarOpen ? "mobile-sidebar-open" : ""}`}>
    {mobileSidebarOpen && <button className="sidebar-backdrop" aria-label="Close navigation menu" onClick={() => setMobileSidebarOpen(false)} />}
    <aside className="workspace-sidebar"><div className="sidebar-top"><a href="/" className="sidebar-brand"><span className="brand-mark">F</span><span className="sidebar-label">ForgeMind X</span></a><button type="button" className="sidebar-collapse" aria-label={sidebarCollapsed ? "Expand menu" : "Collapse menu"} onClick={() => setSidebarCollapsed((value) => !value)}><span aria-hidden="true">{sidebarCollapsed ? "›" : "‹"}</span></button></div>
      <button type="button" className="sidebar-new" onClick={() => selectSection("home")}><span className="sidebar-icon">＋</span><span className="sidebar-label">New project</span></button>
      <p className="sidebar-caption sidebar-label">WORKSPACE</p><div className="sidebar-menu">{sections.map((item) => <button type="button" className={`sidebar-item ${section === item.id ? "sidebar-item-active" : ""}`} key={item.id} onClick={() => selectSection(item.id)} title={sidebarCollapsed ? item.label : undefined}><span className="sidebar-icon">{item.icon}</span><span className="sidebar-label">{item.id === "home" ? "Home · Engineering workspace" : item.label}</span></button>)}</div>
      <div className="sidebar-bottom"><span className="sidebar-user-mark">{(email[0] || "U").toUpperCase()}</span><span className="sidebar-label sidebar-email" title={email}>{email}</span><button type="button" className="sidebar-signout" onClick={() => { localStorage.clear(); location.href = "/login" }} title={sidebarCollapsed ? "Sign out" : undefined}><span aria-hidden="true">↪</span><span className="sidebar-label">Sign out</span></button></div>
    </aside>
    <main className="workspace-main"><div className="workspace-topbar"><button type="button" className="mobile-menu-button" aria-label="Open navigation menu" onClick={() => setMobileSidebarOpen(true)}>☰</button><div className="breadcrumbs"><span>ForgeMind X</span><span aria-hidden="true">/</span><strong>{currentSection.label}</strong>{activeProject && section !== "home" && <><span aria-hidden="true">/</span><span>{activeProject.name}</span></>}</div><span className="workspace-user">{email}</span></div>
      {error && <div className="global-error" role="alert">{error}</div>}{content}
    </main>
  </div>;
}

function SectionPanel({ title, intro, children }: { title: string; intro: string; children: React.ReactNode }) {
  return <><section className="workspace-intro"><div><p className="auth-eyebrow">ENGINEERING WORKSPACE</p><h1>{title}</h1><p className="muted">{intro}</p></div></section>{children}</>;
}

function EmptyState({ text, onHome }: { text: string; onHome: () => void }) {
  return <div className="content-card empty-state"><div className="empty-state-icon">◌</div><h2>No output yet</h2><p className="muted">{text}</p><button type="button" onClick={onHome}>Go to Home</button></div>;
}

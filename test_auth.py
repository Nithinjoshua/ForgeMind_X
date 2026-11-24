"""Fast offline checks for ForgeMind X's local six-agent workflow."""
from backend.app.main import run_agents


def sample_project():
    return {
        "name": "Smart Agricultural Drone Frame",
        "description": "Lightweight agricultural drone frame for crop monitoring and precision agriculture",
        "requirements": ["Lightweight construction", "Durable frame", "Manufacturability"],
    }


def test_all_six_demo_agents_complete():
    result = run_agents(sample_project())
    assert result["mode"] == "rules-based demo"
    assert len(result["agents"]) == 6
    assert all(agent["status"] == "completed" for agent in result["agents"])


def test_cost_total_matches_items_and_carries_limitations():
    result = run_agents(sample_project())
    agents = {agent["name"]: agent["output"] for agent in result["agents"]}
    costs = agents["Cost"]
    assert costs["total_estimated_usd"] == sum(item["estimated_cost_usd"] for item in costs["items"])
    assert "not validated engineering" in result["disclaimer"]
    assert "no numerical stress" in agents["Simulation"]["estimate"]

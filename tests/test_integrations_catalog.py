"""Structural integrity for the integration catalog — the same source the
Integrations UI renders from. These tests encode, as a permanent regression
check, the manual audit already done by hand this session: every entry has
the fields the UI needs, every status is one of the five documented values,
and every "shipped" *connector-style* integration has a real backing file —
so a future edit can't silently claim something is live when the code was
never added (or got deleted).
"""

from __future__ import annotations

from pathlib import Path

from app.integrations_catalog import CATALOG, MVP_STACK

REPO_ROOT = Path(__file__).resolve().parent.parent
VALID_STATUSES = {"shipped", "import", "path", "planned", "commercial", "partial", "path+import"}

# Only the ids that are genuinely "a connector talking to an external vendor"
# — frameworks, AI providers, and file-format import adapters don't have a
# single connector file to check, so they're deliberately excluded here.
CONNECTOR_BACKED_IDS = {
    "wazuh": "app/wazuh.py",
    "thehive": "app/thehive.py",
    "sophos": "app/connectors/sophos.py",
    "crowdstrike": "app/connectors/crowdstrike.py",
    "sentinelone": "app/connectors/sentinelone.py",
    "defender_endpoint": "app/connectors/defender.py",
    "aws_security_hub": "app/connectors/aws_security_hub.py",
    "azure_defender": "app/connectors/azure_defender_cloud.py",
    "gcp_scc": "app/connectors/gcp_scc.py",
    "servicenow": "app/connectors/servicenow.py",
    "slack": "app/connectors/slack.py",
    "teams": "app/connectors/teams.py",
    "sonarqube": "app/connectors/sonarqube.py",
    "openaudit": "app/openaudit.py",
    "github": "app/connectors/github_webhook.py",
}


def test_every_entry_has_required_fields():
    for item in CATALOG:
        assert "id" in item and item["id"], f"entry missing id: {item}"
        assert "name" in item and item["name"], f"{item['id']} missing name"
        assert "category" in item and item["category"], f"{item['id']} missing category"
        assert "status" in item, f"{item['id']} missing status"


def test_every_status_is_a_known_value():
    bad = [item["id"] for item in CATALOG if item["status"] not in VALID_STATUSES]
    assert not bad, f"unknown status value(s) on: {bad}"


def test_no_duplicate_ids():
    ids = [item["id"] for item in CATALOG]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate catalog ids: {dupes}"


def test_shipped_connectors_have_real_backing_files():
    by_id = {item["id"]: item for item in CATALOG}
    missing = []
    for cid, rel_path in CONNECTOR_BACKED_IDS.items():
        entry = by_id.get(cid)
        assert entry is not None, f"expected catalog id '{cid}' not found — was it renamed?"
        if entry["status"] not in ("shipped",):
            continue  # only "shipped" is a live-code claim; import/path/planned aren't
        full = REPO_ROOT / rel_path
        if not full.exists():
            missing.append(f"{cid} claims shipped but {rel_path} does not exist")
    assert not missing, "\n".join(missing)


def test_burpsuite_is_shipped_with_import_hint():
    # Regression guard for this session's Burp Suite XML import addition —
    # if someone reverts the parser without updating the catalog, this fails
    # loudly instead of quietly lying to the UI.
    by_id = {item["id"]: item for item in CATALOG}
    assert "burpsuite" in by_id
    assert by_id["burpsuite"]["status"] == "shipped"
    assert "import" in by_id["burpsuite"].get("hint", "").lower()


def test_pulsedive_and_malwarebazaar_are_discoverable():
    # Regression guard for the earlier discoverability fix — these two are
    # real, working lookups that were previously invisible in the main
    # catalog the Integrations UI actually renders from.
    ids = {item["id"] for item in CATALOG}
    assert "pulsedive" in ids
    assert "malwarebazaar" in ids


def test_mvp_stack_entries_have_category_and_status():
    for item in MVP_STACK:
        assert item.get("category")
        assert item.get("tool")
        assert item.get("status")

"""Security knowledge graph: assets ↔ vulns ↔ risks ↔ controls ↔ evidence ↔ incidents."""

from __future__ import annotations

from typing import Any

from app.commercial_ext import list_evidence_links
from app.db import get_conn, new_id, now, row_to_dict
from app.enterprise import list_assets, list_remediations, list_risks, list_vulnerabilities
from app.ops import list_incidents


def ensure_graph_schema() -> None:
    c = get_conn()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS entity_links (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            src_type TEXT NOT NULL,
            src_id TEXT NOT NULL,
            dst_type TEXT NOT NULL,
            dst_id TEXT NOT NULL,
            relation TEXT NOT NULL DEFAULT 'related',
            notes TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            UNIQUE(user_id, src_type, src_id, dst_type, dst_id, relation)
        );
        """
    )
    c.commit()


def add_entity_link(
    user_id: str,
    *,
    src_type: str,
    src_id: str,
    dst_type: str,
    dst_id: str,
    relation: str = "related",
    notes: str = "",
) -> dict[str, Any]:
    ensure_graph_schema()
    lid = new_id()
    try:
        get_conn().execute(
            """
            INSERT INTO entity_links
            (id, user_id, src_type, src_id, dst_type, dst_id, relation, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lid,
                user_id,
                src_type[:40],
                src_id[:80],
                dst_type[:40],
                dst_id[:80],
                (relation or "related")[:60],
                (notes or "")[:500],
                now(),
            ),
        )
        get_conn().commit()
    except Exception:
        # Unique conflict — return existing
        row = get_conn().execute(
            """
            SELECT * FROM entity_links
            WHERE user_id = ? AND src_type = ? AND src_id = ? AND dst_type = ? AND dst_id = ? AND relation = ?
            """,
            (user_id, src_type[:40], src_id[:80], dst_type[:40], dst_id[:80], (relation or "related")[:60]),
        ).fetchone()
        return row_to_dict(row) or {"id": lid}
    row = get_conn().execute("SELECT * FROM entity_links WHERE id = ?", (lid,)).fetchone()
    return row_to_dict(row)  # type: ignore[return-value]


def list_entity_links(user_id: str) -> list[dict[str, Any]]:
    ensure_graph_schema()
    rows = get_conn().execute(
        "SELECT * FROM entity_links WHERE user_id = ? ORDER BY created_at DESC LIMIT 500",
        (user_id,),
    ).fetchall()
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


def build_knowledge_graph(user_id: str) -> dict[str, Any]:
    """Derive a correlated graph from registers + explicit links."""
    ensure_graph_schema()
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def node(kind: str, nid: str, label: str, meta: dict[str, Any] | None = None) -> str:
        key = f"{kind}:{nid}"
        if key not in nodes:
            nodes[key] = {"id": key, "type": kind, "ref": nid, "label": label, "meta": meta or {}}
        return key

    def edge(src: str, dst: str, relation: str) -> None:
        edges.append({"from": src, "to": dst, "relation": relation})

    assets = list_assets(user_id)
    asset_by_name = {(a.get("name") or "").lower(): a for a in assets}
    for a in assets:
        node("asset", a["id"], a.get("name") or "asset", {"type": a.get("asset_type"), "criticality": a.get("criticality")})

    vulns = list_vulnerabilities(user_id)
    for v in vulns:
        vk = node(
            "vuln",
            v["id"],
            f"{v.get('cve') or ''} {v.get('title') or ''}".strip()[:80],
            {"severity": v.get("severity"), "status": v.get("status")},
        )
        aname = (v.get("asset_name") or "").lower()
        if aname and aname in asset_by_name:
            edge(vk, node("asset", asset_by_name[aname]["id"], asset_by_name[aname].get("name") or aname), "affects")
        elif aname:
            ak = node("asset", f"name:{aname}", v.get("asset_name") or aname, {"synthetic": True})
            edge(vk, ak, "affects")
        cve = (v.get("cve") or "").upper()
        if cve.startswith("CVE-"):
            ck = node("cve", cve, cve)
            edge(vk, ck, "maps_to")

    risks = list_risks(user_id)
    for r in risks:
        rk = node(
            "risk",
            r["id"],
            (r.get("threat") or "risk")[:80],
            {"score": r.get("risk_score"), "status": r.get("status")},
        )
        aname = (r.get("asset_name") or "").lower()
        if aname and aname in asset_by_name:
            edge(rk, node("asset", asset_by_name[aname]["id"], asset_by_name[aname].get("name") or aname), "threatens")

    rems = list_remediations(user_id)
    for rem in rems:
        ck = node(
            "control",
            rem.get("control_id") or rem["id"],
            f"{rem.get('control_id')} — {rem.get('title')}"[:80],
            {"status": rem.get("status"), "owner": rem.get("owner")},
        )
        edge(ck, node("remediation", rem["id"], rem.get("title") or "task", {"status": rem.get("status")}), "tracked_by")

    for ev in list_evidence_links(user_id):
        ek = node(
            "evidence",
            ev["id"],
            ev.get("filename") or ev.get("file_id") or "evidence",
            {"status": ev.get("status"), "control_id": ev.get("control_id")},
        )
        cid = ev.get("control_id")
        if cid:
            edge(ek, node("control", cid, cid), "supports")
        if ev.get("remediation_id"):
            edge(ek, node("remediation", ev["remediation_id"], "remediation"), "attached_to")

    for inc in list_incidents(user_id):
        node(
            "incident",
            inc["id"],
            inc.get("title") or "incident",
            {"severity": inc.get("severity"), "status": inc.get("status")},
        )

    for link in list_entity_links(user_id):
        sk = node(link["src_type"], link["src_id"], f"{link['src_type']}:{link['src_id']}")
        dk = node(link["dst_type"], link["dst_id"], f"{link['dst_type']}:{link['dst_id']}")
        edge(sk, dk, link.get("relation") or "related")

    by_type: dict[str, int] = {}
    for n in nodes.values():
        by_type[n["type"]] = by_type.get(n["type"], 0) + 1

    return {
        "nodes": list(nodes.values()),
        "edges": edges[:2000],
        "counts": {"nodes": len(nodes), "edges": len(edges), "by_type": by_type},
    }

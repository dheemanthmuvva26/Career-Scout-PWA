"""
Career Scout — Streamlit Dashboard
Run: streamlit run app.py
Requires api.py to be running on localhost:8000
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Career Scout",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

API = "http://localhost:8000"

URGENCY_EMOJI = {"hot": "🔴", "active": "🟡", "aging": "⚪", "stale": "💀"}
STATUS_COLORS = {
    "new": "#4CAF50", "reviewed": "#2196F3", "applied": "#FF9800",
    "rejected": "#F44336", "expired": "#9E9E9E",
}
OUTCOME_EMOJI = {
    "pending": "⏳", "interview": "🎉", "offer": "🎊",
    "rejected": "👎", "ghosted": "👻",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def api(method: str, path: str, **kwargs):
    try:
        r = getattr(requests, method)(f"{API}{path}", timeout=10, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def score_bar(score: float) -> str:
    if score < 0:
        return "—"
    filled = int(round(score))
    return "★" * filled + "☆" * (5 - filled) + f" {score:.1f}"


def parse_json_field(val):
    if not val:
        return []
    if isinstance(val, list):
        return val
    try:
        return json.loads(val)
    except Exception:
        return []


# ── Tab: Pipeline ─────────────────────────────────────────────────────────────

def tab_pipeline():
    st.subheader("Job Pipeline")

    c1, c2, c3, c4 = st.columns(4)
    status_filter  = c1.selectbox("Status", ["all", "new", "reviewed", "applied", "rejected", "expired"], index=0)
    urgency_filter = c2.selectbox("Urgency", ["all", "hot", "active", "aging", "stale"], index=0)
    min_score      = c3.slider("Min score", 0.0, 5.0, 0.0, 0.5)
    limit          = c4.number_input("Rows", 20, 200, 50, 10)

    params = {"min_score": min_score, "limit": limit}
    if status_filter  != "all": params["status"]  = status_filter
    if urgency_filter != "all": params["urgency"] = urgency_filter

    jobs = api("get", "/jobs", params=params)
    if not jobs:
        st.info("No jobs found.")
        return

    # Build display dataframe
    rows = []
    for j in jobs:
        rows.append({
            "ID":       j["id"][:8],
            "_id":      j["id"],
            "Urgency":  URGENCY_EMOJI.get(j.get("urgency", ""), "⚪"),
            "Title":    j.get("title", ""),
            "Company":  j.get("company", ""),
            "Location": j.get("location", ""),
            "Score":    score_bar(j.get("score", -1)),
            "Status":   j.get("status", ""),
            "Outcome":  OUTCOME_EMOJI.get(j.get("outcome", "pending"), ""),
            "Posted":   (j.get("posted_date") or "")[:10],
            "Source":   j.get("source", ""),
        })
    df = pd.DataFrame(rows)

    # Click a row to open detail panel
    selected = st.dataframe(
        df.drop(columns=["_id"]),
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    if selected and selected.selection.rows:
        row_idx = selected.selection.rows[0]
        job_id  = df.iloc[row_idx]["_id"]
        _job_detail_panel(job_id)


def _job_detail_panel(job_id: str):
    job = api("get", f"/jobs/{job_id}")
    if not job:
        return

    st.divider()
    urg  = URGENCY_EMOJI.get(job.get("urgency", ""), "⚪")
    st.markdown(f"### {urg} {job['title']} @ {job['company']}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Score", score_bar(job.get("score", -1)))
    col2.metric("Status", job.get("status", ""))
    col3.metric("Outcome", job.get("outcome", ""))
    col4.metric("Source", job.get("source", ""))

    detail = {}
    try:
        sd = job.get("score_detail")
        detail = json.loads(sd) if isinstance(sd, str) else (sd or {})
    except Exception:
        pass

    if detail.get("fit_summary"):
        st.info(f"💡 {detail['fit_summary']}")

    if detail.get("matched_skills") or detail.get("missing_skills"):
        mc, xc = st.columns(2)
        mc.markdown("**✅ Matched skills**")
        for s in detail.get("matched_skills", []):
            mc.markdown(f"- {s}")
        xc.markdown("**❌ Missing skills**")
        for s in detail.get("missing_skills", []):
            xc.markdown(f"- {s}")

    with st.expander("Full job description"):
        st.write(job.get("description") or "No description stored.")

    if job.get("notes"):
        with st.expander("Notes"):
            st.text(job["notes"])

    st.divider()
    st.markdown("**Update status**")
    sc1, sc2, sc3, sc4, sc5, sc6 = st.columns(6)
    if sc1.button("✅ Apply",      key=f"apply_{job_id}"):
        api("post", f"/jobs/{job_id}/apply")
        st.rerun()
    if sc2.button("🎉 Interview",  key=f"iv_{job_id}"):
        api("post", f"/jobs/{job_id}/outcome", json={"outcome": "interview"})
        st.rerun()
    if sc3.button("🎊 Offer",      key=f"offer_{job_id}"):
        api("post", f"/jobs/{job_id}/outcome", json={"outcome": "offer"})
        st.rerun()
    if sc4.button("👎 Rejected",   key=f"rej_{job_id}"):
        api("post", f"/jobs/{job_id}/outcome", json={"outcome": "rejected"})
        st.rerun()
    if sc5.button("👻 Ghosted",    key=f"ghost_{job_id}"):
        api("post", f"/jobs/{job_id}/outcome", json={"outcome": "ghosted"})
        st.rerun()
    if sc6.button("📄 Forge PDF",  key=f"forge_{job_id}"):
        with st.spinner("Generating resume…"):
            result = api("post", f"/forge/{job_id}")
        if result and result.get("ok"):
            st.success(f"PDF saved: {result.get('pdf_path')}\nATS score: {result.get('ats_score')}%")
        elif result:
            st.error(result.get("error", "Forge failed"))

    note_text = st.text_input("Add note", key=f"note_{job_id}", placeholder="Type a note and press Enter")
    if note_text:
        api("post", f"/jobs/{job_id}/note", json={"text": note_text})
        st.rerun()


# ── Tab: Scout ────────────────────────────────────────────────────────────────

def tab_scout():
    st.subheader("Scout Control")

    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("🔍 Run Scout Now", type="primary", use_container_width=True):
            with st.spinner("Scout pipeline started…"):
                result = api("post", "/scout")
            if result:
                st.success("Scout started in background. Refresh in a few minutes.")

    last = api("get", "/scout/last") or {}
    with col2:
        if last.get("message"):
            st.info(last["message"])
        elif last:
            st.json(last)

    st.divider()
    st.markdown("**Scraper health**")
    health = api("get", "/scraper-health") or []
    if not health:
        st.info("No scraper health data yet.")
        return

    rows = []
    for h in health:
        failures = h.get("consecutive_failures", 0)
        status = "🟢 OK" if failures == 0 else ("🔴 FAILING" if failures >= 3 else "🟡 Warning")
        rows.append({
            "Scraper":    h.get("scraper", ""),
            "Status":     status,
            "Failures":   failures,
            "Last success": (h.get("last_success") or "Never")[:19],
            "Last error":   (h.get("last_error") or "")[:80],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ── Tab: Insights ─────────────────────────────────────────────────────────────

def tab_insights():
    st.subheader("Insights & Analytics")

    stats = api("get", "/stats") or {}

    # Application funnel
    st.markdown("#### Application funnel")
    funnel_cols = st.columns(5)
    labels = ["Total", "Applied", "Interviews", "Offers", "Unscored"]
    values = [
        stats.get("total", 0), stats.get("applied", 0),
        stats.get("interviews", 0), stats.get("offers", 0),
        stats.get("unscored", 0),
    ]
    for col, lbl, val in zip(funnel_cols, labels, values):
        col.metric(lbl, val)

    st.divider()

    # Jobs by score and urgency
    all_jobs = api("get", "/jobs", params={"min_score": -1, "limit": 1000}) or []
    if not all_jobs:
        st.info("No job data yet.")
        return

    df = pd.DataFrame(all_jobs)

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### Score distribution")
        scored = df[df["score"] >= 0]["score"]
        if not scored.empty:
            hist_data = pd.cut(scored, bins=[0, 1, 2, 3, 4, 5]).value_counts().sort_index()
            st.bar_chart(hist_data.rename(index=str))
        else:
            st.info("No scored jobs yet.")

    with col_r:
        st.markdown("#### Jobs by urgency")
        if "urgency" in df.columns:
            urg_counts = df["urgency"].value_counts()
            st.bar_chart(urg_counts)

    st.divider()
    st.markdown("#### Missing skills frequency")
    skill_freq: dict[str, int] = {}
    for _, row in df.iterrows():
        try:
            detail = json.loads(row.get("score_detail") or "{}")
            for s in detail.get("missing_skills", []):
                key = s.lower().strip()
                skill_freq[key] = skill_freq.get(key, 0) + 1
        except Exception:
            pass
    if skill_freq:
        top = sorted(skill_freq.items(), key=lambda x: -x[1])[:15]
        skill_df = pd.DataFrame(top, columns=["Skill", "Count"]).set_index("Skill")
        st.bar_chart(skill_df)
    else:
        st.info("No missing-skill data yet.")

    st.divider()
    st.markdown("#### Response rate by source")
    applied_df = df[df["status"] == "applied"]
    if not applied_df.empty:
        by_source: dict[str, dict] = {}
        for _, row in applied_df.iterrows():
            src = row.get("source") or "unknown"
            by_source.setdefault(src, {"applied": 0, "responded": 0})
            by_source[src]["applied"] += 1
            if row.get("outcome") in ("interview", "offer"):
                by_source[src]["responded"] += 1
        rate_rows = [
            {"Source": s, "Applied": d["applied"], "Responded": d["responded"],
             "Rate": f"{d['responded']/d['applied']:.0%}" if d["applied"] else "0%"}
            for s, d in sorted(by_source.items(), key=lambda x: -x[1]["applied"])
        ]
        st.dataframe(pd.DataFrame(rate_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No applied jobs yet.")


# ── Tab: Companies & Roles ────────────────────────────────────────────────────

def tab_companies_roles():
    st.subheader("Companies & Roles")

    left, right = st.columns(2)

    # ── Companies ──
    with left:
        st.markdown("#### Watched companies")
        companies = api("get", "/companies") or []
        if companies:
            for c in companies:
                cols = st.columns([3, 1, 1])
                cols[0].write(f"**{c['name']}**")
                cols[1].write(f"Signal: {c.get('jobs_this_week', 0)}")
                if cols[2].button("🚫 Blacklist", key=f"bl_{c['id']}"):
                    api("post", "/companies/blacklist", params={"name": c["name"]})
                    st.rerun()
        else:
            st.info("No companies yet — add one below.")

        st.divider()
        st.markdown("**Add company**")
        with st.form("add_company"):
            co_name   = st.text_input("Name")
            co_url    = st.text_input("Careers URL (optional)")
            co_slug   = st.text_input("LinkedIn slug (optional)")
            if st.form_submit_button("Add"):
                if co_name:
                    api("post", "/companies", json={
                        "name": co_name, "careers_url": co_url, "linkedin_slug": co_slug
                    })
                    st.rerun()

    # ── Roles ──
    with right:
        st.markdown("#### Watched roles")
        roles = api("get", "/roles") or []
        if roles:
            for r in roles:
                kw = parse_json_field(r.get("keywords"))
                st.write(f"**{r['title']}** — {', '.join(kw[:4])}")
        else:
            st.info("No roles yet — add one below.")

        st.divider()
        st.markdown("**Add role**")
        with st.form("add_role"):
            ro_title = st.text_input("Role title")
            ro_kw    = st.text_input("Keywords (comma-separated)")
            if st.form_submit_button("Add"):
                if ro_title:
                    keywords = [k.strip() for k in ro_kw.split(",") if k.strip()]
                    api("post", "/roles", json={"title": ro_title, "keywords": keywords})
                    st.rerun()


# ── Tab: Resumes ──────────────────────────────────────────────────────────────

def tab_resumes():
    st.subheader("Generated Resumes")

    resumes_dir = Path("shared/resumes")
    if not resumes_dir.exists() or not list(resumes_dir.glob("*.pdf")):
        st.info("No resumes generated yet. Use /resume <id> in Telegram or click 'Forge PDF' on a job.")
        return

    pdfs = sorted(resumes_dir.glob("*.pdf"), key=lambda f: f.stat().st_mtime, reverse=True)
    rows = []
    for pdf in pdfs:
        stat  = pdf.stat()
        parts = pdf.stem.split("_")
        rows.append({
            "_path":    str(pdf),
            "File":     pdf.name,
            "Size":     f"{stat.st_size // 1024} KB",
            "Created":  datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        })

    df = pd.DataFrame(rows)
    selected = st.dataframe(
        df.drop(columns=["_path"]),
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    if selected and selected.selection.rows:
        row_idx  = selected.selection.rows[0]
        pdf_path = df.iloc[row_idx]["_path"]

        col1, col2 = st.columns([1, 1])
        with open(pdf_path, "rb") as f:
            col1.download_button(
                "⬇️ Download PDF",
                data=f,
                file_name=Path(pdf_path).name,
                mime="application/pdf",
                use_container_width=True,
            )
        if col2.button("🗑️ Delete", use_container_width=True):
            Path(pdf_path).unlink(missing_ok=True)
            st.rerun()


# ── App shell ─────────────────────────────────────────────────────────────────

def main():
    st.title("🎯 Career Scout")

    # API health check
    try:
        requests.get(f"{API}/health", timeout=2)
        api_ok = True
    except Exception:
        api_ok = False

    if not api_ok:
        st.error("⚠️ API server not reachable. Run: `python api.py`")
        st.stop()

    tabs = st.tabs(["📋 Pipeline", "🔍 Scout", "📊 Insights", "🏢 Companies & Roles", "📄 Resumes"])
    with tabs[0]: tab_pipeline()
    with tabs[1]: tab_scout()
    with tabs[2]: tab_insights()
    with tabs[3]: tab_companies_roles()
    with tabs[4]: tab_resumes()


if __name__ == "__main__":
    main()

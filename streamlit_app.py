"""Streamlit interface for NaturalSentinel local document analysis."""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path

from naturalsentinel.cli import (
    SUPPORTED_SUFFIXES,
    analyze_local_documents,
    build_provider,
)
from naturalsentinel.models import RegulatoryDomain


def _save_uploaded_files(
    uploaded_files,
) -> tuple[tempfile.TemporaryDirectory, list[str]]:
    tmpdir = tempfile.TemporaryDirectory()
    paths: list[str] = []
    for uploaded in uploaded_files:
        name = Path(uploaded.name).name
        suffix = Path(name).suffix.lower()
        if suffix and suffix not in SUPPORTED_SUFFIXES:
            raise ValueError(
                f"Unsupported file type for {name}: {suffix}. Supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
            )
        target = Path(tmpdir.name) / name
        target.write_bytes(uploaded.getvalue())
        paths.append(str(target))
    return tmpdir, paths


def _render_summary(st, results: list[dict]) -> None:
    severities = Counter(item["impact"]["severity"] for item in results)
    deadlines = sum(1 for item in results if item["impact"].get("compliance_deadline"))
    st.metric("Documents analyzed", len(results))
    st.metric("Deadlines found", deadlines)
    st.metric(
        "Critical / High", severities.get("critical", 0) + severities.get("high", 0)
    )


def main() -> None:
    import streamlit as st

    st.set_page_config(
        page_title="NaturalSentinel",
        page_icon="🛰️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("🛰️ NaturalSentinel")
    st.caption(
        "Upload regulatory or policy documents, analyze them, and review structured outputs."
    )

    with st.sidebar:
        st.header("Analysis settings")
        provider_name = st.selectbox(
            "Provider", ["mock", "anthropic", "openai", "gemini", "ollama"], index=0
        )
        model_override = st.text_input("Model override (optional)")
        domain = st.selectbox(
            "Document domain", [d.value for d in RegulatoryDomain], index=0
        )
        memory_db = st.text_input("Memory DB path (optional)", value="")
        st.markdown("**Supported file types**")
        st.code(", ".join(sorted(SUPPORTED_SUFFIXES)))

    uploaded_files = st.file_uploader(
        "Upload one or more files",
        type=[suffix.lstrip(".") for suffix in sorted(SUPPORTED_SUFFIXES)],
        accept_multiple_files=True,
        help="Upload text, markdown, JSON, or HTML-like source documents for analysis.",
    )

    analyze_clicked = st.button(
        "Analyze documents", type="primary", disabled=not uploaded_files
    )

    if analyze_clicked and uploaded_files:
        try:
            provider = build_provider(provider_name, model_override or None)
            tmpdir, paths = _save_uploaded_files(uploaded_files)
            with st.spinner("Analyzing uploaded documents..."):
                results = analyze_local_documents(
                    provider=provider,
                    domain=RegulatoryDomain(domain),
                    input_paths=paths,
                    input_dir=None,
                    memory_db=memory_db or None,
                )

            st.success(f"Analyzed {len(results)} document(s).")

            summary_cols = st.columns(3)
            with summary_cols[0]:
                _render_summary(st, results)
            with summary_cols[1]:
                sev_counts = Counter(item["impact"]["severity"] for item in results)
                st.subheader("Severity mix")
                st.json(dict(sev_counts))
            with summary_cols[2]:
                st.subheader("Documents")
                st.dataframe(
                    [
                        {
                            "title": item["filing"]["title"],
                            "severity": item["impact"]["severity"],
                            "deadline": item["impact"].get("compliance_deadline"),
                            "source": Path(item["filing"]["source_url"]).name
                            if not item["filing"]["source_url"].startswith("file://")
                            else Path(item["filing"]["source_url"][7:]).name,
                        }
                        for item in results
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

            st.divider()
            tabs = st.tabs(
                [
                    item["filing"]["title"][:40] or f"Document {i + 1}"
                    for i, item in enumerate(results)
                ]
            )
            for tab, item in zip(tabs, results):
                with tab:
                    left, right = st.columns([1, 1])
                    with left:
                        st.subheader("Impact summary")
                        st.write(item["impact"]["risk_summary"])
                        st.json(item["impact"])
                    with right:
                        st.subheader("Filing metadata")
                        st.json(
                            {k: v for k, v in item["filing"].items() if k != "raw_text"}
                        )
                        with st.expander("Raw text preview"):
                            st.text(item["filing"].get("raw_text", "")[:5000])

            st.divider()
            st.subheader("Full JSON output")
            st.download_button(
                "Download analysis JSON",
                data=json.dumps(results, indent=2),
                file_name="naturalsentinel-analysis.json",
                mime="application/json",
            )
            st.code(json.dumps(results, indent=2), language="json")

            tmpdir.cleanup()
        except Exception as exc:
            st.error(str(exc))

    elif not uploaded_files:
        st.info(
            "Upload files to start. This UI is best for clean document review and local analysis workflows."
        )


if __name__ == "__main__":
    main()

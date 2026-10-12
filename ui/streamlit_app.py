import json
from pathlib import Path
from uuid import uuid4

import httpx
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Enterprise AI Chatbot", layout="wide")
API_URL = st.sidebar.text_input("API URL", "http://localhost:8000")
st.title("Enterprise AI Chatbot")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_paths" not in st.session_state:
    st.session_state.uploaded_paths = []

with st.sidebar:
    automatic_mode = st.toggle("Automatic Mode", value=False,
        help="Investigate independently without clarification questions. Database requests inspect the live schema and validate generated SQL.")
    if st.button("New Chat", use_container_width=True):
        st.session_state.session_id = str(uuid4())
        st.session_state.messages = []
        st.session_state.uploaded_paths = []
        st.session_state.pop("last_response", None)
        st.rerun()
    st.caption(f"Chat: {st.session_state.session_id[:8]}")
    st.subheader("Files")
    uploads = st.file_uploader("Upload documents", key=f"uploads-{st.session_state.session_id}", accept_multiple_files=True, type=["pdf", "txt", "md", "docx", "csv", "xlsx"])
    if st.button("Upload", use_container_width=True) and uploads:
        files = [("files", (upload.name, upload.getvalue(), upload.type or "application/octet-stream")) for upload in uploads]
        response = httpx.post(f"{API_URL}/upload", files=files, timeout=60)
        response.raise_for_status()
        st.session_state.uploaded_paths.extend(response.json()["files"])
    if st.session_state.uploaded_paths and st.button("Ingest to RAG", use_container_width=True):
        response = httpx.post(f"{API_URL}/ingest", params={"session_id": st.session_state.session_id}, json=st.session_state.uploaded_paths, timeout=60)
        response.raise_for_status()
        st.success(f"Ingested {response.json()['chunks']} chunks")
    for path in st.session_state.uploaded_paths:
        st.caption(Path(path).name)

    st.subheader("Diagnostics")
    if st.button("Check SQL", use_container_width=True):
        try:
            config_response = httpx.get(f"{API_URL}/config/status", timeout=10)
            sql_response = httpx.get(f"{API_URL}/sql/health", timeout=20)
            if config_response.status_code == 404 or sql_response.status_code == 404:
                health_response = httpx.get(f"{API_URL}/health", timeout=10)
                health_response.raise_for_status()
                st.warning("The API is running, but diagnostic routes are missing. Restart FastAPI from this project folder.")
                st.session_state.config_status = {"health": health_response.json()}
                st.session_state.sql_health = {
                    "connected": False,
                    "error": "Missing /config/status or /sql/health. Restart uvicorn so it loads the latest api/main.py.",
                }
            else:
                config_response.raise_for_status()
                sql_response.raise_for_status()
                st.session_state.config_status = config_response.json()
                st.session_state.sql_health = sql_response.json()
        except Exception as exc:
            st.error(str(exc))
    if "sql_health" in st.session_state:
        sql_health = st.session_state.sql_health
        st.metric("SQL connected", "Yes" if sql_health.get("connected") else "No")
        st.caption(f"Host: {sql_health.get('host')}")
        st.caption(f"Database: {sql_health.get('database')}")
        st.caption(f"Driver: {sql_health.get('driver')}")
        if sql_health.get("error"):
            st.code(sql_health["error"])

left, right = st.columns([0.58, 0.42])

with left:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    prompt = st.chat_input("Ask about documents, SQL Server, or enterprise knowledge")
    clarification_data = st.session_state.get("last_response", {})
    choices = clarification_data.get("clarification_options", [])
    if not automatic_mode and clarification_data.get("status") == "needs_clarification" and choices:
        with st.form(f"clarification-{len(st.session_state.messages)}"):
            replies = []
            for i, item in enumerate(choices):
                question = item["question"]
                options = item.get("options", [])
                if options:
                    selected = st.radio(question, options + ["Other / enter my own answer"], index=None, key=f"choice-{len(st.session_state.messages)}-{i}")
                    custom = st.text_input("Custom answer (if Other selected)", key=f"custom-{len(st.session_state.messages)}-{i}")
                    reply = custom.strip() if selected == "Other / enter my own answer" else selected
                else:
                    reply = st.text_input(question, key=f"subjective-{len(st.session_state.messages)}-{i}").strip()
                replies.append((question, reply))
            if st.form_submit_button("Submit clarification"):
                if all(reply for _, reply in replies):
                    prompt = "\n".join(f"{question}: {reply}" for question, reply in replies)
                else:
                    st.warning("Please answer each clarification before submitting.")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        payload = {"query": prompt, "session_id": st.session_state.session_id, "files": st.session_state.uploaded_paths, "automatic_mode": automatic_mode}
        st.markdown("**Live Agent Progress**")
        current_step = st.empty()
        tool_summary = st.empty()
        progress_table = st.empty()
        progress_rows = {}
        try:
            data = None
            with httpx.stream("POST", f"{API_URL}/chat/stream", json=payload, timeout=httpx.Timeout(30, read=240)) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    event = json.loads(line)
                    if event.get("type") == "progress":
                        progress_rows[event["step"]] = {"Step": event["step"], "Status": event["status"], "Details": event.get("detail", "")}
                        if event["status"] == "In Progress":
                            current_step.info(f"Currently: {event['step']} — {event.get('detail', '')}")
                        if "tools" in event:
                            tool_summary.markdown("**" + event["tool_mode"] + "**\n\n" + "\n\n".join(f"- **{item['tool']}**: {item['purpose']}" for item in event["tools"]))
                        progress_table.dataframe(pd.DataFrame(progress_rows.values()), hide_index=True, use_container_width=True)
                    elif event.get("type") == "result":
                        data = event["data"]
                    elif event.get("type") == "error":
                        raise ValueError("Stream failed")
            if not isinstance(data, dict) or not isinstance(data.get("answer"), str):
                raise ValueError("Invalid chat response")
            st.session_state.messages.append({"role": "assistant", "content": data["answer"]})
            st.session_state.last_response = data
        except (httpx.HTTPError, ValueError):
            st.session_state.messages.append({"role": "assistant", "content": "The request could not be completed. Check that the API is running, then retry your question. Your chat is still available."})
        st.rerun()

with right:
    data = st.session_state.get("last_response")
    if data:
        tabs = st.tabs(["Timeline", "Context", "SQL", "Metrics", "Logs"])
        with tabs[0]:
            progress_events = [item for item in data["timeline"] if item.get("type") == "progress"]
            if progress_events:
                latest = {item["step"]: item for item in progress_events}
                st.dataframe(pd.DataFrame([{"Step": item["step"], "Status": item["status"], "Details": item.get("detail", "")} for item in latest.values()]), hide_index=True, use_container_width=True)
            st.json(data["timeline"])
        with tabs[1]:
            contexts = []
            for result in data["tool_results"]:
                output = result.get("output") or {}
                if isinstance(output, dict) and isinstance(output.get("contexts", []), list):
                    contexts.extend(output.get("contexts", []))
            st.dataframe(pd.DataFrame(contexts))
            st.json(data["citations"])
        with tabs[2]:
            sql_outputs = [r for r in data["tool_results"] if r["tool"] == "sql"]
            for result in sql_outputs:
                output = result.get("output")
                if result.get("success") and isinstance(output, dict) and "column_count" in output:
                    st.code(output["sql"], language="sql")
                    st.caption(f"Total rows: {output['row_count']} · Total columns: {output['column_count']}")
                    st.dataframe(pd.DataFrame(output["rows"], columns=output["columns"]), hide_index=True)
            st.json(sql_outputs)
        with tabs[3]:
            st.json(data["metrics"])
            if st.button("Metrics Details"):
                st.info("Quality scores are currently heuristic indicators, not verified accuracy. Response similarity is unavailable without a reference answer. Confidence is a model self-assessment, not a guarantee.")
                descriptions = {
                    "context_precision": "Share of context relevant to the request",
                    "context_recall": "Coverage of information needed to answer",
                    "answer_relevancy": "How directly the answer addresses the request",
                    "faithfulness": "Consistency with supplied evidence",
                    "groundedness": "Support for claims in the evidence",
                    "response_similarity": "Similarity to a reference answer (currently unavailable)",
                    "retrieval_precision": "Share of retrieved items that are relevant",
                    "retrieval_recall": "Share of necessary evidence retrieved",
                    "tool_success_rate": "Share of tool calls that succeeded; no calls currently reports 100%",
                    "correctness": "Estimated factual correctness",
                    "completeness": "Coverage of the requested answer",
                    "relevance": "How well the answer addresses the topic",
                }
                for name, explanation in descriptions.items():
                    st.markdown(f"**{name}**: {explanation}. Higher is better; lower suggests gaps. Quality scores use a 0–1 scale.")
                st.markdown("**hallucination_score**: Estimated unsupported claims; high is worse, low is better (heuristic).\n\n**latency_ms**: Response time; high means slower, low means faster.\n\n**input_tokens / output_tokens / total_tokens**: Tokens sent, generated, and combined across this request. High means more usage and usually higher cost; low means less usage, not necessarily greater accuracy.\n\n**llm_calls**: Model calls for this request. High means more work and usually higher cost; low means fewer calls.\n\n**tokens_estimated**: True means character-based estimates were used for at least one call; false means provider counts were available.")
            st.metric("Tool success rate", f"{data['metrics']['tool_success_rate']:.0%}")
            st.metric("Latency ms", f"{data['metrics']['latency_ms']:.0f}")
            st.json(data["judge"])
        with tabs[4]:
            st.code(json.dumps(data, indent=2), language="json")

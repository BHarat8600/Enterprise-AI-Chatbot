"""Connection controls and a direct executor, kept separate from chat history."""

import hashlib
import json
from urllib.parse import urlencode

import httpx
import pandas as pd
import streamlit as st


@st.cache_data(ttl=60, show_spinner=False)
def load_defaults(api_url):
    try:
        response = httpx.get(f"{api_url}/database/defaults", timeout=1)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        return {}


def connection_panel(api_url):
    st.subheader("Database connection")
    label = st.selectbox("Database engine", ["SQL Server", "PostgreSQL"])
    engine = "sqlserver" if label == "SQL Server" else "postgresql"
    defaults = load_defaults(api_url).get(engine, {})
    use_env = st.checkbox("Use .env defaults", value=True, key="use_env_database")
    config = {"engine": engine}
    with st.expander("Connection settings", expanded=not use_env):
        if not defaults:
            st.caption(
                "Defaults are resolved by the API. Start the API and reload defaults to display them here."
            )
        elif defaults.get("password_configured"):
            st.caption("A password is configured in .env; it is never displayed here.")
        if st.button("Reload defaults"):
            load_defaults.clear()
            st.rerun()
        host = st.text_input(
            "Host / server",
            value=defaults.get("host", ""),
            key=f"db-host-{engine}",
            disabled=use_env,
        )
        database = st.text_input(
            "Database",
            value=defaults.get("database", ""),
            key=f"db-name-{engine}",
            disabled=use_env,
        )
        username = st.text_input(
            "Username",
            value=defaults.get("username", ""),
            key=f"db-user-{engine}",
            disabled=use_env,
        )
        password = st.text_input(
            "Password override",
            type="password",
            key=f"db-password-{engine}",
            disabled=use_env,
            help="Blank keeps the .env password only for the same connection identity. Enter a password for a different server, database or username.",
        )
        if engine == "sqlserver":
            methods = ["Windows / Integrated", "Username / Password", "ODBC DSN"]
            default_method = (
                2 if defaults.get("dsn") else (0 if defaults.get("trusted_connection", True) else 1)
            )
            auth = st.selectbox("Authentication", methods, index=default_method, disabled=use_env)
            driver = st.text_input(
                "ODBC driver",
                value=defaults.get("driver", "ODBC Driver 18 for SQL Server"),
                disabled=use_env,
            )
            dsn = st.text_input(
                "ODBC DSN", value=defaults.get("dsn", ""), disabled=use_env or auth != "ODBC DSN"
            )
            encrypt = st.checkbox(
                "Encrypt connection", value=defaults.get("encrypt", False), disabled=use_env
            )
            if not use_env:
                config.update(
                    host=host,
                    database=database,
                    username=username,
                    driver=driver,
                    trusted_connection=auth == "Windows / Integrated",
                    dsn=dsn if auth == "ODBC DSN" else "",
                    encrypt=encrypt,
                )
        else:
            port = st.number_input(
                "Port",
                min_value=1,
                max_value=65535,
                value=defaults.get("port", 5432),
                disabled=use_env,
            )
            modes = ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]
            default_ssl = defaults.get("sslmode", "prefer")
            ssl = st.selectbox(
                "TLS / SSL mode",
                modes,
                index=modes.index(default_ssl) if default_ssl in modes else 2,
                disabled=use_env,
            )
            if not use_env:
                config.update(
                    host=host, database=database, username=username, port=port, sslmode=ssl
                )
        if not use_env and password:
            config["password"] = password
        if st.button("Test connection", use_container_width=True):
            try:
                response = httpx.post(f"{api_url}/database/test", json=config, timeout=30)
                response.raise_for_status()
                if response.json().get("connected"):
                    st.success("Connected")
                else:
                    st.error(response.json().get("error", "Connection failed"))
            except (httpx.HTTPError, ValueError):
                st.error("Could not test the connection. Check that the API is running.")
    return config


def executor_panel(api_url, data, config, session_id):
    queries = [
        r
        for r in data.get("tool_results", [])
        if r.get("tool") in {"sql", "postgresql"}
        and isinstance(r.get("output"), dict)
        and r["output"].get("sql")
    ]
    if not queries:
        return
    result = queries[-1]
    output = result["output"]
    bound = st.session_state.get("query_database", config)
    st.markdown("**Query executor**")
    st.caption(
        "Results go directly to this table, never to the LLM. Edit SQL directly or optionally request a change."
    )
    signature = hashlib.sha256(
        (output["sql"] + json.dumps(bound, sort_keys=True) + session_id).encode()
    ).hexdigest()
    sql = st.text_area(
        "SQL to execute (editable)", value=output["sql"], height=240, key=f"sql-editor-{signature}"
    )
    changes = st.text_area(
        "Optional changes to logic or columns",
        key=f"sql-changes-{signature}",
        placeholder="Example: group by region, add net revenue, exclude cancelled records",
    )
    mismatch = bound != config
    if mismatch:
        st.warning(
            "Connection settings changed. Generate a new query for the selected connection before executing or requesting changes."
        )
    if st.button("Update query", disabled=not changes.strip() or mismatch):
        st.session_state.query_revision = f"Revise the following query using the verified schema. Apply only these requested changes: {changes}\nCurrent SQL:\n{sql}"
        st.rerun()
    key = hashlib.sha256((signature + sql).encode()).hexdigest()
    if st.button("Execute", type="primary", disabled=mismatch):
        st.session_state.pop("database_execution", None)
        try:
            with st.spinner("Executing query and preparing the full report…"):
                response = httpx.post(
                    f"{api_url}/database/execute",
                    json={"session_id": session_id, "sql": sql, "database": bound},
                    timeout=240,
                )
                response.raise_for_status()
                execution = response.json()
                st.session_state.database_execution = {"key": key, "data": execution}
        except (httpx.HTTPError, ValueError):
            st.error(
                "Execution failed. Check your SQL, connection and permissions. Only a single read-only SELECT is allowed."
            )
    execution = st.session_state.get("database_execution", {})
    if execution.get("key") == key:
        report = execution["data"]
        st.caption(
            f"Total rows: {report['row_count']} · Total columns: {report['column_count']} · LLM tokens: 0"
        )
        st.dataframe(
            pd.DataFrame(report["rows"], columns=report["columns"]),
            hide_index=True,
            use_container_width=True,
        )
        if not report["rows"]:
            st.info("No rows matched the query.")
        params = urlencode({"session_id": session_id})
        st.link_button(
            "Download all report (CSV)",
            f"{api_url}/database/reports/{report['report_id']}?{params}",
        )
        st.caption(
            "The CSV contains all rows from this execution. Download within one hour; reports are local to the API process."
        )

# import os
# import json
# import sqlite3
# import tempfile
# from pathlib import Path
# import streamlit as st
# import pandas as pd
# from langchain_groq import ChatGroq
# from langchain_core.messages import SystemMessage, HumanMessage
# from dotenv import load_dotenv

# load_dotenv()

# try:
#     import tabulate
#     HAS_TABULATE = True
# except ImportError:
#     HAS_TABULATE = False


# DEFAULT_MODEL = "llama-3.3-70b-versatile"
# MAX_ROWS = 50


# @st.cache_resource
# def get_llm(groq_api_key: str):
#     if not groq_api_key:
#         raise ValueError("Groq API key not provided. Set in sidebar or env GROQ_API_KEY.")
#     return ChatGroq(
#         model=DEFAULT_MODEL,
#         temperature=0,
#         streaming=False,
#         groq_api_key=groq_api_key,
#     )


# # ── DB Helpers ────────────────────────────────────────────────────────────────

# def save_uploaded_db(uploaded_file) -> str:
#     uploaded_file.seek(0)
#     with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
#         tmp.write(uploaded_file.read())
#         tmp.flush()
#         return tmp.name


# def get_db_path(uploaded_file) -> str | None:
#     if uploaded_file is not None:
#         return save_uploaded_db(uploaded_file)
#     default_db = Path(__file__).parent / "students.db"
#     if default_db.exists():
#         return str(default_db)
#     return None


# def connect_db(db_path: str) -> sqlite3.Connection:
#     conn = sqlite3.connect(db_path)
#     conn.row_factory = sqlite3.Row
#     return conn


# def get_schema(conn: sqlite3.Connection) -> dict:
#     schema = {}
#     cur = conn.cursor()
#     tables = cur.execute(
#         "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
#     ).fetchall()
#     for (table_name,) in tables:
#         cols = cur.execute(f"PRAGMA table_info({table_name});").fetchall()
#         schema[table_name] = [c[1] for c in cols]
#     return schema


# def schema_to_text(schema: dict) -> str:
#     lines = []
#     for table, cols in schema.items():
#         preview = ", ".join(cols[:10])
#         extra = " ..." if len(cols) > 10 else ""
#         lines.append(f"- {table}({preview}{extra})")
#     return "\n".join(lines)


# # ── Agent Logic ───────────────────────────────────────────────────────────────

# def ask_llm_for_sql(llm, question: str, schema_text: str) -> dict:
#     system = SystemMessage(
#         content=(
#             "You are 'DataGenie', a helpful SQL expert for a SQLite database.\n"
#             "You MUST use only the tables and columns listed in SCHEMA below.\n"
#             "Write ONLY safe SELECT queries (no INSERT/UPDATE/DELETE, no PRAGMA, no DROP, etc.).\n"
#             "If the question is vague, make a reasonable assumption and mention it in 'thinking'.\n"
#             "ALWAYS add a LIMIT clause (e.g., LIMIT 20) if the user does not specify one.\n"
#             "Return your answer as strict JSON with keys: sql, thinking, followups.\n"
#             "followups = a short list of 2 extra questions the user might like.\n"
#             f"SCHEMA:\n{schema_text}"
#         )
#     )
#     user = HumanMessage(
#         content=(
#             f"User question: {question}\n\n"
#             "Reply ONLY in JSON like this:\n"
#             '{"sql":"...","thinking":"...","followups":["...","..."]}'
#         )
#     )
#     resp = llm.invoke([system, user])
#     text = resp.content.strip()
#     try:
#         start = text.index("{")
#         end = text.rindex("}") + 1
#         data = json.loads(text[start:end])
#     except Exception:
#         data = {
#             "sql": "SELECT 'Sorry, I could not generate SQL' AS error",
#             "thinking": "I failed to follow my own JSON format.",
#             "followups": [
#                 "Try asking a simpler question.",
#                 "Ask me what tables exist and what they contain.",
#             ],
#         }
#     return data


# def run_sql(conn: sqlite3.Connection, sql: str) -> pd.DataFrame | str:
#     sql_clean = sql.strip().rstrip(";")
#     if not sql_clean.lower().startswith("select"):
#         return "Blocked: Only SELECT queries are allowed."
#     if "limit" not in sql_clean.lower():
#         sql_to_run = f"{sql_clean} LIMIT {MAX_ROWS}"
#     else:
#         sql_to_run = sql_clean
#     try:
#         return pd.read_sql_query(sql_to_run, conn)
#     except Exception as e:
#         return f"SQL Error: {e}"


# def build_final_answer(llm, question: str, sql: str, result) -> str:
#     if isinstance(result, pd.DataFrame):
#         if result.empty:
#             result_text = "The query returned 0 rows."
#         else:
#             preview = result.head(min(5, len(result)))
#             result_text = "Here is a preview of the result (up to 5 rows):\n"
#             result_text += (
#                 preview.to_markdown(index=False) if HAS_TABULATE
#                 else preview.to_string(index=False)
#             )
#     else:
#         result_text = str(result)

#     system = SystemMessage(
#         content=(
#             "You are 'DataGenie', an AI tutor.\n"
#             "Explain what the SQL result means in simple, encouraging language.\n"
#             "If there was an error, explain it gently and hint how to fix the query.\n"
#             "End with one short playful line (e.g. about being a data genie)."
#         )
#     )
#     user = HumanMessage(
#         content=f"User question: {question}\nSQL used:\n{sql}\n\nResult summary:\n{result_text}"
#     )
#     resp = llm.invoke([system, user])
#     return resp.content.strip()


# def render_assistant_turn(turn: dict):
#     """Re-render a saved assistant turn from history (including the dataframe)."""
#     with st.chat_message("assistant"):
#         if turn.get("thinking"):
#             st.markdown(f"🧠 **Agent's thought bubble:** {turn['thinking']}")
#         if turn.get("sql"):
#             st.markdown("**Generated SQL:**")
#             st.markdown(f"```sql\n{turn['sql']}\n```")
#         # Re-render the saved dataframe if present
#         if turn.get("df") is not None:
#             df = turn["df"]
#             if df.empty:
#                 st.info("Query ran successfully but returned **0 rows**.")
#             else:
#                 st.dataframe(df, width="stretch")
#         elif turn.get("result_text"):
#             result_str = turn["result_text"]
#             if result_str.startswith("SQL Error") or result_str.startswith("Blocked"):
#                 st.error(result_str)
#             else:
#                 st.write(result_str)
#         st.markdown("---")
#         st.markdown(turn["content"])  # final_answer


# def run_pipeline(llm, conn, schema, user_q: str) -> tuple[dict, list]:
#     """Run the full SQL pipeline, render results, return (turn_dict, followups)."""
#     turn = {"role": "assistant", "content": "", "sql": "", "thinking": "",
#             "df": None, "result_text": ""}

#     with st.chat_message("assistant"):
#         st.markdown("🧞 **DataGenie is reading your schema and cooking up SQL...**")

#         schema_text = schema_to_text(schema)
#         plan = ask_llm_for_sql(llm, user_q, schema_text)

#         sql       = plan.get("sql", "")
#         thinking  = plan.get("thinking", "")
#         followups = plan.get("followups", [])[:3]

#         turn["sql"]      = sql
#         turn["thinking"] = thinking

#         if thinking:
#             st.markdown(f"🧠 **Agent's thought bubble:** {thinking}")

#         if sql:
#             st.markdown("**Generated SQL:**")
#             st.markdown(f"```sql\n{sql}\n```")
#         else:
#             st.warning("No SQL was generated.")

#         result = run_sql(conn, sql) if sql else "No SQL to run."

#         if isinstance(result, pd.DataFrame):
#             turn["df"] = result          # ← save df into the turn
#             if result.empty:
#                 st.info("Query ran successfully but returned **0 rows**.")
#             else:
#                 st.dataframe(result, width="stretch")
#         else:
#             turn["result_text"] = str(result)
#             result_str = str(result)
#             if result_str.startswith("SQL Error") or result_str.startswith("Blocked"):
#                 st.error(result_str)
#             else:
#                 st.write(result_str)

#         final_answer = build_final_answer(llm, user_q, sql, result)
#         turn["content"] = final_answer

#         st.markdown("---")
#         st.markdown(final_answer)

#     return turn, followups


# # ── Streamlit App ─────────────────────────────────────────────────────────────

# def main():
#     st.set_page_config(
#         page_title="DataGenie",
#         page_icon="🧞‍♂️",
#         layout="wide",
#         initial_sidebar_state="expanded",
#     )

#     st.title("🧞‍♀️ DataGenie: Talk to your SQL Database")
#     st.markdown(
#         """
#         - Upload a `.db` file (or keep a `students.db` next to the script).
#         - Ask questions in **English or Roman Urdu**.
#         - See the **exact SQL query**, **results**, and **smart follow-up suggestions**.
#         - Watch how the *DataGenie* thinks about your question. 💫
#         """
#     )

#     # ── Sidebar ──
#     with st.sidebar:
#         st.header("Step 1: Database")
#         uploaded = st.file_uploader("Upload SQLite .db", type=["db", "sqlite"])
#         st.caption("If you don't upload, I'll look for `students.db` in this folder.")

#         st.header("Step 2: Groq API Key")
#         key_input = st.text_input(
#             "GROQ_API_KEY",
#             type="password",
#             help="Get it from console.groq.com → API Keys",
#         )
#         st.markdown("---")
#         st.write("The Genie will show you SQL, results, and its 'Brain'. 💡")

#     active_key = key_input.strip() if key_input else os.getenv("GROQ_API_KEY", "")

#     # ── Database ──
#     db_path = get_db_path(uploaded)
#     if not db_path:
#         st.warning("No database available. Please upload a `.db` file or add `students.db` next to this script.")
#         return

#     try:
#         conn = connect_db(db_path)
#     except Exception as e:
#         st.error(f"Could not open database: {e}")
#         return

#     schema = get_schema(conn)
#     if not schema:
#         st.error("No user tables found in this database.")
#         return

#     st.subheader("📚 Detected Tables and Columns")
#     st.code(schema_to_text(schema))

#     if not active_key:
#         st.warning("Please enter your Groq API key in the sidebar to continue.")
#         return

#     try:
#         llm = get_llm(active_key)
#     except Exception as e:
#         st.error(str(e))
#         return

#     # ── Session state defaults ──
#     if "history" not in st.session_state:
#         st.session_state["history"] = []
#     if "pending_question" not in st.session_state:
#         st.session_state["pending_question"] = None
#     if "followups" not in st.session_state:
#         st.session_state["followups"] = []

#     # ── Render full chat history (including saved dataframes) ──
#     for turn in st.session_state["history"]:
#         if turn["role"] == "user":
#             with st.chat_message("user"):
#                 st.markdown(turn["content"])
#         else:
#             render_assistant_turn(turn)

#     # ── Show followup buttons ──
#     if st.session_state["followups"]:
#         st.markdown("**Do you also want to know:**")
#         cols = st.columns(len(st.session_state["followups"]))
#         for i, fq in enumerate(st.session_state["followups"]):
#             if cols[i].button(fq, key=f"fq_{i}_{fq[:30]}"):
#                 st.session_state["pending_question"] = fq
#                 st.session_state["followups"] = []
#                 st.rerun()

#     # ── Determine active question ──
#     typed_q  = st.chat_input("Ask DataGenie about your data...")
#     active_q = typed_q if typed_q else st.session_state.pop("pending_question", None)

#     if active_q:
#         with st.chat_message("user"):
#             st.markdown(active_q)
#         st.session_state["history"].append({"role": "user", "content": active_q})

#         turn, followups = run_pipeline(llm, conn, schema, active_q)

#         # Save full turn (including df) into history so it survives rerun
#         st.session_state["history"].append(turn)
#         st.session_state["followups"] = followups
#         st.rerun()


# if __name__ == "__main__":
#     main()


import os
import json
import sqlite3
import tempfile
from pathlib import Path
import streamlit as st
import pandas as pd
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()

try:
    import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

try:
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use("Agg")
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


DEFAULT_MODEL = "llama-3.3-70b-versatile"
MAX_ROWS = 50


@st.cache_resource
def get_llm(groq_api_key: str):
    if not groq_api_key:
        raise ValueError("Groq API key not provided.")
    return ChatGroq(
        model=DEFAULT_MODEL,
        temperature=0,
        streaming=False,
        groq_api_key=groq_api_key,
    )


# ════════════════════════════════════════════════════════════
#  DB HELPERS
# ════════════════════════════════════════════════════════════

def save_uploaded_db(uploaded_file) -> str:
    uploaded_file.seek(0)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp.write(uploaded_file.read())
        tmp.flush()
        return tmp.name


def get_db_path(uploaded_file):
    if uploaded_file is not None:
        return save_uploaded_db(uploaded_file)
    default_db = Path(__file__).parent / "students.db"
    if default_db.exists():
        return str(default_db)
    return None


def connect_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_schema(conn: sqlite3.Connection) -> dict:
    schema = {}
    cur = conn.cursor()
    tables = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    ).fetchall()
    for (table_name,) in tables:
        cols = cur.execute(f"PRAGMA table_info({table_name});").fetchall()
        schema[table_name] = [c[1] for c in cols]
    return schema


def schema_to_text(schema: dict) -> str:
    lines = []
    for table, cols in schema.items():
        preview = ", ".join(cols[:10])
        extra = " ..." if len(cols) > 10 else ""
        lines.append(f"- {table}({preview}{extra})")
    return "\n".join(lines)


def run_sql(conn: sqlite3.Connection, sql: str):
    sql_clean = sql.strip().rstrip(";")
    if not sql_clean.lower().startswith("select"):
        return "Blocked: Only SELECT queries are allowed."
    if "limit" not in sql_clean.lower():
        sql_to_run = f"{sql_clean} LIMIT {MAX_ROWS}"
    else:
        sql_to_run = sql_clean
    try:
        return pd.read_sql_query(sql_to_run, conn)
    except Exception as e:
        return f"SQL Error: {e}"


# ════════════════════════════════════════════════════════════
#  AGENT 1 — SUPERVISOR
# ════════════════════════════════════════════════════════════

def supervisor_agent(llm, question: str, schema_text: str) -> dict:
    system = SystemMessage(content=(
        "You are the Supervisor Agent for a SQL data assistant.\n"
        "Analyse the user question and return a JSON routing plan.\n"
        "Return ONLY strict JSON with keys:\n"
        "  intent: 'data_query' | 'schema_question' | 'chart_request' | 'unclear'\n"
        "  refined_question: cleaned version of the question\n"
        "  needs_chart: true or false\n"
        "  chart_hint: e.g. 'bar chart of scores by city' or ''\n"
        f"SCHEMA:\n{schema_text}"
    ))
    user = HumanMessage(content=f"User question: {question}\nReply ONLY in JSON.")
    resp = llm.invoke([system, user])
    text = resp.content.strip()
    try:
        start = text.index("{"); end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return {"intent": "data_query", "refined_question": question,
                "needs_chart": False, "chart_hint": ""}


# ════════════════════════════════════════════════════════════
#  AGENT 2 — SQL AGENT
# ════════════════════════════════════════════════════════════

def sql_agent(llm, question: str, schema_text: str) -> dict:
    system = SystemMessage(content=(
        "You are the SQL Agent — a senior SQLite expert.\n"
        "Write the most accurate, efficient SELECT query for the question.\n"
        "Rules:\n"
        "- Use ONLY tables/columns from SCHEMA.\n"
        "- ONLY safe SELECT queries (no INSERT/UPDATE/DELETE/DROP/PRAGMA).\n"
        "- Always include LIMIT if not specified (use LIMIT 20).\n"
        "Return ONLY strict JSON: {\"sql\":\"...\",\"thinking\":\"...\",\"followups\":[\"...\",\"...\"]}\n"
        f"SCHEMA:\n{schema_text}"
    ))
    user = HumanMessage(content=(
        f"Question: {question}\n"
        "Reply ONLY in JSON: {\"sql\":\"...\",\"thinking\":\"...\",\"followups\":[\"...\",\"...\"]}"
    ))
    resp = llm.invoke([system, user])
    text = resp.content.strip()
    try:
        start = text.index("{"); end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return {"sql": "SELECT 'SQL Agent failed' AS error",
                "thinking": "JSON parsing failed.", "followups": []}


# ════════════════════════════════════════════════════════════
#  AGENT 3 — VALIDATOR AGENT
# ════════════════════════════════════════════════════════════

def validator_agent(llm, sql: str, question: str, schema_text: str) -> dict:
    system = SystemMessage(content=(
        "You are the Validator Agent — a strict SQL safety and correctness reviewer.\n"
        "Check for:\n"
        "1. Safety: no INSERT/UPDATE/DELETE/DROP/PRAGMA/ALTER\n"
        "2. Correctness: columns and tables exist in SCHEMA\n"
        "3. Edge cases: missing LIMIT, wrong JOINs, ambiguous columns\n"
        "4. Logic: does the query answer the question?\n"
        "Return ONLY strict JSON:\n"
        "{\"approved\":true/false,\"corrected_sql\":\"...\",\"issues\":[\"...\"],\"verdict\":\"...\"}\n"
        f"SCHEMA:\n{schema_text}"
    ))
    user = HumanMessage(content=(
        f"Original question: {question}\n"
        f"SQL to review:\n{sql}\n\nReply ONLY in JSON."
    ))
    resp = llm.invoke([system, user])
    text = resp.content.strip()
    try:
        start = text.index("{"); end = text.rindex("}") + 1
        data = json.loads(text[start:end])
        if not data.get("corrected_sql"):
            data["corrected_sql"] = sql
        return data
    except Exception:
        return {"approved": True, "corrected_sql": sql,
                "issues": [], "verdict": "Validator passed through original SQL."}


# ════════════════════════════════════════════════════════════
#  AGENT 4 — EXPLAINER AGENT
# ════════════════════════════════════════════════════════════

def explainer_agent(llm, question: str, sql: str, result) -> str:
    if isinstance(result, pd.DataFrame):
        if result.empty:
            result_text = "The query returned 0 rows."
        else:
            preview = result.head(min(5, len(result)))
            result_text = f"Preview (up to 5 of {len(result)} rows):\n"
            result_text += (preview.to_markdown(index=False) if HAS_TABULATE
                            else preview.to_string(index=False))
    else:
        result_text = str(result)

    system = SystemMessage(content=(
        "You are the Explainer Agent — a friendly data analyst.\n"
        "Explain SQL results in simple, encouraging language.\n"
        "Structure: 1) What the data shows  2) Key insight  3) Playful closing line.\n"
        "If error, explain gently and suggest a fix."
    ))
    user = HumanMessage(content=(
        f"User question: {question}\nSQL:\n{sql}\n\nResult:\n{result_text}"
    ))
    resp = llm.invoke([system, user])
    return resp.content.strip()


# ════════════════════════════════════════════════════════════
#  AGENT 5 — CHART AGENT
# ════════════════════════════════════════════════════════════

def chart_agent(llm, question: str, df: pd.DataFrame, chart_hint: str) -> dict:
    cols = list(df.columns)
    sample = df.head(3).to_dict(orient="records")
    system = SystemMessage(content=(
        "You are the Chart Agent — a data visualisation expert.\n"
        "Decide the best chart for the data.\n"
        "Return ONLY strict JSON:\n"
        "{\"chart_type\":\"bar\"|\"line\"|\"scatter\"|\"pie\"|\"histogram\","
        "\"x_col\":\"...\",\"y_col\":\"...\",\"color_col\":null,\"title\":\"...\","
        "\"reasoning\":\"...\"}\n"
        "Only use column names that actually exist."
    ))
    user = HumanMessage(content=(
        f"Question: {question}\nHint: {chart_hint}\n"
        f"Columns: {cols}\nSample: {json.dumps(sample)}\nReply ONLY in JSON."
    ))
    resp = llm.invoke([system, user])
    text = resp.content.strip()
    try:
        start = text.index("{"); end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None


def render_chart(df: pd.DataFrame, chart_spec: dict):
    if not chart_spec:
        return None
    chart_type = chart_spec.get("chart_type", "bar")
    x_col      = chart_spec.get("x_col")
    y_col      = chart_spec.get("y_col")
    color_col  = chart_spec.get("color_col") or None
    title      = chart_spec.get("title", "Chart")

    if x_col not in df.columns:
        return None
    if y_col and y_col not in df.columns:
        y_col = None
    if color_col and color_col not in df.columns:
        color_col = None

    try:
        if HAS_PLOTLY:
            if chart_type == "bar":
                fig = px.bar(df, x=x_col, y=y_col, color=color_col, title=title)
            elif chart_type == "line":
                fig = px.line(df, x=x_col, y=y_col, color=color_col, title=title)
            elif chart_type == "scatter":
                fig = px.scatter(df, x=x_col, y=y_col, color=color_col, title=title)
            elif chart_type == "pie":
                fig = px.pie(df, names=x_col, values=y_col, title=title)
            elif chart_type == "histogram":
                fig = px.histogram(df, x=x_col, color=color_col, title=title)
            else:
                fig = px.bar(df, x=x_col, y=y_col, title=title)
            return ("plotly", fig)
        elif HAS_MATPLOTLIB:
            fig, ax = plt.subplots(figsize=(10, 5))
            if chart_type == "bar" and y_col:
                df.groupby(x_col)[y_col].mean().plot(kind="bar", ax=ax)
            elif chart_type == "line" and y_col:
                df.plot(x=x_col, y=y_col, ax=ax)
            elif chart_type == "scatter" and y_col:
                ax.scatter(df[x_col], df[y_col])
            elif chart_type == "histogram":
                df[x_col].plot(kind="hist", ax=ax)
            ax.set_title(title)
            plt.tight_layout()
            return ("matplotlib", fig)
    except Exception:
        return None


# ════════════════════════════════════════════════════════════
#  MULTI-AGENT PIPELINE
# ════════════════════════════════════════════════════════════

def run_multi_agent_pipeline(llm, conn, schema, user_q: str):
    schema_text = schema_to_text(schema)
    turn = {
        "role": "assistant", "content": "",
        "sql": "", "thinking": "", "validator": {},
        "df": None, "result_text": "",
        "chart_spec": None, "chart_fig": None,
        "supervisor": {}, "agent_log": []
    }

    with st.chat_message("assistant"):

        # AGENT 1: SUPERVISOR
        with st.status("🧠 **Supervisor Agent** — analysing your question...", expanded=False):
            supervisor = supervisor_agent(llm, user_q, schema_text)
            turn["supervisor"] = supervisor
            refined_q   = supervisor.get("refined_question", user_q)
            intent      = supervisor.get("intent", "data_query")
            needs_chart = supervisor.get("needs_chart", False)
            chart_hint  = supervisor.get("chart_hint", "")
            st.write(f"**Intent:** `{intent}`")
            st.write(f"**Refined:** {refined_q}")
            st.write(f"**Chart needed:** {needs_chart}")

        if intent == "unclear":
            st.warning("I'm not sure what you're asking. Could you rephrase?")
            turn["content"] = "I wasn't sure what you meant. Could you rephrase?"
            return turn, []

        # AGENT 2: SQL AGENT
        with st.status("✍️ **SQL Agent** — writing the query...", expanded=False):
            sql_result = sql_agent(llm, refined_q, schema_text)
            raw_sql    = sql_result.get("sql", "")
            thinking   = sql_result.get("thinking", "")
            followups  = sql_result.get("followups", [])[:3]
            turn["thinking"] = thinking
            st.write(f"**Thinking:** {thinking}")
            st.code(raw_sql, language="sql")

        # AGENT 3: VALIDATOR
        with st.status("🔍 **Validator Agent** — checking the query...", expanded=False):
            validation  = validator_agent(llm, raw_sql, refined_q, schema_text)
            turn["validator"] = validation
            approved    = validation.get("approved", True)
            final_sql   = validation.get("corrected_sql", raw_sql)
            issues      = validation.get("issues", [])
            verdict     = validation.get("verdict", "")
            st.write(f"**Verdict:** {verdict}")
            for iss in issues:
                st.write(f"⚠️ {iss}")
            if not approved:
                st.write("🔧 Corrected SQL:")
                st.code(final_sql, language="sql")
            else:
                st.write("✅ Query approved")
            turn["sql"] = final_sql

        # RUN SQL
        st.markdown("**Generated SQL:**")
        st.markdown(f"```sql\n{final_sql}\n```")
        result = run_sql(conn, final_sql) if final_sql else "No SQL to run."

        if isinstance(result, pd.DataFrame):
            turn["df"] = result
            if result.empty:
                st.info("Query ran successfully but returned **0 rows**.")
            else:
                st.dataframe(result, width="stretch")
        else:
            turn["result_text"] = str(result)
            result_str = str(result)
            if result_str.startswith("SQL Error") or result_str.startswith("Blocked"):
                st.error(result_str)
            else:
                st.write(result_str)

        # AGENT 4: CHART AGENT
        if (needs_chart or intent == "chart_request") and isinstance(result, pd.DataFrame) and not result.empty:
            with st.status("📊 **Chart Agent** — choosing the best visualisation...", expanded=False):
                chart_spec = chart_agent(llm, refined_q, result, chart_hint)
                turn["chart_spec"] = chart_spec
                if chart_spec:
                    st.write(f"**Type:** `{chart_spec.get('chart_type')}`")
                    st.write(f"**Reasoning:** {chart_spec.get('reasoning')}")

            if chart_spec:
                chart_output = render_chart(result, chart_spec)
                if chart_output:
                    kind, fig = chart_output
                    turn["chart_fig"] = (kind, fig)
                    if kind == "plotly":
                        st.plotly_chart(fig, use_container_width=True)
                    elif kind == "matplotlib":
                        st.pyplot(fig)

        # AGENT 5: EXPLAINER
        with st.status("💬 **Explainer Agent** — writing the summary...", expanded=False):
            final_answer = explainer_agent(llm, refined_q, final_sql, result)
            turn["content"] = final_answer
            st.write("Done ✅")

        st.markdown("---")
        st.markdown(final_answer)

    return turn, followups


# ════════════════════════════════════════════════════════════
#  HISTORY RENDERER
# ════════════════════════════════════════════════════════════

def render_assistant_turn(turn: dict):
    with st.chat_message("assistant"):
        if turn.get("thinking"):
            with st.expander("🧠 SQL Agent thinking"):
                st.write(turn["thinking"])

        v = turn.get("validator", {})
        if v:
            approved = v.get("approved", True)
            badge = "✅ Validated" if approved else "🔧 Corrected"
            with st.expander(f"🔍 Validator — {badge}"):
                st.write(v.get("verdict", ""))
                for iss in v.get("issues", []):
                    st.write(f"⚠️ {iss}")

        if turn.get("sql"):
            st.markdown("**SQL:**")
            st.markdown(f"```sql\n{turn['sql']}\n```")

        if turn.get("df") is not None:
            df = turn["df"]
            if df.empty:
                st.info("0 rows returned.")
            else:
                st.dataframe(df, width="stretch")
        elif turn.get("result_text"):
            result_str = turn["result_text"]
            if result_str.startswith("SQL Error") or result_str.startswith("Blocked"):
                st.error(result_str)
            else:
                st.write(result_str)

        chart_fig = turn.get("chart_fig")
        if chart_fig:
            kind, fig = chart_fig
            if kind == "plotly":
                st.plotly_chart(fig, use_container_width=True)
            elif kind == "matplotlib":
                st.pyplot(fig)

        st.markdown("---")
        st.markdown(turn["content"])


# ════════════════════════════════════════════════════════════
#  STREAMLIT APP
# ════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="DataGenie — Multi-Agent",
        page_icon="🧞‍♂️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("🧞‍♀️ DataGenie: Multi-Agent SQL Assistant")
    st.markdown(
        "A team of **5 AI agents** answers your data questions: "
        "`Supervisor` → `SQL Agent` → `Validator` → `Chart Agent` → `Explainer`"
    )
    st.markdown(
        """
        - Upload a `.db` file (or keep a `students.db` next to the script).
        - Ask questions in **English or Roman Urdu**.
        - See the **exact SQL query**, **results**, and **smart follow-up suggestions**.
        - Watch how the *DataGenie* thinks about your question. 🔮
        """
    )

    with st.sidebar:
        st.header("⚙️ Configuration")
        uploaded = st.file_uploader("Upload SQLite .db", type=["db", "sqlite"])
        st.caption("Or add `students.db` next to this script.")
        key_input = st.text_input("Groq API Key", type="password",
                                   help="console.groq.com → API Keys")
        st.markdown("---")
        st.markdown("### 🤖 Agent Pipeline")
        st.markdown("""
1. **Supervisor** — understands intent
2. **SQL Agent** — writes the query
3. **Validator** — checks safety & correctness
4. **Chart Agent** — picks best visualisation
5. **Explainer** — explains the result
        """)
        st.markdown("---")
        st.caption("💡 Try: *'Show me a bar chart of average scores by city'*")

    active_key = key_input.strip() if key_input else os.getenv("GROQ_API_KEY", "")

    db_path = get_db_path(uploaded)
    if not db_path:
        st.warning("No database found. Upload a `.db` file or add `students.db` here.")
        return

    try:
        conn = connect_db(db_path)
    except Exception as e:
        st.error(f"Could not open database: {e}")
        return

    schema = get_schema(conn)
    if not schema:
        st.error("No user tables found in this database.")
        return

    with st.expander("📚 Database Schema", expanded=False):
        st.code(schema_to_text(schema))

    if not active_key:
        st.warning("Please enter your Groq API key in the sidebar.")
        return

    try:
        llm = get_llm(active_key)
    except Exception as e:
        st.error(str(e))
        return

    if "history" not in st.session_state:
        st.session_state["history"] = []
    if "pending_question" not in st.session_state:
        st.session_state["pending_question"] = None
    if "followups" not in st.session_state:
        st.session_state["followups"] = []

    for turn in st.session_state["history"]:
        if turn["role"] == "user":
            with st.chat_message("user"):
                st.markdown(turn["content"])
        else:
            render_assistant_turn(turn)

    if st.session_state["followups"]:
        st.markdown("**Do you also want to know:**")
        cols = st.columns(len(st.session_state["followups"]))
        for i, fq in enumerate(st.session_state["followups"]):
            if cols[i].button(fq, key=f"fq_{i}_{fq[:30]}"):
                st.session_state["pending_question"] = fq
                st.session_state["followups"] = []
                st.rerun()

    typed_q  = st.chat_input("Ask DataGenie about your data...")
    active_q = typed_q if typed_q else st.session_state.pop("pending_question", None)

    if active_q:
        with st.chat_message("user"):
            st.markdown(active_q)
        st.session_state["history"].append({"role": "user", "content": active_q})

        turn, followups = run_multi_agent_pipeline(llm, conn, schema, active_q)
        st.session_state["history"].append(turn)
        st.session_state["followups"] = followups
        st.rerun()


if __name__ == "__main__":
    main()
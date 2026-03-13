import streamlit as st
import requests
import pandas as pd

API_URL = "http://localhost:8000/query"  # change if needed

st.set_page_config(page_title="SUSE Rancher AI Controller", page_icon="logo.svg", layout="wide" )

st.title(" SUSE Rancher AI Controller")
st.caption("Control your Kubernetes  Workloads using SUSE AI")

# Sidebar
st.sidebar.image("logo.svg", width=140)
#st.sidebar.title("Sample Query")

if st.sidebar.button("Clear History"):
    st.session_state.history = []

st.sidebar.markdown("""
Example prompts:

- list pods in default namespace
- scale nginx-deployment to 3
- optimise nginx-deployment by 50%
""")

# Initialize session history
if "history" not in st.session_state:
    st.session_state.history = []

prompt = st.chat_input("Ask something like: list pods, scale deployment, optimize resources")

# Send request
if prompt:
    with st.spinner("Processing request..."):
        try:
            response = requests.post(API_URL, json={"prompt": prompt}, timeout=60)
            data = response.json()

            st.session_state.history.append({
                "prompt": prompt,
                "response": data
            })

        except Exception as e:
            st.error(str(e))


# ---------- Result Renderer ----------
def render_result(response):

    result = response.get("result")

    # POD LIST
    if isinstance(result, list):

        st.success(f"Found {len(result)} pods")

        table = []

        for pod in result:

            status_icon = {
                "Running": "🟢",
                "Pending": "🟡",
                "Failed": "🔴"
            }.get(pod["phase"], "⚪")

            table.append({
                "Namespace": pod["namespace"],
                "Pod Name": pod["name"],
                "Status": f"{status_icon} {pod['phase']}"
            })

        st.table(pd.DataFrame(table))


    # DEPLOYMENT OPTIMIZATION
    elif isinstance(result, dict) and result.get("deployment"):

        st.success("Deployment optimized successfully")

        st.markdown(f"""
### ⚙️ Deployment Optimization

**Deployment:** `{result['deployment']}`
**Namespace:** `{result['namespace']}`

Resources reduced by **{abs(result['scaled_by_percent'])}%**
""")

        table = []

        for c in result["containers"]:
            table.append({
                "Container": c["name"],
                "CPU": c["requests"]["cpu"],
                "Memory": c["requests"]["memory"]
            })

        st.table(pd.DataFrame(table))

        st.info(result["status"])


    # FALLBACK
    else:
        st.json(result)


# ---------- Chat History ----------
for item in st.session_state.history:

    with st.chat_message("user"):
        st.write(item["prompt"])

    with st.chat_message("assistant"):
        render_result(item["response"])

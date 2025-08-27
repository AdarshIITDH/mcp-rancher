# MCP Kubernetes Gemini PoC

This project is a **Model Context Protocol (MCP) server** that connects a natural language interface (via Gemini) to a Kubernetes cluster.  
It allows you to type commands like:

- `list the pods`
- `list pods as per namespace
- `show top pods by cpu in default`
- `optimize nginx by 30%`

and executes them against your Kubernetes cluster (list pods, fetch metrics, scale resources, etc.).

---

## ✨ Features
- MCP server (`app/mcp_server.py`) that exposes a `k8s_query` tool
- Gemini used for intent parsing (`app/gemini_client.py`)
- Kubernetes Python client for cluster operations (`app/k8s_client.py`)
- Supported actions:
  - List pods in a namespace
  - Show top pods by CPU (requires `metrics-server`)
  - Scale Deployment resources up/down by percentage
- Example deployment manifest: `nginx_deployment.yaml`
- Can be used:
  - With `curl` via the included FastAPI API (`main.py`)
  - As an MCP tool inside [Open WebUI](https://github.com/open-webui/open-webui)

Start the Server
```sh
bash run.sh 
```
Query it
```sh
curl -s -X POST http://localhost:8000/query   -H "Content-Type: application/json"   -d '{"prompt":"optimise the nginx by 30%"}' | jq
```


## 🛠 Requirements
- Python 3.10+
- Kubernetes cluster (with `~/.kube/config` accessible on this VM)
- [metrics-server](https://github.com/kubernetes-sigs/metrics-server) installed in cluster
- A valid [Gemini API Key](https://ai.google.dev/)

---

## 📦 Installation

```bash
# clone repo
git clone https://github.com/your-username/mcp-rancher.git
cd mcp-rancher

# install dependencies
pip install -r requirements.txt

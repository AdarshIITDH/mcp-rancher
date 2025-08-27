from typing import Optional, Tuple, List, Dict, Any
from kubernetes import client, config
from kubernetes.client import ApiException

# Load kube: per user, prefer local kubeconfig (outside cluster)
def _load_kube():
    try:
        config.load_kube_config()
    except Exception:
        config.load_incluster_config()

_load_kube()
apps_v1 = client.AppsV1Api()
core_v1 = client.CoreV1Api()
custom_api = client.CustomObjectsApi()

def list_pods(namespace: Optional[str] = None) -> List[Dict[str, str]]:
    if namespace and namespace != "all":
        pods = core_v1.list_namespaced_pod(namespace=namespace, watch=False)
    else:
        pods = core_v1.list_pod_for_all_namespaces(watch=False)
    return [{"namespace": p.metadata.namespace, "name": p.metadata.name, "phase": p.status.phase} for p in pods.items]

def top_pods(namespace: Optional[str] = None) -> Dict[str, Any]:
    """Reads metrics from metrics.k8s.io. Requires metrics-server installed."""
    group = "metrics.k8s.io"
    version = "v1beta1"
    plural = "pods"
    try:
        if namespace and namespace != "all":
            obj = custom_api.list_namespaced_custom_object(group, version, namespace, plural)
        else:
            obj = custom_api.list_cluster_custom_object(group, version, plural)
        # Normalize rows similar to `kubectl top pods`
        rows = []
        for item in obj.get("items", []):
            ns = item.get("metadata", {}).get("namespace", "")
            name = item.get("metadata", {}).get("name", "")
            containers = item.get("containers", [])
            # Sum container usage to get pod totals
            cpu_m = 0
            mem_bytes = 0
            for c in containers:
                cpu = c.get("usage", {}).get("cpu", "0")
                mem = c.get("usage", {}).get("memory", "0")
                # cpu like '5m' or '100n'
                if cpu.endswith('m'):
                    cpu_m += int(cpu[:-1])
                elif cpu.endswith('n'):
                    # nanocores convert to millicores (approx)
                    cpu_m += max(1, int(int(cpu[:-1]) / 1_000_000))
                else:
                    # assume cores -> convert to m
                    cpu_m += int(float(cpu) * 1000)
                # memory: e.g., '12345Ki', '12Mi'
                s = mem
                try:
                    if s.endswith('Ki'):
                        mem_bytes += int(s[:-2]) * 1024
                    elif s.endswith('Mi'):
                        mem_bytes += int(s[:-2]) * 1024 * 1024
                    elif s.endswith('Gi'):
                        mem_bytes += int(s[:-2]) * 1024 * 1024 * 1024
                    else:
                        mem_bytes += int(s)
                except Exception:
                    pass
            rows.append({"NAMESPACE": ns, "NAME": name, "CPU(m)": str(cpu_m), "MEMORY(bytes)": str(mem_bytes)})
        # Sort by CPU desc like --sort-by=cpu
        rows.sort(key=lambda r: int(r["CPU(m)"]), reverse=True)
        return {"headers": ["NAMESPACE","NAME","CPU(m)","MEMORY(bytes)"], "rows": rows}
    except ApiException as e:
        return {"error": f"metrics.k8s.io not available: {e.status} {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

def _resolve_deployment_from_pod(namespace: str, pod_name: str) -> Optional[str]:
    pod = core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)
    owners = pod.metadata.owner_references or []
    # We may find ReplicaSet; then hop to Deployment
    for ref in owners:
        if ref.kind == "ReplicaSet":
            rs = apps_v1.read_namespaced_replica_set(name=ref.name, namespace=namespace)
            rs_owners = rs.metadata.owner_references or []
            for o in rs_owners:
                if o.kind == "Deployment":
                    return o.name
        if ref.kind == "Deployment":
            return ref.name
    return None

def _scale_container_resources(container, operation: str, pct: int) -> Dict[str, str]:
    if not container.resources or (not container.resources.requests and not container.resources.limits):
        raise ValueError("Container has no resources set; cannot scale safely")
    def scale_quan(q: Optional[str]) -> Optional[str]:
        if not q:
            return q
        # very basic: handle cpu m and memory Mi/Gi
        try:
            if q.endswith('m'):
                v = int(q[:-1])
                v = int(v * (1 + pct/100) ) if operation == 'increase' else max(1, int(v * (1 - pct/100)))
                return f"{v}m"
            if q.endswith('Mi'):
                v = int(q[:-2])
                v = max(1, int(v * (1 + pct/100))) if operation == 'increase' else max(1, int(v * (1 - pct/100)))
                return f"{v}Mi"
            if q.endswith('Gi'):
                v = int(q[:-2])
                v = max(1, int(v * (1 + pct/100))) if operation == 'increase' else max(1, int(v * (1 - pct/100)))
                return f"{v}Gi"
            # Fallback: try int
            v = int(q)
            v = max(1, int(v * (1 + pct/100))) if operation == 'increase' else max(1, int(v * (1 - pct/100)))
            return str(v)
        except Exception:
            return q
    out = {}
    if container.resources.requests:
        new = {}
        for k,v in container.resources.requests.items():
            new[k] = scale_quan(v)
        container.resources.requests = new
        out["requests"] = new
    if container.resources.limits:
        newl = {}
        for k,v in container.resources.limits.items():
            newl[k] = scale_quan(v)
        container.resources.limits = newl
        out["limits"] = newl
    return out

def scale_resources(resource_name: str, namespace: str = "default", percentage: int = 30, operation: str = "decrease") -> Dict[str, Any]:
    # resource_name may be a Deployment or a Pod; resolve if needed
    dep_name = None
    # Try read as deployment first
    try:
        apps_v1.read_namespaced_deployment(name=resource_name, namespace=namespace)
        dep_name = resource_name
    except ApiException:
        # maybe it's a pod
        try:
            dep = _resolve_deployment_from_pod(namespace, resource_name)
            if dep:
                dep_name = dep
        except ApiException:
            pass
    if not dep_name:
        return {"error": f"Could not resolve a Deployment from '{resource_name}'", "namespace": namespace}

    dep = apps_v1.read_namespaced_deployment(name=dep_name, namespace=namespace)
    containers = dep.spec.template.spec.containers or []
    patched = []
    for c in containers:
        try:
            changed = _scale_container_resources(c, operation=operation, pct=percentage)
            patched.append({"name": c.name, **changed})
        except ValueError as e:
            patched.append({"name": c.name, "skipped": str(e)})
    # Patch deployment
    apps_v1.patch_namespaced_deployment(name=dep_name, namespace=namespace, body=dep)
    # Rollout restart by bumping annotation
    from datetime import datetime
    if dep.spec.template.metadata is None:
        dep.spec.template.metadata = client.V1ObjectMeta(annotations={})
    ann = dep.spec.template.metadata.annotations or {}
    ann["kubectl.kubernetes.io/restartedAt"] = datetime.utcnow().isoformat() + "Z"
    dep.spec.template.metadata.annotations = ann
    # Build a minimal patch instead of sending the full object
    patch = {
      "spec": {
          "template": {
              "spec": {
                  "containers": []
              }
          }
      }
    }

    for container in dep.spec.template.spec.containers:
      patch["spec"]["template"]["spec"]["containers"].append({
          "name": container.name,
          "resources": container.resources.to_dict() if container.resources else {}
      })

    apps_v1.patch_namespaced_deployment(
      name=dep_name,
      namespace=namespace,
      body=patch
    )



#    apps_v1.patch_namespaced_deployment(name=dep_name, namespace=namespace, body=dep)
    return {
        "namespace": namespace,
        "deployment": dep_name,
        "scaled_by_percent": percentage if operation=="increase" else -percentage,
        "operation": operation,
        "containers": patched,
        "status": "Deployment resources patched; rollout restart triggered"
    }

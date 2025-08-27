import os
from dotenv import load_dotenv
from kubernetes import config as k8s_config

load_dotenv(override=True)

class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_URL: str = os.getenv(
        "GEMINI_URL",
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
    )

    def load_kube_config(self):
        # Per user: prefer local kubeconfig; fallback to in-cluster
        try:
            k8s_config.load_kube_config()
        except Exception:
            k8s_config.load_incluster_config()

settings = Settings()

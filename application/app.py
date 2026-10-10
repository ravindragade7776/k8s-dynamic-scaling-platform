import os

from flask import Flask, render_template, request, redirect, url_for, flash
from kubernetes import client, config
from kubernetes.client.rest import ApiException

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

NAMESPACE = os.environ.get("TARGET_NAMESPACE", "scaling-demo")
DEPLOYMENT = os.environ.get("TARGET_DEPLOYMENT", "scaling-demo")
MIN_REPLICAS = 1
MAX_REPLICAS = 10


def get_apps_api():
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.AppsV1Api()


@app.route("/", methods=["GET"])
def home():
    try:
        api = get_apps_api()
        deployment = api.read_namespaced_deployment(
            name=DEPLOYMENT,
            namespace=NAMESPACE
        )

        desired = deployment.spec.replicas or 0
        ready = deployment.status.ready_replicas or 0

        return render_template(
            "index.html",
            desired=desired,
            ready=ready,
            minimum=MIN_REPLICAS,
            maximum=MAX_REPLICAS
        )
    except (ApiException, config.ConfigException) as exc:
        app.logger.exception("Unable to read Kubernetes Deployment")
        return "Unable to read Deployment. Check Kubernetes configuration and RBAC.", 503


@app.route("/scale", methods=["POST"])
def scale():
    raw_replicas = request.form.get("replicas", "")

    try:
        replicas = int(raw_replicas)
    except ValueError:
        flash("Enter a valid whole number.")
        return redirect(url_for("home"))

    if not MIN_REPLICAS <= replicas <= MAX_REPLICAS:
        flash(f"Choose between {MIN_REPLICAS} and {MAX_REPLICAS} replicas.")
        return redirect(url_for("home"))

    try:
        api = get_apps_api()
        api.patch_namespaced_deployment_scale(
            name=DEPLOYMENT,
            namespace=NAMESPACE,
            body={"spec": {"replicas": replicas}}
        )
        flash(f"Scaling requested: {replicas} replicas.")
    except (ApiException, config.ConfigException):
        app.logger.exception("Unable to scale Kubernetes Deployment")
        flash("Scaling failed. Check the application logs and RBAC permissions.")

    return redirect(url_for("home"))


@app.route("/health", methods=["GET"])
def health():
    return {"status": "healthy"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

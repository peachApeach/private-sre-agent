def deployment_selector_to_label_selector(deploy_json: dict) -> str:
    match_labels = (
        deploy_json
        .get("spec", {})
        .get("selector", {})
        .get("matchLabels", {})
    )

    if not match_labels:
        return ""

    return ",".join(
        f"{key}={value}"
        for key, value in match_labels.items()
    )


def summarize_deployment(deploy_json: dict) -> dict:
    metadata = deploy_json.get("metadata", {})
    spec = deploy_json.get("spec", {})
    status = deploy_json.get("status", {})

    return {
        "name": metadata.get("name"),
        "namespace": metadata.get("namespace"),
        "replicas": spec.get("replicas", 0),
        "ready_replicas": status.get("readyReplicas", 0),
        "available_replicas": status.get("availableReplicas", 0),
        "updated_replicas": status.get("updatedReplicas", 0),
        "selector": deployment_selector_to_label_selector(deploy_json),
    }
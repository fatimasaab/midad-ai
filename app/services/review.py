from datetime import datetime, timezone


def requires_scholarly_review(clip):
    return any(
        flag["type"] == "religious_reference"
        for flag in clip.get("review_flags", [])
    ) or clip.get("scholarly_review_required", False)


def can_export(clip):
    if clip.get("scholarly_status") == "rejected":
        return False

    if clip.get("editorial_status") != "approved":
        return False

    if requires_scholarly_review(clip):
        return clip.get("scholarly_status") == "approved"

    return True


def apply_review(
    clip,
    review_type,
    decision,
    reviewer,
    notes,
    require_scholarly=False
):
    if review_type == "scholarly":
        if clip.get("editorial_status") != "approved":
            raise ValueError(
                "Editorial approval is required first."
            )

    if review_type == "editorial":
        clip["editorial_status"] = decision

        if require_scholarly:
            clip["scholarly_review_required"] = True

        clip["scholarly_status"] = "pending"

    else:
        clip["scholarly_status"] = decision

    event = {
        "review_type": review_type,
        "decision": decision,
        "reviewer": reviewer,
        "notes": notes,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat()
    }

    clip.setdefault("review_history", []).append(event)

    clip["scholarly_review_required"] = (
        requires_scholarly_review(clip)
    )

    if (
        clip.get("editorial_status") == "rejected"
        or clip.get("scholarly_status") == "rejected"
    ):
        clip["status"] = "rejected"

    elif can_export(clip):
        clip["status"] = "approved"

    elif clip.get("editorial_status") == "approved":
        clip["status"] = "pending_scholarly_review"

    else:
        clip["status"] = "pending_review"

    clip["export_allowed"] = can_export(clip)

    return clip

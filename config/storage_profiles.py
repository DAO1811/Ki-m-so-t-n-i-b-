"""Confirmed deployment limits, not automatic Neon plan detection.

The owner identified the production project and Free plan on 2026-10-21.
Neon's plan documentation was checked that day: 1 GB of Postgres per project.
A different deployment/database remains unknown until explicitly configured.
"""

CONFIRMED_PROFILES = {
    "kiemsoatnoibolemon.onrender.com": {
        "project_id": "bold-resonance-26000114",
        "plan": "Neon Free",
        "limit_bytes": 1_000_000_000,
        "limit_label": "1 GB",
        "confirmed_at": "2026-10-21",
        "source_url": "https://neon.com/docs/introduction/plans",
    }
}


def storage_profile(hostname, database_host):
    """Apply only to the identified Render deployment using a Neon database."""
    if not str(database_host).lower().endswith(".neon.tech"):
        return None
    profile = CONFIRMED_PROFILES.get(str(hostname).lower())
    return dict(profile) if profile else None

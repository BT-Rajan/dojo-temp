"""
Regenerates docs/security/RBAC_MATRIX.md (EA-SYS-SEC-02) from apps/rbac/catalog.py.

    python scripts/build_rbac_matrix.py

The rules section at the end of the document is kept as it is.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from apps.rbac.catalog import PERMISSIONS, ROLES  # noqa: E402

SHORT = {
    "ceo": "CEO",
    "operations_manager": "OM",
    "training_lead": "Train",
    "track_lead": "Track",
    "instructor": "Coach",
    "marketing_lead": "Mkt",
    "marketing_staff": "MktI",
    "it_admin": "IT",
    "branch_admin": "BrAdm",
    "operations_support": "OpsSp",
    "purchasing_coordinator": "Purch",
    "accountant": "Acct",
    "guardian": "Parent",
}
DOC = ROOT.parent / "docs" / "security" / "RBAC_MATRIX.md"


def build() -> str:
    lines = [
        "# RBAC Matrix — Default Roles and Permissions",
        "",
        "Document: EA-SYS-SEC-02 · Generated from `backend/apps/rbac/catalog.py` (the single source of truth) by "
        "`backend/scripts/build_rbac_matrix.py`. Regenerate after any change.",
        "",
        "✓ = granted. Branch-scoped roles (e.g. Branch Admin, Instructor) apply the permission only in their assigned "
        "branch. ★ = privileged role (two-factor login required in production).",
        "",
        "| Role code | Role | Privileged | Description |",
        "|---|---|---|---|",
    ]
    for code, (name, name_ar, desc, privileged, _perms) in ROLES.items():
        lines.append(f"| `{code}` ({SHORT[code]}) | {name} / {name_ar} | {'★' if privileged else ''} | {desc} |")
    lines += [
        "",
        "| Permission | Meaning | " + " | ".join(SHORT[c] for c in ROLES) + " |",
        "|---|---|" + "---|" * len(ROLES),
    ]
    for perm, meaning in PERMISSIONS.items():
        cells = ["✓" if perm in ROLES[c][4] else "" for c in ROLES]
        lines.append(f"| `{perm}` | {meaning} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    current = DOC.read_text(encoding="utf-8")
    rules = current[current.index("## Rules that apply on top of the matrix") :]
    DOC.write_text(build() + "\n" + rules, encoding="utf-8")
    print(f"Wrote {DOC}")

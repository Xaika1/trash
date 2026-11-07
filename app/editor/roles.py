CLOSED = 0
VIEW = 1
EDIT = 2

ROLE_ORDER = {"owner": 0, "edit": 1, "view": 2}


def role_of(owner, access):
    if owner:
        return "owner"
    return "edit" if access == EDIT else "view"

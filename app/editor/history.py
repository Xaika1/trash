from app import config

steps_by_user = {}


def remember(canvas_id, member, step):
    steps = steps_by_user.setdefault((canvas_id, member["user_id"]), [])
    steps.append(step)
    del steps[: -config.UNDO_LIMIT]


def take_last(canvas_id, member):
    steps = steps_by_user.get((canvas_id, member["user_id"]))
    if not steps:
        return None
    return steps.pop()


def forget(canvas_id):
    for key in [key for key in steps_by_user if key[0] == canvas_id]:
        del steps_by_user[key]

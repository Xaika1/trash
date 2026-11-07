from app import config

MAX_ID = 2**62


def to_int(value, low, high):
    number = int(value)
    if not low <= number <= high:
        raise ValueError
    return number


def to_id(value):
    return to_int(value, 1, MAX_ID)


def to_side(value):
    return to_int(value, 0, 3)


def to_type(value):
    return to_int(value, 1, 4)


def to_point(value):
    return to_int(value, -config.MAX_COORD, config.MAX_COORD)


def to_size(value):
    return to_int(value, config.BLOCK_SIZE_MIN, config.BLOCK_SIZE_MAX)


def to_coordinates(x, y, width, height):
    return f"{to_point(x)};{to_point(y)};{to_size(width)};{to_size(height)}"


def to_ids(text):
    if not text:
        return []
    ids = [to_id(value) for value in text.split(",")]
    if len(ids) > config.MAX_BLOCKS * 2:
        raise ValueError
    return ids


def block_line(block):
    return f"N;{block['id']};{block['type']};{block['coordinates']};{block['text']}"


def edge_line(edge):
    sides = f"{edge['from_block']};{edge['from_side']};{edge['to_block']};{edge['to_side']}"
    return f"E;{edge['id']};{sides};{edge['label']}"

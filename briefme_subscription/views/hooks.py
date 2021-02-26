def parse_chargify_webhook(post_data):
    """
    Converts Chargify webhook parameters to a python dictionary of nested dictionaries
    Cast true/false to boolean
    :return:
    """
    result = {}
    for k, v in post_data.items():
        keys = [x.strip("]") for x in k.split("[")]
        cur = result
        for key in keys[:-1]:
            cur = cur.setdefault(key, {})
        bool_map = {"true": True, "false": False}
        v = bool_map.get(v, v)
        cur[keys[-1]] = v
    return result

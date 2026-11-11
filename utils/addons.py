
_addons_fns = {}
def addon(addon_code: str):
    global _addons_fns
    def deco(fn):
        _addons_fns[addon_code] = fn
        return fn
    return deco

_addons = {}
def get_addon(addon_code: str):
    global _addons
    if addon_code not in _addons:
        fn = _addons_fns.get(addon_code)
        if fn is not None: _addons[addon_code] = fn()
    return _addons.get(addon_code, None)

def get_addons(source: dict) -> dict:
    addons = {}
    wanted_addons = source.get("addons", '')
    if wanted_addons != '':
        for wanted_addon in wanted_addons.split(','):
            addons[wanted_addon] = get_addon(wanted_addon)
    return addons

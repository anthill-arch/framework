def error(e):
    """
    We cannot write `callback=lambda: raise ValueError`,
    but with this simple function we can write `callback=error(ValueError)`
    """
    raise e

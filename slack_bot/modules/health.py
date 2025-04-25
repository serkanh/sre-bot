def healthcheck():
    """Health check path for load balancers

    Returns:
        [string]: Returns a json string
    """
    return {"status": "ok"}

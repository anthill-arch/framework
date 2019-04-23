import ipaddress


def first(*args):
    return next((item for item in args if item is not None), None)


def get_ip(request):
    return first(
        request.headers.get('X-Forwarded-For'),
        request.headers.get('X-Real-IP'),
        request.remote_ip
    )


def has_ip(network_str, ip_str):
    ip = ipaddress.ip_address(ip_str)
    network = ipaddress.ip_network(network_str)
    return ip in network

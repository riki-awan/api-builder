# Auto-generated dynamic routes

def generic_handler(request):
    path = getattr(request, 'url', 'unknown')
    return {'message': f'Hello from dynamic route {path}'}

routes = [
    {'path': '/api/test', 'method': 'GET', 'auth': '', 'handler': generic_handler},
]

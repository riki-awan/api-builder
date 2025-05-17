import os
import json
import importlib
import threading
import time

from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse, Response
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
from starlette.requests import Request
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles
from starlette.routing import Mount
import uvicorn

PORT = 8000
STATIC_DIR = "static"

STATIC_ROUTES = []
DYNAMIC_ROUTES = []

# ==== Dekorator route statis ====
def route(path, method="GET", auth=None):
    def decorator(func):
        STATIC_ROUTES.append({
            "path": path,
            "method": method.upper(),
            "auth": auth,
            "handler": func,
        })
        return func
    return decorator

# ==== Dynamic routes ====
import dynamic_routes

def load_dynamic_routes():
    global DYNAMIC_ROUTES
    importlib.reload(dynamic_routes)
    DYNAMIC_ROUTES = [
        {
            "path": r["path"],
            "method": r["method"].upper(),
            "auth": r.get("auth"),
            "handler": r["handler"],
        }
        for r in dynamic_routes.routes
    ]
    print(f"Loaded {len(DYNAMIC_ROUTES)} dynamic routes from dynamic_routes.py")

# ==== Watcher ====
class RouteFileChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith("dynamic_routes.py"):
            print("dynamic_routes.py changed, reloading routes...")
            load_dynamic_routes()

def start_watcher():
    def watch():
        event_handler = RouteFileChangeHandler()
        observer = Observer()
        observer.schedule(event_handler, path=".", recursive=False)
        observer.start()
        print("Started watching dynamic_routes.py for changes")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
    threading.Thread(target=watch, daemon=True).start()

# ==== Penyimpanan route dinamis ====
def save_routes_py_file(routes, filename="dynamic_routes.py"):
    with open(filename, "w") as f:
        f.write("# Auto-generated dynamic routes\n\n")
        f.write("def generic_handler(request):\n")
        f.write("    path = getattr(request, 'url', 'unknown')\n")
        f.write("    return {'message': f'Hello from dynamic route {path}'}\n\n")
        f.write("routes = [\n")
        for r in routes:
            path = r["path"]
            method = r["method"]
            auth = repr(r.get("auth"))
            f.write(f"    {{'path': '{path}', 'method': '{method}', 'auth': {auth}, 'handler': generic_handler}},\n")
        f.write("]\n")

# ==== Routing handler utama ====
async def unified_handler(request: Request):
    path = request.url.path
    method = request.method.upper()

    # Cari handler statis atau dinamis
    for r in STATIC_ROUTES + DYNAMIC_ROUTES:
        if r["path"] == path and r["method"] == method:
            # Baca body jika POST
            if method == "POST":
                try:
                    data = await request.json()
                except Exception:
                    data = {}
                return JSONResponse(r["handler"](request, data))
            else:
                return JSONResponse(r["handler"](request))

    # Not found
    return JSONResponse({"error": "Route not found"}, status_code=404)

# ==== API route bawaan ====
@route("/api/hello", method="GET")
def hello_handler(request):
    return {"message": "Hello from PyAPI Framework!"}

@route("/api/routes", method="GET")
def list_routes(request):
    all_routes = STATIC_ROUTES + DYNAMIC_ROUTES
    return [{"path": r["path"], "method": r["method"], "auth": r["auth"]} for r in all_routes]

@route("/api/routes/add", method="POST")
def add_route_handler(request, data):
    path = data.get("path")
    method = data.get("method", "GET").upper()
    auth = data.get("auth")

    if not path or not method:
        return {"error": "path and method are required"}

    for r in STATIC_ROUTES + DYNAMIC_ROUTES:
        if r["path"] == path and r["method"] == method:
            return {"error": "route already exists"}

    DYNAMIC_ROUTES.append({
        "path": path,
        "method": method,
        "auth": auth,
        "handler": dynamic_routes.generic_handler
    })

    save_routes_py_file(DYNAMIC_ROUTES)
    return {"success": True, "message": f"Route {method} {path} added"}

# ==== Generate semua route ke Starlette ====
def generate_routes():
    unique_paths = set((r["path"], r["method"]) for r in STATIC_ROUTES + DYNAMIC_ROUTES)
    starlette_routes = []
    for path, method in unique_paths:
        starlette_routes.append(Route(path, unified_handler, methods=[method]))
    return starlette_routes


async def index(request):
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

# ==== Inisialisasi Starlette App ====
load_dynamic_routes()
start_watcher()

app = Starlette(
    debug=True,
    routes=[
        Route("/", index),
        Mount("/static", StaticFiles(directory=STATIC_DIR), name="static"),
    ] + generate_routes()
)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ==== Jalankan server ====
if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=True)

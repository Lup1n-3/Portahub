from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from werkzeug.utils import secure_filename
import json, os, uuid
import qrcode

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "hubserver-dev-key-change-me")

DATA_FILE = 'data.json'
IMAGES_DIR = os.path.join('static', 'images')
ICONS_DIR = os.path.join('static', 'service_icons')


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump([], f)
    with open(DATA_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def find_server(data, server_id):
    for s in data:
        if s["id"] == server_id:
            return s
    return None


def save_upload(file_storage, folder):
    """Save an uploaded file with a safe, unique name. Returns the filename or ''."""
    if not file_storage or not file_storage.filename:
        return ""
    os.makedirs(folder, exist_ok=True)
    safe_name = secure_filename(file_storage.filename)
    filename = f"{uuid.uuid4()}_{safe_name}"
    file_storage.save(os.path.join(folder, filename))
    return filename


def delete_file_if_exists(folder, filename):
    if not filename:
        return
    path = os.path.join(folder, filename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


@app.context_processor
def inject_asset_version():
    """Cache-bust static/css/style.css automatically based on its own
    last-modified time, so browsers always fetch the latest CSS after an
    update instead of serving a stale cached copy."""
    css_path = os.path.join(app.static_folder, 'css', 'style.css')
    try:
        version = int(os.path.getmtime(css_path))
    except OSError:
        version = 1
    return {"asset_version": version}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    servers = load_data()
    total_services = sum(len(s.get("services", [])) for s in servers)
    stats = {
        "servers": len(servers),
        "services": total_services,
    }
    return render_template("home.html", servers=servers, stats=stats)


# ---------------------------------------------------------------------------
# Servers
# ---------------------------------------------------------------------------

@app.route("/server/<id>")
def server_detail(id):
    servers = load_data()
    server = find_server(servers, id)
    if not server:
        return render_template("404.html", message="Servidor no encontrado"), 404
    return render_template("server.html", server=server)


@app.route("/add", methods=["GET", "POST"])
def add_server():
    if request.method == "POST":
        data = load_data()
        filename = save_upload(request.files.get("image"), IMAGES_DIR)
        new_server = {
            "id": str(uuid.uuid4()),
            "name": request.form["name"].strip(),
            "ip": request.form["ip"].strip(),
            "image": filename,
            "services": []
        }
        data.append(new_server)
        save_data(data)
        flash(f"Servidor '{new_server['name']}' creado correctamente.", "success")
        return redirect(url_for("home"))
    return render_template("add.html")


@app.route("/server/<id>/edit", methods=["POST"])
def edit_server(id):
    data = load_data()
    server = find_server(data, id)
    if not server:
        flash("Servidor no encontrado.", "danger")
        return redirect(url_for("home"))

    server["name"] = request.form["name"].strip()
    server["ip"] = request.form["ip"].strip()

    image = request.files.get("image")
    if image and image.filename:
        delete_file_if_exists(IMAGES_DIR, server.get("image"))
        server["image"] = save_upload(image, IMAGES_DIR)

    save_data(data)
    flash(f"Servidor '{server['name']}' actualizado.", "success")
    return redirect(url_for("home"))


@app.route("/server/<id>/delete")
def delete_server(id):
    data = load_data()
    server = find_server(data, id)
    if not server:
        flash("Servidor no encontrado.", "danger")
        return redirect(url_for("home"))

    delete_file_if_exists(IMAGES_DIR, server.get("image"))
    for srv in server.get("services", []):
        delete_file_if_exists(ICONS_DIR, srv.get("icon"))
    delete_file_if_exists(IMAGES_DIR, f"qr_{id}.png")

    data = [s for s in data if s["id"] != id]
    save_data(data)
    flash(f"Servidor '{server['name']}' eliminado.", "success")
    return redirect(url_for("home"))


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

@app.route("/server/<id>/add_service", methods=["POST"])
def add_service(id):
    data = load_data()
    server = find_server(data, id)
    if not server:
        flash("Servidor no encontrado.", "danger")
        return redirect(url_for("home"))

    icon_name = save_upload(request.files.get("icon"), ICONS_DIR)
    server.setdefault("services", []).append({
        "sid": str(uuid.uuid4()),
        "name": request.form["name"].strip(),
        "address": request.form["address"].strip(),
        "icon": icon_name,
        "info": request.form.get("info", "").strip()
    })
    save_data(data)
    flash("Servicio agregado correctamente.", "success")
    return redirect(url_for("server_detail", id=id))


@app.route("/server/<server_id>/delete_service/<sid>")
def delete_service(server_id, sid):
    data = load_data()
    server = find_server(data, server_id)
    if server:
        for srv in server.get("services", []):
            if srv["sid"] == sid:
                delete_file_if_exists(ICONS_DIR, srv.get("icon"))
                break
        server["services"] = [srv for srv in server.get("services", []) if srv["sid"] != sid]
        save_data(data)
        flash("Servicio eliminado.", "success")
    return redirect(url_for("server_detail", id=server_id))


@app.route("/server/<server_id>/edit_service/<sid>", methods=["POST"])
def edit_service(server_id, sid):
    data = load_data()
    server = find_server(data, server_id)
    if not server:
        flash("Servidor no encontrado.", "danger")
        return redirect(url_for("home"))

    for srv in server.get("services", []):
        if srv["sid"] == sid:
            srv["name"] = request.form["name"].strip()
            srv["address"] = request.form["address"].strip()
            srv["info"] = request.form.get("info", "").strip()
            icon = request.files.get("icon")
            if icon and icon.filename:
                delete_file_if_exists(ICONS_DIR, srv.get("icon"))
                srv["icon"] = save_upload(icon, ICONS_DIR)
            break
    save_data(data)
    flash("Servicio actualizado.", "success")
    return redirect(url_for("server_detail", id=server_id))


# ---------------------------------------------------------------------------
# QR codes
# ---------------------------------------------------------------------------

@app.route("/qr/<id>")
def get_qr(id):
    url = request.host_url + "server/" + id
    img = qrcode.make(url)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    path = os.path.join(IMAGES_DIR, f"qr_{id}.png")
    img.save(path)
    return send_file(path, mimetype='image/png')


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

from flask import Flask, render_template, request, jsonify, redirect, send_from_directory
import sqlite3
import os
import cv2

app = Flask(__name__)

# ------------------ PATH SETTINGS ------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "database.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


print("Database path:", DB)
print("Upload folder:", UPLOAD_FOLDER)

# ------------------ DATABASE ------------------

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        title TEXT,
        image TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ------------------ IMAGE MATCHING ------------------

def compare_images(img1_name, img2_name):
    img1_path = os.path.join(UPLOAD_FOLDER, img1_name)
    img2_path = os.path.join(UPLOAD_FOLDER, img2_name)

    img1 = cv2.imread(img1_path, 0)
    img2 = cv2.imread(img2_path, 0)

    if img1 is None or img2 is None:
        print("⚠️ Image read failed")
        return 0

    orb = cv2.ORB_create(nfeatures=2000)

    kp1, des1 = orb.detectAndCompute(img1, None)
    kp2, des2 = orb.detectAndCompute(img2, None)

    if des1 is None or des2 is None:
        return 0

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)

    return len(matches)
# ------------------ REGISTER ------------------

@app.route("/register", methods=["GET", "POST"])
def register_page():

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DB)
        c = conn.cursor()

        c.execute(
            "INSERT INTO users(username,password) VALUES(?,?)",
            (username, password)
        )

        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("register.html")

# ------------------ LOGIN ------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DB)
        c = conn.cursor()

        c.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        )

        user = c.fetchone()
        conn.close()

        if user:
            return render_template("dashboard.html", user=username)
        else:
            return render_template("login.html",
                                   error="Invalid Username or Password")

    return render_template("login.html")

# ------------------ POST ITEM ------------------

@app.route("/post_item", methods=["POST"])
def post_item():

    user_id = request.form["user_id"]
    item_type = request.form["type"]
    title = request.form["title"]

    file = request.files["image"]

    if file.filename == "":
        return jsonify({"error": "No file selected"})

    filename = file.filename
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    # store only filename in DB
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        INSERT INTO items(user_id,type,title,image)
        VALUES(?,?,?,?)
    """, (user_id, item_type, title, filename))

    conn.commit()
    conn.close()

    return jsonify({"message": "Item Posted"})

# ------------------ FIND MATCH ------------------

@app.route("/find_match/<int:item_id>")
def find_match(item_id):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # get base item
    c.execute("SELECT * FROM items WHERE id=?", (item_id,))
    base_item = c.fetchone()

    if not base_item:
        conn.close()
        return jsonify({"status": "not_found"})

    base_img = base_item[4]
    base_type = base_item[2]

    # match only opposite type
    opposite_type = "found" if base_type == "lost" else "lost"

    c.execute(
        "SELECT * FROM items WHERE type=? AND id!=?",
        (opposite_type, item_id)
    )
    all_items = c.fetchall()

    best_match = None
    max_score = 0

    for item in all_items:
        score = compare_images(base_img, item[4])
        print("Comparing", base_img, "vs", item[4], "Score:", score)
        if score > max_score:
            max_score = score
            best_match = item

    conn.close()

    # ---------- THRESHOLD ----------
    print("DEBUG max_score:", max_score)
    print("DEBUG best_match:", best_match)
    print("DEBUG base_type:", base_type)
    print("DEBUG opposite searched:", opposite_type)
    print("DEBUG total opposite items:", len(all_items))
    THRESHOLD = 300
    if best_match and max_score > THRESHOLD:
        return jsonify({
            "status": "found",
            "image": best_match[4],
            "title": best_match[3]
        })

    return jsonify({"status": "not_found"})

# ------------------ ROUTES ------------------

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        return "Item Uploaded (Later Connect DB)"
    return render_template("upload.html")

@app.route("/view_items")
def view_items():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT * FROM items")
    items = c.fetchall()

    conn.close()

    return render_template("items.html", items=items)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/match_ui/<int:item_id>")
def match_ui(item_id):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT * FROM items WHERE id=?", (item_id,))
    item = c.fetchone()
    conn.close()

    return render_template("match.html", item=item)

# ------------------ MAIN ------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
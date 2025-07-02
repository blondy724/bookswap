from flask import Flask, request, redirect, url_for, render_template, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
import mysql.connector
import bcrypt
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secure_secret_key'

# Configure upload folder
UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="blondy@724",
        database="swap_db"
    )

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user_data = cursor.fetchone()
    connection.close()
    return User(user_data["id"], user_data["username"], user_data["email"], user_data["password_hash"]) if user_data else None

class User(UserMixin):
    def __init__(self, id, username, email, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            flash("Email already registered.", "danger")
            connection.close()
            return redirect(url_for("register"))

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)", 
                       (username, email, hashed_password))
        connection.commit()
        connection.close()

        flash("Registration successful! You can now log in.", "success")  
        return redirect(url_for("login"))  
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user_data = cursor.fetchone()
        connection.close()

        if user_data and bcrypt.checkpw(password.encode('utf-8'), user_data["password_hash"].encode('utf-8')):
            user = User(user_data["id"], user_data["username"], user_data["email"], user_data["password_hash"])
            login_user(user)
            flash("Login successful! Welcome back.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid credentials.", "danger")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully. See you next time!", "success")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT books.id, books.title, books.author, books.genre, books.book_condition, books.image_url, books.description
        FROM books
        WHERE books.owner_id = %s
    """, (current_user.id,))
    books = cursor.fetchall()
    connection.close()
    return render_template("dashboard.html", books=books)

@app.route("/books")
def books():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT books.id, books.title, books.author, books.genre, books.book_condition, books.image_url, books.description, users.username AS owner
        FROM books
        JOIN users ON books.owner_id = users.id
    """)
    books = cursor.fetchall()
    connection.close()
    return render_template("books.html", books=books)

@app.route("/book/<int:book_id>")
def book_details(book_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT books.id, books.title, books.author, books.genre, books.book_condition, books.image_url, books.description, users.username AS owner
        FROM books
        JOIN users ON books.owner_id = users.id
        WHERE books.id = %s
    """, (book_id,))
    book = cursor.fetchone()
    connection.close()

    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for("books"))

    return render_template("book_details.html", book=book)

@app.route("/add_book", methods=["GET", "POST"])
@login_required
def add_book():
    if request.method == "POST":
        title = request.form["title"]
        author = request.form["author"]
        genre = request.form["genre"]
        condition = request.form["condition"]
        description = request.form["description"]

        image_file = request.files["image"]
        image_filename = None
        if image_file and allowed_file(image_file.filename):
            image_filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image_file.save(image_path)

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO books (title, author, genre, book_condition, description, image_url, owner_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (title, author, genre, condition, description, image_filename, current_user.id))
        connection.commit()
        connection.close()

        flash("Book added successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_book.html")

@app.route("/edit_book/<int:book_id>", methods=["GET", "POST"])
@login_required
def edit_book(book_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM books WHERE id = %s AND owner_id = %s", (book_id, current_user.id))
    book = cursor.fetchone()

    if not book:
        flash("Book not found or access denied.", "danger")
        connection.close()
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        title = request.form["title"]
        author = request.form["author"]
        genre = request.form["genre"]
        condition = request.form["condition"]
        description = request.form["description"]

        cursor.execute("""
            UPDATE books
            SET title = %s, author = %s, genre = %s, book_condition = %s, description = %s
            WHERE id = %s AND owner_id = %s
        """, (title, author, genre, condition, description, book_id, current_user.id))
        connection.commit()
        connection.close()
        flash("Book updated successfully!", "success")
        return redirect(url_for("dashboard"))

    connection.close()
    return render_template("edit_book.html", book=book)

@app.route("/swap_book/<int:book_id>", methods=["POST"])
@login_required
def swap_book(book_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM books WHERE id = %s", (book_id,))
    book = cursor.fetchone()

    if not book:
        flash("Book not found.", "danger")
        connection.close()
        return redirect(url_for("books"))

    flash(f"You requested to swap '{book['title']}'. Feature coming soon!", "info")
    connection.close()
    return redirect(url_for("books"))

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        message = request.form["message"]
        flash("Thank you for reaching out. We will get back to you soon.", "success")
        return redirect(url_for("contact"))
    return render_template("contact.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

if __name__ == "__main__":
    app.run(debug=True)

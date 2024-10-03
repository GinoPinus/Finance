import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    portfolio = db.execute(
        "SELECT * FROM portfolio WHERE user_id = ?", session["user_id"]
    )
    # current prices of each stock
    prices = []
    # total value of each holding
    total = 0

    for i, stock in enumerate(portfolio):
        prices.append(lookup(stock["symbol"])["price"])
        total += prices[i] * stock["shares"]

    return render_template(
        "index.html",
        portfolio=portfolio,
        prices=prices,
        balance=db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"]),
        total=total,
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        results = lookup(symbol)
        try:
            nshares = int(request.form.get("shares"))
        except ValueError:
            return apology("invalid number of shares")

        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        # checking the validity of inputs
        if not results:
            return apology("symbol not found")

        if nshares <= 0:
            return apology("invalid number of shares")

        final_price = nshares * float(results["price"])

        if balance[0]["cash"] >= final_price:

            db.execute(
                "INSERT INTO transactions (user_id, symbol, shares, price, action) values(?, ?, ?, ?, ?)",
                session["user_id"],
                results["symbol"],
                nshares,
                final_price,
                "buy",
            )
            db.execute(
                "UPDATE users SET cash = ? WHERE id = ?",
                balance[0]["cash"] - final_price,
                session["user_id"],
            )

            rows = db.execute(
                "SELECT * FROM portfolio WHERE user_id = ? AND symbol = ?",
                session["user_id"],
                results["symbol"],
            )

            if len(rows) != 0:
                db.execute(
                    "UPDATE portfolio SET shares = shares + ? WHERE user_id = ?",
                    nshares,
                    session["user_id"],
                )
            else:
                db.execute(
                    "INSERT INTO portfolio (user_id, symbol, shares) values (?, ?, ?)",
                    session["user_id"],
                    results["symbol"],
                    nshares,
                )

        else:
            return apology("not enough money")

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute(
        "SELECT * FROM transactions WHERE user_id = ?", session["user_id"]
    )

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        print("Symbol:", symbol)

        results = lookup(symbol)
        print("Results:", results)

        # checking the validity of inputs
        if not results:
            return apology("symbol not found")

        return render_template("quoted.html", results=results)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # checking the validity of inputs
        if not username:
            return apology("must provide username")

        if not password:
            return apology("must provide password")

        if not password == confirmation:
            return apology("the passwords do not match")

        passhash = generate_password_hash(password)

        try:
            db.execute(
                "INSERT INTO users (username, hash) values (?, ?)", username, passhash
            )
        except ValueError:
            return apology("username already exists")

        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":
        stock = request.form.get("symbol")

        if not stock:
            return apology("must provide symbol")
        stock = lookup(stock)
        shares = request.form.get("shares")

        # checking the validity of inputs
        if not stock["symbol"]:
            return apology("invalid symbol")

        if not shares:
            return apology("invalid number of shares")
        shares = int(shares)
        if shares <= 0:
            return apology("invalid number of shares")

        # Selecting all the table i need to update
        portfolio = db.execute(
            "SELECT * FROM portfolio WHERE user_id = ? AND symbol = ?",
            session["user_id"],
            stock["symbol"],
        )
        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        final_price = shares * float(stock["price"])

        if len(portfolio) != 0 and portfolio[0]["shares"] >= shares:
            db.execute(
                "INSERT INTO transactions (user_id, symbol, shares, price, action) values(?, ?, ?, ?, ?)",
                session["user_id"],
                stock["symbol"],
                -shares,
                final_price,
                "sell",
            )
            db.execute(
                "UPDATE users SET cash = ? WHERE id = ?",
                balance[0]["cash"] + final_price,
                session["user_id"],
            )
            db.execute(
                "UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?",
                (portfolio[0]["shares"] - shares),
                session["user_id"],
                stock["symbol"],
            )
        else:
            return apology("invalid shares number")

        return redirect("/")
    else:
        stocks = db.execute(
            "SELECT * FROM portfolio WHERE user_id = ? AND shares > 0",
            session["user_id"],
        )

        return render_template("sell.html", stocks=stocks)


@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    """Change user's passoword"""

    if request.method == "POST":
        old_password = request.form.get("old-password")
        new_password = request.form.get("new-password")
        confirmation = request.form.get("confirmation")

        # Ensure old password was submitted
        if not old_password:
            return apology("must provide old passoword")

        # Ensure new password was submitted
        elif not new_password:
            return apology("must provide new password")

        # Ensure new passwords match
        if not new_password == confirmation:
            return apology("the passwords do not match")

        if old_password == new_password:
            return apology("old password and new passoword are the same")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

        # Ensure username exists and password is correct
        if not check_password_hash(rows[0]["hash"], old_password):
            return apology("old password not correct")

        passhash = generate_password_hash(new_password)

        db.execute(
            "UPDATE users SET hash = ? WHERE id = ?", passhash, session["user_id"]
        )

        return redirect("/login")

    else:
        return render_template("password.html")

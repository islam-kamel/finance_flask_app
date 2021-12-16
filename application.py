import os

from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

now = datetime.now()
format_date = now.strftime("%d-%m-%Y %H:%M:%S")


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """ Show portfolio of stocks """
    shares = db.execute("SELECT stock_symbol, stock_name, price, shares_count FROM stocks WHERE stocks_list = ? ",
                        session["username"])
    total = 0
    for i in shares:
        """ Total stocks price """
        temp = i["price"] * i["shares_count"]
        # Set price to total
        total += temp

    user_cash = db.execute("SELECT cash FROM users WHERE username = ?", session["username"])
    return render_template("index.html", shares=shares, cash=user_cash[0]["cash"], total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """ Buy shares of stock """
    if request.method == "POST":

        # Get Price of Stock And Set All Data to Variables
        symbol_data = lookup(request.form.get("symbol").upper().strip())

        if not symbol_data:
            return apology("invalid Symbol", 400)

        # Verify user input
        if symbol_data:
            name = symbol_data["name"]
            price = symbol_data["price"]
            symbol = symbol_data["symbol"]
            try:
                shares_count = int(request.form.get("shares_count"))
                if shares_count < 1:
                    flash("Enter Valid Count 😐", "info")
                    return redirect("/buy")
            except ValueError:
                flash("Enter Valid Count 😐", "info")
                return redirect("/buy")
        else:
            flash("Enter Valid Symbol 😐", "info")
            return redirect("/buy")

        # Get Current Cash From Current User
        user_cash = db.execute("SELECT cash FROM users WHERE username = ?", session["username"])

        # Set Total Price For Stock To total_price
        total_price = float(price) * int(shares_count)

        # Check User Cash Enough to By shares
        if user_cash[0]["cash"] >= total_price:
            new_cash = user_cash[0]["cash"] - total_price

            # Update User Cash After Buy Shares
            db.execute("UPDATE users SET cash = ? WHERE username = ?", new_cash, session["username"])

            # Get Specific Stock From Table For Current User
            row = db.execute("SELECT stock_symbol FROM stocks WHERE stock_symbol = ? AND stocks_list = ?",
                             symbol, session["username"])

            # Check Stock Is Exists
            if row.__len__() != 1:
                # if Stock Not Exists Insert Now Row In Table
                db.execute("INSERT INTO stocks(stocks_list, stock_symbol, price, shares_count, stock_name) "
                           "VALUES(?,?,?,?,?)", session["username"], symbol, price, shares_count, name)
            else:
                # if Stock Exists Update Count, Set New Price
                current_count = db.execute(
                    "SELECT shares_count FROM stocks WHERE stocks_list = ? AND stock_symbol = ? ",
                    session["username"], symbol)

                current_count[0]["shares_count"] += shares_count
                db.execute("UPDATE stocks SET shares_count = ?, price = ? WHERE stocks_list = ? AND stock_symbol = ?",
                           current_count[0]["shares_count"], price, session["username"], symbol)

            # Set All Transacted For Current User To History
            db.execute("INSERT INTO history(history_list, symbol, shares_count, price, transacted ) "
                       "VALUES(?,?,?,?,?)", session["username"], symbol, shares_count, price, format_date)

            flash("Payment completed successfully 😎", "success")
            return redirect("/")

        flash("You don't have enough money to buy! 😓", "danger")
        return redirect("/")
    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """TODO Show history of transactions"""
    history = db.execute("SELECT symbol,shares_count,price,transacted FROM history WHERE history_list = ?",
                         session["username"])
    return render_template("history.html", historys=history)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username").strip())

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]

        # Redirect user to home page
        flash(f"Welcome To Back {session['username']} 😘", "success")
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
    """ stock quote."""
    if request.method == "POST":
        quote = lookup(request.form.get("symbol").upper().strip())

        if not quote:
            return apology("invalid symbol", 400)

        flash("Now you can buy from within this page 🙂", "info")
        return render_template("quote.html", quote=quote)
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """ Register user """
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password")
        password2 = request.form.get("confirmation")

        if password != password2:
            # flash("Password Not Matching 😓", "danger")
            return apology("Password Not Matching", 400)
            # return redirect("/register")
        elif password.__len__() < 8:
            # flash("Minimum password length to at least a value of 8 👌.", "info")
            return apology("Minimum password length to at least a value of 8", 400)

        try:
            db.execute("INSERT INTO users(username,hash) VALUES(?, ?)", username, generate_password_hash(password))
        except ValueError:
            return apology("Username already exists", 400)

        flash("successfully registered 🤩", "success")
        return redirect('/login')
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        # Fetch the user's current balance
        cash = db.execute("SELECT cash FROM users WHERE username = ?", session["username"])

        # Get stock symbol to form
        symbol = request.form.get("symbol").upper().strip()

        # Verify user input
        try:
            count = int(request.form.get("shares_count"))
        except ValueError:
            flash("You cannot sell 0 shares 😟", "warning")
            return redirect("/sell")

        if count < 1:
            return apology("invalid shares count", 400)

        # Verify user input
        try:
            sell_data = lookup(symbol)
        except TypeError:
            flash("Check Enter Your Symbol Or Internet Connection 😟", "warning")
            return redirect("/sell")

        # total selling price
        sell_price = (sell_data["price"] * count) + cash[0]["cash"]

        # Fetch shares count from database
        shares_count = db.execute("SELECT shares_count FROM stocks WHERE stocks_list = ? AND stock_symbol = ?",
                                  session["username"], symbol)
        # Verify user input
        if count == 0:
            flash("You cannot sell 'Zero' shares 😓", "danger")
            return redirect("/sell")

        elif shares_count[0]["shares_count"] > count:

            # Add balance to user
            db.execute("UPDATE users SET cash = ? WHERE username = ?",
                       sell_price, session["username"])

            # Add new count of stocks
            db.execute("UPDATE stocks SET shares_count = ? WHERE stocks_list = ? AND stock_symbol = ?",
                       shares_count[0]["shares_count"] - count, session["username"], symbol)

            # Add transacted example -1
            negative = -abs(count)
            db.execute("INSERT INTO history(symbol, shares_count, price, transacted,history_list) VALUES(?,?,?,?,?)",
                       symbol, negative, sell_data["price"], format_date, session["username"])
            flash("Sale completed successfully 🤑", "success")
            return redirect("/")

        elif shares_count[0]["shares_count"] == count:
            """ The same previous operations, with the entire stock field cleared from the database  """

            db.execute("UPDATE users SET cash = ? WHERE username = ?",
                       sell_price, session["username"])

            db.execute("DELETE FROM stocks WHERE stocks_list = ? AND stock_symbol = ?",
                       session["username"], symbol)

            negative = -abs(count)
            db.execute("INSERT INTO history(symbol, shares_count, price, transacted,history_list) VALUES(?,?,?,?,?)",
                       symbol, negative, sell_data["price"], format_date, session["username"])

            flash("Sale completed successfully 🤑", "success")
            return redirect("/")
        else:
            flash("Sorry, you don't have enough shares! 😟", "warning")
            return redirect("/sell")

    symbols = db.execute("SELECT stock_symbol FROM stocks WHERE stocks_list = ?", session["username"])
    return render_template("sell.html", symbols=symbols)


@app.route("/wallet", methods=["GET", "POST"])
@login_required
def wallet():
    """ Add more imaginary balance """

    # Fetch the user's current balance
    cash = db.execute("SELECT cash FROM users WHERE username = ?", session["username"])

    if request.method == "POST":

        # Verify user input
        if int(request.form.get("cash")) < 1:
            flash("The operation failed 😓", "danger")
            return redirect("/")

        # Add the new balance to the user's current balance
        credit = int(cash[0]["cash"]) + int(request.form.get("cash"))

        # Add the new balance to the user's current balance
        db.execute("UPDATE users SET cash = ? WHERE username = ?", credit, session["username"])
        flash("Balance added successfully 😄", "success")
        return redirect("/")

    flash("Add more virtual balance for free 🤑", "info")
    return render_template("wallet.html", cash=cash[0]["cash"])


@app.route("/clear_history")
@login_required
def clear():
    db.execute("DELETE FROM history WHERE history_list = ?", session["username"])
    flash("History deleted successfully 👍", "success")
    return redirect("/history")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

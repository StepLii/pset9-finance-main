# apk token: pk_6ec47f7cc208468eb0a531c4093b2ffc

import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


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
    """Show portfolio of stocks"""
    current_user_id = session["user_id"]
    user_cash = db.execute("SELECT cash FROM users WHERE id = ?", current_user_id)
    cash = user_cash[0]["cash"]
    cash_balance = user_cash[0]["cash"]
    records = db.execute("SELECT symbol, price, shares FROM records WHERE user_id = ?", current_user_id)
    
    # add current price & total value into the dict
    for rows in records:
        lookedup = lookup(rows["symbol"])
        current_price = lookedup["price"]
        rows["current_price"] = current_price
        rows["total_value"] = (current_price * int(rows["shares"]))
        cash = cash + rows["total_value"]

    # rows: symbol, price, shares, current_price, total_value_of_that_stock
    # records: each dictionary: symbol, price, shares, current_price, total_value_of_that_stock

    return render_template("index.html", cash=cash, records=records, cash_balance=cash_balance)

    # no need return apology("TODO")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = lookup(request.form.get("symbol"))
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Shares must be positive integers")
            
        if not symbol or not shares:
            return apology("Invalid Input", 400)
            
        shares = int(request.form.get("shares"))
        if shares <= 0:
            return apology("Invalid Shares Input", 400)

        # check enough cash or not
        current_price = symbol["price"]
        current_user_id = session["user_id"]
        cash = db.execute("SELECT cash FROM users WHERE id = ?", current_user_id)
        if (float(current_price) * int(shares)) > float(cash[0]["cash"]):
            return apology("Not enough cash")
        else:

            date = datetime.now()
            remaining_cash = float(cash[0]["cash"]) - (float(current_price) * int(shares))
            db.execute("UPDATE users SET cash = ? WHERE id = ?", remaining_cash, current_user_id)
            current_record = db.execute("SELECT * FROM records WHERE user_id = ? AND symbol = ?", current_user_id, symbol["symbol"])
            if not current_record:
                db.execute("INSERT INTO records(user_id, symbol, price, shares, date) VALUES (?, ?, ?, ?, ?)",
                           current_user_id, symbol["symbol"], symbol["price"], shares, date)
                db.execute("INSERT INTO all_records (user_id, symbol, buysell, price, shares, date) VALUES (?, ?, ?, ?, ?, ?)",
                           current_user_id, symbol["symbol"], "Buy", symbol["price"], shares, date)
            else:
                total_shares = int(shares) + int(current_record[0]["shares"])
                db.execute("UPDATE records SET shares = ? WHERE user_id = ? AND symbol = ?",
                           total_shares, current_user_id, symbol["symbol"])
                db.execute("INSERT INTO all_records (user_id, symbol, buysell, price, shares, date) VALUES (?, ?, ?, ?, ?, ?)",
                           current_user_id, symbol["symbol"], "Buy", symbol["price"], shares, date)
            return redirect("/")
            
            
@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    current_user_id = session["user_id"]
    history = db.execute("SELECT * FROM all_records WHERE user_id = ?", current_user_id)
    return render_template("history.html", history=history)

    # return apology("TODO")


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
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
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Missing Ticker")
        quote = lookup(symbol)
        if not quote:
            return apology("Incorrect Ticker Input")
        company = quote["name"]
        symbol = quote["symbol"]
        price = quote["price"]
        return render_template("quoted.html", company=company, symbol=symbol, price=price)
    # seems not need this apology
    # return apology("TODO")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        name = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        users = db.execute("SELECT * FROM users WHERE username = ?", name)
        # if the username already exist
        if len(users) != 0:
            return apology("Username already exist!", 400)
        if not name:
            return apology("Missing Username", 400)
        if not password:
            return apology("Missing Password", 400)
        if password != confirmation:
            return apology("Passwords do not match", 400)

        password_hash = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", name, password_hash)

        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # input stock symbol, select menu: name = symbol
    # input number of shares: name = shares
    current_user_id = session["user_id"]
    if request.method == "GET":
        symbol = db.execute("SELECT symbol FROM records WHERE user_id = ?", current_user_id)
        return render_template("sell.html", symbol=symbol)
    else:
        # get data from sell.html
        symbol = request.form.get("symbol")
        shares_to_sell = int(request.form.get("shares"))
        # check if the user own the stock
        stock_owned = db.execute("SELECT symbol FROM records WHERE user_id = ?", current_user_id)
        STOCK_OWNED_LIST = []
        for rows in stock_owned:
            STOCK_OWNED_LIST.append(rows["symbol"])
        if not symbol or symbol not in STOCK_OWNED_LIST:
            return apology("Invalid Stock Choice")

        # figure out how many shares the user own
        shares_owned = db.execute("SELECT shares FROM records WHERE user_id =? AND symbol = ?", current_user_id, symbol)
        shares_owned_number = int(shares_owned[0]["shares"])
        if shares_to_sell > shares_owned_number:
            return apology("Not Enough Shares")
        if shares_to_sell <= 0:
            return apology("Invalid Shares Input")

        # sell successfully
        # update shares number in records
        date = datetime.now()
        shares_left = shares_owned_number - shares_to_sell
        if (shares_left == 0):
            db.execute("DELECT FROM records WHERE user_id = ? AND symbol = ?", current_user_id, symbol)
        else:
            db.execute("UPDATE records SET shares = ? WHERE user_id = ? AND symbol = ?", shares_left, current_user_id, symbol)

        # update cash balance
        lookedup = lookup(symbol)
        selling_price = lookedup["price"]
        cash_deposit = selling_price * shares_to_sell
        cash = db.execute("SELECT cash FROM users WHERE id = ?", current_user_id)
        cash_deposit += cash[0]["cash"]
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_deposit, current_user_id)

        # update history
        db.execute("INSERT INTO all_records (user_id, symbol, buysell, price, shares, date) VALUES (?, ?, ?, ?, ?, ?)",
                   current_user_id, symbol, "Sell", selling_price, shares_to_sell, date)

        return redirect("/")
    # return apology("TODO")
    
    
@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    """Change Account Password"""

    if request.method == "GET":
        return render_template("password.html")
    else:
        current_user_id = session["user_id"]
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirm = request.form.get("confirm")
        user_info = db.execute("SELECT hash FROM users WHERE id = ?", current_user_id)

        # check if the old password is correct
        if not check_password_hash(user_info[0]["hash"], request.form.get("old_password")):
            return apology("Incorrect Password")

        # check if the new password matches the confirm password
        confirm_hash = generate_password_hash(confirm)
        if not new_password == confirm:
            return apology("New Passwords Do Not Match")

        # update the user database for new password
        db.execute("UPDATE users SET hash = ? WHERE id = ?", confirm_hash, current_user_id)
        return redirect("/")
        
        
def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)
    
    
# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

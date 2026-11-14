import os
import sqlite3
from datetime import datetime

from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)

PARTIES = ["ACN", "ANPP", "CDC", "CPP", "DPP",
           "JP", "LABO", "PDP", "PPA"]

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bincom.db")


# ---------- DATABASE (SQLite) ----------
def db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def query(sql, args=()):
    conn = db()
    try:
        cur = conn.execute(sql, args)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ---------- PAGE DESIGN ----------
BASE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bincom Election Results</title>
<style>
body {
    font-family: Arial, sans-serif;
    max-width: 760px;
    margin: 30px auto;
    padding: 0 15px;
}
nav a {
    margin-right: 14px;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin-top: 14px;
}
td, th {
    border: 1px solid #ccc;
    padding: 8px;
    text-align: left;
}
select, input, button {
    padding: 8px;
    margin: 5px 0;
    max-width: 100%;
}
.err {
    color: #b00;
}
</style>
</head>
<body>
<nav>
<a href="/">Q1: Polling Unit</a>
<a href="/lga">Q2: LGA Total</a>
<a href="/new">Q3: New Result</a>
</nav>
<hr>
{{ body|safe }}
</body>
</html>
"""


def page(body_tpl, **ctx):
    body = render_template_string(body_tpl, **ctx)
    return render_template_string(BASE, body=body)


# ---------- Q1: POLLING UNIT RESULTS ----------
@app.route("/", methods=["GET", "POST"])
def polling_unit():

    units = query("""
        SELECT uniqueid, polling_unit_name, polling_unit_number
        FROM polling_unit
        ORDER BY polling_unit_name
    """)

    selected = request.form.get("pu") or request.args.get("pu")
    results = None
    name = None

    if selected:
        results = query("""
            SELECT party_abbreviation AS party,
                   party_score AS score,
                   entered_by_user AS entered_by
            FROM announced_pu_results
            WHERE polling_unit_uniqueid = ?
            ORDER BY date_entered, result_id
        """, (str(selected),))

        row = next(
            (u for u in units if str(u["uniqueid"]) == str(selected)),
            None
        )

        name = row["polling_unit_name"] if row else selected

    return page("""
    <h2>Polling Unit Result</h2>

    <form method="post">
        <select name="pu" required>
            <option value="">-- select polling unit --</option>

            {% for u in units %}
            <option value="{{u.uniqueid}}"
            {% if selected|string == u.uniqueid|string %}selected{% endif %}>
                {{u.polling_unit_name or 'Unnamed'}}
                ({{u.polling_unit_number}}) [ID {{u.uniqueid}}]
            </option>
            {% endfor %}
        </select>

        <button type="submit">Show result</button>
    </form>

    {% if results is not none %}
        <h3>{{name}}</h3>

        {% if results %}
        <table>
            <tr>
                <th>Party</th>
                <th>Score</th>
                <th>Entered by</th>
            </tr>

            {% for r in results %}
            <tr>
                <td>{{r.party}}</td>
                <td>{{r.score}}</td>
                <td>{{r.entered_by}}</td>
            </tr>
            {% endfor %}
        </table>

        {% else %}
        <p>No results recorded for this polling unit.</p>
        {% endif %}
    {% endif %}
    """, units=units, selected=selected,
         results=results, name=name)


# ---------- Q2: LGA TOTAL RESULTS ----------
@app.route("/lga", methods=["GET", "POST"])
def lga_total():

    lgas = query("""
        SELECT lga_id, lga_name
        FROM lga
        ORDER BY lga_name
    """)

    selected = request.form.get("lga")
    results = None
    total = 0
    name = None

    if selected:

        # Aggregated directly from polling_unit + announced_pu_results
        # (announced_lga_results is NOT used)
        results = query("""
            SELECT r.party_abbreviation AS party,
                   SUM(r.party_score) AS score
            FROM polling_unit p
            JOIN announced_pu_results r
              ON r.polling_unit_uniqueid = CAST(p.uniqueid AS TEXT)
            WHERE p.lga_id = ?
            GROUP BY r.party_abbreviation
            ORDER BY score DESC
        """, (selected,))

        total = sum(int(r["score"]) for r in results)

        lga = next(
            (l for l in lgas if str(l["lga_id"]) == selected),
            None
        )

        name = lga["lga_name"] if lga else "Selected LGA"

    return page("""
    <h2>Total Result by Local Government</h2>

    <form method="post">
        <select name="lga" required>
            <option value="">-- select LGA --</option>

            {% for l in lgas %}
            <option value="{{l.lga_id}}"
            {% if selected == l.lga_id|string %}selected{% endif %}>
                {{l.lga_name}}
            </option>
            {% endfor %}
        </select>

        <button type="submit">Show total</button>
    </form>

    {% if results is not none %}
        <h3>{{name}}</h3>

        {% if results %}
        <table>
            <tr>
                <th>Party</th>
                <th>Total score</th>
            </tr>

            {% for r in results %}
            <tr>
                <td>{{r.party}}</td>
                <td>{{r.score}}</td>
            </tr>
            {% endfor %}

            <tr>
                <th>All parties</th>
                <th>{{total}}</th>
            </tr>
        </table>

        {% else %}
        <p>No polling unit results for this LGA.</p>
        {% endif %}
    {% endif %}
    """, lgas=lgas, selected=selected,
         results=results, total=total, name=name)


# ---------- Q3: ADD NEW POLLING UNIT RESULTS ----------
@app.route("/new", methods=["GET", "POST"])
def new_result():

    parties = PARTIES

    wards = query("""
        SELECT w.uniqueid, w.ward_id, w.ward_name,
               w.lga_id, l.lga_name
        FROM ward w
        LEFT JOIN lga l ON l.lga_id = w.lga_id
        ORDER BY l.lga_name, w.ward_name
    """)

    err = None

    if request.method == "POST":

        try:
            ward_id = request.form.get("ward", "").strip()

            ward = next(
                (w for w in wards if str(w["uniqueid"]) == ward_id),
                None
            )

            if not ward:
                raise ValueError("Please select a valid ward.")

            name = request.form.get("name", "").strip()
            number = request.form.get("number", "").strip()
            user = request.form.get("user", "").strip()

            if not name or not number or not user:
                raise ValueError("All fields are required.")

            scores = {}

            for party in parties:
                value = request.form.get(party, "").strip()

                if not value:
                    raise ValueError(f"Enter a score for {party}.")

                try:
                    score = int(value)
                except ValueError:
                    raise ValueError(
                        f"{party} score must be a whole number."
                    )

                if score < 0 or score > 2147483647:
                    raise ValueError(
                        f"Invalid score entered for {party}."
                    )

                scores[party] = score

            conn = db()

            try:
                entered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ip_address = request.remote_addr or ""

                cur = conn.execute("""
                    INSERT INTO polling_unit
                    (
                        polling_unit_id,
                        ward_id,
                        lga_id,
                        uniquewardid,
                        polling_unit_number,
                        polling_unit_name,
                        entered_by_user,
                        date_entered,
                        user_ip_address
                    )
                    VALUES (0, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ward["ward_id"],
                    ward["lga_id"],
                    ward["uniqueid"],
                    number,
                    name,
                    user,
                    entered_at,
                    ip_address
                ))

                pu_id = cur.lastrowid

                for party, score in scores.items():
                    conn.execute("""
                        INSERT INTO announced_pu_results
                        (
                            polling_unit_uniqueid,
                            party_abbreviation,
                            party_score,
                            entered_by_user,
                            date_entered,
                            user_ip_address
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        str(pu_id),
                        party,
                        score,
                        user,
                        entered_at,
                        ip_address
                    ))

                conn.commit()

            except Exception:
                conn.rollback()
                raise

            finally:
                conn.close()

            return redirect(
                url_for("polling_unit", pu=pu_id)
            )

        except ValueError as e:
            err = str(e)

        except Exception:
            app.logger.exception("Failed to save polling unit results")
            err = "Could not save results. Please check your database connection."

    return page("""
    <h2>Add New Polling Unit Result</h2>

    {% if err %}
        <p class="err">{{err}}</p>
    {% endif %}

    <form method="post">

        <label>Ward (LGA)</label><br>

        <select name="ward" required>
            <option value="">-- select ward --</option>

            {% for w in wards %}
            <option value="{{w.uniqueid}}">
                {{w.ward_name}} ({{w.lga_name}})
            </option>
            {% endfor %}
        </select>

        <br>

        <label>Polling unit name</label><br>
        <input name="name" required><br>

        <label>Polling unit number</label><br>
        <input name="number" required><br>

        <label>Entered by</label><br>
        <input name="user" required><br>

        <h3>Party Scores</h3>

        {% for p in parties %}
            <label>{{p}}</label><br>
            <input type="number"
                   min="0"
                   step="1"
                   name="{{p}}"
                   value="0"
                   required>
            <br>
        {% endfor %}

        <button type="submit">Save result</button>

    </form>
    """, parties=parties, wards=wards, err=err)


# ---------- START APPLICATION (local testing only) ----------
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=False
    )
"""Readable, escaped HTML for the discovery table and question list."""
from html import escape


def fraud_table(rows):
    body = ""
    for row in rows:
        body += ("<tr><th scope='row'><strong>" + escape(row["vector"]) +
                 "</strong><span class='risk-description'>" + escape(row["description"]) + "</span></th>" +
                 "".join("<td>" + escape(row[key]) + "</td>" for key in ("impact", "signals", "mitigation")) + "</tr>")
    return ("<div class='risk-table-scroll' tabindex='0' role='region' aria-label='Fraud vectors table'>"
            "<table class='risk-table'><caption>Potential fraud vectors · hypotheses to validate</caption>"
            "<thead><tr><th scope='col'>Fraud vector</th><th scope='col'>Business impact</th>"
            "<th scope='col'>Detection signals</th><th scope='col'>Potential mitigations</th></tr></thead>"
            "<tbody>" + body + "</tbody></table></div>")


def question_list(questions):
    return "<ol class='discovery-questions'>" + "".join("<li>" + escape(q) + "</li>" for q in questions) + "</ol>"

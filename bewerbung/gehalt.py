"""Vergleichswerte in ihrer ursprünglichen Einheit mit Quellenbezug festhalten."""
from decimal import Decimal
import re
from .core import text


def marktwert(workspace, jid, title, source, role, region, basis, period, statistic, value, currency, data_as_of):
    """Eine belegte Zahl pro Bezugsgruppe; Durchschnitt, Median und Quartile bleiben erkennbar."""
    if not re.fullmatch(r"[0-9]{1,9}(?:[.,][0-9]{1,2})?", str(value)):
        raise ValueError("Exakten Betrag ohne Tausendertrennzeichen mit höchstens zwei Nachkommastellen angeben.")
    amount = Decimal(str(value).replace(",", "."))
    if amount <= 0:
        raise ValueError("Der Marktwert muss positiv sein.")
    def number(n):
        return format(n.quantize(Decimal("0.01")), ",.2f").replace(",", " ").replace(".", ",")
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise ValueError("Währung mit drei Buchstaben angeben.")
    currency = currency.upper()
    group = text(role, "Berufsgruppe", 300) + " · " + text(region, "Region", 300)
    original = f"{statistic}: {number(amount)} {currency} brutto pro {period} ({basis})."
    lines = [group, original, "Datenstand: " + text(data_as_of, "Datenstand", 200)]
    if period == "Monat":
        lines.append(f"Jahreshochrechnung: {number(amount * 12)} {currency} (12 Monatswerte).")
    key = f"{title} · {group} · {statistic} · {period} · {basis} · {currency}"
    workspace.add_note(jid, "marktvergleich", key, "\n".join(lines), [source])


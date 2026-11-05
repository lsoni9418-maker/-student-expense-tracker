"""AI logic: next-month expense prediction and rule-based saving suggestions.

Prediction = 50% linear regression trend + 50% weighted moving average
(recent months weigh more). Pure Python, so it is easy to read and test.
"""


def forecast(values):
    """values: monthly totals, oldest -> newest. Returns the predicted next value."""
    n = len(values)
    if n == 0:
        return 0.0
    if n == 1:
        return max(float(values[0]), 0.0)
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    den = sum((x - mean_x) ** 2 for x in range(n))
    slope = sum((x - mean_x) * (v - mean_y) for x, v in enumerate(values)) / den
    regression = mean_y + slope * (n - mean_x)          # trend line value at x = n
    weights = list(range(1, n + 1))
    weighted = sum(w * v for w, v in zip(weights, values)) / sum(weights)
    prediction = 0.5 * regression + 0.5 * weighted
    return max(prediction, 0.0)


def confidence_for(months_used):
    if months_used >= 4:
        return "high"
    if months_used >= 2:
        return "medium"
    return "low"


def _rs(n):
    return "₹{:,.0f}".format(n)


def _tip(kind, title, text):
    return {"type": kind, "title": title, "text": text}


def build_suggestions(s, pred):
    """s: month summary dict, pred: prediction dict (or None). Returns a list of tips."""
    spent, income, budget = s["spent"], s["income"], s["budget"]
    if spent <= 0:
        return [_tip("info", "Start tracking", "Add your first expense and I will start finding ways for you to save.")]
    tips = []
    day, dim = max(s["day_of_month"], 1), s["days_in_month"]

    if budget > 0:
        if spent > budget:
            tips.append(_tip("danger", "You are over budget",
                             f"You have spent {_rs(spent - budget)} more than your {_rs(budget)} budget. "
                             "Pause non-essential spending for the rest of the month."))
        else:
            used = spent / budget * 100
            projected = spent / day * dim
            if used >= 80:
                tips.append(_tip("warning", "Budget almost used",
                                 f"You have used {used:.0f}% of your budget. Only {_rs(budget - spent)} is left."))
            elif s["is_current"] and day >= 3 and projected > budget:
                left_days = max(dim - day, 1)
                tips.append(_tip("warning", "On track to overspend",
                                 f"At this pace you will spend about {_rs(projected)}. "
                                 f"Keep to roughly {_rs((budget - spent) / left_days)} per day to stay within budget."))
            else:
                tips.append(_tip("success", "Budget on track", f"You have used {used:.0f}% of your budget. Keep it up!"))
    else:
        tips.append(_tip("info", "Set a monthly budget", "A budget gives you a clear limit. Set one in Income & Budget."))

    cats = s["categories"]
    if cats:
        top = cats[0]
        if top["pct"] >= 40:
            tips.append(_tip("info", f"{top['category']} is your biggest spend",
                             f"It makes up {top['pct']:.0f}% of your spending. Cutting it by 10% would save about "
                             f"{_rs(top['total'] * 0.1)} this month."))
    fun = sum(c["total"] for c in cats if c["category"] in ("Entertainment", "Shopping"))
    if spent > 0 and fun / spent >= 0.25:
        tips.append(_tip("warning", "Wants are high",
                         f"Entertainment and Shopping are {fun / spent * 100:.0f}% of your spending. "
                         "Try a weekly limit for these two."))

    if income > 0:
        rate = (income - spent) / income
        if rate < 0:
            tips.append(_tip("danger", "Spending more than your income",
                             f"You have spent {_rs(spent - income)} more than your income this month."))
        elif rate < 0.2:
            tips.append(_tip("info", "Aim to save 20%",
                             f"Saving 20% of your income means keeping {_rs(income * 0.2)} aside. "
                             f"You are currently at {rate * 100:.0f}%."))
        else:
            tips.append(_tip("success", "Great saving habit", f"You are saving {rate * 100:.0f}% of your income so far."))

    if pred and pred.get("predicted_total", 0) > 0:
        p = pred["predicted_total"]
        if income > 0 and p > income:
            tips.append(_tip("warning", "Next month may exceed your income",
                             f"Predicted spend is {_rs(p)} but your income is {_rs(income)}. Plan ahead."))
        elif budget > 0 and p > budget:
            tips.append(_tip("warning", "Next month may exceed your budget",
                             f"Predicted spend is {_rs(p)}, above your {_rs(budget)} budget."))
    return tips[:6]

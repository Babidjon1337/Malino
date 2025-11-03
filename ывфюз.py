import calendar
from datetime import date, timedelta, datetime
from urllib.parse import quote

# today = date.today()
# next_month_date = today + timedelta(
#     days=calendar.monthrange(date.today().year, date.today().month)[1]
# )
# print(today)
# print(next_month_date)
today = datetime.now()
# Исправлено: datetime.now() и calendar.monthrange
_, days_in_month = calendar.monthrange(today.year, today.month)
end_date = today + timedelta(days=days_in_month)
# Преобразуем в datetime для совместимости с моделью (если поле DateTime)


# print(datetime.now())
# print(days_in_month)
# print(end_date)

# today_start = datetime.now().replace(
#     hour=0, minute=0, second=0, microsecond=0
# ) + timedelta(days=1)
# today_end = today_start + timedelta(days=1)
# print(today_start)
# print(today_end)
# print("-------------------")

# question = "Родион выввв '' "
# encoded_question = quote(question)
# print("24" in "Пробная подписка — 99 ₽ / 2 часа")


# print(True == True)
args = "gift-month"
print("gift" in args)

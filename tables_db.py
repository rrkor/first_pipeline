# Файл перезаписывается автоматически при создании/отмене брони (booking.py).
# TABLES можно править руками, BOOKINGS — лучше через агента.

OPENING_HOURS = {'open': '11:00', 'close': '23:00'}

BOOKING_DURATION_MIN = 120

TABLES = {1: {'seats': 2, 'zone': 'у окна'},
 2: {'seats': 2, 'zone': 'у окна'},
 3: {'seats': 4, 'zone': 'основной зал'},
 4: {'seats': 4, 'zone': 'основной зал'},
 5: {'seats': 4, 'zone': 'основной зал'},
 6: {'seats': 6, 'zone': 'основной зал'},
 7: {'seats': 8, 'zone': 'веранда'}}

BOOKINGS = [{'id': 1,
  'table_id': 3,
  'date': '2026-10-15',
  'time': '19:00',
  'guests': 4,
  'name': 'Иван',
  'phone': '+79991234567'},
 {'id': 2,
  'table_id': 7,
  'date': '2026-10-15',
  'time': '18:00',
  'guests': 7,
  'name': 'Ольга',
  'phone': '+79997654321'}]

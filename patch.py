with open('bot/tests.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('"+919000666914"', '"919000666914"')
with open('bot/tests.py', 'w', encoding='utf-8') as f:
    f.write(c)

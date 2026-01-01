from st7789 import color565,RED,GREEN,YELLOW

DANGER = RED #color565(187,33,36)
INFO = color565(91,192,222)

def precission(text,dec:int = 2):
    parts = str(text).split(".")
    
    if len(parts) == 2:
        parts[1] = parts[1][0:dec]
        if len(parts[1]) < dec: parts[1] += '0'*(dec-len(parts[1]))
        
    return ".".join(parts)

def colorize_temp(temp:int):
    return GREEN if temp < 35 else YELLOW if temp < 50 else RED
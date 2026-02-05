from machine import Pin,UART
from time import sleep_ms

IN = Pin.IN
OUT = Pin.OUT
PULLDOWN = Pin.PULL_DOWN

led = Pin(25,OUT)
led.toggle()

recv = b""
# readAccess = True
pins = []

uart = UART(0,rx=Pin(1),tx=None,baudrate=400)

for n in range(0,16):
    pins.append(Pin(n+3,OUT,value=int(n<7)))

print("ready to listen.")
firstTime = True
while True:
    if uart.any():
        if firstTime:
            firstTime = False
            uart.read(1)
            continue
        recv+=uart.read(1)
        print("byte received, total: ",recv)
    
    
    if recv != b"" and len(recv) >= 2:
        xB = bin(recv[0]).replace("0b","")
        if len(xB)<8: xB = xB+"0"*(8-len(xB))
        
        yB = bin(recv[0]).replace("0b","")
        if len(yB)<8: yB = yB+"0"*(8-len(yB))
        binary = xB+yB
        
        print("generated binary: ",binary)
        for n in range(0,16):
            pins[n].value(int(binary[n]))
            print("bytes placed.")
        recv = b""
        print("buffer cleared.")


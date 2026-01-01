from time import sleep_us,sleep,sleep_ms

class SR595:
    def __init__(self, serial, clock, latch, bytes:int = 1):
        self.serial = serial
        self.clock = clock
        self.latch = latch
        self.bits = bytes*8
        self.data = self.bits*"0"
        
    def send(self, data:str):
        self.latch.off()
        sleep_us(100)
        self.data = data        
        for n in data:
            self.clock.off()
            self.serial.value(int(n))
            self.clock.on()
            sleep_us(100)
        self.latch.on()
    
    def clear(self): self.latch.off()
    def fill(self):self.send(self.bits*"1")
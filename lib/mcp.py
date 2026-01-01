from time import sleep_ms

class MCP:
    def __init__(self,data,clock,serialReady,delay:int = 5):
        self.clock = clock
        self.serialReady = serialReady
        self.data = data
        self.delay = delay
        
        self.clock.off()
        self.data.off()
    
    def sendText(self,text:str):
        while not self.serialReady.value():
            pass
        for c in text:
            binary = bin(ord(c)).replace("0b","")
            for v in binary:
                self.data.value(int(v))
                self.clock.on()
                sleep_ms(self.delay)
                self.clock.off()
            
    
    def sendBin(self,value:int):
        binary = bin(value).replace("0b","")
        for c in binary:
            self.data.value(int(c))
            self.clock.on()
            sleep_ms(self.delay)
            self.clock.off()
    
    def send(self,value:str):
        for c in value:
            self.data.value(int(c))
            self.clock.on()
            sleep_ms(self.delay)
            self.clock.off()
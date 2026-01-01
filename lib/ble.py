from time import ticks_ms

class BLE:
    def __init__(self, uart, config,suffix:str = "\r\n"):
        self.uart = uart
        self.suffix = suffix
        self.timeout = 5000
        self.watchdog = 150
        self.config = config
        self.spacialChar = None
        self.uart.read(1)
        
    def _write_(self,text:str):
        self.uart.write(str(text+self.suffix).encode("utf-8"))
        self.uart.flush()
        
    def _read_(self,timeout:int = None, watchdog:int = 125):
        time = ticks_ms()
        recv = b""
        while True:
            temp = None
            try:
                temp = str(recv,"utf-8")
            except OSError as e:
                pass
            if(self.uart.any()): 
                recv+=self.uart.read(1)
                watchdog+=self.watchdog
            
            
            elif((timeout and ticks_ms()-time > timeout) or (ticks_ms()-time > watchdog) or (temp != None and self.spacialChar != None and self.spacialChar in temp)): break
        output = None
        try:
            output = str(recv,"utf-8")
            if self.spacialChar:
                output = output.replace(self.spacialChar,"")
        except OSError as e:
            output = recv
            
        return output
    
    def _talk_(self,text:str):
        if self.config["ble"]["enabled"]:
            self._write_(text)
            return str(self._read_(self.timeout, self.watchdog),"utf-8")
    
    def test(self):
        result = self._talk_("AT+RESET")
        return "+OK" in result        

    def version(self):
        result = self._talk_("AT+VERSION")
        if "+VERSION=" in result: result = result.replace("+VERSION=","")
        return result

    def reset(self):
        result = self._talk_("AT+RESET")
        return "+OK" in result

    def set_baudrate(self, baudrate:int = 9600):
        result = self._talk_(f"AT+BAUD<{baudrate}>")
        isOk = "+OK" in result
        if isOk: self.uart.baudrate = baudrate
        return isOk

    def set_pin(self, pin:str):
        isValid = False
        for c in pin:
            for n in range(0,10):
                if c == str(n): 
                    isValid = True
                    break
        isValid &= len(pin)<=4
        
        if not isValid: return ValueError("Invalid pin for jdy-31 bluetooth module!")
        result = self._talk_(f"AT+PIN{pin}")
        return  "+OK" in result

    def set_name(self, name:str):
        if len(name)>18: return ValueError("Invalid length for broadcast name in jdy-31 bluetooth module!")
        result = self._talk_(f"AT+NAME{name}")
        return "+OK" in result
    
    def restore_default(self):
        return "+OK" in self._talk_("AT+DEFAULT")
    
    def get_name(self):
        result = self._talk_("AT+NAME")
        return result.replace("+NAME=","").replace("\r\n","") if "+NAME" in result else ""
    
    def get_pin(self):
        result = self._talk_("AT+PIN")
        return result.replace("+PIN=","").replace("\r\n","") if "+PIN" in result else ""
    
    def get_baudrate(self):
        result = self._talk_("AT+BAUD")
        return int(result.replace("+BAUD=","")) if "+BAUD" in result else 0
    
    def get_mac_address(self):
        result = self._talk_("AT+LADDR")
        return result.replace("+LADDR=","") if "+LADDR" in result else ""
    
    def disconnect(self):
        self._talk_("AT+DISC")

    def send(self,text:str):
        self._write_(text)
        
    def read(self):
        return self._read_(self.timeout,self.watchdog)
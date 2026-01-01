from time import sleep_ms

class BUZZER:
    SUCCESS_WAVES = [{"freq":4000,"cycle":4000,"time":25},{"freq":4000,"cycle":8000,"time":65}]
    
    def __init__(self, buzzer,config):
        self.buzzer = buzzer
        self.config = config

    def set_value(self,value:bool,freq:int=0):
        if self.config["buzzer"]:
            self.buzzer.duty_u16(int(value)*65355)
            self.buzzer.freq(max(freq,4000))
    
    def run_waves(self,waves):
        if self.config["buzzer"]:
            for w in waves:
                self.buzzer.duty_u16(w["cycle"])
                self.buzzer.freq(w["freq"])
                sleep_ms(w["time"])
            self.buzzer.duty_u16(0)
        
    def run_file(self,file):
        if self.config["buzzer"]:
            waves = []
            with open(file,"r") as f:
                lines = f.read().split("\r\n")
                
                for n in lines:
                    if n == '' or n == ' ': continue
                    parts = n.split("-")
                    waves.append({"freq":int(parts[0]),"cycle":int(parts[1]),"time":int(parts[2])})
                    
            self.run_waves(waves)
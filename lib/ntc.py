from math import log

# 3950 B
# 5K in 25C

class NTC:
    def __init__(self,adc,r25:int, beta:int, r2:int, ref_v:float = 3.3):
        self.adc = adc
        self.r2 = r2
        self.ntc_r = 0
        self.ref_v = ref_v
        self.r25 = r25
        self.beta = beta
        
    def _read_resistance_(self):
        voltage = self.adc.read_u16()*(self.ref_v/65355)
        self.ntc_r = self.r2*(self.ref_v-voltage)/voltage
    
    def getTemperatureK(self):
        self._read_resistance_()
        kelvin = 1/((log(self.ntc_r/self.r25)/self.beta)+(1/298.15))
        return kelvin
    
    def getTemperature(self):
        return self.getTemperatureK()-273.15
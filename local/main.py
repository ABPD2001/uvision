from machine import Pin,UART,SPI,ADC,PWM,lightsleep,deepsleep
from time import sleep_ms,ticks_ms
from gui import TFT_GUI, TFT_MENU, TFT_MENU_ICON_CONTROLLER
from ble import BLE
from interpreter import Interpreter
from ntc import NTC
from sr595 import SR595
from buzzer import BUZZER
from machine import Pin,UART,SPI,ADC,PWM,lightsleep,reset
from st7789 import ST7789, WHITE, BLACK, BLUE, GREEN, RED,color565
import vga1_8x16 as f16x8
import vga1_16x16 as f16x16 
import vga1_8x8 as f8x8
import vga1_16x32 as f32x16
from interpreter import Interpreter
from contants import INFO,DANGER,precission,colorize_temp
from buzzer import BUZZER
from ds18x20 import DS18X20
from onewire import OneWire
from sdcard import SDCard
from json import dumps, loads
import vga1_16x16 as fbig
import gc
from math import floor,trunc
from os import mount,listdir
import _thread


OUT = Pin.OUT
IN = Pin.IN
PULLDOWN = Pin.PULL_DOWN
PULLUP = Pin.PULL_UP

# LEDs
stat = Pin(3,OUT)
internal = Pin(25,OUT)

# KEYs
tl = Pin(0,IN,PULLDOWN)
ok = Pin(1,IN,PULLDOWN)
br = Pin(2,IN,PULLDOWN)

# I/Os
displayTFT = SPI(0,sck=Pin(18),mosi=Pin(19),miso=None,baudrate=62500000,polarity=1,phase=1)
sdcardSPI = SPI(1,sck=Pin(10),mosi=Pin(11),miso=Pin(12))
bleUART = UART(1,tx=Pin(8),rx=Pin(9), baudrate=9600)
ntcADC = ADC(2)
sr595Serial = Pin(15,OUT)
sr595Clock = Pin(14,OUT)
sr595Latch = Pin(5,OUT)
ds18b20OW = OneWire(Pin(4))
microwave = Pin(6,IN,PULLDOWN)
buzzerPWM = PWM(Pin(16))
ugn3503 = Pin(7,IN,PULLDOWN)

# Drivers
tft = ST7789(spi=displayTFT, width=240,height=300,dc=Pin(21,OUT),backlight=Pin(22,OUT),reset=Pin(20,OUT),cs=Pin(17,OUT))
gui = TFT_GUI(tft)
ntc = NTC(ntcADC,5000,3950,10000)
ds18b20 = DS18X20(ds18b20OW)
sr595 = SR595(sr595Serial,sr595Clock,sr595Latch,2)
ble = None
buzzer = BUZZER(buzzerPWM)
sdcard = None
menu = None


files = []
page_table = []
config =  {
"sdcard":True,
"buzzer":True,
"sensevity":
    { "movement":True,
    "door":True,
    "core":35,
    "inside":60,
    "power": {
        "outside":45,
        "inside":75,
        "core":40
        }
     },
     "machine": {
     "frequency":120000000,
     "debug":True,
     "configureFrom":"sdcard"
     },
     "ble":{
         "enabled":False,
         "logging":False,
         "name":"Uvision",
         "pin":"1234"
         }
}


# States
errors = []
page_idx = 0 
ble_running = False
executables = []

# Icon controllers
icon_controllers = []

def to_binary(num:int):
    binary = bin(num)
    return binary.replace("0b","")

def _ble_cmd_settings(params):
    global config
    global ble
    
    keys = params[1].split(',')
    current = config
    for key in keys[:-1]:
        current = current[key]
    final_key = keys[-1]
    
    if params[0] == "write":    
        config[final_key] = params[2]
    elif params[0] == "read":
        ble.send(config[final_key])

def _ble_cmd_controll(params):
    global sr595
    
    if params[0] == "set":
        sr595.send(params[1])
    elif params[0] == "pixel":
        x = sr595.data[0:8]
        y = sr595.data[8:]
        
        [xp,yp] = params[1].split(",")
        x[int(xp)] = "1"
        y[int(yp)] = "1"
        sr595.send(x+y)
    elif params[0] == "on":
        sr595.send("1"*sr595.bits)
    elif params[0] == "off":
        sr595.send("0"*sr595.bits)

def _ble_cmd_log(cmd:str):
    global microwave
    global ugn3503
    global sr595
    global ntc
    global ds18b20
    global ble
    
    str_data = dumps({"matrix":f"x:{sr595.data[0:8]}, y:{sr595.data[8:]}","microwave":microwave.value(),"ugn3503":ugn3503.value(),"temperatures":{"inside":readDS18B20(ds18b20),"outside":ntc.getTemperature()}})
    ble.send(str_data)

def _ble_cmd_file(params):
    global file_buffer
    global ble
    
    if params[0] == "write":
        if params[1] == "new":
            file_buffer = {"name":params[2],"description":params[3],"date":params[4],"text":""}
            ble.send("NEW BUFFER FILE SET.")
        elif params[1] == "buffer":
            full_cmd = " ".join(params)
            file_buffer["text"] += params[2]+"\n"
            ble.send("BUFFER FILE UPDATED.")
    elif params[0] == "read":
        for n in executables:
            if n[params[1]] == params[2]:
                ble.send("FILE FOUND: "+dumps(n))

def _ble_cmd_(cmd:str):
    parts = cmd.split("|")
    generals = ["settings","controll","log","file"]
    generals_callbacks = [_ble_cmd_settings,_ble_cmd_controll,_ble_cmd_file]
    stat.toggle()
    if parts[0] in generals: generals_callbacks[generals.index(parts[0])](parts[1:])
    stat.toggle()

def _setPage_(value,params):
    global page_idx
    global gui
    
    page_idx = value
    gui.params = [params]
    

def readDS18B20(sensor):
    rom = sensor.scan()
    sensor.convert_temp()
    return sensor.read_temp(rom[0])

def writeConfig():
    global config
    with open("/config.json","w") as cnf:
        cnf.write(dumps(config))

seconds_thread_stop = False
keys = [None,None,None]
    
def do_once(entry,idx=0):
    global keys
    if keys[idx] != entry:
        keys[idx] = entry
        return True
    else: return False
    
def run_file(path:str):
    global sr595
    global seconds_thread_stop

    with open(path) as tmp_f:
        content = tmp_f.read()
        lines = content.split("\n")
        for n in range(0,len(lines)-1):
            l = lines[n+1]
            if seconds_thread_stop:
                n-=1
                continue
            [x,y,t] = l.split(",")
            sr595.send(to_binary(int(x))+to_binary(int(y)))
            sleep_ms(int(t))
        sr595.send("0"*sr595.bits)
    
def two_digit(txt): return "0"+str(txt) if len(str(txt)) == 1 else str(txt) 

def to_std_time(time:int):
    time = trunc(time/1000)
    hours = trunc(time/3600)
    time = time%3600
    minutes = min(59,trunc(time/60))
    time = time%60
    seconds = time
    
    return f"{two_digit(hours)}:{two_digit(minutes)}:{two_digit(seconds)}"

# Main

def _page_main(self,non):
    display = self.display
    
    if do_once("main"):
        display.fill(0)
        menu._update_display_()
    
    display.text(f32x16,"Menu",82,56,WHITE)
    
def _menu_main_callback(option):
    global menu
    global ble
    global config
    global gui
    
    pages_name = ["main","start","bluetooth","power","storage","info"]
    for idx,value in enumerate(pages_name):
        if value == option["text"]:
            menu.deinit()
            menu.erase()
            gui.display.fill(0)
            gui.change_page(idx)
            gui.params = []
            if page_table[idx]["action"]:
                page_table[idx]["action"]()
            if page_table[idx]["menu"]:
                menu = TFT_MENU(tl,br,ok,*page_table[idx]["menu"],gui)
                menu.listen()
            
            gui.show()
            break
    
main_menu = [0,140,240,80,_menu_main_callback,[{"color":WHITE,"text":"start"},{"color":BLUE,"text":"bluetooth"},{"color":DANGER,"text":"power"},{"color":WHITE, "text":"storage"},{"color":INFO,"text":"info"}]]

prev_target = None
def _power_page(self,non):
    global menu
    global prev_target
    
    display = self.display
    if do_once("power"):
        display.fill(0)
        menu._update_display_()
    
    display.text(f32x16,"Power",82,46,WHITE)
    
    items = [{"key":"sleep","icon":"/icons/sleep.png","text":"Sleep|just ready to awake..."},{"key":"shutdown","icon":"/icons/shutdown.png","text":"Shutdown|shutdown completely..."},{"key":"reset","icon":"/icons/reset.png","text":"Reset|resets machine..."}]

    
    if prev_target != menu.cur_item and menu.cur_item != 0:
        titleDesc = items[menu.cur_item-1]["text"].split("|")
        icon_controllers[0].show(items[menu.cur_item-1]["icon"],32,32,104,115,True)
        prev_target = menu.cur_item
        display.fill_rect(0,160,240,60,0)
        display.text(f16x8,titleDesc[0],floor((240-len(titleDesc[0])*8)/2),160,WHITE)
        display.text(f8x8,titleDesc[1],floor((240-len(titleDesc[1])*8)/2),190,WHITE)

def _power_callback(option):
    global menu
    global gui
    if option["text"] == "Back":
        menu.deinit()
        menu.erase()
        gui.display.fill(0)
        gui.change_page(0)
        gui.params = []
        menu = TFT_MENU(tl,br,ok,*page_table[0]["menu"],gui)
        menu.listen()
        gui.show()
        return
    
    actions = [{"text":"sleep","callback":_system_sleep_},{"text":"shutdown","callback":_system_shutdown_},{"text":"reset","callback":_system_reset_}]
    
    for n in actions:
        if n["text"] == option["text"]:
            sleep_ms(500)
            n["callback"]()
            break
        
power_menu = [0,220,240,60,_power_callback,[{"color":WHITE,"text":"Back"},{"color":WHITE,"text":"sleep"},{"color":RED,"text":"shutdown"},{"color":RED,"text":"reset"}]]

def _ble_page(self,non):
    display = self.display
    
    if do_once("ble"):
        display.fill(0)
        icon_controllers[0].png = False
    
    icon_controllers[0].show("/icons/ble.png",32,32,92,55,True)
    display.text(f32x16,"Bluetooth",48,120,WHITE)
    display.text(f8x8,"> press ok to return <",32,260,color565(195,195,195))

def _ble_page_action_thread():
    global ble_running
    global ble
    global menu
    global gui
    
    ble.send("BLE MODE ACTIVATED")

    while True:
        readed = ble.read()
        if readed != None:
            stat.toggle()
            if readed == "OFF":
                ble_running = False
                menu.deinit()
                menu.erase()
                gui.display.fill(0)
                gui.change_page(0)
                gui.params = []
                menu = TFT_MENU(tl,br,ok,*page_table[0]["menu"],gui)
                menu.listen()
                gui.show()
                break
            else: _ble_cmd_log(readed)

def _ble_back(pin):
    global ble_running
    
    icon_controllers[0].png = False
    _power_callback({"text":"Back"})
    ble_running=False
    
def _ble_page_action():
    global ble_running
    
    stat.toggle()
    ble_running=True
    _thread.start_new_thread(_ble_page_action_thread,())
    ok.irq(handler=_ble_back,trigger=Pin.IRQ_RISING)

minutes = 0
seconds = 0
hours = 0
current_selection = 0
current_value = 0

def _page_start_ok_action(pin):
    global current_selection
    global current_value
    global hours
    global seconds
    global minutes
    global tl
    global br
    global ok
    
    if not current_selection:
        hours = current_value
    if current_selection == 1:
        minutes = current_value
    if current_selection == 2:
        seconds = current_value
        #turn on waves
    stat.toggle()
    current_value = 0
    current_selection = min(2,current_selection+1)
    sleep_ms(400)

def _page_start(self,non):
    global minutes
    global hours
    global seconds
    global tl
    global br
    global ok
    global current_selection
    global current_value
    
    display = self.display
    
    if do_once("start"):
        display.fill(0)

    print(f"{current_value}--{current_selection}")
    
    display.text(f32x16,f"{two_digit(current_value if not current_selection else hours)}:{current_value if current_selection == 1 else two_digit(minutes)}:{current_value if current_selection == 2 else two_digit(seconds)}",56,50,WHITE)
    if do_once(current_selection,1):
        display.fill_rect(0,50,240,35)
        display.fill_rect(0,90,240,6,0)
        display.fill_rect(56+(48*current_selection),90,32,6,WHITE)

def _page_start_br_action(pin):
    global current_value
    current_value = max(current_value-1,0)

def _page_start_tl_action(pin):
    global current_value
    global current_selection
    limits = [11,59,59]    
    current_value = min(limits[min(2,current_selection)],current_value+1)

def _page_start_action():
    global ok
    global br
    global tl
    global current_value
    global current_selection
    global hours
    global minutes
    global seconds
    
    hours = 0
    minutes = 0
    seconds = 0
    current_selection = 0
    current_value = 0
    stat.toggle()
    sleep_ms(400)
    br.irq(handler=_page_start_br_action,trigger=Pin.IRQ_RISING)
    tl.irq(handler=_page_start_tl_action,trigger=Pin.IRQ_RISING)
    ok.irq(handler=_page_start_ok_action,trigger=Pin.IRQ_RISING)

def _page_storage(self,non):
    global menu
    global executables
    
    display = self.display

    if do_once("storage"):
        display.fill(0)
        menu._update_display_()

    if not len(executables):
        display.text(f32x16,"No files!",56,40,WHITE)
        return
    if menu.cur_item:
        cur_item = executables[menu.cur_item-1]["data"]
    
        if do_once(menu.cur_item,1):
            display.fill_rect(0,10,240,80,0)
            display.text(f16x8,cur_item["name"],floor((240-len(cur_item["name"])*8)/2),40,WHITE)
            display.text(f8x8,cur_item["description"],floor((240-len(cur_item["description"])*8)/2),70,WHITE)
            display.text(f8x8,cur_item["date"],floor((240-len(cur_item["date"])*8)/2),90,WHITE)

def _page_storage_action():
    global executables
    global storage_menu
    global menu
    
    out_menu = [{"text":"Back","color":WHITE}]
    for n in executables:
        out_menu.append({"text":n["data"]["name"],"color":WHITE})
    storage_menu[5] = out_menu

def _page_storage_callback(option):
    global executables
    global menu
    global sr595
    global gui
    global seconds_thread_stop
    
    display = gui.display
        
    if option["text"] == "Back":
        menu.deinit()
        menu.erase()
        gui.display.fill(0)
        gui.change_page(0)
        gui.params = []
        menu = TFT_MENU(tl,br,ok,*page_table[0]["menu"],gui)
        menu.listen()
        gui.show()
        return
    
    for n in executables:
        if n["data"]["name"] == option["text"]:
            menu.deinit()
            menu.erase()
            _thread.start_new_thread(run_file,[n["path"]])
            display.fill(0)
            start_time = ticks_ms()
            menu.deinit()
            menu.erase()
            sleep_ms(500)
            display.text(f8x8,"> press ok to pause <",32,260,color565(195,195,195))
            saved_state_diff = 0
            
            while ticks_ms()-start_time <= n["data"]["time"]:                
                print(saved_state_diff)
                if ok.value():
                    seconds_thread_stop = not seconds_thread_stop
                if seconds_thread_stop:
                    display.text(f32x16," Paused ",54,220,color565(195,195,195))
                    display.text(f8x8,"> press ok to resume <",32,260,color565(195,195,195))
                    if do_once(seconds_thread_stop):
                        saved_state_diff = ticks_ms()-start_time
                        buzzer.run_file("/sounds/done.uvw")
                        sleep_ms(500)
                    start_time = 999999999999999999999

                else:
                    if saved_state_diff:
                        start_time = ticks_ms()-saved_state_diff
                        saved_state_diff = 0
                        buzzer.run_file("/sounds/done.uvw")
                        do_once(False)
                    timeStr = to_std_time(n["data"]["time"]-(ticks_ms()-start_time))
                    display.text(f32x16,"Running",64,220,color565(195,195,195))
                    display.text(f32x16,timeStr,floor((240-len(timeStr)*16)/2),124,WHITE)
                sleep_ms(1000)
            while True:
                buzzer.run_file("/sounds/done.uvw")
                if ok.value():
                    break
            buzzer.run_file("/sounds/notification.uvw")
            menu.deinit()
            menu.erase()
            gui.display.fill(0)
            gui.change_page(4)
            gui.params = []
            menu = TFT_MENU(tl,br,ok,*page_table[4]["menu"],gui)
            menu.listen()
            gui.show()
            return

storage_menu = [0,140,240,140,_page_storage_callback,[]]

def _page_info(self,non):
    global microwave
    global ds18b20
    global ntc
    global icon_controllers
    display = self.display
    
    if do_once("info"):
        display.fill(0)
        menu._update_display_()
        icon_controllers[0].png = False
        icon_controllers[1].png = False
        icon_controllers[2].png = False
        icon_controllers[3].png = False
        gc.collect()
        
    display.text(f32x16,"Info",88,30,WHITE)

    outside = readDS18B20(ds18b20)
    inside = ntc.getTemperature()
    moving = microwave.value()
    opened = ugn3503.value()

    icon_controllers[0].show("/icons/outside.png",32,32,10,140,True)
    display.rect(10,140,32,32,GREEN if (0 >= outside and outside <= 40) else color565(255,127,39) if (-10 <= outside and outside < 0) or (outside >= 40 and outside <= 60) else RED)
    display.text(f32x16, f"{precission(outside,2)} C",48,140,WHITE)
    
    icon_controllers[1].show("/icons/inside.png",32,32,10,190,True)
    display.fill_rect(20,200,12,12,GREEN if (-10 <= inside and inside <= 45) else color565(255,127,39) if (-20 <= outside and outside < -10) or (outside >= 45 and outside <= 65) else RED)
    display.text(f32x16,f"{precission(inside,2)} C",48,190,WHITE)
    
    icon_controllers[2].show( f"/icons/{'moving' if moving else 'stopped'}.png",16,16,10,235,True)
    display.text(f16x8,"Moving" if moving else "Still",45,235,WHITE)
    
    icon_controllers[3].show(f"/icons/{'open' if opened else 'lock'}.png",16,16,10,258,True)
    display.text(f16x8,"Opened" if opened else "Closed",45,258,WHITE)
    
def _page_info_callback(option):
    global menu
    global gui
    
    if option["text"] == "Back":
        menu.deinit()
        menu.erase()
        gui.display.fill(0)
        gui.change_page(0)
        gui.params = []
        menu = TFT_MENU(tl,br,ok,*page_table[0]["menu"],gui)
        menu.listen()
        gui.show()
        return
    
    options = ["machine","bluetooth"]
    for idx,value in enumerate(options):
        if option["text"] == value:
            menu.deinit()
            menu.erase()
            gui.display.fill(0)
            gui.change_page(idx+6)
            gui.params = []
            page_table[idx+6]["action"]()
            sleep_ms(400)
            gui.show()
            break

def _page_info_machine(self,non):
    global config
    display = self.display
    
    if do_once("info-machine"):
        display.fill(0)
        icon_controllers[0].png = False
        icon_controllers[1].png = False
        icon_controllers[2].png = False
        icon_controllers[3].png = False
        icon_controllers[4].png = False
        gc.collect()
    
    debugMode = config['machine']['debug']
    
    display.text(f32x16,config['machine']['core'],floor((240-len(config['machine']['core'])*16)/2),30,WHITE)
    
    icon_controllers[0].show("/icons/time.png",16,16,10,80,True)
    display.text(f16x8,f"Clock at {config['machine']['frequency']/1000000} MHz.",40,80,WHITE)
    
    icon_controllers[1].show(f"/icons/{'debug' if debugMode else 'standard'}.png",16,16,10,100,True)
    display.text(f16x8,f"Booted at {'Debug' if debugMode else 'Standard'} mode.",40,100,WHITE)
    
    icon_controllers[2].show(f"/icons/{'in-sdcard' if config['sdcard'] else 'out-sdcard'}.png",16,16,10,120,True)
    display.text(f16x8,f"SDCard is {'' if config['sdcard'] else 'not '}inserted.",40,120,WHITE)
    
    icon_controllers[3].show(f"/icons/ble-{'active' if config['ble']['enabled'] else 'deactive'}.png",16,16,10,140,True)
    display.text(f16x8,f"Bluetooth is {'active' if config['ble']['enabled'] else 'deactive'}.",40,140,WHITE)
    
    display.text(f8x8,"> press ok to return <",32,260,color565(195,195,195))
    
def _page_info_ble(self,non):
    global ble
    
    display = self.display
    version = ["",""]
    
    if do_once("info-ble"):
        display.fill(0)
        icon_controllers[0].png = False
        display.text(f16x8,"loading...",80,132,WHITE)
        version = ble.version().replace("\r\n","").split(",")
        display.fill(0)
    
    icon_controllers[0].show("/icons/ble.png",32,32,92,55,True)
    display.text(f16x8,version[0],floor((240-len(version[0])*8)/2),128,WHITE)
    display.text(f8x8,version[1],floor((240-len(version[1])*8)/2),152,WHITE)
    display.text(f8x8,"> press ok to return <",32,260,color565(195,195,195))

def _page_info_ok_back_handler(pin):
    global gui
    global menu
    
    gui.display.fill(0)
    gui.change_page(5)
    gui.params = []
    menu = TFT_MENU(tl,br,ok,*page_table[5]["menu"],gui)
    menu.listen()
    gui.show()
    return    

def _page_info_ok_back():
    global ok
    ok.irq(handler=_page_info_ok_back_handler,trigger=Pin.IRQ_RISING)

info_menu = [0,70,240,50,_page_info_callback,[{"text":"Back","color":WHITE},{"text":"machine","color":WHITE},{"text":"bluetooth","color":BLUE}]]

page_table = [
    {"action":None,"menu":main_menu,"content":_page_main},
    {"action":_page_start_action,"menu":None,"content":_page_start},
    {"action":_ble_page_action,"menu":None,"content":_ble_page},
    {"action":None,"menu":power_menu,"content":_power_page},
    {"action":_page_storage_action,"menu":storage_menu,"content":_page_storage},
    {"action":None,"menu":info_menu,"content":_page_info},
    {"action":_page_info_ok_back,"menu":None,"content":_page_info_machine},
    {"action":_page_info_ok_back,"menu":None,"content":_page_info_ble}
]

def _system_initialize_():
    global config
    global ble
    global executables
    
    tft.init()
    tft.fill(0)
    buzzer.set_value(False)
    sr595.clear()
    stat.off()
    internal.off()
    gui.set_pages(page_table)
    gui.create_bar_box(10,220,0,width=220,extraHeight=10)
    try:
        tft.text(f16x8,"reading config file...",10,152,WHITE)
        if config["machine"]["debug"]: sleep_ms(700)
        with open("/config.json",'r') as config_f:
            config = loads(config_f.read())
        tft.fill_rect(0,0,240,200,0)
        tft.text(f16x8,"Done.",10,152,GREEN)
        stat.toggle()
        if config["machine"]["debug"]: sleep_ms(1000)
        
    except OSError as err:
        errors.append({"cuase":"CONFIG_FAILURE","raw":err,"message":"Failed to process or read config file!","time":ticks_ms()})
        tft.fill_rect(0,0,240,200,0)
        tft.text(f16x8,str(errors[len(errors-1)]["raw"]),10,152,RED)
        stat.toggle()
        if config["machine"]["debug"]: sleep_ms(1250)
        
    tft.fill_rect(0,0,240,200,0)
    gui.create_bar_box(10,220,25,width=220,extraHeight=10)
    ble = BLE(bleUART,config)
    
    try:
        tft.text(f16x8,"initializing SDcard...",10,152,WHITE)
        if config["machine"]["debug"]: sleep_ms(700)
        sdcard = SDCard(sdcardSPI,cs=Pin(13,OUT))
        mount(sdcard,"/sdcard")
        if config["machine"]["configureFrom"] == "sdcard" and config["sdcard"]:
            with open("/sdcard/config.json","r") as sdCnf:
                config = loads(sdCnf.read())
                writeConfig()

        tft.fill_rect(0,0,240,200,0)
        tft.text(f16x8,"Done.",10,152,GREEN)
        stat.toggle()
        if config["machine"]["debug"]: sleep_ms(1000)

        
    except OSError as err:
        tft.fill_rect(0,0,240,200,0)
        config["sdcard"] = False
        errors.append({"cause":"SDCARD_FAILURE","raw":err,"message":"Failed to read sdcard!","time":ticks_ms()})
        tft.text(f16x8,str(errors[len(errors)-1]["raw"]),10,152,RED)
        stat.toggle()
        if config["machine"]["debug"]: sleep_ms(1250)

    
    gui.create_bar_box(10,220,50,width=220,extraHeight=10)
    tft.fill_rect(0,0,240,200,0)
    tft.text(f16x8,"reading executable files...",10,152,WHITE)
    if config["machine"]["debug"]: sleep_ms(750)
    if config["sdcard"]:# config["sdcard"]
        files = listdir("/sdcard") # /sdcard
        for n in files:
            if n[len(n)-4:] == ".uvb":
                temp_f_content = ""
                with open("/local/"+n,"r") as temp_f:
                    temp_f_content = temp_f.read()
                lines = temp_f_content.split("\n")
                executables.append({"path":"/sdcard/"+n,"data":loads(lines[0])})

        tft.fill_rect(0,0,240,200,0)
        tft.text(f16x8,"Done.",10,152,GREEN)
        stat.toggle()
        if config["machine"]["debug"]: sleep_ms(1000)
    else:
        tft.fill_rect(0,0,240,200,0)
        tft.text(f16x8,"no sdcard available.",10,152,RED)
        tft.text(f16x8,"using local...",10,172,RED)
        stat.toggle()
        if config["machine"]["debug"]:sleep_ms(2000)
        files = listdir("/local")
        for n in files:
            if n[len(n)-4:] == ".uvb":
                temp_f_content = ""
                with open("/local/"+n,"r") as temp_f:
                    temp_f_content = temp_f.read()
                lines = temp_f_content.split("\n")
                executables.append({"path":"/local/"+n,"data":loads(lines[0])})
                stat.toggle()
        tft.fill_rect(0,0,240,200,0)
        stat.toggle()
        tft.text(f16x8,"Done.",10,152,GREEN)
        if config["machine"]["debug"]: sleep_ms(1250)
    gui.create_bar_box(10,220,75,width=220,extraHeight=10)

    tft.fill_rect(0,0,240,200,0)
    tft.text(f16x8,"initializing Bluetooth...",10,152,WHITE)
    if config["machine"]["debug"]: sleep_ms(700)
    if config["ble"]:
        if not ble.test():
            errors.append({"cause":"BLE_FAILURE","raw":OSError("Bluetooth timeout."),"message":"Failed to intialize bluetooth!","time":ticks_ms()})
            tft.fill_rect(0,0,240,200,0)
            tft.text(f16x8,str(errors[len(errors)-1]["raw"]),10,152,RED)
            gui.create_bar_box(10,220,100,width=220,extraHeight=10)
            if config["machine"]["debug"]: sleep_ms(1250)
            config["ble"]["enabled"] = False
            ble = BLE(bleUART,config)
            
        else:
            ble.set_name(config["ble"]["name"])
            ble.set_pin(config["ble"]["pin"])
            tft.fill_rect(0,0,240,200,0)
            gui.create_bar_box(10,220,100,width=220,extraHeight=10)
            tft.text(f16x8,"Done.",10,152,GREEN)
            if config["machine"]["debug"]: sleep_ms(1000)
        stat.toggle()
    tft.png("/icons/home_screen.png",0,30)
    buzzer.run_file("/sounds/welcome.uvw")
    tft.fill(0)
    print(errors)
    icon_controllers.append(TFT_MENU_ICON_CONTROLLER(gui))
    icon_controllers.append(TFT_MENU_ICON_CONTROLLER(gui))
    icon_controllers.append(TFT_MENU_ICON_CONTROLLER(gui))
    icon_controllers.append(TFT_MENU_ICON_CONTROLLER(gui))
    icon_controllers.append(TFT_MENU_ICON_CONTROLLER(gui))
    


def _system_awake_(pin):
    global gui
    global menu
    global sr595
    global stat
    
    tft.on()
    sr595.erase()
    if menu:
        menu.init()
        menu.listen()
    gui.show()
    menu.listen()
    stat.off()
    internal.on()
    buzzer.run_file("/sounds/welcome.uvw")

def _system_sleep_():
    global menu
    global ok
    global br
    global tl
    
    if menu:
        menu.deinit()
        menu.erase()
        tft.fill(0)
    
    tft.off()
    tl.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,handler=_system_awake_)
    br.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,handler=_system_awake_)
    ok.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,handler=_system_awake_)
    stat.on()
    buzzer.set_value(False)
    sleep_ms(250)
    lightsleep()

def _system_shutdown_():
    global ble
    global config
    global menu
    global ok
    global tl
    global br
    
    if menu:
        menu.deinit()
        menu.erase()
        tft.fill(0)
        
    tl.irq(None)
    br.irq(None)
    ok.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,handler=_system_awake_)
    sr595.clear()
    stat.off()
    if config["ble"]["enabled"]:
            ble.disconnect()
    buzzer.set_value(False)
    tft.off()
    sleep_ms(250)
    lightsleep()

def _system_reset_():
    global ble
    global menu
    
    if menu:
        menu.deinit()
        menu.erase()
        tft.fill(0)
    tl.irq(None)
    br.irq(None)
    ok.irq(None)
    sr595.clear()
    internal.off()
    ble.disconnect()
    stat.off()
    tft.off()
    reset()

def _system_():
    global page_table
    global menu
    global gui
    
    _system_initialize_()
    tft.fill(0)
    menu = TFT_MENU(tl,br,ok,*page_table[0]["menu"],gui)
    menu.listen()
    gui.change_page(0)
    gui.show()
    
_system_()

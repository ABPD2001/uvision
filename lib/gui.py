from machine import Timer, Pin
from st7789 import WHITE, BLACK, BLUE, GREEN,color565
import vga1_8x16 as f16x8
import vga1_16x16 as f16x16 
import vga1_8x8 as f8x8
import vga1_16x32 as f16x32
from math import trunc,floor
import gc
from time import sleep_ms, ticks_ms
# import _thread

class TFT_GUI:
    def __init__(self,display, maskColor: int = BLACK,period:int = 200):
        self.display = display
        self.pages = []
        self.idx = 0
        self.timer = Timer(-1)
        self.period = period
        self.maskColor = maskColor
        self.alert_buttons_gap = 10
        self.padding_horizontal = 8
        self.inline_padding = 3
        self.padding_veritcal = 12
        self.border_width = 2
        self.inline_gap = 8
        self.tick = 0
        self.width = 240
        self.height = 280
        self.animate_queue = []
        self.params = []
        
    def set_pages(self,pages):
        self.pages = pages

    def change_page(self, idx:int):
        self.idx = idx
        self.timer.deinit()

    def _screen_timer_(self,timer):
        self.pages[self.idx]["content"](self,timer,*self.params)
        self.tick+=1

    def show(self):
        self.timer.init(mode=Timer.PERIODIC, period=self.period, callback=lambda t: self._screen_timer_(t))

    def create_alert_box(self,title,buttons,x:int,y:int,color:int = WHITE):
        width = 0
        btn_height = 16+(2*self.border_width)+(2*2)
        vert_gap = 12
    
        height = (self.padding_veritcal*2)+vert_gap+16+btn_height+(2*self.border_width)

        for n in range(0,len(buttons)):
            btn_width = len(buttons[n]["text"])*8+(self.inline_padding*2)+(self.border_width*2)

            width+=len(buttons[n]["text"])*8+(self.inline_padding*2)+(self.border_width*2)
            self.create_button_box(buttons[n]["text"], x+n*btn_width+self.padding_horizontal+(n*self.inline_gap), y+self.padding_veritcal+vert_gap+16+self.border_width, buttons[n]["bordercolor"],buttons[n]["color"])

        width+=(len(buttons)-1)*self.alert_buttons_gap
        width+=(self.padding_horizontal*2)+(self.border_width*2)


        self.display.rect(x,y,width,height,color)
        self.display.text(f16x8, title["text"], trunc((width-len(title["text"])*8)/2)+x ,y+self.padding_veritcal, title["color"])

        return {"title":title,"buttons":buttons,"width":width, "height":height,"x":x,"y":y,"color":color}

    def clear_alert_box(self, alert_box): 
        self.display.fill_rect(alert_box.x, alert_box.y, alert_box.width, alert_box.height, self.maskColor)

    def create_button_box(self,text:str,x:int,y:int, bordercolor: int = WHITE,color:int = WHITE):
        width = len(text)*8+(self.inline_padding*2)+(self.border_width*2)
        print(width)
        height = (self.inline_padding*2)+(self.border_width*2)+16
        self.display.rect(x,y, width, height, bordercolor)
        self.display.text(f16x8, text, x+self.inline_padding+self.border_width,self.border_width+self.inline_padding+y, color)

        return {"text":text, "x":x, "y":y, "width": width,"height":height}
    
    def clear_button_box(self,button_box): 
        self.display.fill_rect(button_box.x,button_box.y,button_box.width,button_box.height,self.maskColor)

    def _calc_center_(self, width:int): return trunc((self.width-width)/2)

    def create_page_header_box(self, title, color:int = WHITE):
        self.display.line(0, 25, self.display.width, 25, color)
        self.display.text(f16x16, title.text, self._calc_center_(len(title)*16),8, color)

        return {"x":0,"y":0,"height": 26, "width":self.display.width}

    def clear_page_header(self, header_box): 
        self.display.fill_rect(header_box.x, header_box.y, header_box.width, header_box.height, self.maskColor)

    def create_bar_box(self,x:int, y:int, percentage: int, borderColor:int = WHITE, fillColor:int = BLUE, width:int = None,extraHeight:int = 0, inlineGap:int = 1):
        height = extraHeight+self.border_width*2+inlineGap*2
        if not width: width = self.display.width - self.padding_horizontal*2
        self.display.rect(x, y, width, height, borderColor)
        self.display.fill_rect(x+inlineGap, y+inlineGap, floor(percentage/100*(width-inlineGap-self.border_width)), height-inlineGap-self.border_width, fillColor)
    
        return {"width":width, "height":height, "x":x,"y":x,"percentage":percentage}
    
    def clear_bar_box(self,bar_box): 
        self.display.fill_rect(bar_box.x. bar_box.y, bar_box.width, bar_box.height, self.maskColor)

    def show_icon(self, path:str, x:int, y:int,png:dict = None):
        width = -1
        height = -1
        
        if not png:
            buffer = self.display.jpg_decode(path)
            width = len(buffer[0])
            height = len(buffer)
            self.display.jpg(buffer, x, y)
        
            del buffer
        else:
            width = png["width"]
            height = png["height"]
            
            self.display.png(path,x,y)
        
        return {"width":width,"height":height, "x":x, "y":y}
    
    def clear_icon(self, icon_box):
        self.display.fill_rect(icon_box.x,icon_box.y,icon_box.width,icon_box.height,self.maskColor)
    
    def show_animated_icon(self,frames, x:int,y:int,period:int=100,forever:bool = False):
            for n in frames:
                self.show_icon(n["path"],x,y,n["png"])
                sleep_ms(period)
            if forever:
                gc.collect()
                self.show_icon(frames,x,y,period,forever)
        
class TFT_MENU:
    def __init__(self, tl, br, ok, x:int, y:int, width:int, height:int, callback, options, gui: TFT_GUI, default:int = 0, period:int = 250, delayClick: int = 10):        
        # KEYS
        self.br_key = br
        self.tl_key = tl
        self.ok_key = ok
        
        # TIMING/CORDANATING
        self.period = period
        self.width = width
        self.height = height
        self.y = y
        self.x = x
        self.delayClick = delayClick
        
        # ITEMS MANAGAMENT
        self.callback = callback
        self.cur_action = -1
        self.options = options
        self.cur_item = default
        
        # GUI
        self.padding_horizontal = gui.padding_horizontal
        self.padding_vertical = gui.padding_veritcal
        self.gap = 8
        self.gui = gui
        self.hoverColor = color565(255,255,0)
        self.activeColor = GREEN
        
        # Erasing Interrupt requests
        self.deinit()
    
    # Update menu display method (internal)
    
    def _update_display_(self):
        self.erase()
        fitable_count = trunc(self.height/(8+self.gap))
        hiddenItems = max(self.cur_item+1-fitable_count,0)
                
        for idx,itm in enumerate(self.options):
            index = idx-hiddenItems
            prefix = "  "
            x = self.x+self.padding_horizontal
            y = self.y+self.padding_vertical+(index*self.gap+index*8)
            text = itm["text"]
            color = itm["color"]
            
            if(self.cur_action == idx):
                prefix = ">>"
                color = self.activeColor
                
            elif(self.cur_item == idx):
                prefix = "> "
                color = self.hoverColor
                
            if(index<0 or index+1>fitable_count): continue
            
            
            self.gui.display.text(f8x8,f"{prefix}{text}",x,y,color)   

    # IRQ for ok key
    def _br_key_handler_(self,pin):
        self.cur_item+=1
        if self.cur_item > len(self.options)-1: self.cur_item = 0
        self._update_display_()
        sleep_ms(self.delayClick)
    
    # IRQ for top/left key
    def _tl_key_handler_(self,pin):
        self.cur_item-=1
        if self.cur_item < 0: self.cur_item = len(self.options)-1   
        self._update_display_()
        
        sleep_ms(self.delayClick)
    
    # IRQ for ok key
    def _ok_key_handler_(self,pin):
        self.cur_action = self.cur_item
        cur_option = self.options[self.cur_item]
        time = ticks_ms()
        self.callback(cur_option)
        self._update_display_()
        sleep_ms(max(0,self.delayClick-(ticks_ms()-time)))
        self.cur_action = -1
        self._update_display_()
    
    # Set Interrupt requests to pins
    def listen(self):
        self._update_display_()
        self.br_key.irq(trigger=Pin.IRQ_RISING, handler=self._br_key_handler_)
        self.tl_key.irq(trigger=Pin.IRQ_RISING, handler=self._tl_key_handler_)
        self.ok_key.irq(trigger=Pin.IRQ_RISING, handler=self._ok_key_handler_)
    
    # Deinit all IRQs
    def deinit(self):
        self.br_key.irq(None)
        self.tl_key.irq(None)
        self.ok_key.irq(None)
    
    # Erase menu
    def erase(self):
        self.gui.display.fill_rect(self.x, self.y, self.width, self.height, self.gui.maskColor)
    
    # Re-init
    def init(self,x = None, y = None, width = None, height = None, callback = None, options = None, gui = None, default = None, period = None, delayClick = None):
        if x and y:
            self.x = x
            self.y = y
        if width and height:
            self.height = height
            self.width = width
        if callback: self.callback = callback
        if options: self.options = options
        if gui: self.gui = gui
        if default: self.cur_item  = default
        if period: self.period = period
        if delayClick: self.delayClick = delayClick
        self.deinit()
        
class TFT_MENU_ICON_CONTROLLER:
    def __init__(self,gui:TFT_GUI):
        self.width = 0
        self.height = 0
        self.path = 0
        self.x = 0
        self.y = 0
        self.png = False
        self.gui = gui
        
    def show(self,path:str,width:int,height:int,x:int,y:int,png:bool = False):
        data = [path,width,height,x,y,png]
        old_data = [self.path,self.width,self.height,self.x,self.y,self.png]
        
        for n in range(0,len(data)):
            if data[n] != old_data[n]:
                self.path = data[0]
                self.width = data[1]
                self.height = data[2]
                self.x = data[3]
                self.y = data[4]
                self.png = data[5]
                
                self.gui.show_icon(self.path,self.x,self.y,{"width":self.width,"height":self.height} if self.png else None)
                break
        
            

            
'''
Created on Jan 23, 2024

@author: Pat Deegan
@copyright: Copyright (C) 2024 Pat Deegan, https://psychogenic.com
'''


RP2040SystemClockDefaultHz = 125000000

IsRP2040 = False 
try:
    import machine 
    import rp2
    IsRP2040 = True 
except:
    pass


if IsRP2040:
    '''
        low-level machine related methods.
        
        
        
        Have some read_ and write_ for in/bidir/out ports
        NOTE: [mappings] that these rely on GPIO pin mappings that 
        are specific to TT 4/5 demoboard layout
        
        The read_ will only return bits for GPIO that are set 
        as INPUTs
        The write_ will write values to all GPIO but these will only
        impact GPIO that are setup as OUTPUTs.  For input gpio, this 
        value will be remembered and apply should the pin be turned
        into an output.
        
        NOTE: [muxing] there is a MUX on some pins of the low 
        output nibble on TT04/05 demoboards, that could in theory
        interfere with this.
        If you use the tt.shuttle to select/enable projects, it 
        ensures that the mux is set to let these pins out as you'd 
        expect.  If you're down in the weeds and want to make sure 
        or play with this, you can use
            tt.muxCtrl.mode_admin() 
                to send out 1/2/3 to the asic mux, and
            tt.muxCtrl.mode_project_IO()
                to behave normally.
        
    '''
    
    @rp2.asm_pio(set_init=rp2.PIO.OUT_HIGH)
    def _pio_toggle_pin():
        wrap_target()
        set(pins, 1)
        mov(y, osr)
        label("delay1")
        jmp(y_dec, "delay1")  # Delay
        set(pins, 0)
        mov(y, osr)
        label("delay2")
        jmp(y_dec, "delay2")  # Delay
        wrap()
        
    class PIOClock:
        def __init__(self, pin):
            self.freq = 0
            self.pin = pin
            self._current_pio = None 
            
        def start(self, freq_hz:int):
            self.freq = freq_hz 
            
            self.stop()
            if self.freq <= 0:
                return
                
            set_RP_system_clock(100_000_000)
            if self._current_pio is None:
                self._current_pio = rp2.StateMachine(
                    0,
                    _pio_toggle_pin,
                    freq=2000,
                    set_base=self.pin,
                )
            
            # Set the delay: 1000 cycles per hz minus 2 cycles for the set/mov instructions
            self._current_pio.put(int(500 * (2 / self.freq) - 2))
            self._current_pio.exec("pull()")
            self._current_pio.active(1)
            
        def stop(self):
            if self._current_pio is None or not self.freq:
                return 
            
            self._current_pio.active(0)
            self.freq = 0
            self._current_pio = None
            self.pin.init(machine.Pin.IN)
    
    def isfile(file_path:str):
        try:
            f = open(file_path, 'r')
        except OSError:
            return False 
        f.close()
        return True 
    def get_RP_system_clock():
        return machine.freq()
    def set_RP_system_clock(freqHz:int):
        machine.freq(int(freqHz))
    
    @micropython.native
    def write_input_byte(val):
        # low level machine stuff
        # move the value bits to GPIO spots
        # low nibble starts at 9 | high nibble at 17 (-4 'cause high nibble)
        val = ((val & 0xF) << 9) | ((val & 0xF0) << 17-4)
        # xor with current GPIO values, and mask to keep only input bits
        # 0x1E1E00 == 0b111100001111000000000 so GPIO 9-12 and 17-20
        val = (machine.mem32[0xd0000010] ^ val) & 0x1E1E00
        # val is now be all the input bits that have CHANGED:
        # writing to 0xd000001c will flip any GPIO where a 1 is found
        machine.mem32[0xd000001c] = val
        
    @micropython.native
    def read_input_byte():
        # just read the high and low nibbles from GPIO and combine into a byte
        return ( (machine.mem32[0xd0000004] & (0xf << 17)) >> (17-4)) | ((machine.mem32[0xd0000004] & (0xf << 9)) >> 9)
    
    @micropython.native
    def write_bidir_byte(val):
        # low level machine stuff
        # move the value bits to GPIO spots
        # for bidir, all uio bits are in a line starting 
        # at GPIO 21
        val = (val << 21)
        # xor with current GPIO values, and mask to keep only input bits
        val = (machine.mem32[0xd0000010] ^ val) & 0x1FE00000
        # val is now be all the bits that have CHANGED:
        # writing to 0xd000001c will flip any GPIO where a 1 is found,
        # only applies immediately to pins set as output 
        machine.mem32[0xd000001c] = val
        
        
    @micropython.native
    def read_bidir_byte():
        # just read the high and low nibbles from GPIO and combine into a byte
        return (machine.mem32[0xd0000004] & (0xff << 21)) >> 21
        
    @micropython.native
    def write_output_byte(val):
        # low level machine stuff
        # move the value bits to GPIO spots
        
        val = ((val & 0xF) << 5) | ((val & 0xF0) << 13-4)
        val = (machine.mem32[0xd0000010] ^ val) & 0x1E1E0
        # val is now be all the bits that have CHANGED:
        # writing to 0xd000001c will flip any GPIO where a 1 is found,
        # only applies immediately to pins set as output 
        machine.mem32[0xd000001c] = val
    
    @micropython.native
    def read_output_byte():
        
        # sample code to deal with differences between 
        # PCBs, not actually required as we didn't move anything
        # after all!
        # global PCBVERSION_TT06
        # all_io = machine.mem32[0xd0000004]
        #if PCBVERSION_TT06 is None:
        #    import ttboard.boot.demoboard_detect as dbdet
        #    PCBVERSION_TT06 = True if dbdet.DemoboardDetect.PCB == dbdet.DemoboardVersion.TT06 else False
        
        #if PCBVERSION_TT06:
        #    # gpio output bits are
        #    # 0x1e1e0 == 0b11110000111100000 so GPIO5-8 and GPIO 13-17
        #    val =  ((all_io & (0xf << 13)) >> (13 - 4)) | ((all_io & (0xf << 5)) >> 5)
        #else:
        # just read the high and low nibbles from GPIO and combine into a byte
        return ( (machine.mem32[0xd0000004] & (0xf << 13)) >> (13-4)) | ((machine.mem32[0xd0000004] & (0xf << 5)) >> 5)
    
    
else:
    import os.path 
    isfile = os.path.isfile
    
    class PIOClock:
        def __init__(self, pin):
            self.freq = 0
            self.pin = pin
            
        def start(self, freq_hz:int):
            self.freq = freq_hz 
            print(f"(mock) PIO clock @ {freq_hz}Hz")
            
        def stop(self):
            self.freq = 0
            print("PIO clock stop")
            
    def get_RP_system_clock():
        return RP2040SystemClockDefaultHz
    def set_RP_system_clock(freqHz:int):
        print(f"Set machine clock to {freqHz}")
import serial
import serial.tools.list_ports
import threading
import time
from typing import Callable, Optional, List

#*******************************************************************
def get_available_ports()->List[str]:
    """
    --------------------------------------------------------------------
    get_available_ports()
    Returns list of available COM ports

    OUTPUTS
    returns: List of COM port names (e.g., ['COM1', 'COM3', 'COM5'])

    (c) Kai Kuck 8-Jan-2026 20:45
    --------------------------------------------------------------------
    """
    ports = serial.tools.list_ports.comports()
    port_list = [port.device for port in ports]
    return sorted(port_list)
#*******************************************************************

#*******************************************************************
class SerialReader:
    """
    Serial communication handler for ESP-32
    """
    def __init__(self, com_port__str: str, baud_rate__int: int, data_callback__func: Callable[[float, float, bool, bool], None], raw_data_callback__func: Optional[Callable[[str], None]] = None):
        """
        --------------------------------------------------------------------
        __init__()
        Initializes SerialReader instance

        INPUTS
        com_port__str… COM port name (e.g., 'COM3')

        baud_rate__int… Baud rate for serial communication

        data_callback__func… Callback function that receives parsed data:
                              (Weight__g, Flow__mLPmin, FlowsensorError_Air, FlowsensorError_Overflow)

        raw_data_callback__func… Optional callback function that receives raw serial data as string

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        self.com_port__str = com_port__str
        self.baud_rate__int = baud_rate__int
        self.data_callback__func = data_callback__func
        self.raw_data_callback__func = raw_data_callback__func
        self.serial_connection = None
        self.reading_thread = None
        self.is_connected__bool = False
        self.should_stop__bool = False
#*******************************************************************

#*******************************************************************
    def connect(self)->bool:
        """
        --------------------------------------------------------------------
        connect()
        Attempts to connect to ESP-32 via serial port

        OUTPUTS
        returns: True if connection successful, False otherwise

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        if self.is_connected__bool:
            return True
        
        try:
            self.serial_connection = serial.Serial(
                port=self.com_port__str,
                baudrate=self.baud_rate__int,
                timeout=1.0
            )
            self.is_connected__bool = True
            self.should_stop__bool = False
            self.reading_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.reading_thread.start()
            return True
        except (serial.SerialException, ValueError, OSError) as e:
            self.is_connected__bool = False
            return False
#*******************************************************************

#*******************************************************************
    def disconnect(self)->None:
        """
        --------------------------------------------------------------------
        disconnect()
        Disconnects from ESP-32 and stops reading thread

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        self.should_stop__bool = True
        if self.reading_thread and self.reading_thread.is_alive():
            # Wait a bit for thread to finish
            self.reading_thread.join(timeout=2.0)
        
        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.close()
            except:
                pass
        
        self.is_connected__bool = False
        self.serial_connection = None
#*******************************************************************

#*******************************************************************
    def _read_loop(self)->None:
        """
        --------------------------------------------------------------------
        _read_loop()
        Internal method that continuously reads from serial port and parses data

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        buffer__str = ""
        
        while not self.should_stop__bool and self.is_connected__bool:
            try:
                if self.serial_connection and self.serial_connection.in_waiting > 0:
                    data__bytes = self.serial_connection.read(self.serial_connection.in_waiting)
                    decoded_data__str = data__bytes.decode('ascii', errors='ignore')
                    buffer__str += decoded_data__str
                    
                    # Send raw data to callback if registered
                    if self.raw_data_callback__func:
                        try:
                            self.raw_data_callback__func(decoded_data__str)
                        except:
                            pass
                    
                    # Process complete lines
                    while '\n' in buffer__str:
                        line__str, buffer__str = buffer__str.split('\n', 1)
                        line__str = line__str.strip()
                        
                        if line__str:
                            # Debug: Print first few lines received
                            if not hasattr(self, '_debug_line_count'):
                                self._debug_line_count = 0
                            if self._debug_line_count < 5:
                                print(f"DEBUG: Received line: {line__str}")
                                self._debug_line_count += 1
                            self._parse_line(line__str)
                
                # Check stop flag more frequently
                if self.should_stop__bool:
                    break
                    
                time.sleep(0.01)  # Small delay to prevent CPU spinning
                
            except (serial.SerialException, UnicodeDecodeError):
                self.is_connected__bool = False
                break
            except Exception:
                # Continue on other errors, but check stop flag
                if self.should_stop__bool:
                    break
                time.sleep(0.1)
#*******************************************************************

#*******************************************************************
    def _parse_line(self, line__str: str)->None:
        """
        --------------------------------------------------------------------
        _parse_line()
        Parses a line of data from ESP-32

        INPUTS
        line__str… Single line of ASCII data in format: t_us, mass_g, flowRate, airInLine, highFlow
                   (comma-separated values where 999.9 indicates invalid data)

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        try:
            parts = line__str.split(',')
            if len(parts) >= 5:
                t_us = float(parts[0].strip())  # Time in microseconds (not currently used)
                mass_g = float(parts[1].strip())
                flowRate = float(parts[2].strip())
                airInLine = bool(int(parts[3].strip()))
                highFlow = bool(int(parts[4].strip()))
                
                # Skip data points with invalid values (999.9)
                INVALID_VALUE = 999.9
                if mass_g >= INVALID_VALUE or flowRate >= INVALID_VALUE:
                    if not hasattr(self, '_debug_skip_count'):
                        self._debug_skip_count = 0
                    if self._debug_skip_count < 3:
                        print(f"DEBUG: Skipping invalid data - mass_g: {mass_g}, flowRate: {flowRate}")
                        self._debug_skip_count += 1
                    return
                
                # Map to callback format
                Weight__g = mass_g
                Flow__mLPmin = flowRate
                FlowsensorError_Air = airInLine
                FlowsensorError_Overflow = highFlow
                
                if self.data_callback__func:
                    self.data_callback__func(Weight__g, Flow__mLPmin, FlowsensorError_Air, FlowsensorError_Overflow)
            else:
                if not hasattr(self, '_debug_parse_error_count'):
                    self._debug_parse_error_count = 0
                if self._debug_parse_error_count < 3:
                    print(f"DEBUG: Line has insufficient parts ({len(parts)} < 5): {line__str}")
                    self._debug_parse_error_count += 1
        except (ValueError, IndexError) as e:
            # Skip malformed lines
            if not hasattr(self, '_debug_exception_count'):
                self._debug_exception_count = 0
            if self._debug_exception_count < 3:
                print(f"DEBUG: Parse exception for line '{line__str}': {e}")
                self._debug_exception_count += 1
#*******************************************************************


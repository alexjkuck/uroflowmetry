import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.font import Font
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
import numpy as np
import csv
import os
from pathlib import Path
from datetime import datetime
import threading
import time
import sys
from typing import Optional, List, Tuple, Callable

from settings_manager import load_settings, save_settings, get_default_settings
from serial_comm import SerialReader, get_available_ports

#*******************************************************************
class SerialMonitorWindow:
    """
    Serial monitor window for displaying raw serial data
    """
    def __init__(self, parent__tk, on_data_callback__func):
        """
        --------------------------------------------------------------------
        __init__()
        Initializes serial monitor window

        INPUTS
        parent__tk… Parent tkinter window

        on_data_callback__func… Callback function to register for receiving raw data

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        self.parent__tk = parent__tk
        self.on_data_callback__func = on_data_callback__func
        self.window = tk.Toplevel(parent__tk)
        self.window.title("Serial Monitor")
        self.window.geometry("600x400")
        self.window.transient(parent__tk)
        
        # Set font size to 12 points for this window
        default_font = ('TkDefaultFont', 12)
        self.window.option_add('*Font', default_font)
        
        # Create text widget with scrollbar
        frame = ttk.Frame(self.window)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.text_widget = tk.Text(frame, wrap=tk.WORD, yscrollcommand=scrollbar.set, font=('Courier', 12))
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.text_widget.yview)
        
        # Clear button
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        clear_button = ttk.Button(button_frame, text="Clear", command=self._clear_text)
        clear_button.pack(side=tk.LEFT, padx=5)
        
        # Close button
        close_button = ttk.Button(button_frame, text="Close", command=self._close_window)
        close_button.pack(side=tk.RIGHT, padx=5)
        
        # Register callback
        if self.on_data_callback__func:
            self.on_data_callback__func(self._on_raw_data_received)
        
        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self._close_window)
#*******************************************************************

#*******************************************************************
    def _on_raw_data_received(self, raw_data__str: str)->None:
        """
        --------------------------------------------------------------------
        _on_raw_data_received()
        Called when raw serial data is received

        INPUTS
        raw_data__str… Raw serial data string

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        if self.text_widget:
            self.text_widget.insert(tk.END, raw_data__str)
            self.text_widget.see(tk.END)  # Auto-scroll to bottom
#*******************************************************************

#*******************************************************************
    def _clear_text(self)->None:
        """
        --------------------------------------------------------------------
        _clear_text()
        Clears the text widget

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        if self.text_widget:
            self.text_widget.delete(1.0, tk.END)
#*******************************************************************

#*******************************************************************
    def _close_window(self)->None:
        """
        --------------------------------------------------------------------
        _close_window()
        Closes serial monitor window

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        if self.on_data_callback__func:
            self.on_data_callback__func(None)  # Unregister callback
        self.window.destroy()
#*******************************************************************

#*******************************************************************
class PreferencesWindow:
    """
    Preferences window for configuring application settings
    """
    def __init__(self, parent__tk, settings__dict: dict, on_save__callback):
        """
        --------------------------------------------------------------------
        __init__()
        Initializes preferences window

        INPUTS
        parent__tk… Parent tkinter window

        settings__dict… Current settings dictionary

        on_save__callback… Callback function called when settings are saved

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        self.parent__tk = parent__tk
        self.on_save__callback = on_save__callback
        self.settings__dict = settings__dict.copy()
        
        self.window = tk.Toplevel(parent__tk)
        self.window.title("Preferences")
        self.window.transient(parent__tk)
        self.window.grab_set()
        
        # Set font size to 12 points for this window
        default_font = ('TkDefaultFont', 12)
        self.window.option_add('*Font', default_font)
        
        # COM Port selection
        ttk.Label(self.window, text="COM Port:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
        self.com_port_var = tk.StringVar(value=settings__dict.get("com_port", "COM3"))
        self.com_port_combo = ttk.Combobox(self.window, textvariable=self.com_port_var, width=15)
        self.com_port_combo['values'] = get_available_ports()
        if not self.com_port_combo['values']:
            self.com_port_combo['values'] = ['COM3', 'COM1', 'COM2', 'COM4', 'COM5']
        self.com_port_combo.grid(row=0, column=1, padx=10, pady=5)
        self.com_port_combo.bind('<<ComboboxSelected>>', self._on_setting_changed)
        self.com_port_combo.bind('<KeyRelease>', self._on_setting_changed)
        
        # Baud Rate selection
        ttk.Label(self.window, text="Baud Rate:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
        self.baud_rate_var = tk.StringVar(value=str(settings__dict.get("baud_rate", 230400)))
        baud_rate_combo = ttk.Combobox(self.window, textvariable=self.baud_rate_var, width=15)
        baud_rate_combo['values'] = ['115200', '230400', '460800', '921600']
        baud_rate_combo.grid(row=1, column=1, padx=10, pady=5)
        baud_rate_combo.bind('<<ComboboxSelected>>', self._on_setting_changed)
        baud_rate_combo.bind('<KeyRelease>', self._on_setting_changed)
        
        # Plot time length scrollbar
        ttk.Label(self.window, text="Plot Time Length (sec):").grid(row=2, column=0, padx=10, pady=5, sticky='w')
        self.plot_time_var = tk.IntVar(value=settings__dict.get("plot_time_length__sec", 180))
        self.plot_time_label = ttk.Label(self.window, text=str(self.plot_time_var.get()))
        self.plot_time_label.grid(row=2, column=2, padx=10, pady=5)
        
        plot_time_scale = ttk.Scale(self.window, from_=60, to=420, variable=self.plot_time_var, 
                                    orient=tk.HORIZONTAL, length=200, command=self._on_plot_time_changed)
        plot_time_scale.grid(row=2, column=1, padx=10, pady=5)
        
        # Data folder selection
        ttk.Label(self.window, text="Data Folder:").grid(row=3, column=0, padx=10, pady=5, sticky='w')
        self.data_folder_var = tk.StringVar(value=settings__dict.get("data_folder", 
            r"C:\KaisDir\Dropbox\K0_Work\00_Elbeon\Elbeon_SkunkWorxx\UrineFlowmeter\Logging"))
        data_folder_entry = ttk.Entry(self.window, textvariable=self.data_folder_var, width=40)
        data_folder_entry.grid(row=3, column=1, columnspan=2, padx=10, pady=5, sticky='ew')
        data_folder_entry.bind('<KeyRelease>', self._on_setting_changed)
        
        folder_button = ttk.Button(self.window, text="Browse...", command=self._browse_folder)
        folder_button.grid(row=4, column=1, padx=10, pady=5, sticky='w')
        
        # Close button
        close_button = ttk.Button(self.window, text="Close", command=self._close_window)
        close_button.grid(row=5, column=1, padx=10, pady=10)
        
        self.window.columnconfigure(1, weight=1)
#*******************************************************************

#*******************************************************************
    def _on_plot_time_changed(self, value__str: str)->None:
        """
        --------------------------------------------------------------------
        _on_plot_time_changed()
        Called when plot time scrollbar is moved

        INPUTS
        value__str… String value from scrollbar

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        value__int = int(float(value__str))
        self.plot_time_var.set(value__int)
        self.plot_time_label.config(text=str(value__int))
        self._on_setting_changed(None)
#*******************************************************************

#*******************************************************************
    def _browse_folder(self)->None:
        """
        --------------------------------------------------------------------
        _browse_folder()
        Opens folder selection dialog

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        folder__str = filedialog.askdirectory(initialdir=self.data_folder_var.get())
        if folder__str:
            self.data_folder_var.set(folder__str)
            self._on_setting_changed(None)
#*******************************************************************

#*******************************************************************
    def _on_setting_changed(self, event)->None:
        """
        --------------------------------------------------------------------
        _on_setting_changed()
        Called when any setting is changed, saves settings immediately

        INPUTS
        event… Tkinter event (may be None)

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        try:
            self.settings__dict["com_port"] = self.com_port_var.get()
            self.settings__dict["baud_rate"] = int(self.baud_rate_var.get())
            self.settings__dict["plot_time_length__sec"] = self.plot_time_var.get()
            self.settings__dict["data_folder"] = self.data_folder_var.get()
            
            save_settings(self.settings__dict)
            if self.on_save__callback:
                self.on_save__callback(self.settings__dict)
        except (ValueError, KeyError):
            pass
#*******************************************************************

#*******************************************************************
    def _close_window(self)->None:
        """
        --------------------------------------------------------------------
        _close_window()
        Closes preferences window

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        self.window.destroy()
#*******************************************************************

#*******************************************************************
class DataCollectionGUI:
    """
    Main GUI application for data collection from ESP-32
    """
    def __init__(self):
        """
        --------------------------------------------------------------------
        __init__()
        Initializes main GUI application

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        self.settings__dict = load_settings()
        self.root = tk.Tk()
        self.root.title("Uroflowmetry Data Collection")
        
        # Set minimum window size to ensure all elements are visible
        self.root.minsize(800, 600)
        
        # Update the window to get accurate screen dimensions
        self.root.update_idletasks()
        
        # Set initial window size
        window_width = 2000
        window_height = 1200
        # Position window (centered + 200 pixels offset)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x_position = int((screen_width - window_width) / 2) + 800
        y_position = int((screen_height - window_height) / 2) + 200
        self.root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
        
        # Set default font size to 12 points for all GUI elements
        default_font = ('TkDefaultFont', 12)
        self.root.option_add('*Font', default_font)
        self.root.option_add('*TkDefaultFont', default_font)
        self.root.option_add('*TkTextFont', default_font)
        self.root.option_add('*TkFixedFont', ('Courier', 12))
        self.root.option_add('*TkMenuFont', default_font)
        self.root.option_add('*TkHeadingFont', default_font)
        self.root.option_add('*TkCaptionFont', default_font)
        self.root.option_add('*TkSmallCaptionFont', default_font)
        self.root.option_add('*TkIconFont', default_font)
        self.root.option_add('*TkTooltipFont', default_font)
        # Ensure menu items use 12pt font (don't set Label font globally as it may override explicit settings)
        self.root.option_add('*Menu.Font', default_font)
        self.root.option_add('*menubar.Font', default_font)
        
        # Data storage
        self.time_data__list: List[float] = []
        self.weight_data__list: List[float] = []
        self.flow_data__list: List[float] = []
        self.error_air_data__list: List[bool] = []
        self.error_overflow_data__list: List[bool] = []
        self.start_time__float: Optional[float] = None
        
        # CSV file handling
        self.csv_file__path: Optional[Path] = None
        self.csv_file__handle: Optional[object] = None
        self.csv_writer: Optional[object] = None
        self.last_save_time__float: Optional[float] = None
        self.save_interval__sec = 30.0
        
        # Serial connection
        self.serial_reader: Optional[SerialReader] = None
        self.raw_data_callback__func: Optional[Callable[[str], None]] = None
        self.serial_monitor_window: Optional[SerialMonitorWindow] = None
        
        # Create GUI elements
        self._create_menu()
        self._create_status_bar()  # Create status bar first so it's always visible
        self._create_control_panel()
        self._create_plot_area()  # Create plot area last so it fills remaining space
        
        # Ensure window size is set correctly after all widgets are created
        self.root.update_idletasks()
        window_width = 2000
        window_height = 1200
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x_position = int((screen_width - window_width) / 2) + 800
        y_position = int((screen_height - window_height) / 2) + 200
        self.root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
        
        # Start with connection attempt
        self._connect_serial()
        
        # Setup window close handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Start periodic save timer
        self.save_timer_id = None
        self._schedule_save()
#*******************************************************************

#*******************************************************************
    def _create_menu(self)->None:
        """
        --------------------------------------------------------------------
        _create_menu()
        Creates menu bar with File and Help menus

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        menubar = tk.Menu(self.root, font=('TkDefaultFont', 12))
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0, font=('TkDefaultFont', 12))
        menubar.add_cascade(label="File", menu=file_menu, underline=0)
        file_menu.add_command(label="Save As...", command=self._save_as, accelerator="Alt+F, A")
        file_menu.add_separator()
        file_menu.add_command(label="Preferences...", command=self._show_preferences, accelerator="Alt+F, P")
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0, font=('TkDefaultFont', 12))
        menubar.add_cascade(label="Tools", menu=tools_menu, underline=0)
        tools_menu.add_command(label="Serial Monitor", command=self._show_serial_monitor, accelerator="Alt+T, S")
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0, font=('TkDefaultFont', 12))
        menubar.add_cascade(label="Help", menu=help_menu, underline=0)
        help_menu.add_command(label="About", command=self._show_about, accelerator="Alt+H, A")
        
        # Keyboard shortcuts
        self.root.bind('<Alt-f>', lambda e: file_menu.post(0, 0))
        self.root.bind('<Alt-F>', lambda e: file_menu.post(0, 0))
        self.root.bind('<Alt-t>', lambda e: tools_menu.post(0, 0))
        self.root.bind('<Alt-T>', lambda e: tools_menu.post(0, 0))
        self.root.bind('<Alt-h>', lambda e: help_menu.post(0, 0))
        self.root.bind('<Alt-H>', lambda e: help_menu.post(0, 0))
#*******************************************************************

#*******************************************************************
    def _create_plot_area(self)->None:
        """
        --------------------------------------------------------------------
        _create_plot_area()
        Creates matplotlib plot area for real-time data visualization

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        # Set font size to 12 points
        plt.rcParams.update({'font.size': 12})
        
        # Calculate figure size - account for menu, control panel, and status bar
        # Use a reasonable default size that fits in the window
        # The figure should be smaller than the window to leave room for other UI elements
        fig_width = 18.0  # inches
        fig_height = 10.0  # inches
        
        # Create figure with two subplots
        self.fig, (self.ax_weight, self.ax_flow) = plt.subplots(2, 1, figsize=(fig_width, fig_height))
        self.fig.tight_layout(pad=3.0)
        
        # Weight plot
        self.ax_weight.set_xlabel('Time (sec)', fontsize=12)
        self.ax_weight.set_ylabel('Weight (g)', fontsize=12)
        self.ax_weight.set_title('Weight vs Time', fontsize=12)
        self.ax_weight.grid(True)
        self.ax_weight.tick_params(labelsize=12)
        self.line_weight, = self.ax_weight.plot([], [], 'b-')
        
        # Flow plot
        self.ax_flow.set_xlabel('Time (sec)', fontsize=12)
        self.ax_flow.set_ylabel('Flow (mL/min)', fontsize=12)
        self.ax_flow.set_title('Flow vs Time', fontsize=12)
        self.ax_flow.grid(True)
        self.ax_flow.tick_params(labelsize=12)
        self.line_flow, = self.ax_flow.plot([], [], 'r-')
        
        # Set initial x-axis limits to prevent auto-scaling to wrong values
        plot_time_length__sec = self.settings__dict.get("plot_time_length__sec", 180)
        self.ax_weight.set_xlim(0, plot_time_length__sec)
        self.ax_flow.set_xlim(0, plot_time_length__sec)
        self.ax_weight.set_autoscale_on(False)  # Disable autoscaling on x-axis
        self.ax_flow.set_autoscale_on(False)  # Disable autoscaling on x-axis
        
        # Embed in tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, self.root)
        self.canvas.draw()
        # Pack canvas above the status bar, filling remaining space
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Animation for real-time updates
        self.animation = FuncAnimation(self.fig, self._update_plot, interval=100, blit=False, cache_frame_data=False)
#*******************************************************************

#*******************************************************************
    def _create_control_panel(self)->None:
        """
        --------------------------------------------------------------------
        _create_control_panel()
        Creates control panel with connect/disconnect button

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        control_frame = ttk.Frame(self.root)
        control_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        # Use tk.Button instead of ttk.Button for better font control
        # Set font to 12pt (20 pixels) like the status bar
        button_font = Font(family='Segoe UI', size=20)
        self.connect_button = tk.Button(control_frame, text="Connect", command=self._toggle_connection, font=button_font)
        self.connect_button.pack(side=tk.LEFT, padx=5)
#*******************************************************************

#*******************************************************************
    def _create_status_bar(self)->None:
        """
        --------------------------------------------------------------------
        _create_status_bar()
        Creates status bar showing connection status

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        # Use regular tk.Label instead of ttk.Label for better font control
        # Tkinter Font size is in pixels
        # For 12pt at standard 96 DPI: 12pt = 16 pixels
        # For higher DPI displays (125%, 150%), we need more pixels
        # Use 20 pixels to ensure 12pt appearance on most displays
        self.status_font = Font(family='Segoe UI', size=20)
        
        self.status_bar = tk.Label(self.root, text="Disconnected", relief=tk.SUNKEN, anchor=tk.W, 
                                   font=self.status_font, bg='#f0f0f0', bd=1)
        # Force font to be applied
        self.status_bar['font'] = self.status_font
        self.status_bar.configure(font=self.status_font)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self._update_status_bar()
#*******************************************************************

#*******************************************************************
    def _update_status_bar(self)->None:
        """
        --------------------------------------------------------------------
        _update_status_bar()
        Updates status bar text with current connection information

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        if self.serial_reader and self.serial_reader.is_connected__bool:
            status_text = f"Connected - {self.settings__dict['com_port']} @ {self.settings__dict['baud_rate']} bps"
        else:
            status_text = f"Disconnected - {self.settings__dict['com_port']} @ {self.settings__dict['baud_rate']} bps"
        
        # Ensure font is maintained at 12pt when updating - explicitly set font again
        self.status_bar.config(text=status_text)
        self.status_bar.configure(font=self.status_font)
#*******************************************************************

#*******************************************************************
    def _connect_serial(self)->None:
        """
        --------------------------------------------------------------------
        _connect_serial()
        Connects to ESP-32 via serial port

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        if self.serial_reader:
            self.serial_reader.disconnect()
        
        self.serial_reader = SerialReader(
            self.settings__dict["com_port"],
            self.settings__dict["baud_rate"],
            self._on_data_received,
            self.raw_data_callback__func
        )
        
        if self.serial_reader.connect():
            self.connect_button.config(text="Disconnect")
            self._update_status_bar()
        else:
            self.connect_button.config(text="Connect")
            self._update_status_bar()
            messagebox.showerror("Connection Error", 
                                f"Failed to connect to {self.settings__dict['com_port']}")
#*******************************************************************

#*******************************************************************
    def _disconnect_serial(self)->None:
        """
        --------------------------------------------------------------------
        _disconnect_serial()
        Disconnects from ESP-32

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        if self.serial_reader:
            self.serial_reader.disconnect()
            self.serial_reader = None
        self.connect_button.config(text="Connect")
        self._update_status_bar()
#*******************************************************************

#*******************************************************************
    def _toggle_connection(self)->None:
        """
        --------------------------------------------------------------------
        _toggle_connection()
        Toggles connection state when button is clicked

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        if self.serial_reader and self.serial_reader.is_connected__bool:
            self._disconnect_serial()
        else:
            self._connect_serial()
#*******************************************************************

#*******************************************************************
    def _on_data_received(self, Weight__g: float, Flow__mLPmin: float, 
                         FlowsensorError_Air: bool, FlowsensorError_Overflow: bool)->None:
        """
        --------------------------------------------------------------------
        _on_data_received()
        Callback function called when data is received from ESP-32

        INPUTS
        Weight__g… Weight measurement in grams

        Flow__mLPmin… Flow rate in mL/min

        FlowsensorError_Air… Boolean indicating air error

        FlowsensorError_Overflow… Boolean indicating overflow error

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        current_time__float = time.time()
        
        if self.start_time__float is None:
            self.start_time__float = current_time__float
            self._initialize_csv_file()
        
        elapsed_time__sec = current_time__float - self.start_time__float
        
        # Store data (this is thread-safe for appending)
        self.time_data__list.append(elapsed_time__sec)
        self.weight_data__list.append(Weight__g)
        self.flow_data__list.append(Flow__mLPmin)
        self.error_air_data__list.append(FlowsensorError_Air)
        self.error_overflow_data__list.append(FlowsensorError_Overflow)
        
        # Write to CSV
        if self.csv_writer:
            self.csv_writer.writerow([
                elapsed_time__sec,
                Weight__g,
                Flow__mLPmin,
                1 if FlowsensorError_Air else 0,
                1 if FlowsensorError_Overflow else 0
            ])
        
        # Check if we need to save
        if self.last_save_time__float is None:
            self.last_save_time__float = current_time__float
        elif current_time__float - self.last_save_time__float >= self.save_interval__sec:
            self._save_csv_file()
            self._reopen_csv_file()
            self.last_save_time__float = current_time__float
#*******************************************************************

#*******************************************************************
    def _initialize_csv_file(self)->None:
        """
        --------------------------------------------------------------------
        _initialize_csv_file()
        Creates and initializes CSV file for data logging

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        try:
            data_folder__path = Path(self.settings__dict["data_folder"])
            if not data_folder__path.exists():
                data_folder__path.mkdir(parents=True, exist_ok=True)
            
            datetime_str = datetime.now().strftime("%d%m%Y_%H%M")
            filename = f"UroData_{datetime_str}.csv"
            self.csv_file__path = data_folder__path / filename
            
            self._reopen_csv_file()
        except (OSError, PermissionError) as e:
            messagebox.showerror("File Error", f"Could not create data file: {e}")
#*******************************************************************

#*******************************************************************
    def _reopen_csv_file(self)->None:
        """
        --------------------------------------------------------------------
        _reopen_csv_file()
        Opens or reopens CSV file for appending

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        if self.csv_file__path:
            try:
                if self.csv_file__handle:
                    self.csv_file__handle.close()
                
                file_exists = self.csv_file__path.exists()
                self.csv_file__handle = open(self.csv_file__path, 'a', newline='')
                self.csv_writer = csv.writer(self.csv_file__handle)
                
                if not file_exists:
                    # Write header
                    self.csv_writer.writerow([
                        'Time__sec',
                        'Weight__g',
                        'Flow__mLPmin',
                        'FlowsensorError_Air',
                        'FlowsensorError_Overflow'
                    ])
            except (OSError, PermissionError) as e:
                messagebox.showerror("File Error", f"Could not open data file: {e}")
#*******************************************************************

#*******************************************************************
    def _save_csv_file(self)->None:
        """
        --------------------------------------------------------------------
        _save_csv_file()
        Closes CSV file to ensure data is written to disk

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        if self.csv_file__handle:
            try:
                self.csv_file__handle.close()
                self.csv_file__handle = None
                self.csv_writer = None
            except:
                pass
#*******************************************************************

#*******************************************************************
    def _update_plot(self, frame)->None:
        """
        --------------------------------------------------------------------
        _update_plot()
        Updates the plot with current data (called by animation)

        INPUTS
        frame… Frame number from animation (unused)

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        plot_time_length__sec = self.settings__dict.get("plot_time_length__sec", 180)
        current_time__float = time.time()
        
        if self.start_time__float is None:
            # Initialize plot with full time window even if no data yet
            self.ax_weight.set_xlim(0, plot_time_length__sec)
            self.ax_flow.set_xlim(0, plot_time_length__sec)
            self.canvas.draw_idle()
            return
        
        elapsed_time__sec = current_time__float - self.start_time__float
        
        if not self.time_data__list:
            # No data yet, show empty plot with initial time window
            self.ax_weight.set_xlim(0, plot_time_length__sec)
            self.ax_flow.set_xlim(0, plot_time_length__sec)
            self.line_weight.set_data([], [])
            self.line_flow.set_data([], [])
            self.canvas.draw_idle()
            return
        
        # Calculate time window - always start at 0, never negative
        if elapsed_time__sec <= plot_time_length__sec:
            # Show from 0 to current time (with small padding) when we have less data than window
            time_window_start__sec = 0
            time_window_end__sec = max(elapsed_time__sec + 1, plot_time_length__sec)  # Show full window or current time + padding
        else:
            # Show rolling window when we have more data than window size
            time_window_start__sec = max(0, elapsed_time__sec - plot_time_length__sec)  # Ensure never negative
            time_window_end__sec = elapsed_time__sec
        
        # Get all data - ensure arrays are synchronized (same length)
        # Data might be appended from background thread, so get lengths first
        time_len = len(self.time_data__list)
        weight_len = len(self.weight_data__list)
        flow_len = len(self.flow_data__list)
        
        # Use minimum length to ensure all arrays are synchronized
        min_len = min(time_len, weight_len, flow_len)
        
        if min_len == 0:
            # No data yet
            self.line_weight.set_data([], [])
            self.line_flow.set_data([], [])
            self.canvas.draw_idle()
            return
        
        # Create arrays with synchronized length
        time_array = np.array(self.time_data__list[:min_len])
        weight_array = np.array(self.weight_data__list[:min_len])
        flow_array = np.array(self.flow_data__list[:min_len])
        
        # Filter data to show only within time window
        mask = (time_array >= time_window_start__sec) & (time_array <= time_window_end__sec)
        
        if np.any(mask):
            time_plot = time_array[mask]
            weight_plot = weight_array[mask]
            flow_plot = flow_array[mask]
        else:
            # Fallback: show all data if mask is empty
            time_plot = time_array
            weight_plot = weight_array
            flow_plot = flow_array
        
        # Set x-axis limits FIRST to prevent autoscale from changing them
        self.ax_weight.set_xlim(time_window_start__sec, time_window_end__sec)
        self.ax_flow.set_xlim(time_window_start__sec, time_window_end__sec)
        
        # Update weight plot
        if len(time_plot) > 0:
            self.line_weight.set_data(time_plot, weight_plot)
        else:
            self.line_weight.set_data([], [])
        
        # Update flow plot
        if len(time_plot) > 0:
            self.line_flow.set_data(time_plot, flow_plot)
        else:
            self.line_flow.set_data([], [])
        
        # Update y-axis limits only (not x-axis)
        # Only update y-axis if we have data
        if len(time_plot) > 0:
            # Manually set y-limits based on data range with some padding
            if len(weight_plot) > 0:
                weight_min = np.min(weight_plot)
                weight_max = np.max(weight_plot)
                weight_range = weight_max - weight_min
                if weight_range > 0:
                    self.ax_weight.set_ylim(weight_min - 0.1 * weight_range, weight_max + 0.1 * weight_range)
                else:
                    self.ax_weight.set_ylim(weight_min - 1, weight_max + 1)
            
            if len(flow_plot) > 0:
                flow_min = np.min(flow_plot)
                flow_max = np.max(flow_plot)
                flow_range = flow_max - flow_min
                if flow_range > 0:
                    self.ax_flow.set_ylim(flow_min - 0.1 * flow_range, flow_max + 0.1 * flow_range)
                else:
                    self.ax_flow.set_ylim(flow_min - 1, flow_max + 1)
        
        # Ensure x-axis limits are set (never negative)
        self.ax_weight.set_xlim(max(0, time_window_start__sec), time_window_end__sec)
        self.ax_flow.set_xlim(max(0, time_window_start__sec), time_window_end__sec)
        
        # Use draw_idle for non-blocking updates
        try:
            self.canvas.draw_idle()
        except:
            pass
#*******************************************************************

#*******************************************************************
    def _schedule_save(self)->None:
        """
        --------------------------------------------------------------------
        _schedule_save()
        Schedules periodic CSV file saves

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        self._save_csv_file()
        if self.csv_file__path:
            self._reopen_csv_file()
        self.save_timer_id = self.root.after(int(self.save_interval__sec * 1000), self._schedule_save)
#*******************************************************************

#*******************************************************************
    def _show_preferences(self)->None:
        """
        --------------------------------------------------------------------
        _show_preferences()
        Shows preferences window

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        def on_settings_saved(settings__dict: dict)->None:
            old_plot_time = self.settings__dict.get("plot_time_length__sec", 180)
            self.settings__dict = settings__dict
            new_plot_time = self.settings__dict.get("plot_time_length__sec", 180)
            self._update_status_bar()
            
            # If plot time changed, trigger plot update
            if old_plot_time != new_plot_time:
                # Force plot update by calling the animation callback
                if hasattr(self, 'animation'):
                    self._update_plot(None)
            
            # Reconnect if currently connected
            if self.serial_reader and self.serial_reader.is_connected__bool:
                self._disconnect_serial()
                self._connect_serial()
        
        PreferencesWindow(self.root, self.settings__dict, on_settings_saved)
#*******************************************************************

#*******************************************************************
    def _save_as(self)->None:
        """
        --------------------------------------------------------------------
        _save_as()
        Opens save dialog for exporting data (placeholder for future implementation)

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        messagebox.showinfo("Save As", "Save As functionality will be implemented in a future version.")
#*******************************************************************

#*******************************************************************
    def _show_serial_monitor(self)->None:
        """
        --------------------------------------------------------------------
        _show_serial_monitor()
        Shows serial monitor window

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        if self.serial_monitor_window is None or not self.serial_monitor_window.window.winfo_exists():
            def register_callback(callback__func):
                self.raw_data_callback__func = callback__func
                # Update serial reader if connected
                if self.serial_reader and self.serial_reader.is_connected__bool:
                    self.serial_reader.raw_data_callback__func = callback__func
            
            self.serial_monitor_window = SerialMonitorWindow(self.root, register_callback)
        else:
            # Bring existing window to front
            self.serial_monitor_window.window.lift()
            self.serial_monitor_window.window.focus_force()
#*******************************************************************

#*******************************************************************
    def _show_about(self)->None:
        """
        --------------------------------------------------------------------
        _show_about()
        Shows about dialog

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        messagebox.showinfo("About", 
                          "Uroflowmetry Data Collection\n\n"
                          "Software for collecting data from ESP-32\n"
                          "via serial communication.\n\n"
                          "(c) Kai Kuck 2026")
#*******************************************************************

#*******************************************************************
    def _on_closing(self)->None:
        """
        --------------------------------------------------------------------
        _on_closing()
        Handles window close event - saves data and disconnects

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        # Cancel any pending timers
        if hasattr(self, 'save_timer_id') and self.save_timer_id:
            self.root.after_cancel(self.save_timer_id)
        
        # Save CSV file
        self._save_csv_file()
        
        # Disconnect serial (this will stop the reading thread)
        self._disconnect_serial()
        
        # Stop animation
        if hasattr(self, 'animation'):
            try:
                self.animation.event_source.stop()
            except:
                pass
        
        # Close matplotlib figure
        if hasattr(self, 'fig'):
            try:
                plt.close(self.fig)
            except:
                pass
        
        # Quit mainloop and destroy window
        self.root.quit()
        self.root.destroy()
        
        # Force exit to ensure all threads terminate
        sys.exit(0)
#*******************************************************************

#*******************************************************************
    def run(self)->None:
        """
        --------------------------------------------------------------------
        run()
        Starts the GUI main loop

        OUTPUTS
        None

        (c) Kai Kuck 8-Jan-2026 20:45
        --------------------------------------------------------------------
        """
        self.root.mainloop()
#*******************************************************************


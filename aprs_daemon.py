#! /usr/bin/python
"""APRS daemon"""
import threading
import subprocess
import re
import time
from math import sin, cos, acos, atan2, degrees

# Simulation and data storage
import numpy as np
import pyBalloon.pyb_io
import pyBalloon.pyb_traj

# SRD
#from rtlsdr import *
from libfap.libfap import libfap, fapLOCATION

#GPS
import pynmea2

# RS232
import serial

SDR, RS232, FILE = range(3)

def distance(lat0, lon0, lat1, lon1):
    """Calculate distance between two locations"""
    return acos(sin(lat0)*sin(lat1) + cos(lat0)*cos(lat1) * \
           cos(lon1 - lon0)) * 6371

def direction(lat0, lon0, lat1, lon1):
    """Calculate compass heading of target"""
    ydir = sin(lon1 - lon0) * cos(lat1)
    xdir = cos(lat0)*sin(lat1) - sin(lat0)*cos(lat1)*cos(lon1 - lon0)
    bearing = degrees(-atan2(ydir, xdir))
    return (bearing+360) % 360

#LIVE_DATA = {
    #'timestamps':  np.array([]),
    #'lats':  np.array([]),
    #'lons':  np.array([]),
    #'pressures': np.array([]),
    #'altitudes':  np.array([]),
    #'temperatures': np.array([]),
    #'horizontal_speed': np.array([]),
    #'vertical_speed': np.array([]),
#}

LIVE_DATA = {
    'timestamps': [],
    'lats': [],
    'lons': [],
    'pressures': [],
    'altitudes': [],
    'temperatures': [],
    'horizontal_speed': [],
    'vertical_speed': [],
}

# parameters
PARAMETERS = {
    'aprs_source':                 0,
    'aprs_file':                   "",
    'update_interval':             1,
    'callsign':                    "",
    'sdr_freq':                    144.8,
    'sdr_rate':                    22050,
    'sdr_gain':                    4,
    'sdr_serial_port':             0,
    'sdr_serial_rate':             9600,
    'sdr_serial_bytesize':         8,
    'sdr_serial_parity':           'N',
    'sdr_serial_stopbits':         1,
    'sdr_serial_timeout':          None,
    'sdr_serial_xonxoff':          False,
    'sdr_serial_rtscts':           False,
    'sdr_serial_writetimeout':     None,
    'sdr_serial_dsrdtr':           False,
    'sdr_serial_interchartimeout': None,
    'raw_file':                    "/tmp/raw_data.dat",
    'data_file':                   "/tmp/live_data.dat",
    'simulate':                    False,
    'gfs_dir':                     "/tmp/gfs",
    'kml_file':                    "/tmp/pyballoon_trajectories.kml",
    'gps':                         False,
    'gps_serial_port':             0,
    'gps_serial_rate':             9600,
    'gps_serial_bytesize':         8,
    'gps_serial_parity':           'N',
    'gps_serial_stopbits':         1,
    'gps_serial_timeout':          None,
    'gps_serial_xonxoff':          False,
    'gps_serial_rtscts':           False,
    'gps_serial_writetimeout':     None,
    'gps_serial_dsrdtr':           False,
    'gps_serial_interchartimeout': None,
}

BALLOON = {
    'lat0':                      60.1,
    'lon0':                      25.0,
    'alt0':                      10.0,
    'altitude_step':             100.0,
    'equip_mass':                1.0,
    'balloon_mass':              1.0,
    'fill_radius':               1.0,
    'radius_empty':              0.5,
    'burst_radius':              3.0,
    'thickness_empty':           0.2,
    'Cd_balloon':                0.5,
    'Cd_parachute':              0.8,
    'parachute_areas':           np.pi * np.array([0.5, 1.5])**2, # m^2
    'parachute_change_altitude': 2000.0,
}

class DataCollectorThread(threading.Thread):
    """Thread for collecting data"""
    def __init__(self, aprs_data_handler, gps_data_handler):
        """Initialise datacollector thread"""
        threading.Thread.__init__(self, name='DataCollectorThread')
        self._running = False
        self.start_frame_re = re.compile(r'^APRS: (.*)')
        self.aprs_data_handler = aprs_data_handler
        self.gps_data_handler = gps_data_handler
        self.subprocs = {}
        self.filep = None
        self.sdr_ser = None
        self.gps_ser = None

    def _init_process(self):
        """Initialise background processes"""
        if PARAMETERS['aprs_source'] == SDR:
            try:
                self.subprocs['rtl_fm'] = subprocess.Popen(
                    ['rtl_fm', '-f', str(PARAMETERS['sdr_freq']),
                    '-s', str(PARAMETERS['sdr_rate']),
                    '-g', str(PARAMETERS['sdr_gain']), '-'],
                    stdout=subprocess.PIPE, stderr=open('/dev/null')
                )
                self.subprocs['mm'] = subprocess.Popen(
                    ['multimon-ng', '-a', 'AFSK1200', '-A', '-'],
                    stdin=self.subprocs['rtl_fm'].stdout,
                    stdout=subprocess.PIPE, stderr=open('/dev/null')
                )
            except ValueError:
                print "Invalid parameters when opening subprocesses"
            except OSError:
                print "OSError"
        elif PARAMETERS['aprs_source'] == RS232:
            try:
                self.sdr_ser = serial.Serial(PARAMETERS['sdr_serial_port'],
                                PARAMETERS['sdr_serial_rate'],
                                PARAMETERS['sdr_serial_bytesize'],
                                PARAMETERS['sdr_serial_parity'],
                                PARAMETERS['sdr_serial_stopbits'],
                                PARAMETERS['sdr_serial_timeout'],
                                PARAMETERS['sdr_serial_xonxoff'],
                                PARAMETERS['sdr_serial_rtscts'],
                                PARAMETERS['sdr_serial_writetimeout'],
                                PARAMETERS['sdr_serial_dsrdtr'],
                                PARAMETERS['sdr_serial_interchartimeout'])
            except serial.SerialException:
                pass
        else: #data from file
            try:
                self.filep = open(PARAMETERS['aprs_file'], 'r')
            except IOError:
                print "IO error"
        if PARAMETERS['gps']:
            try:
                self.gps_ser = serial.Serial(PARAMETERS['gps_serial_port'],
                                PARAMETERS['gps_serial_rate'],
                                PARAMETERS['gps_serial_bytesize'],
                                PARAMETERS['gps_serial_parity'],
                                PARAMETERS['gps_serial_stopbits'],
                                PARAMETERS['gps_serial_timeout'],
                                PARAMETERS['gps_serial_xonxoff'],
                                PARAMETERS['gps_serial_rtscts'],
                                PARAMETERS['gps_serial_writetimeout'],
                                PARAMETERS['gps_serial_dsrdtr'],
                                PARAMETERS['gps_serial_interchartimeout'])
            except serial.SerialException:
                print "SerialException"

    def exit(self):
        """Dispose thread"""
        self._running = False
        if PARAMETERS['aprs_source'] == SDR:
            for name in ['mm', 'rtl_fm']:
                try:
                    proc = self.subprocs[name]
                    proc.terminate()
                except OSError:
                    print "OSError"
        elif PARAMETERS['aprs_source'] == RS232:
            try:
                self.sdr_ser.close()
            except serial.SerialException:
                pass
        else: #data from file
            try:
                self.filep.close()
            except IOError:
                print "IO error"
        if PARAMETERS['gps']:
            try:
                self.gps_ser.close()
            except serial.SerialException:
                print "SerialException"

    def run(self):
        """Run thread"""
        print '', self.name, 'started.'
        self._init_process()
        self._running = True
        while self._running:
            #print "data collector loop"
            if PARAMETERS['aprs_source'] == SDR:
                try:
                    aprs_line = self.subprocs['mm'].stdout.readline()
                except OSError:
                    print "OSError"
            elif PARAMETERS['aprs_source'] == RS232:
                aprs_line = self.sdr_ser.readline()
            else: #data from file
                try:
                    aprs_line = self.filep.readline()
                except IOError:
                    print "IO error"
            if PARAMETERS['gps']:
                try:
                    gps_line = self.gps_ser.readline()
                except serial.SerialException:
                    print "SerialException"
            #print aprs_line
            if aprs_line != '':
                #aprs_line = aprs_line.strip()
                tnc2_frame = aprs_line.strip()
                #m = self.start_frame_re.match(aprs_line)
                #if m:
                # tnc2_frame = m.group(1)
                # print tnc2_frame
                #self.aprs_data_handler.handle_data(tnc2_frame)
                self.aprs_data_handler(tnc2_frame)
            if PARAMETERS['gps'] and gps_line != '':
                self.gps_data_handler(gps_line)
            time.sleep(PARAMETERS['update_interval'])
        print '', self.name, 'ended.'

class DataHandlerThread(threading.Thread):
    """Thread for handling collected data"""
    def __init__(self, master):
        """Initialise datahandler thread"""
        threading.Thread.__init__(self, name='DataHandlerThread')
        self.master = master
        self.lock = threading.Lock()
        self._running = False
        self.time0 = 0
        self.loc0 = None
        self.loc = {'lat': BALLOON['lat0'],
                    'lon': BALLOON['lon0'],
                    'alt': BALLOON['alt0']}
        self.datacollector = DataCollectorThread(self.handle_aprs_data,
                                                 self.handle_gps_data)
        self.model_data = None
        libfap.fap_init()
        try:
            self.datafile = open(PARAMETERS['data_file'], 'w')
            self.rawfile = open(PARAMETERS['raw_file'], 'w')
        except IOError:
            pass

    def exit(self):
        """Dispose thread"""
        self._running = False
        self.datacollector.exit()
        self.datacollector.join()
        libfap.fap_cleanup()
        try:
            self.rawfile.close()
            self.datafile.close()
        except IOError:
            print "IO error"

    def is_active(self):
        """Check if thread is active"""
        return self._running

    def _init_simulation(self):
        """Initialise pyBalloon simulation"""
        self.loc0 = (BALLOON['lat0'],
                     BALLOON['lon0'],
                     BALLOON['alt0'])
        self.loc['lat'] = BALLOON['lat0']
        self.loc['lon'] = BALLOON['lon0']
        self.loc['alt'] = BALLOON['alt0']
        self.model_data = pyBalloon.pyb_io.read_gfs_set(PARAMETERS['gfs_dir'],
                            (PARAMETERS['lat0']+1.5, PARAMETERS['lon0']-1.5,
                            PARAMETERS['lat0']-1.5, PARAMETERS['lon0']+1.5))

    def run(self):
        """Run thread"""
        print '', self.name, 'started.'
        if PARAMETERS['simulate']:
            self._init_simulation()
        self._running = True
        self.time0 = time.time()
        old_size = 0
        if not self.datacollector.is_alive():
            self.datacollector = DataCollectorThread(self.handle_aprs_data,
                                                     self.handle_gps_data)
        self.datacollector.start()
        while self._running:
            self.lock.acquire()
            # check if we have new data
            if len(LIVE_DATA['timestamps']) > old_size:
                if PARAMETERS['simulate']:
                    self._update_trajectories()
                self.master.update_data()
                old_size = len(LIVE_DATA['timestamps'])
            self.lock.release()
            time.sleep(PARAMETERS['update_interval'])
        print '', self.name, 'ended.'

    def handle_aprs_data(self, tnc2_frame):
        """Handle APRS data from data collector thread"""
        #print "handle new aprs data"
        packet = libfap.fap_parseaprs(tnc2_frame, len(tnc2_frame), 0)
        # handle location data
        if packet[0].type[0] == fapLOCATION.value:
            if packet[0].src_callsign == PARAMETERS['callsign']:
                self.lock.acquire()
                if PARAMETERS['aprs_source'] == FILE:
                    if len(LIVE_DATA['timestamps']) == 0:
                        self.time0 = packet[0].timestamp[0]
                    LIVE_DATA['timestamps'].append(packet[0].timestamp[0] - \
                                                   self.time0)
                else:
                    LIVE_DATA['timestamps'].append(time.time() - self.time0)
                LIVE_DATA['lats'].append(packet[0].latitude[0])
                LIVE_DATA['lons'].append(packet[0].longitude[0])
                LIVE_DATA['altitudes'].append(packet[0].altitude[0])
                #FIXME temperatures
                LIVE_DATA['temperatures'].append(0)
                if len(LIVE_DATA['timestamps']) > 1:
                    horizontal = distance(LIVE_DATA['lats'][-2],
                                          LIVE_DATA['lons'][-2],
                                          LIVE_DATA['lats'][-1],
                                          LIVE_DATA['lons'][-1]) / \
                                          (LIVE_DATA['timestamps'][-1] - \
                                           LIVE_DATA['timestamps'][-2])
                    vertical = (LIVE_DATA['altitudes'][-1] - \
                                LIVE_DATA['altitudes'][-2]) / \
                                (LIVE_DATA['timestamps'][-1] - \
                                LIVE_DATA['timestamps'][-2])
                    LIVE_DATA['horizontal_speed'].append(horizontal)
                    LIVE_DATA['vertical_speed'].append(vertical)
                    if len(LIVE_DATA['timestamps']) == 2:
                        LIVE_DATA['horizontal_speed'][0] = horizontal
                        LIVE_DATA['vertical_speed'][0] = vertical
                else:
                    LIVE_DATA['horizontal_speed'].append(0)
                    LIVE_DATA['vertical_speed'].append(0)
                #
                # are these always available? what else?
                # dynamic selection?
                #
                #np.append(LIVE_DATA['pressures'],
                #          packet[0].wx_report.pressure)
                #np.append(LIVE_DATA['temperatures'],
                #          packet[0].wx_report.temp)
                try:
                    self.rawfile.write(''.join([tnc2_frame, '\n']))
                    self.datafile.write(''.join([str(time.time()-self.time0),
                                        ',', str(packet[0].latitude[0]),
                                        ',', str(packet[0].longitude[0]),
                                        ',', str(packet[0].altitude[0]),
                                        #FIXME extra data
                                        #packet[0].wx_report.pressure,
                                        #',', packet[0].wx_report.temp,
                                        '\n']))
                except IOError:
                    print "IO error"
                self.lock.release()
        libfap.fap_free(packet)

    def handle_gps_data(self, nmea_sentence):
        """Handle GPS data from data collector thread"""
        print "handle new gps data"
        nmea = pynmea2.NMEASentence.parse(nmea_sentence)
        # handle location data
        if nmea.sentence_type == pynmea2.GGA:
            if nmea['gps_qual'] != 0:
                print "location obtained", nmea['lat'], \
                      ",", nmea['lon'], " @", nmea['altitude']
                self.lock.acquire()
                self.loc['lat'] = nmea['lat']
                self.loc['lon'] = nmea['lon']
                self.loc['alt'] = nmea['altitude']
                self.lock.release()

    def _calculate_trajectories(self):
        """Calculate estimated trajectories using pyBalloon"""
        print "calculate initial trajectories"
        trajectories = []
        for data in self.model_data:
            trajectories.append(pyBalloon.pyb_traj.calc_movements(data,
                                self.loc0, BALLOON))
        pyBalloon.pyb_io.save_kml(PARAMETERS['kml_fname'], trajectories)

    def _update_trajectories(self):
        """Calculate estimated trajectories using\
           pyBalloon using collected data"""
        print "update trajectories"
        trajectories = []
        for data in self.model_data:
            trajectories.append(pyBalloon.pyb_traj.calc_movements(data,
                                self.loc0, BALLOON,
                                live_data=LIVE_DATA))
        pyBalloon.pyb_io.save_kml(PARAMETERS['kml_fname'], trajectories)

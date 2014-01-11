#! /usr/bin/python
"""Balloon tracker"""
import sys
import os
from collections import OrderedDict
import aprs_daemon

from PyQt4 import QtGui, QtCore
from PyQt4 import QtWebKit
from PyQt4.QtWebKit import QWebPage
import PyQt4.Qwt5 as Qwt

from matplotlib import rcParams
from mpl_toolkits.axes_grid1 import host_subplot
import mpl_toolkits.axisartist as aa
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg\
                                            as FigureCanvas
#from matplotlib.backends.backend_qt4agg import NavigationToolbar2QTAgg\
#                                                as NavigationToolbar

DATA_LABELS = [
    'timestamps', 'Time',
    'lats', 'Latitude',
    'lons', 'Longitude',
    'pressures', 'Pressure (hPa)',
    'altitudes', 'Altitude (m)',
    'temperatures', u'Temperature (\u00b0C)',#$^\circ$
    'vertical_speed', 'Vertical speed (m/s)',
    'horizontal_speed', 'Horizontal speed (m/s)',
]

# key, title, type, num parameters=0, parameters...
PARAMETER_SETTINGS = OrderedDict([
    ('aprs_source',                 ["APRS source",                   "selectint", 3, "SDR", 0, "RS232", 1, "File", 2]),
    ('aprs_file',                   ["APRS file",                     "string"]),
    ('update_interval',             ["Update interval (s)",           "int"]),
    ('callsign',                    ["Callsign",                      "string"]),
    ('sdr_freq',                    ["SDR frequency (MHz)",           "double"]),
    ('sdr_rate',                    ["SDR sample rate (Hz)",          "int"]),
    ('sdr_gain',                    ["SDR gain",                      "int"]),
    ('sdr_serial_port',             ["SDR Serial port",               "int"]),
    ('sdr_serial_rate',             ["SDR Serial baudrate",           "int"]),
    ('sdr_serial_bytesize',         ["SDR Serial bytesize",           "selectint", 4, "5", 5, "6", 6, "7", 7, "8", 8]),
    ('sdr_serial_parity',           ["SDR Serial parity",             "selectstring", 5, "None", 'N', "Even", 'E', "Odd", 'O',\
                                                                                     "Mark", 'M', "Space", 'S']),
    ('sdr_serial_stopbits',         ["SDR Serial stopbits",           "selectint", 3, "1", 1, "1.5", 1.5, "2", 2]),
    ('sdr_serial_timeout',          ["SDR Serial timeout",            "int"]),
    ('sdr_serial_xonxoff',          ["SDR Serial XONXOFF",            "bool"]),
    ('sdr_serial_rtscts',           ["SDR Serial rtscts",             "bool"]),
    ('sdr_serial_writetimeout',     ["SDR Serial write timeout",      "int"]),
    ('sdr_serial_dsrdtr',           ["SDR Serial DSRDTS",             "bool"]),
    ('sdr_serial_interchartimeout', ["SDR Serial inter char timeout", "int"]),
    ('raw_file',                    ["Raw data file",                 "string"]),
    ('data_file',                   ["Parsed data file",              "string"]),
    ('simulate',                    ["Simulate trajectory",           "bool"]),
    ('gfs_dir',                     ["GFS directory",                 "string"]),
    ('kml_file',                    ["KML file",                      "string"]),
    ('gps',                         ["Enable GPS",                    "bool"]),
    ('gps_serial_port',             ["GPS Serial port",               "int"]),
    ('gps_serial_rate',             ["GPS Serial baudrate",           "int"]),
    ('gps_serial_bytesize',         ["GPS Serial bytesize",           "selectint", 4, "5", 5, "6", 6, "7", 7, "8", 8]),
    ('gps_serial_parity',           ["GPS Serial parity",             "selectstring", 5, "None", 'N', "Even", 'E', "Odd", 'O',\
                                                                                     "Mark", 'M', "Space", 'S']),
    ('gps_serial_stopbits',         ["GPS Serial stopbits",           "selectint", 3, "1", 1, "1.5", 1.5, "2", 2]),
    ('gps_serial_timeout',          ["GPS Serial timeout",            "int"]),
    ('gps_serial_xonxoff',          ["GPS Serial XONXOFF",            "bool"]),
    ('gps_serial_rtscts',           ["GPS Serial rtscts",             "bool"]),
    ('gps_serial_writetimeout',     ["GPS Serial write timeout",      "int"]),
    ('gps_serial_dsrdtr',           ["GPS Serial DSRDTS",             "bool"]),
    ('gps_serial_interchartimeout', ["GPS Serial inter char timeout", "int"])
])

BALLOON_SETTINGS = OrderedDict([
    ('lat0',                      ["Latitude (deg)",                "double"]),
    ('lon0',                      ["Longitude (deg)",               "double"]),
    ('alt0',                      ["Altitude (m)",                  "double"]),
    ('altitude_step',             ["Altitude step (m)",             "double"]),
    ('equip_mass',                ["Equipment mass (kg)",           "double"]),
    ('balloon_mass',              ["Balloon mass (kg)",             "double"]),
    ('fill_radius',               ["Fill radius (m)",               "double"]),
    ('radius_empty',              ["Empty radius (m)",              "double"]),
    ('burst_radius',              ["Burst radius (m)",              "double"]),
    ('thickness_empty',           ["Empty thickness (mm)",          "double"]),
    ('Cd_balloon',                ["Cd balloon",                    "double"]),
    ('Cd_parachute',              ["Cd parachute",                  "double"]),
    ('parachute_areas',           ["Parachute areas (m^2)",         "string"]),
    ("parachute_change_altitude", ["Parachute change altitude (m)", "double"])
])

class SettingsDialog(QtGui.QDialog):
    """GUI for handling settings"""
    def __init__(self, parent, title, params, param_conf):
        """Initialise dialog"""
        QtGui.QDialog.__init__(self, parent)
        self.params = params
        self.param_conf = param_conf
        self.title = title
        self.setObjectName("Settings")
        self.setWindowTitle("Settings")
        self.resize(640, 480)
        sizepol = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,
                                    QtGui.QSizePolicy.Expanding)
        sizepol.setHorizontalStretch(0)
        sizepol.setVerticalStretch(0)
        sizepol.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizepol)
        mainlayout = QtGui.QVBoxLayout(self)
        mainlayout.setObjectName("mainlayout")

        self.settings = {}
        settingsarea = QtGui.QScrollArea()
        settingsarea.setWidget(self.create_settings())
        mainlayout.addWidget(settingsarea)

        buttonbox = QtGui.QDialogButtonBox(self)
        buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|
                                     QtGui.QDialogButtonBox.Ok)
        buttonbox.setObjectName("buttonbox")
        mainlayout.addWidget(buttonbox)

        QtCore.QObject.connect(buttonbox, QtCore.SIGNAL("accepted()"),
                               self._accept)
        QtCore.QObject.connect(buttonbox, QtCore.SIGNAL("rejected()"),
                               self._reject)
        QtCore.QMetaObject.connectSlotsByName(self)

    def create_settings(self):
        """Create settings frame"""
        settingsframe = QtGui.QFrame(self)
        sizepol = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,
                                    QtGui.QSizePolicy.Expanding)
        sizepol.setHorizontalStretch(0)
        sizepol.setVerticalStretch(0)
        sizepol.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        settingsframe.setSizePolicy(sizepol)
        settingsframe.setObjectName("settingsframe")
        settingslayout = QtGui.QFormLayout(settingsframe)
        settingslayout.setObjectName("settingslayout")
        settingslayout.setSpacing(0)
        settingslayout.setMargin(0)

        # add parameter_settings
        intvalidator = QtGui.QIntValidator()
        doublevalidator = QtGui.QDoubleValidator()
        for key in self.param_conf:
            if self.param_conf[key][1] == "string" or \
               self.param_conf[key][1] == "double" or \
               self.param_conf[key][1] == "int":
                self.settings[key] = QtGui.QLineEdit(self)
                if self.param_conf[key][1] == "double":
                    self.settings[key].setValidator(doublevalidator)
                elif self.param_conf[key][1] == "int":
                    self.settings[key].setValidator(intvalidator)
                if self.param_conf[key][1] == "int" and \
                   self.params[key] is None:
                    self.settings[key].setText('-1')
                else:
                    self.settings[key].setText(str(self.params[key]))
            elif self.param_conf[key][1] == "selectint" or \
                 self.param_conf[key][1] == "selectstring":
                self.settings[key] = QtGui.QComboBox(self)
                for item in range(0, self.param_conf[key][2]):
                    self.settings[key].addItem(self.param_conf[key][3+2*item])
                    if self.params[key] == self.param_conf[key][4+2*item]:
                        self.settings[key].setCurrentIndex(item)
            elif self.param_conf[key][1] == "bool":
                self.settings[key] = QtGui.QCheckBox(self)
                self.settings[key].setTristate(self.params[key])
            self.settings[key].setObjectName(key)
            settingslayout.addRow(self.param_conf[key][0], self.settings[key])
        return settingsframe

    def _accept(self):
        """Store all settings to global variables"""
        for key in self.param_conf:
            if self.param_conf[key][1] == "string" or\
               self.param_conf[key][1] == "double" or\
               self.param_conf[key][1] == "int":
                if self.param_conf[key][1] == "int":
                    if self.settings[key].text() == '-1':
                        self.params[key] = None
                    else:
                        self.params[key] = int(self.settings[key].text())
                elif self.param_conf[key][1] == "double":
                    self.params[key] = float(self.settings[key].text())
                else:
                    self.params[key] = self.settings[key].text()
            elif self.param_conf[key][1] == "selectint":
                self.params[key] = int(self.param_conf[key][4+2*self.settings[key].currentIndex()])
            elif self.param_conf[key][1] == "selectstring":
                self.params[key] = self.param_conf[key][4+2*self.settings[key].currentIndex()]
            elif self.param_conf[key][1] == "bool":
                self.params[key] = self.settings[key].isChecked()
        self.accept()

    def _reject(self):
        """Dicard all modified settings"""
        self.reject()

class MainWindow(QtGui.QMainWindow):
    """Balloon tracker main window"""
    updatetrigger = QtCore.pyqtSignal()
    def __init__(self):
        """Initialise main window"""
        super(MainWindow, self).__init__()
        # Create data handler (creates also data collector)
        self.datahandler = aprs_daemon.DataHandlerThread(self)
        self.setWindowTitle("Balloon Tracker")
        self.setObjectName("mainwindow")
        self.resize(800, 600)
        centralwidget = QtGui.QWidget(self)
        self.updatetrigger.connect(self._update_all)
        sizepol = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,
                                    QtGui.QSizePolicy.Expanding)
        sizepol.setHorizontalStretch(0)
        sizepol.setVerticalStretch(0)
        sizepol.setHeightForWidth(centralwidget.sizePolicy().hasHeightForWidth())
        centralwidget.setSizePolicy(sizepol)
        centralwidget.setObjectName("centralwidget")
        mainlayout = QtGui.QHBoxLayout(centralwidget)
        mainlayout.setMargin(0)
        mainlayout.setObjectName("mainlayout")
        gridlayout = QtGui.QGridLayout()
        gridlayout.setSizeConstraint(QtGui.QLayout.SetNoConstraint)
        gridlayout.setSpacing(0)
        gridlayout.setObjectName("gridlayout")
        # compass area
        self.compass = None
        self.distancelabel = None
        gridlayout.addWidget(self.create_compass(centralwidget), 1, 1, 1, 1)
        # data area
        self.items = []
        gridlayout.addWidget(self.create_dataframe(centralwidget), 0, 1, 1, 1)
        # plot area
        self.canvas = None
        self.plots = []
        self.axes = []
        gridlayout.addWidget(self.create_plot(centralwidget), 1, 0, 1, 1)
        #map area
        self.webview = None
        self.create_map(centralwidget)
        gridlayout.addWidget(self.webview, 0, 0, 1, 1)
        mainlayout.addLayout(gridlayout)
        self.setCentralWidget(centralwidget)
        #menubar
        self.startstop = None
        self.setMenuBar(self.create_menubar())
        #statusbar
        self.statusbar = QtGui.QStatusBar(self)
        self.statusbar.setObjectName("statusbar")
        self.setStatusBar(self.statusbar)
        #toolbar
        #self.toolBar = QtGui.QToolBar(self)
        #self.toolBar.setObjectName("toolBar")
        #self.addToolBar(QtCore.Qt.TopToolBarArea, self.toolBar)


    def create_compass(self, parent):
        """Create compass area"""
        compassframe = QtGui.QFrame(parent)
        compassframe.setAutoFillBackground(False)
        #compassframe.setStyleSheet("background-color: rgb(255, 255, 255);")
        #  compassframe.setFrameShape(QtGui.QFrame.StyledPanel)
        #  compassframe.setFrameShadow(QtGui.QFrame.Raised)
        compassframe.setObjectName("compassframe")
        compasslayout = QtGui.QVBoxLayout(compassframe)
        compasslayout.setMargin(0)
        compasslayout.setObjectName("compasslayout")

        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Base, QtCore.Qt.darkBlue)
        palette.setColor(QtGui.QPalette.Foreground,
                         QtGui.QColor(QtCore.Qt.darkBlue).dark(120))
        palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
        self.compass = Qwt.QwtCompass()
        self.compass.setLineWidth(4)
        self.compass.setScaleTicks(1, 1, 3)
        self.compass.setScale(36, 5, 0)
        self.compass.setReadOnly(True)
        self.compass.setNeedle(Qwt.QwtCompassMagnetNeedle(
                               Qwt.QwtCompassMagnetNeedle.ThinStyle))
        self.compass.setValue(0.0)
        compasslayout.addWidget(self.compass)
        self.distancelabel = QtGui.QLabel("NA")
        self.distancelabel.setAlignment(QtCore.Qt.AlignCenter)
        compasslayout.addWidget(self.distancelabel)
        return compassframe

    def create_dataframe(self, parent):
        """Create data frame"""
        dataframe = QtGui.QFrame(parent)
        sizepol = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed,
                                    QtGui.QSizePolicy.Expanding)
        sizepol.setHorizontalStretch(0)
        sizepol.setVerticalStretch(0)
        sizepol.setHeightForWidth(dataframe.sizePolicy().hasHeightForWidth())
        dataframe.setSizePolicy(sizepol)
        dataframe.setMinimumSize(QtCore.QSize(200, 0))
        #  dataframe.setFrameShape(QtGui.QFrame.StyledPanel)
        #  dataframe.setFrameShadow(QtGui.QFrame.Raised)
        dataframe.setObjectName("dataframe")
        datalayout = QtGui.QVBoxLayout(dataframe)
        datalayout.setMargin(0)
        datalayout.setObjectName("datalayout")
        treewidget = QtGui.QTreeWidget()
        treewidget.setColumnCount(2)
        treewidget.setIndentation(0)
        treewidget.setAlternatingRowColors(1)
        treewidget.header().hide()
        for row in range(len(DATA_LABELS)/2):
            self.items.append(QtGui.QTreeWidgetItem(treewidget,
                              [DATA_LABELS[1+2*row], '']))
        treewidget.resizeColumnToContents(0)
        treewidget.resizeColumnToContents(1)
        treewidget.insertTopLevelItems(0, self.items)
        datalayout.addWidget(treewidget)
        return dataframe

    def create_menubar(self):
        """Create menu bar"""
        menubar = QtGui.QMenuBar(self)
        menubar.setObjectName("menubar")
        menu_file = QtGui.QMenu("&File", menubar)
        menu_file.setObjectName("menuFile")
        menu_operation = QtGui.QMenu("&Operation", menubar)
        menu_operation.setObjectName("menuOperation")
        menu_help = QtGui.QMenu("&Help", menubar)
        menu_help.setObjectName("menuHelp")
        menu_settings = QtGui.QMenu("&Settings", menubar)
        menu_settings.setObjectName("menuSettings")
        #actions
        new_session = QtGui.QAction("&New Session", self)
        new_session.setIconVisibleInMenu(False)
        new_session.setObjectName("new_session")
        open_session = QtGui.QAction("&Open Session", self)
        open_session.setObjectName("open_session")
        save_session = QtGui.QAction("&Save Session", self)
        save_session.setObjectName("save_session")
        exit_program = QtGui.QAction("&Exit", self)
        exit_program.setObjectName("exit")
        self.startstop = QtGui.QAction("&Start", self)
        self.startstop.setObjectName("startstop")
        general_settings = QtGui.QAction("&General", self)
        general_settings.setObjectName("general_settings")
        balloon_settings = QtGui.QAction("&Balloon", self)
        balloon_settings.setObjectName("balloon_settings")
        help_window = QtGui.QAction("&Help", self)
        help_window.setObjectName("help")
        about = QtGui.QAction("&About", self)
        about.setObjectName("about")
        #menu content
        menu_file.addAction(new_session)
        menu_file.addAction(open_session)
        menu_file.addAction(save_session)
        menu_file.addSeparator()
        menu_file.addAction(exit_program)
        menu_operation.addAction(self.startstop)
        menu_help.addAction(help_window)
        menu_help.addSeparator()
        menu_help.addAction(about)
        menu_settings.addSeparator()
        menu_settings.addAction(general_settings)
        menu_settings.addAction(balloon_settings)
        menubar.addAction(menu_file.menuAction())
        menubar.addAction(menu_operation.menuAction())
        menubar.addAction(menu_settings.menuAction())
        menubar.addAction(menu_help.menuAction())
        #self.toolbar.addSeparator()
        #self.toolbar.addAction(self.startstop)

        QtCore.QObject.connect(new_session,
                QtCore.SIGNAL("triggered()"), self._new_session)
        QtCore.QObject.connect(open_session,
                QtCore.SIGNAL("triggered()"), self._open_session)
        QtCore.QObject.connect(save_session,
                QtCore.SIGNAL("triggered()"), self._save_session)
        QtCore.QObject.connect(exit_program,
                QtCore.SIGNAL("triggered()"), self._exit)
        QtCore.QObject.connect(self.startstop,
                QtCore.SIGNAL("triggered()"), self._startstop)
        QtCore.QObject.connect(general_settings,
                QtCore.SIGNAL("triggered()"), self._general_settings)
        QtCore.QObject.connect(balloon_settings,
                QtCore.SIGNAL("triggered()"), self._balloon_settings)
        QtCore.QObject.connect(help_window,
                QtCore.SIGNAL("triggered()"), self._help)
        QtCore.QObject.connect(about,
                QtCore.SIGNAL("triggered()"), self._about)
        QtCore.QMetaObject.connectSlotsByName(self)
        #self.toolBar.setWindowTitle("toolBar")
        return menubar

    def create_plot(self, parent):
        """Create plot area"""
        plotframe = QtGui.QFrame(parent)
        sizepol = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,
                                    QtGui.QSizePolicy.Fixed)
        sizepol.setHorizontalStretch(0)
        sizepol.setVerticalStretch(0)
        sizepol.setHeightForWidth(plotframe.sizePolicy().hasHeightForWidth())
        plotframe.setSizePolicy(sizepol)
        plotframe.setMinimumSize(QtCore.QSize(0, 200))
        plotframe.setMaximumSize(QtCore.QSize(1980, 200))
        #  plotframe.setFrameShape(QtGui.QFrame.StyledPanel)
        #  plotframe.setFrameShadow(QtGui.QFrame.Raised)
        plotframe.setObjectName("plotframe")
        plotlayout = QtGui.QVBoxLayout(plotframe)
        plotlayout.setMargin(0)
        plotlayout.setObjectName("plotlayout")
        fig = plt.figure(dpi=100)#, frameon=False figsize=(20, 4), 
        fig.patch.set_facecolor('white')
        rcParams['axes.color_cycle'] = ['k', 'b', 'g', 'r']
        self.canvas = FigureCanvas(fig)
        self.axes.append(host_subplot(111, axes_class=aa.Axes))
        self.axes[0].set_xlabel("Time")
        self.axes[0].set_ylabel("Altitude")
        self.axes[0].set_aspect('auto', 'datalim') 
        self.plots.append(self.axes[0].plot(aprs_daemon.LIVE_DATA['timestamps'],
                           aprs_daemon.LIVE_DATA['altitudes'])[0])
        fig.add_axes(self.axes[0])
        self.axes[0].axis["left"].label.set_color(self.plots[0].get_color())
        self.axes[0].tick_params(axis='y', color=self.plots[0].get_color())
        for row in range(5, len(DATA_LABELS)/2):
            if row % 2 == 0:
                side = "left"
                offset = -1
            else:
                side = "right"
                offset = 1
            self.axes.append(self.axes[0].twinx())
            self.axes[row-4].axis["right"].set_visible(False)
            new_fixed_axis =  self.axes[row-4].get_grid_helper().new_fixed_axis
            self.axes[row-4].axis[side] = new_fixed_axis(loc=side, axes=self.axes[row-4],
                        offset=(offset*(60*((row-5)%2+(row-5)/2)), 0))

            self.axes[row-4].axis[side].label.set_visible(True)
            self.axes[row-4].axis[side].set_label(DATA_LABELS[2*row+1])
            self.plots.append(self.axes[row-4].plot(aprs_daemon.LIVE_DATA['timestamps'],
                        aprs_daemon.LIVE_DATA[DATA_LABELS[2*row]])[0])

            self.axes[row-4].axis[side].label.set_color(self.plots[row-4].get_color())
            self.axes[row-4].set_aspect('auto', 'datalim') 
            self.axes[row-4].tick_params(axis='y',
                            colors=self.plots[row-4].get_color())
        plt.subplots_adjust(bottom=0.3, left=0.20, right=0.8, top=0.85)
        fig.tight_layout()
        self.canvas.setParent(plotframe)
        self.canvas.setStyleSheet("background-color: rgb(255, 0, 255);")
        self.canvas.draw()
        plotlayout.addWidget(self.canvas)
        return plotframe

    def create_map(self, parent):
        """Create maps widget"""
        self.webview = QtWebKit.QWebView(parent)
        sizepol = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,
                                    QtGui.QSizePolicy.Expanding)
        sizepol.setHorizontalStretch(0)
        sizepol.setVerticalStretch(0)
        sizepol.setHeightForWidth(self.webview.sizePolicy().hasHeightForWidth())
        self.webview.setPage(WebPage(self.webview))
        self.webview.setSizePolicy(sizepol)
        self.webview.setAutoFillBackground(False)
        self.webview.setObjectName("webview")
        self.webview.load(QtCore.QUrl.fromLocalFile(os.path.dirname(os.path.realpath(__file__)) + "/gmap_openlayers.html"))
        self.webview.show()

    def _about(self):
        """Show information about program"""
        QtGui.QMessageBox.about(self, "About Balloon Tracker",
                                "Balloon Tracker is a program.")

    def _help(self):
        """Show help for program"""
        QtGui.QMessageBox.about(self, "About Balloon Tracker",
                                "Balloon Tracker is a program.")

    def _general_settings(self):
        """Show dialog for modifying general program settings"""
        dialog = SettingsDialog(self, "General settings",
                                aprs_daemon.PARAMETERS,
                                PARAMETER_SETTINGS)
        dialog.exec_()

    def _balloon_settings(self):
        """Show dialog for modifying balloon related settings"""
        dialog = SettingsDialog(self, "Balloon settings",
                                aprs_daemon.BALLOON, BALLOON_SETTINGS)
        dialog.exec_()

    def _update_current_data(self):
        """Update current data and compass"""
        for row in range(len(DATA_LABELS)/2):
            if len(aprs_daemon.LIVE_DATA[DATA_LABELS[2*row]]) > 0:
                self.items[row].setText(1,
                    str(round(aprs_daemon.LIVE_DATA[DATA_LABELS[2*row]][-1], 2)))
        lat0 = self.datahandler.loc['lat']
        lon0 = self.datahandler.loc['lon']
        lat1 = aprs_daemon.LIVE_DATA['lats'][-1]
        lon1 = aprs_daemon.LIVE_DATA['lons'][-1]
        self.compass.setValue(aprs_daemon.direction(lat0, lon0, lat1, lon1))
        self.distancelabel.setText(''.join([str(int(aprs_daemon.distance(lat0, lon0, lat1, lon1))), ' m']))

    def _update_dataplot(self):
        """Update data plot"""
        for row in range(4, len(DATA_LABELS)/2):
            self.plots[row-4].set_data(aprs_daemon.LIVE_DATA['timestamps'],
                    aprs_daemon.LIVE_DATA[DATA_LABELS[2*row]])
            
            self.axes[row-4].relim()
            self.axes[row-4].autoscale_view()
        self.canvas.draw()

    def _update_map(self):
        """Update map"""
        #FIXME follow current location or balloon?
        string = "setCenter(%s, %s);\naddPosition(%s, %s);" % \
                 (str(aprs_daemon.LIVE_DATA['lats'][-1]),
                 str(aprs_daemon.LIVE_DATA['lons'][-1]),
                 str(self.datahandler.loc['lat']),
                 str(self.datahandler.loc['lon']))
        self.webview.page().mainFrame().evaluateJavaScript(string)
        #update tracks
        string = "addNode(%s, %s);" % (str(aprs_daemon.LIVE_DATA['lats'][-1]),
                 str(aprs_daemon.LIVE_DATA['lons'][-1]))
        self.webview.page().mainFrame().evaluateJavaScript(string)

    def _update_all(self):
        """Update all data in window"""
        self._update_current_data()
        self._update_dataplot()
        self._update_map()

    def update_data(self):
        """Trigger data update"""
        self.updatetrigger.emit()

    def _startstop(self):
        """Start collecting and processing data"""
        if self.datahandler.is_active():
            self.startstop.setText("&Start")
            self.datahandler.exit()
            self.datahandler.join()
        else:
            self.startstop.setText("&Stop")
            string = "cleanUpMarkers(0);\naddKML(%s);\n\
                     setCenter(%s, %s);\naddPosition(%s, %s);\n\
                     addPosition(%s, %s);" % \
                     (aprs_daemon.PARAMETERS['kml_file'],
                     str(aprs_daemon.BALLOON['lat0']),
                     str(aprs_daemon.BALLOON['lon0']),
                     str(aprs_daemon.BALLOON['lat0']),
                     str(aprs_daemon.BALLOON['lon0']),
                     str(self.datahandler.loc['lat']),
                     str(self.datahandler.loc['lon']))
            self.webview.page().mainFrame().evaluateJavaScript(string)
            if not self.datahandler.is_alive():
                self.datahandler = aprs_daemon.DataHandlerThread(self)
            self.datahandler.start()

    def closeEvent(self, event):
        """Handle window close event"""
        self._exit()

    def _exit(self):
        """Verify exiting program"""
        if QtGui.QMessageBox.question(self, 'Quit',
           "Do you really want to quit?", QtGui.QMessageBox.Yes,
           QtGui.QMessageBox.No) == QtGui.QMessageBox.Yes:
            if self.datahandler.is_active():
                self.datahandler.exit()
                self.datahandler.join()
            QtCore.QCoreApplication.instance().quit()

    def _new_session(self):
        """Load default session settings"""
        self._open_session('default.ucl')

    def _open_session(self, fname=''):
        """Load stored session settings"""
        if fname == '':
            fname = QtGui.QFileDialog.getOpenFileName(self, 'Open session',
                        '/home', 'Session files (*.ucl)')
        if fname:
            try:
                filep = open(fname, 'r')
                for line in filep:
                    line = line.strip('\n')
                    if line == "##GENERAL##":
                        params = aprs_daemon.PARAMETERS
                        param_conf = PARAMETER_SETTINGS
                    elif line == "##BALLOON##":
                        params = aprs_daemon.BALLOON
                        param_conf = BALLOON_SETTINGS
                    elif line != "":
                        content = line.split('\t')
                        if param_conf[content[0]][1] == "double":
                            params[content[0]] =  float(content[1])
                        elif param_conf[content[0]][1] == "int" or \
                             param_conf[content[0]][1] == "selectint":
                            if param_conf[content[0]][1] == "int" and \
                               content[1] == '-1':
                                params[content[0]] = None
                            else:
                                params[content[0]] = int(content[1])
                        elif param_conf[content[0]][1] == "bool":
                            params[content[0]] = bool(int(content[1]))
                        else:
                            params[content[0]] = content[1]
                filep.close()
            except IOError:
                print "IOError"
            except ValueError:
                print "ValueError"
            except TypeError:
                print "TypeError"

    def _save_session(self):
        """Save current session settings"""
        fname = QtGui.QFileDialog.getSaveFileName(self,
                "Save session", "/home", "Session files (*.ucl)")
        if fname:
            try:
                filep = open(fname, 'w')
                filep.write('##GENERAL##\n')
                for key in PARAMETER_SETTINGS.keys():
                    if PARAMETER_SETTINGS[key][1] == "bool":
                        filep.write(''.join([key, '\t',
                                str(int(aprs_daemon.PARAMETERS[key])), '\n']))
                    elif PARAMETER_SETTINGS[key][1] == "int" and \
                         aprs_daemon.PARAMETERS[key] is None:
                        filep.write(''.join([key, '\t-1\n']))
                    else:
                        filep.write(''.join([key, '\t',
                                    str(aprs_daemon.PARAMETERS[key]), '\n']))
                filep.write('##BALLOON##\n')
                for key in BALLOON_SETTINGS.keys():
                    if BALLOON_SETTINGS[key][1] == "bool":
                        filep.write(''.join([key, '\t',
                                    str(int(aprs_daemon.BALLOON[key])), '\n']))
                    elif BALLOON_SETTINGS[key][1] == "int" and \
                         aprs_daemon.BALLOON[key] is None:
                        filep.write(''.join([key, '\t-1\n']))
                    else:
                        filep.write(''.join([key, '\t',
                                    str(aprs_daemon.BALLOON[key]), '\n']))
                filep.close()
            except IOError:
                print "IO error"



class WebPage(QWebPage):
    """
    Print out javascript console messages
    """
    def javaScriptConsoleMessage(self, msg, lineNumber, sourceID):
        print("JsConsole(%s:%d): %s" % (sourceID, lineNumber, msg))



def main():
    """Start GUI for Balloon tracker"""
    root = QtGui.QApplication(sys.argv)
    app = MainWindow()
    app.show()
    sys.exit(root.exec_())

if __name__ == "__main__":
    main()

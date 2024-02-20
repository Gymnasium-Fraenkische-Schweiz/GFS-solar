import hassapi as hass
import time
import urllib.request
import urllib.error
from datetime import datetime
from enum import Enum



#
# App implementing the GFS_cPVman Application
#############################################
#
# https://github.com/ReneTode/My-AppDaemon/tree/master/AppDaemon_for_Beginner
#
#
# Simple Version:
#
# We have 2 hardware items:
# - Endity: 
#      counter.gfs_cdummymeter
#
# Device: GFS_CSWITCHF01
# - Endity:
#      switch.gfs_cswitchf01
# - Sensor
#      sensor.gfs_cswitchf01_energy_apparentpower
#      sensor.gfs_cswitchf01_energy_current
#      sensor.gfs_cswitchf01_energy_factor
#      sensor.gfs_cswitchf01_energy_power
#      sensor.gfs_cswitchf01_energy_reactivepower
#      sensor.gfs_cswitchf01_energy_today
#      sensor.gfs_cswitchf01_energy_total
#      sensor.gfs_cswitchf01_energy_totalstarttime
#      sensor.gfs_cswitchf01_energy_voltage
#      sensor.gfs_cswitchf01_energy_yesterday
#      sensor.gfs_cswitchf01_last_restart_time
#      sensor.gfs_cswitchf01_mqtt_connect_count
#      sensor.gfs_cswitchf01_restart_reason
#      sensor.gfs_cswitchf01_ssid
#      sensor.gfs_cswitchf01_wifi_connect_count
#      sensor.gfs_cswitchf01_firmware_version
#      sensor.gfs_cswitchf01_ip
#
#
# Beim Start: counter wird ausgelsen und in lokale variable geschrieben
# 
# Bei Änderung des Counters:
#    wenn counter > 2100 W
#       -> cswitchf01 wird eingeschaltet
#    wenn counter < 1000 W
#       -> cswitchf01 wird ausgeschaltet
# 
#
#Globale Variable: availablePower gibt die derzeit verfügbare Leistung an
#
# Version 1.0:
#   Initial Version




class cpvman(hass.Hass):
    
    class Color(Enum):
        RED = 1
        YELLOW = 2
        GREEN = 3

    class LedState(Enum):
        OFF = 0
        ON  = 1

    def initialize(self):
        # Lesen der Parmeter aus der apps.yaml Datei
        self.Simulation = self.args["Simulation"]
        self.SimulierteCLeistung = 0

        #Einrichten der Zeit
        time_now = datetime.now()
        self.current_time = time_now.strftime("%H")
        self.log(f'{self.current_time} Uhr und ein paar Zerquetschte ;D')

        #Letzte Überprüfung der Haushaltsgeräte
        self.last_hour = int(self.current_time)

        # Parameter für gfs_cswitchf01
        self.TriggerLevelForSwitchF_on = self.args['TriggerLevelForSwitchF_on']
        self.TriggerLevelForSwitchF_off = self.args['TriggerLevelForSwitchF_off']

        # Parameter für gfs_cswitchwb
        self.MinimalWbPower = self.args["MinimalWbPower"]

        # Parameter für gfs_cswitchc01
        self.MinimalCPower  = self.args["MinimalCPower"]
        self.TriggerLevelForSwitchC = self.args['TriggerLevelForSwitchC']
        self.TriggerIntervalStart = self.args['TriggerIntervalStart']
        self.TriggerIntervalEnd = self.args['TriggerIntervalEnd']
        self.TriggerAutoStart = self.args['TriggerAutoStart']
        

        # Definition der verfügbaren Leistung
        self.availablePower = 0

        # Remember the minute when the last selftest was performed
        self.lastMinute = time_now.minute

        # Variable for storing the selftest error
        self.hardwareErrorDetected = False

        #Avoids RFID trigger twice, for on and off
        self.rfidtimer=False

        # Aufruf der Initialisierungsfunktion
        self.initComponents()

        ###################################################
        # SECTION BEGIN for init of application
            
        #cSwitch Triggers only if one or more minutes overspill
        self.ctimer = False
        
        self.change_led_state(self.Color.YELLOW, self.LedState.ON)
            
        # SECTION END
        ###################################################


        



    # ACTUATORS
    def switch_on(self, entity):
        try:
            self.log("------------------------------")
            self.log(f'entity: {entity}')
            if (entity.exists()):
                entity.turn_on()
                self.log("switch_on()")
            else:
                self.log(f'entity does not exist')
            self.log("------------------------------")
        except Exception as e:
            self.log(f'an exception occurred {e}')

    def switch_off(self, entity):
        try:
            self.log("------------------------------")
            self.log(f'entity: {entity}')
            if (entity.exists()):
                entity.turn_off()
                self.log("switch_off()")
            else:
                self.log(f'entity does not exist')
            self.log("------------------------------")
        except Exception as e:
            self.log(f'an exception occurred {e}')

    def change_led_state(self, col, state):
        try:
            self.log("------------------------------")
            self.log(f'color: {col}')
            self.log(f'state: {state}')
            match col:
                case self.Color.YELLOW:
                    if state == self.LedState.ON:
                        self.turn_on("switch.gfs_cd1mini_wb_3_yellow")
                    else:
                        self.turn_off("switch.gfs_cd1mini_wb_3_yellow")
                case self.Color.GREEN:
                    if state == self.LedState.ON:
                        self.turn_on("switch.gfs_cd1mini_wb_2_green")
                    else:
                        self.turn_off("switch.gfs_cd1mini_wb_2_green")
                case self.Color.RED:
                    if state == self.LedState.ON:
                        self.turn_on("switch.gfs_cd1mini_wb_1_red")
                    else:
                        self.turn_off("switch.gfs_cd1mini_wb_1_red")
            self.log("------------------------------")
        except Exception as e:
            self.log(f'an exception occurred {e}')

    def beep(self, count):
        try:
            self.log("------------------------------")
            self.log(f'beep {count} times')
            i=0
            while (i < count):
                self.turn_on("switch.gfs_cd1mini_wb_4_buzzer")
                time.sleep(1)
                self.turn_off("switch.gfs_cd1mini_wb_4_buzzer")
                time.sleep(1)
                i+=1
            self.log("------------------------------")
        except Exception as e:
            self.log(f'an exception occurred {e}')

    # SENSORS
    def handle_entity_update_cb(self, entity, attribute, old, new, kwargs):
        try:
            self.log("    .................................")
            self.log(f'    Entity state change for {entity}')
            self.log(f'    attr:   {attribute}')
            self.log(f'    old:    {old}')
            self.log(f'    new:    {new}')
            self.log(f'    kwargs: {kwargs}')
            self.log("    .................................")


            match f'{entity}':
                case 'switch.gfs_cswitchf01':
                    self.handle_entry_update_switchf(attribute, old, new)
                case 'switch.gfs_cswitchc01':
                    self.handle_entry_update_switchc(attribute, old, new)
                case 'switch.gfs_cswitchwb':
                    self.handle_entry_update_switchwb(attribute, old, new)

                case 'sensor.config_d1_update':
                    self.handle_entry_update_rfid(attribute, old, new)

                case 'sensor.gfs_cmeter_haus_power':
                    old = int(old) * (-1)
                    new = int(new) * (-1)
                    self.handle_entry_update_meter(old, new)

                case 'counter.gfs_cdummymeter':
                    self.handle_entry_update_meter(old, new)

                case 'input_select.last_simulation':
                    self.handle_entry_update_used_devices_simulation(old, new)
                
                case 'input_boolean.rfid_simulation':
                    self.handle_entry_update_rfid_reader_simulation(old, new)

                case _:
                    self.log("entry could not be found")

        except Exception as e:
            self.log(f'an exception occurred {e}')


    def handle_entry_update_rfid_reader_simulation(self, old, new):
        try:
            self.log("    .................................")
            self.log(f'    Entity state change for simulate RFID')
            self.log(f'    old:     {old} ')
            self.log(f'    new:     {new} ')
            self.log("    .................................")

            if f'{new}' == "on":
                self.listen_state(self.handle_entity_update_cb, "input_boolean.rfid_simulation")
                self.turn_off("input_boolean.rfid_simulation")

                # simulate scanning of rfid card
                self.handle_entry_update_rfid('Simulation', old, new)


        except Exception as e:
            self.log(f'an exception occurred {e}')

    def handle_entry_update_used_devices_simulation(self, old, new):
        try:
            self.log("    .................................")
            self.log(f'    Entity state change for USED DEVICES')
            self.log(f'    old:     {old} ')
            self.log(f'    new:     {new} ')
            self.log("    .................................")

            match f'{new}':
                case 'WB:0,C:0':
                    SimulierteWbLeistung = 0
                    self.SimulierteCLeistung = 0
                case 'WB:0,C:1':
                    SimulierteWbLeistung = 0
                    self.SimulierteCLeistung = 2000
                case 'WB:1,C:0':
                    SimulierteWbLeistung = 2000
                    self.SimulierteCLeistung = 0
                case 'WB:1,C:1':
                    SimulierteWbLeistung = 2000
                    self.SimulierteCLeistung = 2000

                case _:
                    SimulierteWbLeistung = 0
                    self.SimulierteCLeistung = 0
            self.handle_entry_update_switchwb_power(0, SimulierteWbLeistung)
            self.handle_entry_update_switchc_power(0, self.SimulierteCLeistung)

        except Exception as e:
            self.log(f'an exception occurred {e}')




    def handle_entry_update_switchf(self, attribute, old, new):
        try:
            self.log("    .................................")
            self.log(f'    Entity state change for switchf')
            self.log(f'    attr:   {attribute}')
            self.log(f'    old:    {old}')
            self.log(f'    new:    {new}')
            self.log("    .................................")

            match f'{attribute}':
                case 'energy_power':
                    self.handle_entry_update_switchf_power( old, new)
                case 'state':
                    self.handle_entry_update_switchf_state( old, new)

                case _:
                    self.log("attrib could not be found")

        except Exception as e:
            self.log(f'an exception occurred {e}')

    def handle_entry_update_switchc(self, attribute, old, new):
        try:
            self.log("    .................................")
            self.log(f'    Entity state change for switchc')
            self.log(f'    attr:   {attribute}')
            self.log(f'    old:    {old}')
            self.log(f'    new:    {new}')
            self.log("    .................................")

            match f'{attribute}':
                case 'energy_power':
                    self.handle_entry_update_switchc_power( old, new)
                case 'state':
                    self.handle_entry_update_switchc_state( old, new)

                case _:
                    self.log("attrib could not be found")

        except Exception as e:
            self.log(f'an exception occurred {e}')

    def handle_entry_update_switchwb(self, attribute, old, new):
        try:
            self.log("    .................................")
            self.log(f'    Entity state change for switchwb')
            self.log(f'    attr:   {attribute}')
            self.log(f'    old:    {old}')
            self.log(f'    new:    {new}')
            self.log("    .................................")

            match f'{attribute}':
                case 'energy_power':
                    self.handle_entry_update_switchwb_power( old, new)
                case 'state':
                    self.handle_entry_update_switchwb_state( old, new)

                case _:
                    self.log("attrib could not be found")

        except Exception as e:
            self.log(f'an exception occurred {e}')

    def handle_2_s_timer_event_cb(self, kwargs):
        # Diese Nachricht kommt im Abstand von 2 s
        try:
            self.handle_minute_timer_event(kwargs)
            ###################################################
            # SECTION BEGIN for forwarding event to application

            self.log(f'{self.app_interval()}')

            # SECTION END
            ###################################################
            
        except Exception as e:
            self.log(f'an exception occurred {e}')


    def handle_minute_timer_event(self, kwargs):
        try:
            if self.lastMinute != datetime.now().minute:
                self.lastMinute = datetime.now().minute
                
                # SECTION BEGIN for forwarding event to error module
                self.error_check_each_minute()
                # SECTION END

                ###################################################
                # SECTION BEGIN for forwarding event to application
                #self.log(f'avPower:{self.availablePower+self.f_power}')

                #if(self.availablePower+self.f_power>1500):#Leistung, die der cSwitch benötigt
                #    self.log(f'{self.ctimer}')
                #    if(self.ctimer==False):
                #        self.ctimer=True
                #    else:
                #        self.app_cswitchOn(self.availablePower,self.f_power)
                #else:
                #    self.ctimer=False

                # SECTION END
                ###################################################

        except Exception as e:
            self.log(f'An exception: {e} occured in handle_minute_timer_event')



    def handle_entry_update_rfid(self, attribute, old, new):
        try:
            self.log("    .................................")
            self.log(f'    Entity state change for rfid')
            self.log(f'    attr:   {attribute}')
            self.log(f'    old:    {old}')
            self.log(f'    new:    {new}')

            if attribute == 'Simulation':
                scanned_id = "DC925CD3"
            else:
                scanned_id =self.my_rfid_scan.get_state()

            self.log(f'    scanned id: {scanned_id}')
            self.log("    .................................")



            ###################################################
            # SECTION BEGIN for forwarding event to application
            #if(attribute=='state'):
            if(attribute== 'Simulation'):
                if(self.rfidtimer==False):
                    self.app_rfidscanned(new, scanned_id,attribute)
                    self.rfidtimer=True
                else:
                    self.rfidtimer=False
            
            if(attribute!= 'Simulation'):
                self.app_rfidscanned(new, scanned_id,attribute)
                

            
            
            #self.log(f'{self.rfidtimer}')
            # SECTION END
            ###################################################
            

        except Exception as e:
            self.log(f'an exception occurred {e}')

    
    def handle_entry_update_switchf_power(self, old, new):
        # wenn sich die Leistung an einem NOUS - Zwischenstecker 
        # ändert, wird diese Nachricht empfangen

        try:
            self.log("    .................................")
            self.log(f'    Entity state change for switchf power')
            self.log(f'    old:    {old} W')
            self.log(f'    new:    {new} W')
            self.log("    .................................")

            ###################################################
            # SECTION BEGIN for forwarding event to application

            # SECTION END
            ###################################################

        except Exception as e:
            self.log(f'an exception occurred {e}')

    def handle_entry_update_switchf_state(self, old, new):
        # wenn ein NOUS - Zwischenstecker mit der grünen
        # Taste ein oder ausgeschaltet wird, Meldet der Schalter
        # diesen Wechsel über diese Nachricht 
        try:
            self.log("    .................................")
            self.log(f'    Entity state change for switchf state')
            self.log(f'    old:    {old}')
            self.log(f'    new:    {new}')
            self.log("    .................................")

            ###################################################
            # SECTION BEGIN for forwarding event to application

            # SECTION END
            ###################################################

        except Exception as e:
            self.log(f'an exception occurred {e}')


    def handle_entry_update_switchc_power(self, old, new):
        # wenn sich die Leistung an einem NOUS - Zwischenstecker 
        # ändert, wird diese Nachricht empfangen

        try:
            self.log("    .................................")
            self.log(f'    Entity state change for switchc power')
            self.log(f'    old:    {old} W')
            self.log(f'    new:    {new} W')
            self.log("    .................................")

            ###################################################
            # SECTION BEGIN for forwarding event to application

            self.app_cswitchOff(new)
            # SECTION END
            ###################################################


        except Exception as e:
            self.log(f'an exception occurred {e}')

    def handle_entry_update_switchc_state(self, old, new):
        # wenn ein NOUS - Zwischenstecker mit der grünen
        # Taste ein oder ausgeschaltet wird, Meldet der Schalter
        # diesen Wechsel über diese Nachricht 
        try:
            self.log("    .................................")
            self.log(f'    Entity state change for switchc state')
            self.log(f'    old:    {old}')
            self.log(f'    new:    {new}')
            self.log("    .................................")

            ###################################################
            # SECTION BEGIN for forwarding event to application

            # SECTION END
            ###################################################

        except Exception as e:
            self.log(f'an exception occurred {e}')

    
    def handle_entry_update_switchwb_power(self, old, new):
        # wenn sich die Leistung an einem NOUS - Zwischenstecker 
        # ändert, wird diese Nachricht empfangen

        try:
            self.log("    .................................")
            self.log(f'    Entity state change for switchwb power')
            self.log(f'    old:    {old} W')
            self.log(f'    new:    {new} W')
            self.log("    .................................")

            ###################################################
            # SECTION BEGIN for forwarding event to application
            
            self.app_wbswitchOff(self.availablePower, new)
            
            # SECTION END
            ###################################################

        except Exception as e:
            self.log(f'an exception occurred {e}')

    def handle_entry_update_switchwb_state(self, old, new):
        # wenn ein NOUS - Zwischenstecker mit der grünen
        # Taste ein oder ausgeschaltet wird, Meldet der Schalter
        # diesen Wechsel über diese Nachricht 
        try:
            self.log("    .................................")
            self.log(f'    Entity state change for switchwb state')
            self.log(f'    old:    {old}')
            self.log(f'    new:    {new}')
            self.log("    .................................")

            ###################################################
            # SECTION BEGIN for forwarding event to application


            # SECTION END
            ###################################################

        except Exception as e:
            self.log(f'an exception occurred {e}')




    def handle_entry_update_meter(self, old, new):
        #  negative Werte:  Strom vom Netz
        #  positive Werte:  Strom von der PV-Anlage

        #  für die Bewertung des Energiewertes für die LEDs der
        #  Wallbox und den Einschaltwert des C-Schalters muss
        #  der Wert f_power abgezogen werden. Sobald der C-Schalter
        #  oder der WB-Schalter einschalten, wird der Überschuss
        #  geringer und der F-Schalter wird dann automatisch
        #  ausschalten
        
        
        try:
            """ 
            self.log(f'{self.Simulation}')

            if(self.Simulation==False):
                self.f_power = self.get_state("sensor.gfs_cswitchf01_energy_power")
            else:
                if(self.get_state("sensor.gfs_cswitchf01")=="None"):
                    self.f_power = 2000
                else:
                    self.f_power=0 """
            if (self.Simulation == False):
                self.f_power = self.get_state("sensor.gfs_cswitchf01_energy_power")
            else:
                self.f_power = self.SimulierteCLeistung 
            
            self.log(f'{self.get_state("sensor.gfs_cswitchf01")}')
            self.log("    .................................")
            self.log(f'    Entity state change for meter')
            self.log(f'    old:     {old} W')
            self.log(f'    new:     {new} W')
            self.log(f'    f-power: {self.f_power} W')
            self.log("    (negative Werte = Strom vom Netz)")
            self.log("    .................................")

            self.availablePower = int(new)

            self.log(f'{self.availablePower}, {self.f_power}')


            ###################################################
            # SECTION BEGIN for forwarding event to application
            
            self.app_fswitchControl(self.availablePower)
            self.app_cswitchOn(self.availablePower,self.f_power)

            self.app_controlLEDs(self.availablePower,self.f_power)
            # SECTION END
            ###################################################

        except Exception as e:
            self.log(f'an exception occurred {e}')



####################################################
#  E R R O R   D E T E C T I O N
####################################################
# BEGIN

    def error_check_each_minute(self):
        try:
            self.log(f'check each minute')
            # first set error mode to no error
            self.error_setError(False, 'init')
            # check whether the followig
            # components are availabe
            self.error_checkSwitchf()
            self.error_checkSwitchc()
            self.error_checkSwitchWB()
            self.error_checkD1mini()
            if (self.Simulation == False):
                self.error_checkMeter()

        except Exception as e:
            self.log(f'an exception occurred {e}')

    def error_checkSwitchf(self):
        try:
            # try to get the sensors state
            x=self.get_state("sensor.gfs_cswitchf01_energy_power")
            if f'{x}' == 'unavailable' :
                self.error_setError(True, 'cSwitchF')                
        except Exception as e:
            self.log(f'an exception occurred {e}') 
            self.error_setError(True, 'cSwitchf')   

    def error_checkSwitchc(self):
        try:
            # try to get the sensors state
            x=self.get_state("switch.gfs_cswitchc01")   
            if f'{x}' == 'unavailable' :
                self.error_setError(True, 'cSwitchC')                
        except Exception as e:
            self.log(f'an exception occurred {e}') 
            self.error_setError(True, 'cSwitchC')

    def error_checkMeter(self):
        try:
            # try to get the sensors state
            x = self.get_entity("sensor.gfs_cmeter_haus_power")
            y = x.get_state(attribute="state")  
            if f'{y}' == 'unavailable' :
                self.error_setError(True, 'cMeter')
        except Exception as e:
            self.log(f'an exception occurred {e}') 
            self.error_setError(True, 'cMeter')

    def error_checkD1mini(self):
        try:
            # try to get the sensors state
            x=self.get_state("sensor.config_d1_scan") 
            if f'{x}' == 'unavailable' :
                self.error_setError(True, 'cD1mini')                
        except Exception as e:
            self.log(f'an exception occurred {e}') 
            self.error_setError(True, 'cD1mini')

    def error_checkSwitchWB(self):
        try:
            # try to get the sensors state
            x=self.get_state("switch.gfs_cswitchwb")
            if f'{x}' == 'unavailable' :
                self.error_setError(True, 'cSwitchWB')                
        except Exception as e:
            self.log(f'an exception occurred {e}') 
            self.error_setError(True, 'cSwitchWB')

    def error_setError(self, errorMode, device):
        try:
            self.log(f'device: {device}')
            if errorMode == False:
                # this is the first call to setError of a sequence
                # now the hardwareErrorDetected can be published
                self.error_errorStateUpdate(self.hardwareErrorDetected)
                self.hardwareErrorDetected = False
            else:
                self.log(f'defect device: {device}')
                self.hardwareErrorDetected = True

        except Exception as e:
            self.log(f'an exception occurred {e}')


    def error_errorStateUpdate(self, errorState):
        try:
            self.log(f'The error state is changed')
            if errorState == True:
                self.log(f'########### ERROR ###############')
                ###################################################
                # SECTION BEGIN for forwarding event to application
                self.app_error()
                # SECTION END
                ###################################################

            else:
                self.log(f'######### NO ERROR ##############')
                ###################################################
                # SECTION BEGIN for forwarding event to application
                self.app_noError()
                # SECTION END
                ###################################################

        except Exception as e:
            self.log(f'an exception occurred {e}')
# END


####################################################
#  A P P L I C A T I O N        C O D E
####################################################
# BEGIN




    def app_fswitchControl(self, newPowerOverSpill):
        try:
            #Logik für die Kontrolle des fswitches
            self.log("-----------------")
            self.log("Called fswitchControl")
            self.log("-----------------")           #Kontrolle zum Methodenaufruf
            self.log(f'{self.get_state("switch.gfs_cswitchf01")}')  #Überprüfung des aktuellen Zustands

            if(self.get_state("switch.gfs_cswitchf01")=="off" and newPowerOverSpill > self.TriggerLevelForSwitchF_on): #Wenn Messgerät über Grenze und aus ist
                self.switch_on(self.get_entity("switch.gfs_cswitchf01")) #wird Schalter angeschaltet
                self.log("Enough Power, turned fswitch on.")
                self.log("------------------")
            if(self.get_state("switch.gfs_cswitchf01")=="on" and newPowerOverSpill < self.TriggerLevelForSwitchF_off): #Wenn Power unter Grenze ist, 
                self.switch_off(self.get_entity("switch.gfs_cswitchf01")) #geht Schalter aus
                self.log("Low Power, turned fswitch off.")
                self.log("------------------")


        except Exception as e:
            self.log(f'An exception: {e} occured in app_fswitchcontrol()')



    def app_cswitchOff(self, currentPower):

        try:
            self.log("------------------")
            self.log("Called app_cswitchOff") 
            self.log("------------------")
            self.log(f'C-Switch power = {currentPower} W')

            if(currentPower<self.MinimalCPower):
                self.switch_off(self.get_entity("switch.gfs_cswitchc01"))

            
        except Exception as e:
            self.log(f'An exception: {e} occured in app_cswitchCurrentPower()')



    def app_cswitchOn(self, newPowerOverSpill, f_power):
        try:
            self.log("------------------")
            self.log("Called cswitchControl") #Kontrolle Aufruf
            self.log("------------------")
            self.log(f'{self.get_state("switch.gfs_cswitchc01")}')  #Überprüfung des aktuellen Zustands
            
            
            if newPowerOverSpill+self.f_power > self.TriggerLevelForSwitchC:
                self.switch_on(self.get_entity("switch.gfs_cswitchc01"))


            
        except Exception as e:
            self.log(f'An exception: {e} occured in app_cswitchcontrol()')







    def app_wbswitchOff(self, newPowerOverSpill, energyUsedBywbSwitch):
        try:
            self.log("-----------------")
            self.log("Called wbswitchOff")
            self.log("-----------------")
            wbstate = self.log(f'{self.get_state("switch.gfs_cswitchwb")}')#check Zustand
            wbpower = energyUsedBywbSwitch
            self.log(f'{wbpower}, {self.MinimalWbPower}')

            if(self.get_state("switch.gfs_cswitchwb")=="on"):
                if(wbpower<self.MinimalWbPower):
                    self.switch_off(self.get_entity("switch.gfs_cswitchwb"))
                else:
                    self.availablePower=newPowerOverSpill
        
        except Exception as e:
            self.log(f'An exception: {e} occured in app_wbswitchOff()')
            




    def app_rfidscanned(self, time_stamp, scanned_id,att):
        self.log("--------------------")
        self.log("rfidscanned method call successful")
        self.log("--------------------")

        self.my_scanned_id = scanned_id
        self.log(f'{att}')
        
        try:
            if(self.my_scanned_id == "DC925CD3"):
                self.switch_on(self.get_entity("switch.gfs_cswitchwb"))
                self.beep(1)
                self.log(f'{self.get_state("switch.gfs_cd1mini_wb_2_green")}')
                if(self.get_state("switch.gfs_cd1mini_wb_2_green")=="on"):
                    self.change_led_state(self.Color.GREEN,self.LedState.OFF)
                    time.sleep(0.25)
                    self.change_led_state(self.Color.GREEN,self.LedState.ON)
                else:
                    if(self.get_state("switch.gfs_cd1mini_wb_3_yellow")=="on"):
                        self.change_led_state(self.Color.YELLOW,self.LedState.OFF)
                        time.sleep(0.25)
                        self.change_led_state(self.Color.YELLOW,self.LedState.ON)
                            
            else:
                
                self.beep(3)



        except Exception as e:
            self.log(f'An Exception: {e} occured in app_rfidscanned()')


    
    def app_controlLEDs(self, currentPowerOverSpill, f_power):
        if(currentPowerOverSpill>=0):
            self.change_led_state(self.Color.YELLOW,self.LedState.OFF)
            self.change_led_state(self.Color.GREEN,self.LedState.ON)
        else:
            self.change_led_state(self.Color.GREEN,self.LedState.OFF)
            self.change_led_state(self.Color.YELLOW, self.LedState.ON)




    def app_interval(self):
        try:
            #Überprüft ob sich der aktuelle Zeitpunkt im Intervall befindet und ob die Haushaltsgeräte in der letzten Stunde schon überprüft worden sind
            self.log("------------------")
            self.log("interval method call successful")
            self.log("------------------")

            time_now = datetime.now()
            self.current_time = time_now.strftime("%H")
            
            intv=False
            hour = int(self.current_time)
            if(hour != int(self.last_hour)):
                intv = True
                self.log("Cswitch untested in interval")
                self.last_hour=self.current_time
            else:
                intv= False
                self.log("Interval tested")
            

            self.log(hour)
            if(hour >= self.TriggerIntervalEnd or hour < self.TriggerIntervalStart):
                intv=False
                self.log("Interval timed out")
            else:
                self.log("Interval timed")
            
            return intv
        
        except Exception as e:
            self.log(f'An Excepton: {e} occured in app_interval()')
        
        
    def app_error(self):
        try:
            self.log(f'We have an error detected')

            self.change_led_state(self.Color.RED,self.LedState.ON)

        except Exception as e:
            self.log(f'An Excepton: {e} occured in app_error()')
        

    def app_noError(self):
        try:
            self.log(f'There is no error')

            self.change_led_state(self.Color.RED,self.LedState.OFF)

        except Exception as e:
            self.log(f'An Excepton: {e} occured in ap_noError()')
        




####################################################
#  A P P L I C A T I O N S       C O D E
####################################################
# ENDE








    # Initialisierung der Komponenten
    #
    # Diese Funktion wurde an das Ende des Programms
    # verschoben. Diese Funktion muss nur in seltenen Fällen
    # angepasst werden und ist relativ lang
    # 

    def initComponents(self):
        self.log("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") 
        self.log("init cpvman")
        self.log("")
        if (self.Simulation == True):
            self.log("Physical energy meter is not used (SIMULATION-MODE)")


        my_trackers = self.get_trackers()
        self.log(f'trackers: {my_trackers}')
        self.log("")

        self.log("-------------------------")
        self.log("entity: switch.gfs_cswitchf01:")
        self.my_switchf = self.get_entity("switch.gfs_cswitchf01")
        if (self.my_switchf.exists()):
            self.log("switchf power plug found")
        else:
            self.log("switchf power plug not found")
        self.log("-------------------------")



        self.log("")
        self.log("-------------------------")
        self.log("entity: switch.gfs_cswitchc01:")
        self.my_switchc = self.get_entity("switch.gfs_cswitchc01")
        if (self.my_switchc.exists()):
            self.log("switchc power plug found")
        else:
            self.log("switchc power plug not found")
        self.log("-------------------------")



        self.log("")
        self.log("-------------------------")
        self.log("entity: switch.gfs_cswitchwb:")
        self.my_switchwb = self.get_entity("switch.gfs_cswitchwb")
        if (self.my_switchwb.exists()):
            self.log("switchwb power plug found")
        else:
            self.log("switchwb power plug not found")
        self.log("-------------------------")



        self.log("")
        self.log("-------------------------")
        self.log("entity: sensor.GFS_ManConfig_D1_Scan:")
        self.my_rfid_scan = self.get_entity("sensor.config_d1_scan")
        if (self.my_rfid_scan.exists()):
            self.log("sensor.GFS_ManConfig_D1_Scan found")
        else:
            self.log("sensor.GFS_ManConfig_D1_Scan not found")
        self.log("-------------------------")





        self.log("")
        self.log("-------------------------")
        self.log("entity: sensor.gfs_cmeter_haus_power:")
        self.my_meter = self.get_entity("sensor.gfs_cmeter_haus_power")
        if (self.my_meter.exists()):
            self.log("meter found")
            try:
                self.my_meter_state = self.my_meter.get_state(attribute="state")
                self.log(f'state = {self.my_meter_state} W')
                self.newMeterState = int(self.my_meter_state) * (-1)

                self.handle_entry_update_meter(0, self.newMeterState)
                self.log("-------------------------")
            except Exception as e:
                self.log(f'seems that cMeter is not installed')
                self.log(f'An Excepton: {e} occured in interval()')


        else:
            self.log("meter not found")



        if ((False == self.my_meter.exists()) or (self.Simulation == True)):
            self.log("")
            self.log("-------------------------")
            self.log("entity: counter.gfs_cdummymeter:")
            self.my_dummy_meter = self.get_entity("counter.gfs_cdummymeter")
            if (self.my_dummy_meter.exists()):
                self.log("dummy meter found")
            else:
                self.log("dummy meter not found")
            my_dummy_meter_state = self.my_dummy_meter.get_state(attribute="state")
            self.log(f'state = {my_dummy_meter_state} W')
            self.handle_entry_update_meter(0, my_dummy_meter_state)

            self.log("-------------------------")
        else:
            self.log("")
            self.log("dummy meter not created!!") 
            self.log("") 

        self.log("")
        time.sleep(1)
        self.log("-------------------------")
        self.log(" sleep 1 second")
        self.log("-------------------------")

        self.log("")


        self.log("-------------------------")
        self.log("register state change: switchf state")
        self.my_switchf.listen_state(self.handle_entity_update_cb)

        self.log("register state change: switchc state")
        self.my_switchc.listen_state(self.handle_entity_update_cb)

        self.log("register state change: switchwb state")
        self.my_switchwb.listen_state(self.handle_entity_update_cb)


        self.log("register change: cswitchf energy counter")
        self.listen_state(self.handle_entity_update_cb, "sensor.gfs_cswitchf01_energy_power")

        self.log("register change: cswitchc energy counter")
        self.listen_state(self.handle_entity_update_cb, "sensor.gfs_cswitchc01_energy_power")

        self.log("register change: cswitchwb energy counter")
        self.listen_state(self.handle_entity_update_cb, "sensor.gfs_cswitchwb_energy_power")

        self.log("register change: input_select.last_simulation")
        self.listen_state(self.handle_entity_update_cb, "input_select.last_simulation")

        self.log("register change: input_boolean.rfid_simulation")
        self.listen_state(self.handle_entity_update_cb, "input_boolean.rfid_simulation")

        if ((False == self.my_meter.exists()) or (self.Simulation == True)):
            self.log("register change: power dummy METER state")
            if self.my_dummy_meter.exists():
                self.my_dummy_meter.listen_state(self.handle_entity_update_cb)
            else:
                self.log("dummy_meter does not exist")
        else:
            self.log("register change: power METER state")
            self.my_meter.listen_state(self.handle_entity_update_cb)


        self.log("register change: sensor.GFS_ManConfig_D1_Update")
        self.listen_state(self.handle_entity_update_cb, "sensor.config_d1_update")


        self.log("register 2 second timer")
        self.run_every(self.handle_2_s_timer_event_cb, datetime.now(), 2)
        
        self.log("-------------------------")

        self.switch_off(self.my_switchf)
        self.switch_off(self.my_switchc)
        self.switch_off(self.my_switchwb)

        self.log("")
        self.log("-------------------------")
        self.log("LED and BEEPER TEST")
        self.change_led_state(self.Color.RED, self.LedState.ON)
        self.change_led_state(self.Color.YELLOW, self.LedState.ON)
        self.change_led_state(self.Color.GREEN, self.LedState.ON)
        self.beep(3)
        self.change_led_state(self.Color.RED, self.LedState.OFF)
        self.change_led_state(self.Color.YELLOW, self.LedState.OFF)
        self.change_led_state(self.Color.GREEN, self.LedState.OFF)
        self.log("-------------------------")

        self.log("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") 
        




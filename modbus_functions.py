from threading import Lock
from pyModbusTCP.client import ModbusClient
from datetime import datetime as dt, timedelta
import json
import struct
import inspect
import itertools
import logging
from enum import IntEnum


SERVER_PORT = 502


def get_config(config_name):
    """
    Lädt die Konfiguration entweder aus einer JSON-Datei oder aus dem config-Modul
    und filtert dabei alle Einträge heraus, die den String "Modbus" (oder "Mobus") enthalten.
    Es werden nur diese Einträge zurückgegeben.
    
    :param config_name: Name der JSON-Datei (ohne Endung) oder False, um das config-Modul zu verwenden.
    :return: Gefiltertes Konfigurationsdictionary oder None bei Fehler.
    """
    def contains_modbus(item):
        """
        Rekursive Hilfsfunktion, die prüft, ob im übergebenen Objekt (String, Liste, Dict)
        der Substring "modbus" (oder "mobus") enthalten ist.
        """
        if isinstance(item, str):
            return "modbus" in item.lower() or "mobus" in item.lower()
        elif isinstance(item, dict):
            return any(contains_modbus(value) for value in item.values())
        elif isinstance(item, list):
            return any(contains_modbus(elem) for elem in item)
        else:
            return False

    try:
        if config_name:
            with open(f'./json_files/{config_name}.json', 'r') as config_file:
                config_data = json.load(config_file)
        else:
            import config as cfg
            config_data = cfg.config  # Hier wird cfg.config verwendet

        # Filtere nur die Einträge, bei denen der Substring "Modbus" (oder "Mobus") vorkommt
        filtered_config = {k: v for k, v in config_data.items() if contains_modbus(v)}
        return filtered_config

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading config: {e}")
        return None


class MOD_TCP:
    class OperationModes(IntEnum):
        normalMode = 0
        dummyMode = 1

    class WarningLevels(IntEnum):
        normal = 0
        failOperational = 1
        failSafe = 2
        shutdown = 4    # TBD

    class IOtypes(IntEnum):
        inputDevice = 1
        outputDevice = 2

    def setup_devices(self):        
        channels_required = {}
        for device_key, value in self.config.items():
             # Überspringe externe Geräte, z.B. Modbus oder über andere Protokolle
            if "input_type" in value and "mks_modbus" in value["input_type"]  or "output_type" in value and "mks_modbus" in value["output_type"].lower():
                print(f"Setting up device {device_key} as Modbus MFC")
                self.devices[device_key] = Modbus_MFC_MKS(value["ip_address"])
            if  "output_type" in value and "modbus_pump" in value["output_type"].lower():
                print(f"Setting up device {device_key} as Modbus Pump")
                self.devices[device_key] = Modbus_Pump(value["ip_address"])
            if  "output_type" in value and "coupon_modbus" in value["output_type"].lower():
                print(f"Setting up device {device_key} as coupon_modbus")
                self.devices[device_key] = Modbus_Coupon(value["ip_address"])

                



    def __init__(self, config_name=False, debug_mode=OperationModes.normalMode):
        self.devices = {}
        self.operation_mode = debug_mode
        self.config = get_config(config_name)
        self.setup_devices()
        self.run = True


class Modbus_Coupon:
    def __init__(self, ip, port=SERVER_PORT, unit_id=1, timeout=0.2):
        """
        Initialisiert den Modbus-Client.
        
        :param ip: IP-Adresse des Geräts
        :param port: Port (Standard: 502)
        :param unit_id: Slave-/Unit-ID des Geräts (falls benötigt)
        :param timeout: Timeout in Sekunden
        """
        self.client = ModbusClient(host=ip, port=port, auto_open=True, timeout=timeout)
        self.client.unit_id = unit_id
        
    @property
    def stop(self):
        """
        Schließt die Modbus-Verbindung ordnungsgemäß.
        """
        if self.client.is_open:
            self.client.close()
            print("Modbus-Verbindung geschlossen.")
    
    def set(self, value, callback=None):
        """
        Schreibt den Flow Set Point in die Register 
        
        :param value: Float-Wert, der gesetzt werden soll.
        :return: Boolean, ob das Schreiben erfolgreich war.
        """
        # Schreibe die Register 
        success = self.client.write_multiple_registers(2100, [int(value)])
        return success

class Modbus_MFC_MKS:
    def __init__(self, ip, port=SERVER_PORT, unit_id=1, timeout=0.2):
        """
        Initialisiert den Modbus-Client.
        
        :param ip: IP-Adresse des Geräts
        :param port: Port (Standard: 502)
        :param unit_id: Slave-/Unit-ID des Geräts (falls benötigt)
        :param timeout: Timeout in Sekunden
        """
        self.client = ModbusClient(host=ip, port=port, auto_open=True, timeout=timeout)
        self.client.unit_id = unit_id
    @property
    def stop(self):
        """
        Schließt die Modbus-Verbindung ordnungsgemäß.
        """
        if self.client.is_open:
            self.client.close()
            print("Modbus-Verbindung geschlossen.")

    @property
    def flow(self):
        """
        Liest den Flow (sccm, als 32-Bit Float) aus den Input-Registern ab Adresse 0x4000.
        """
        try:
            regs = self.client.read_input_registers(0x4000, 2)
            if regs:
                # Wandelt die zwei 16-Bit Register in einen 32-Bit Float um (Big-Endian)
                return struct.unpack('>f', struct.pack('>HH', regs[0], regs[1]))[0]
            else:
                return None  # Falls keine Daten empfangen wurden
        except Exception as e:
            print(f"Fehler beim Lesen des Flow-Werts: {e}")
            return None
    
    @property        
    def flow_str(self):
        """
        Wandelt  den Flow in einen String aus und gibt bei None "Error2" aus
        """
        flow_value = self.flow
        return f"{flow_value:.0f}" + " sccm" if flow_value is not None else "Error"
    

    @property
    def temp(self):
        """
        Liest die Temperatur (degC, als 32-Bit Float) aus den Input-Registern ab Adresse 0x4002.
        """
        regs = self.client.read_input_registers(0x4002, 2)
        if regs:
            return struct.unpack('>f', struct.pack('>HH', regs[0], regs[1]))[0]
        else:
            return None

    @property
    def valve(self):
        """
        Liest die Ventilstellung (0-100%, als 32-Bit Float) aus den Input-Registern ab Adresse 0x4004.
        """
        regs = self.client.read_input_registers(0x4004, 2)
        if regs:
            return struct.unpack('>f', struct.pack('>HH', regs[0], regs[1]))[0]
        else:
            return None
        
    @property
    def modbus_control(self):
        """
        Prüft, ob Full Modbus Control aktiviert ist (Register 0xA006).
        """
        regs = self.client.read_holding_registers(0xA006, 2)
        if regs:
            return struct.unpack('>f', struct.pack('>HH', regs[0], regs[1]))[0]
        return None

    @property
    def current_setpoint(self):
        """
        Liest den aktuellen Flow-Setpoint aus Register 0xA000.
        """
        regs = self.client.read_holding_registers(0xA000, 2)
        if regs:
            return struct.unpack('>f', struct.pack('>HH', regs[0], regs[1]))[0]
        return None
    @property
    def close_valve(self):
        """
        Schließt das Ventil vollständig (Register 0xE002, Wert 0xFF00).
        """
        success = self.client.write_single_coil(0xE002, 0xFF00)
        return success
    @property
    def release_valve(self):
        """
        Gibt das Ventil wieder frei (Register 0xE002, Wert 0x0000).
        """
        success = self.client.write_single_coil(0xE002, 0x0000)
        return success
    
    @property
    def zero_flow(self):
        """
        Setzt den Flow Zero (Register 0xE003, 2-Byte Integer).
        Dies wird durch das Schreiben von 1 auf das Coil-Register 0xE003 erreicht.
        
        :return: Boolean, ob das Schreiben erfolgreich war.
        """
        success = self.client.write_single_coil(0xE003, 1)
        return success

    def set(self, value, callback=None):
        """
        Schreibt den Flow Set Point in die Register ab Adresse 0xA000.
        Hierbei wird der übergebene Float-Wert in eine 32-Bit IEEE754-Darstellung (4 Byte) umgewandelt,
        in zwei 16-Bit Register zerlegt und mittels write_multiple_registers geschrieben.
        
        :param value: Float-Wert, der gesetzt werden soll.
        :return: Boolean, ob das Schreiben erfolgreich war.
        """
        #self.release_valve
        # Float-Wert in 4 Byte (32-Bit IEEE754) umwandeln, Big-Endian
        packed = struct.pack('>f', value)
        # Aufteilen in zwei 16-Bit Register (unsigned short)
        registers = struct.unpack('>HH', packed)
        # Schreibe die Register ab Adresse 0xA000
        success = self.client.write_multiple_registers(0xA000, list(registers))
        return success


# Beispiel für die Verwendung der Klasse:
if __name__ == "__main__":
    # Instanziiere die Klasse für ein Gerät (z.B. MFC)
    MFC = Modbus_MFC_MKS(ip='192.168.2.13', port=502, unit_id=1)

    # Lese und drucke die Werte
    print("Flow:", MFC.flow, "sccm")
    print("Temp:", MFC.temp, "degC")
    print("Valve:", MFC.valve, "%")
     # Prüfe den Modbus Control-Status
    modbus_status = MFC.modbus_control
    #print("Modbus Control aktiv?", modbus_status)
    # Lese den aktuellen Setpoint aus
    current_sp = MFC.current_setpoint
    print("Aktueller Flow-Setpoint:", current_sp, "sccm")
    # Setze einen neuen Flow Set Point (z.B. 50.0 sccm) und führe den Callback aus
    if MFC.set(500):
        print("Schreiben erfolgreich...")
    else:
        print("Schreiben nicht erfolgreich initiiert.")

    
    #MFC.close_valve # Ventil vollständig schließen
    #MFC.release_valve

class Modbus_Pump:
    """
    Diese Klasse stellt die Kommunikation zu einer Modbus-gesteuerten Pumpe bereit.
    
    Sie ermöglicht das Lesen von Statuswerten (z. B. stalled, moving, velocity, position)
    sowie das Schreiben von Steuerbefehlen (z. B. slew, holdCurrent, runCurrent, etc.).
    """
    REGISTER_SIZE = 16
    MAX_REGISTER_RANGE = 1 << REGISTER_SIZE  # Maximale Anzahl darstellbarer Werte (0 inklusive)
    STEPS_PER_REV = 51200

    def __init__(self, ip_address):
        """
        Initialisiert den Modbus-Client für die Pumpe und konfiguriert die Lese- und Schreibaktionen.
        
        :param ip_address: IP-Adresse der Pumpe.
        :raises Exception: Falls keine Verbindung hergestellt werden kann.
        """
        self.client = ModbusClient(host=ip_address, port=SERVER_PORT, auto_open=True, timeout=0.2)
        if not self.client.open():
            raise Exception(f"Verbindung zu {ip_address} konnte nicht hergestellt werden.")
        self.bus_semaphore = Lock()
        
        # Initialisiere Schreibaktionen als Dictionary von WriteCommand-Instanzen.
        self.__writeActions = {
            "slew": self.WriteCommand(self, 0x0078, (-5000000, 5000000), 2),
            "holdCurrent": self.WriteCommand(self, 0x0029, (0, 100), 1),
            "runCurrent": self.WriteCommand(self, 0x0067, (0, 100), 1),
            "setTorque": self.WriteCommand(self, 0x00A6, (0, 100), 1),
            "setMaxVelocity": self.WriteCommand(self, 0x008B, (1, 2560000), 2),
            "error": self.WriteCommand(self, 0x0021, (0, 0), 1),
            "driveEnable": self.WriteCommand(self, 0x001C, (0, 1), 1),
            "microStep": self.WriteCommand(self, 0x0048, (1, 256), 1),
            "encodeEnable": self.WriteCommand(self, 0x001E, (0, 1), 1),
            "position": self.WriteCommand(self, 0x0057, (-2147483648, 2147483647), 2),
            "makeUp": self.WriteCommand(self, 0x00A0, (0, 2), 1)
        }
        
        # Initialisiere Leseaktionen als Dictionary von ReadCommand-Instanzen.
        self.__readActions = {
            "stalled": self.ReadCommand(self, 0x007B),
            "moving": self.ReadCommand(self, 0x004A),
            "outputFault": self.ReadCommand(self, 0x004E),
            "error": self.ReadCommand(self, 0x0021),
            "velocity": self.ReadCommand(self, 0x0085, 2),
            "position": self.ReadCommand(self, 0x0057, 2)
        }
        
        # Setze Standardwerte und starte den Motor in einem sicheren Zustand.
        self.write_encodeEnable(1)
        self.write_error(0)
        self.write_position(0)
        self.write_makeUp(1)
        self.halt()
        self.polling_thread = None

    def convert_value_to_register(self, value, value_range, register_count):
        """
        Konvertiert einen Wert in das passende Registerformat.
        
        Der Wert wird in den zulässigen Bereich begrenzt. Falls der Bereich kleiner als der
        maximal darstellbare Registerbereich ist, wird ein einzelner Wert zurückgegeben;
        ansonsten werden zwei Register (High- und Low-Register) zurückgegeben.
        
        :param value: Der einzustellende Wert.
        :param value_range: Tupel (min, max) des zulässigen Bereichs.
        :param register_count: Anzahl der zu verwendenden Register.
        :return: Liste der Registerwerte.
        """
        clipped_value = max(min(value, value_range[1]), value_range[0])
        if clipped_value != value:
            print(f"Wert: {value} liegt außerhalb des Bereichs {value_range}. Auf {clipped_value} begrenzt.")
            value = clipped_value
        abs_range = sum(abs(x) for x in value_range)
        if abs_range < self.MAX_REGISTER_RANGE:
            return [value]
        else:
            high_register = (value >> self.REGISTER_SIZE) & 0xFFFF
            low_register = value & 0xFFFF
            return [low_register, high_register]

    class ReadCommand:
        """
        Hilfsklasse zur Durchführung von Leseaktionen über Modbus.
        """
        def __init__(self, modbus: "Modbus_Pump", register: int, register_count: int = 1):
            self.register = register
            self.register_count = register_count
            self.modbus = modbus

        def get_value(self):
            """
            Liest Registerwerte und gibt den entsprechenden Wert zurück.
            
            Falls zwei Register gelesen werden, wird ein 32-Bit-Wert zusammengesetzt.
            
            :return: Gelesener Wert oder False bei Fehler.
            """
            with self.modbus.bus_semaphore:
                regs = self.modbus.client.read_holding_registers(self.register, self.register_count)
            if regs is None:
                print("Kommunikationsfehler: Kein Wert empfangen.")
                return False
            if len(regs) > 2:
                print("Unerwartete Länge der Rückgabe.")
                return False
            if len(regs) == 2:
                low_reg, high_reg = regs
                combined = (high_reg << 16) | low_reg
                # Vorzeichenanpassung, falls notwendig
                if combined & (1 << 31):
                    combined -= (1 << 32)
                regs = [combined]
            return regs[0]

    class WriteCommand:
        """
        Hilfsklasse zur Durchführung von Schreibaktionen über Modbus.
        """
        def __init__(self, modbus: "Modbus_Pump", register: int, value_range: tuple, register_count: int):
            self.modbus = modbus
            self.register = register
            self.value_range = value_range
            self.register_count = register_count

        def set_value(self, value: int) -> bool:
            """
            Setzt den übergebenen Wert in das entsprechende Register.
            
            Der Wert wird konvertiert und mittels write_multiple_registers gesendet.
            
            :param value: Der einzustellende Wert.
            :return: True bei Erfolg, sonst False.
            """
            reg_value = self.modbus.convert_value_to_register(value, self.value_range, self.register_count)
            with self.modbus.bus_semaphore:
                res = self.modbus.client.write_multiple_registers(self.register, reg_value)
            if res:
                return True
            # Fehlerbehandlung: Ausgabe der Fehlermeldung und Rücksetzen des Fehlerregisters.
            print("Modbus-Fehler:", self.modbus.client.last_error_as_txt)
            print("Ausnahme:", self.modbus.client.last_except_as_full_txt)
            self.modbus.write_error(0)
            return False

    # ---------------------------
    # Properties für Leseaktionen
    # ---------------------------
    @property
    def stalled(self):
        """
        Liest den 'stalled'-Status der Pumpe.
        
        :return: Wert des 'stalled'-Status oder False bei Fehler.
        """
        return self.__readActions["stalled"].get_value()

    @property
    def moving(self):
        """
        Liest den 'moving'-Status der Pumpe.
        
        :return: Wert des 'moving'-Status oder False bei Fehler.
        """
        return self.__readActions["moving"].get_value()

    @property
    def output_fault(self):
        """
        Liest den 'outputFault'-Status der Pumpe.
        
        :return: Wert des 'outputFault'-Status oder False bei Fehler.
        """
        return self.__readActions["outputFault"].get_value()

    @property
    def error(self):
        """
        Liest den 'error'-Status der Pumpe.
        
        :return: Wert des 'error'-Status oder False bei Fehler.
        """
        return self.__readActions["error"].get_value()

    @property
    def velocity(self):
        """
        Liest die aktuelle Geschwindigkeit der Pumpe.
        
        :return: Geschwindigkeit oder False bei Fehler.
        """
        return self.__readActions["velocity"].get_value()

    @property
    def position(self):
        """
        Liest die aktuelle Position der Pumpe.
        
        :return: Position oder False bei Fehler.
        """
        return self.__readActions["position"].get_value()

    # ---------------------------
    # Methoden für Schreibaktionen
    # ---------------------------
    def write_slew(self, value: int) -> bool:
        """
        Schreibt den 'slew'-Wert in das zugehörige Register.
        
        :param value: Der einzustellende 'slew'-Wert.
        :return: True bei Erfolg, sonst False.
        """
        return self.__writeActions["slew"].set_value(value)

    def write_holdCurrent(self, value: int) -> bool:
        """
        Schreibt den 'holdCurrent'-Wert in das zugehörige Register.
        
        :param value: Der einzustellende 'holdCurrent'-Wert.
        :return: True bei Erfolg, sonst False.
        """
        return self.__writeActions["holdCurrent"].set_value(value)

    def write_runCurrent(self, value: int) -> bool:
        """
        Schreibt den 'runCurrent'-Wert in das zugehörige Register.
        
        :param value: Der einzustellende 'runCurrent'-Wert.
        :return: True bei Erfolg, sonst False.
        """
        return self.__writeActions["runCurrent"].set_value(value)

    def write_setTorque(self, value: int) -> bool:
        """
        Schreibt den 'setTorque'-Wert in das zugehörige Register.
        
        :param value: Der einzustellende 'setTorque'-Wert.
        :return: True bei Erfolg, sonst False.
        """
        return self.__writeActions["setTorque"].set_value(value)

    def write_setMaxVelocity(self, value: int) -> bool:
        """
        Schreibt den 'setMaxVelocity'-Wert in das zugehörige Register.
        
        :param value: Der einzustellende 'setMaxVelocity'-Wert.
        :return: True bei Erfolg, sonst False.
        """
        return self.__writeActions["setMaxVelocity"].set_value(value)

    def write_error(self, value: int) -> bool:
        """
        Schreibt den 'error'-Wert in das zugehörige Register.
        
        :param value: Der einzustellende 'error'-Wert.
        :return: True bei Erfolg, sonst False.
        """
        return self.__writeActions["error"].set_value(value)

    def write_driveEnable(self, value: int) -> bool:
        """
        Schreibt den 'driveEnable'-Wert in das zugehörige Register.
        
        :param value: Der einzustellende 'driveEnable'-Wert.
        :return: True bei Erfolg, sonst False.
        """
        return self.__writeActions["driveEnable"].set_value(value)

    def write_microStep(self, value: int) -> bool:
        """
        Schreibt den 'microStep'-Wert in das zugehörige Register.
        
        :param value: Der einzustellende 'microStep'-Wert.
        :return: True bei Erfolg, sonst False.
        """
        return self.__writeActions["microStep"].set_value(value)

    def write_encodeEnable(self, value: int) -> bool:
        """
        Schreibt den 'encodeEnable'-Wert in das zugehörige Register.
        
        :param value: Der einzustellende 'encodeEnable'-Wert.
        :return: True bei Erfolg, sonst False.
        """
        return self.__writeActions["encodeEnable"].set_value(value)

    def write_position(self, value: int) -> bool:
        """
        Schreibt den 'position'-Wert in das zugehörige Register.
        
        :param value: Der einzustellende 'position'-Wert.
        :return: True bei Erfolg, sonst False.
        """
        return self.__writeActions["position"].set_value(value)

    def write_makeUp(self, value: int) -> bool:
        """
        Schreibt den 'makeUp'-Wert in das zugehörige Register.
        
        :param value: Der einzustellende 'makeUp'-Wert.
        :return: True bei Erfolg, sonst False.
        """
        return self.__writeActions["makeUp"].set_value(value)

    def halt(self):
        """
        Stoppt den Motor, indem der 'slew'-Wert auf 0 gesetzt wird.
        """
        self.write_slew(0)

    def set_Flow(self, flow: float, a: float, b: float) -> bool:
        """
        Rechnet den Volumenstrom (in ml/min) in einen Drehzahlwert (slew) um und sendet ihn an die Pumpe.
        
        Formel: slew = flow * a + b
        
        :param flow: Volumenstrom in ml/min.
        :param a: Umrechnungsfaktor.
        :param b: Offset.
        :return: True, wenn der Befehl erfolgreich gesendet wurde, sonst False.
        """
        slew = flow * a + b
        return self.write_slew(int(slew))


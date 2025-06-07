#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime

class CustomInput:
    def __init__(self):
        self.data = {}
        self.values = [0, 0, 0, 0]
    
class DirectHeatController:
    def __init__(self, name):
        self.deviceName = name
        self.entry = None
        self.label = None
        self.running = False
        self.out = 0
        self.soll = 0

    def set_soll(self,soll):
        """
        Stoppt den Heizer und setzt den Heizwert auf 0,
        um den Ausgang zurückzusetzen.
        """
        self.running = True
        self.soll = soll
        self.out = soll
    
    def start(self,soll):
        """
        Stoppt den Heizer und setzt den Heizwert auf 0,
        um den Ausgang zurückzusetzen.
        """
        self.running = True
        self.soll = soll
        self.out = soll

    def stop(self):
        """
        Stoppt den Heizer und setzt den Heizwert auf 0,
        um den Ausgang zurückzusetzen.
        """
        self.running = False
        self.out = 0

class easy_PI:
    def __init__(self, out_handle, output_channel, input_handle, input_channel, ki, kp) -> None:
        """
        Initialisiert den easy_PI-Regler.

        :param out_handle: Handle zum Ausgangsgerät
        :param output_channel: Ausgabekanal (wird aktuell nicht weiter genutzt)
        :param input_handle: Handle zum Eingang oder ein String zur Kennzeichnung eines externen Eingangs (Debug)
        :param input_channel: Kanal, über den der Messwert abgerufen wird
        :param ki: Integrationskoeffizient
        :param kp: Proportionalitätskoeffizient
        """
        self.running = False           # Kennzeichnet, ob der Regler aktiv läuft
        self.input_channel = input_channel

        # Bei externen Eingabewerten im Debug-Modus wird ein CustomInput-Objekt erzeugt.
        if isinstance(input_handle, str) and "extern" in input_handle.lower():
            self.input = CustomInput()  # CustomInput muss in diesem Fall definiert sein
        else:
            self.input = input_handle

        self.output_device = out_handle
        self.output_channel = output_channel
        self.ki = ki
        self.kp = kp
        self.out = 0                   # Aktueller Regler-Ausgang (zwischen 0 und 1)
        self.soll = 0                  # Zielwert (Sollwert)
        self.i = 0                     # Integrierter Fehler (I-Anteil)
        self.time_last_call = datetime.now()  # Zeitpunkt der letzten Regelung
        self.sec_diff = 0              # Sicherheitsdifferenz (z. B. Temperatur-Schutz)
        self.secureOff = False         # Flag für manuelle Sicherheitsabschaltung
        self.tc_S = None               # Handle für die Temperaturüberwachung (muss Attribut 't' besitzen)

    def config(self, ki, kp):
        """
        Aktualisiert die PI-Regler-Parameter.

        :param ki: Neuer Integrationskoeffizient
        :param kp: Neuer Proportionalitätskoeffizient
        """
        self.ki = ki
        self.kp = kp

    def start(self, soll):
        """
        Startet den Regler mit dem angegebenen Sollwert.

        :param soll: Neuer Sollwert
        """
        self.soll = soll
        self.running = True
        self.time_last_call = datetime.now()

    def security(self, tc_handle, threshold=30):
        """
        Konfiguriert den Temperaturschutz.

        :param tc_handle: Handle zur Temperaturüberwachung (muss ein Attribut 't' besitzen)
        :param threshold: Sicherheitsdifferenz; wenn die Temperatur (tc_handle.t)
                          den Sollwert plus diesen Schwellenwert übersteigt, wird
                          der Regler abgeschaltet (Standard: 30)
        """
        self.tc_S = tc_handle
        self.sec_diff = threshold

    def stop(self):
        """
        Stoppt den Regler und führt eine letzte Regelung durch,
        um den Ausgang zurückzusetzen.
        """
        self.running = False
        self.regeln()

    def set_soll(self, soll):
        """
        Setzt einen neuen Sollwert.

        :param soll: Neuer Sollwert
        """
        self.soll = soll

    def set_secureOff(self):
        """
        Aktiviert die manuelle Sicherheitsabschaltung.
        """
        self.secureOff = True

    def regeln(self):
        """
        Führt die PI-Regelung durch und aktualisiert den Ausgangswert (self.out)
        basierend auf dem aktuellen Messwert und dem Sollwert.
        Liegt ein Sicherheitsfall (z. B. zu hohe Temperatur) vor oder ist der
        Regler nicht aktiv, wird der Ausgang auf 0 gesetzt.
        """
        # Überprüfe, ob ein Sicherheitsfall vorliegt
        safety_active = False
        if self.tc_S is not None and self.sec_diff > 0:
            # Annahme: self.tc_S besitzt ein Attribut 't', das die aktuelle Temperatur liefert.
            # Sicherheitsfall: Temperatur über Sollwert + Sicherheitsdifferenz oder über 300.
            if self.tc_S.t > self.soll + self.sec_diff or self.tc_S.t > 300:
                safety_active = True

        if safety_active:
            print('Temperaturwächter aktiv')

        # Wenn der Regler aktiv ist, kein Sicherheitsfall vorliegt und keine manuelle Abschaltung
        # erfolgt ist, dann führe die PI-Regelung aus.
        if self.running and not safety_active and not self.secureOff:
            # Ermittle den aktuellen Messwert
            current_value = self.input.values[self.input_channel]
            # Berechne den Fehler zwischen Soll- und Ist-Wert
            delta = self.soll - current_value

            # Proportionalanteil berechnen
            p = self.kp * delta

            # Berechne die verstrichene Zeit seit dem letzten Aufruf
            now = datetime.now()
            dtime = (now - self.time_last_call).total_seconds()
            self.time_last_call = now

            # Integriere den Fehler (mit Zeitskalierung)
            self.i += delta * self.ki * dtime

            # PI-Regler-Ausgang berechnen
            pi = p + self.i

            # Begrenze den Ausgangswert zwischen 0 und 1
            if pi > 1:
                pi = 1
                # Anti-Windup: Passe den I-Anteil an, um Überschwinger zu vermeiden
                self.i = pi - p
            elif pi < 0:
                pi = 0
                # Setze den I-Anteil zurück, falls er negativ geworden ist
                self.i = 0

            self.out = pi
        else:
            # Im Sicherheitsfall oder wenn der Regler gestoppt ist, setze den Ausgang auf 0.
            self.out = 0
            # Setze die manuelle Sicherheitsabschaltung zurück.
            self.secureOff = False
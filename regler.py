#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime

class CustomInput:
    def __init__(self):
        self.data = {}
        self.values = [0, 0, 0, 0]
    

class easy_PI:
    soll = 0
    ki = 0.000013
    kp = 0.018
    i = 0
    time_last_call = datetime.now()
    pwroutput = 0

    def __init__(self, out_handle, ouput_channel, input_handle, input_channel, ki, kp) -> None:
        self.running = False
        self.input_channel = input_channel
        if isinstance(input_handle,str) and "extern" in input_handle.lower(): # nur für Debug. muss noch was hinzugefügt werden
            self.input= CustomInput()
        else:
            self.input = input_handle
            

        self.output_device = out_handle
        self.ki = ki
        self.kp = kp
        self.out = 0
        self.sec_diff = 0

    def config(self, ki, kp):
        self.ki = ki
        self.kp = kp

    def start(self, soll):
        self.soll = soll
        self.running = True
        self.time_last_call = datetime.now()

    def security(self, tc_handle, diff):
        self.tc_S = tc_handle
        self.sec_diff = 30

    def stop(self):
        self.running = False
        self.regeln()
    
    def set_soll(self, soll):
        self.soll = soll

    def set_secureOff(self):
        self.secureOff = True

    def regeln(self):
        dT_sec = 0
        if self.sec_diff > 0:
            dT_sec =  self.tc_S.t - (self.t_soll+self.sec_diff)     #Sicherheitstemperatur
            if self.tc_S.t > 300:
                dT_sec = 50
        if dT_sec > 0:
            print('Temperaturwächter aktiv')
        if self.running == True and dT_sec <= 0 and self.secureOff == False:
            delta = self.soll - self.input.values[self.input_channel]
            p = self.kp*(delta)
            now = datetime.now()
            dtime = (now - self.time_last_call).total_seconds()
            self.time_last_call = now
            self.i = self.i + delta*self.ki*(dtime)
            
            pi = p+self.i
            if pi > 1: # Output begrenzen auf 100%
                pi = 1
                self.i = pi - p
            elif pi < 0: # Output begrenzen auf 0%
                pi = 0
            if self.i < 0: # I-Anteil zurücksetzen
                self.i = 0
            duty = (pi)
            self.out = duty
        else:
            duty = 0
            self.out = duty
            self.secureOff = False
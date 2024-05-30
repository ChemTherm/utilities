#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime


class easy_PI:
    soll = 0
    ki = 0.000013
    kp = 0.018
    i = 0
    time_last_call = datetime.now()
    pwroutput = 0

    def __init__(self, out_handle, ouput_channel, input_handle, input_channel, ki, kp) -> None:
        self.running = False
        self.input = input_handle
        self.input_channel = input_channel
        self.output_device = out_handle
        self.ki = ki
        self.kp = kp
        self.out = 0

    def config(self, ki, kp):
        self.ki = ki
        self.kp = kp

    def start(self, soll):
        self.soll = soll
        self.running = True
        self.time_last_call = datetime.now()

    def stop(self):
        self.running = False
        self.regeln()
    
    def set_soll(self, soll):
        self.soll = soll

    def regeln(self):
        if self.running == True:
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
#!/usr/bin/env python3

import math
import matplotlib.pyplot as plt
import numpy as np
import random
import sys
import itertools
import time

import person
import car
import utils

#############################################################
class SensingModel():
    def __init__(self, npeople, ncars, searchmap, crossings, log):
        self.rng = random.SystemRandom()
        plt.ion()
        #h, w = searchmap.shape
        h, w = utils.get_mapshape_from_searchmap(searchmap)
        self.mapshape = (h, w)
        self.tick = 0
        self.carrange = 1
        self.log = log
        self.maph = h
        self.mapw = w
        self.searchmap = searchmap
        self.crossings = crossings
        self.lastid = -1
        self.people = []
        self.cars = []

        self.truesensor = Sensor(self.mapshape)
        self.tdens = np.full(self.mapshape, 0.0)
        self.fleetsensor = Sensor(self.mapshape)
        self.sdens = np.full(self.mapshape, 0.0)

        self.free = list(self.searchmap.keys())
        self.place_agents(npeople, ncars)
        self.denserror = -1

    def get_free_pos(self, avoided=[], n=1):
        nfree = len(self.free)
        freepos = []    # we accept repetitions

        while len(freepos) < n:
            rndidx = self.rng.randrange(0, nfree)
            chosen = self.free[rndidx]
            if chosen != avoided: freepos.append(chosen)
        return freepos

    def place_people(self, npeople):
        freepos = self.get_free_pos([], 2*npeople)

        for i in range(npeople):
            #pos = self.get_free_pos()
            pos = freepos.pop()
            destiny = freepos.pop()
            #destiny = self.get_free_pos(pos)
            self.lastid += 1
            a = person.Person(self.lastid, self, pos, destiny, self.searchmap, self.crossings)
            self.people.append(a)
            t0 = time.time()
            a.create_path()
            self.log.debug('Create_path of person {} {}->{} took {}.'. \
                      format(self.lastid, pos, destiny, time.time() - t0))

            self.place_person(a, pos)

    def place_cars(self, ncars, _range):
        freepos = self.get_free_pos([], 2*ncars)
        for i in range(ncars):
            #pos = self.get_free_pos()
            #destiny = self.get_free_pos(pos)
            pos = freepos.pop()
            destiny = freepos.pop()
            self.lastid += 1
            a = car.Car(self.lastid, self, pos, destiny,
                        self.searchmap, self.crossings, _range)
            self.cars.append(a)
            t0 = time.time()
            a.create_path()
            self.log.debug('Create_path of car {} {}->{} took {}.'. \
                      format(self.lastid, pos, destiny, time.time() - t0))
            self.place_car(a, pos)

    def place_agents(self, npeople, ncars):
        self.place_people(npeople)
        self.place_cars(ncars, self.carrange)

    def compute_true_density(self):
        if self.tick == 0: return np.full(self.mapshape, -1)
        tdens = np.full(self.mapshape, 0)

        for j in range(self.maph):
            for i in range(self.mapw):
                count = float(self.truesensor.count[j][i])
                tdens[j][i] = count / float(self.tick)
        return tdens

    def update_true_density(self):
        self.tdens = self.compute_true_density()

    def compute_sensed_density(self):
        sdens = np.full(self.mapshape, -1)

        for j in range(self.maph):
            for i in range(self.mapw):
                count = float(self.fleetsensor.count[j][i])
                s = self.fleetsensor.samplesz[j][i]

                if s != 0: sdens[j][i] = count / float(s)
        return sdens

    def update_sensed_density(self):
        self.sdens = self.compute_sensed_density()

    def increment_people_count(self, pos, delta=1):
        y, x = pos
        self.truesensor.count[y][x] += delta

    def place_person(self, person, pos):
        self.people.append(person)
        person.pos = pos
        self.increment_people_count(pos)

    def place_car(self, car, pos):
        self.cars.append(car)
        car.pos = pos

    def get_densities(self):
        return self.tdens, self.sdens

    def update_car_sensing(self, nearby):
        peoplepos = [p.pos for p in self.people]
        for p in nearby:
            y, x = p
            self.fleetsensor.samplesz[y][x] += 1
            self.fleetsensor.count[y][x] += peoplepos.count(p)
        car.Car.clicks += 1

    def sense_region(self, _car):
        nearby = _car.get_cells_in_range(self.maph, self.mapw)
        self.update_car_sensing(nearby)

    def compute_density_error(self):
        sdens = self.sdens
        tdens = self.tdens
        acc = 0
        error = 0

        for y in range(self.maph):
            for x in range(self.mapw):
                sensed = sdens[y][x]

                if sensed != -1:
                    true = tdens[y][x]
                    error += math.fabs(sensed - true)
                    acc += 1
        return error / float(acc)

    def update_density_error(self):
        self.denserror = self.compute_density_error()

    def step(self, update_densities=True):
        freepos = self.get_free_pos([], len(self.people) + len(self.cars))

        for p in self.people:
            p.step(freepos)
            self.increment_people_count(p.pos)

        for c in self.cars:
            c.step(freepos)
            self.sense_region(c)
        self.tick += 1

        if update_densities:
            self.update_true_density()
            self.update_sensed_density()
            self.update_density_error()

class Sensor:
    def __init__(self, _shape):
        self.count = np.full(_shape, 0)
        self.samplesz = np.full(_shape, 0)

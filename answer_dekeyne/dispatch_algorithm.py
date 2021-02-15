
import logging as log
import pandas as pd
from copy import deepcopy

logger = log.getLogger(__name__)


class PowerDispatcher:
    """
    Dispatches the load over the different power plants according to their capacities and availabilities
    """
    def __init__(self, payload, carbon_rate=None):
        self.plants = payload['powerplants']
        self.fuels = payload['fuels']
        self.required_load = payload['load']
        if carbon_rate is None:
            self.carbon_price = None
        else:
            self.carbon_price = carbon_rate * self.fuels['co2(euro/ton)']
        self.dispatch_build = pd.DataFrame(columns=('name', 'p', 'pmin'))
        self.current_load = 0
        self.get_merit_plants = {'gasfired': (self.get_merit_gasfired, ('efficiency',)),
                                 'turbojet': (self.get_merit_turbojet, ('efficiency',)),
                                 'windturbine': (self.get_merit_windturbine, ())}
    
    def define_merit_orders(self):
        """
        Defines the merit order of each power plant
        :return: pandas data frame detailing the power plants
        """
        merit_plant = deepcopy(self.plants)
        for plant in merit_plant:
            if plant['type'] not in self.get_merit_plants:
                raise ValueError('Unknown power plant type {}'.format(plant['type']))

            plant['merit_order'] = self.get_merit_plant(plant)

        # Converting the dictionary in a Pandas data frame ordered by merit
        return pd.DataFrame.from_dict(merit_plant).sort_values('merit_order')

    def get_merit_plant(self, plant):
        """
        Computes the merit order for one specific plant with its own method
        :param plant: dictionary describing the plant
        :return: the merit order value
        """
        merit_order_method = self.get_merit_plants[plant['type']][0]
        args_keys = self.get_merit_plants[plant['type']][1]
        args = [plant[key] for key in args_keys]

        try:
            merit_order = merit_order_method(*args)

        except ZeroDivisionError:
            raise ValueError('Failed to compute merit order for plant {}, efficiency is null'.format(plant['name']))

        return merit_order

    def get_merit_gasfired(self, efficiency):
        """
        Computes the merit order of a gasfired plant given its efficiency and the eventual carbon price
        :param efficiency: energetic efficiency of the powerplant
        :return: the merit order value
        """
        if self.carbon_price is None:
            return self.fuels['gas(euro/MWh)'] / efficiency
        return self.fuels['gas(euro/MWh)'] / efficiency * self.carbon_price

    def get_merit_turbojet(self, efficiency):
        """
        Computes the merit order of a turbojet plant given its efficiency and the eventual carbon price
        :param efficiency: energetic efficiency of the powerplant
        :return: the merit order value
        """
        if self.carbon_price is None:
            return self.fuels['kerosine(euro/MWh)'] / efficiency
        return self.fuels['kerosine(euro/MWh)'] / efficiency * self.carbon_price

    @staticmethod
    def get_merit_windturbine():
        """
        Computes the merit order of a wind turbine power plant
        :return: the merit order value
        """
        return 0

    def dispatch_load(self, power_plants):
        """
        Core method of the power dispatch algorithm
        :param power_plants: pandas DataFrame describing the plants
        :return: the formatted json containing the power dispatch
        """
        for _, plant in power_plants.iterrows():
            # Computing how much power left is needed
            self.current_load = self.dispatch_build['p'].sum()
            remaining_load = round(self.required_load - self.current_load, 1)
            # Compute how much power can the current plant handle
            power, overload = self.find_load_for_plant(remaining_load, plant)
            # If the load stays above the plant's pmin, add a new row
            if overload == 0:
                plant_dict = {'name': plant['name'], 'p': power, 'pmin': plant['pmin']}
                self.dispatch_build = self.dispatch_build.append(plant_dict, ignore_index=True)
                logger.info('%sMWh attributed to power plant %s', power, plant['name'])

            else:
                logger.info('Overload of %sMWh detected for plant %s, attempting redistribution', overload, plant['name'])
                self.handle_overload(plant, overload)

            logger.info('Total is now %sMWh', self.current_load)

        self.current_load = self.dispatch_build['p'].sum()
        return self.sort_results()

    def find_load_for_plant(self, remaining_load, plant):
        """
        Computes how much power can a given plant handle
        If the needed load is above the plant's minimum output, the difference between both
        will be considered as an overload to remove from the previous plants
        :param remaining_load: how much power is left to dispatch
        :param plant: dictionary describing the plant
        :return: the amount of power attributed to the plant and the eventual overload
        """
        if remaining_load == 0:
            return 0, 0

        maximal_power = self.find_max_power(plant)
        minimal_power = plant['pmin']

        if remaining_load >= maximal_power:
            return maximal_power, 0

        if remaining_load < minimal_power:
            return minimal_power, round(minimal_power - remaining_load, 1)

        return remaining_load, 0

    def find_max_power(self, plant):
        """
        Computes the maximal power a plant can produce with respect to its type
        :param plant: dictionary describing the plant
        :return: the maximal value in MWh
        """
        if plant['type'] == 'windturbine':
            # Compute the maximal power given the wind conditions
            return plant['pmax'] * self.fuels['wind(%)'] / 100

        return plant['pmax']

    def handle_overload(self, plant, overload):
        """
        Recomputes the power distribution by removing the extra power from the plants of lower order
        Keeps the power plant off if no solution has been found
        :param plant: dictionary describing the plant
        :param overload: the amount of power to remove from the previous plants
        """
        new_dispatch_build = pd.DataFrame(columns=('name', 'p', 'pmin'))
        # Sifting through the dispatch backwards to remove power from plants of lower merit
        for _, previous_plant in self.dispatch_build[::-1].iterrows():
            plant_dict, overload = self.compute_power_reduction(previous_plant, overload)
            new_dispatch_build = new_dispatch_build.append(plant_dict, ignore_index=True)

        if overload == 0:
            self.dispatch_build = new_dispatch_build[::-1]
            plant_dict = {'name': plant['name'], 'p': plant['pmin'], 'pmin': plant['pmin']}
            self.dispatch_build = self.dispatch_build.append(plant_dict, ignore_index=True)
            logger.info('Load corrected:')
            for _, previous_plant in self.dispatch_build.iterrows():
                logger.info('Correction: %sMWh attributed to power plant %s',
                            previous_plant['p'], previous_plant['name'])

        else:
            plant_dict = {'name': plant['name'], 'p': 0, 'pmin': plant['pmin']}
            self.dispatch_build = self.dispatch_build.append(plant_dict, ignore_index=True)
            logger.info('Failed to include power plant %s, 0 attributed', plant['name'])

    @staticmethod
    def compute_power_reduction(previous_plant, overload):
        """
        Compute how much power can be removed from a plant
        :param previous_plant: dictionary describing a plant of lower order
        :param overload: the amount of power to remove from the previous plants
        """
        remaining_power = round(previous_plant['p'] - overload, 1)
        # If the overload is above the power assigned to the plant
        if remaining_power <= 0:
            plant_dict = {'name': previous_plant['name'], 'p': 0, 'pmin': previous_plant['pmin']}
            return plant_dict, -1 * remaining_power

        # If the overload falls within the previous plant's operational range
        elif remaining_power >= previous_plant['pmin']:
            plant_dict = {'name': previous_plant['name'], 'p': remaining_power, 'pmin': previous_plant['pmin']}
            return plant_dict, 0

        # The overload (pmin-remaining_load) would be higher than the previous plant's range (pmax-pmin)
        # While unlikely, it is theoretically possible and is one of the cases where the distribution might fail
        plant_dict = {'name': previous_plant['name'], 'p': previous_plant['pmin'], 'pmin': previous_plant['pmin']}
        remaining_overload = round(previous_plant['pmin'] - remaining_power, 1)
        return plant_dict, remaining_overload

    def sort_results(self):
        """
        Removes the minimal power from the dispatch results and formats the result list
        """
        if self.current_load != self.required_load:
            raise ValueError('Failed to reached the required power load: {}MWh instead of {}MWh required'
                             .format(self.current_load, self.required_load))

        return [{'name': plant['name'], 'p': plant['p']} for _, plant in self.dispatch_build.iterrows()]

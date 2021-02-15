import json
import unittest
import pytest
import pandas as pd

from dispatch_algorithm import PowerDispatcher
from json_checker import JsonChecker


class TestChecker(unittest.TestCase):
    def test_correct_key_value(self):
        assert JsonChecker.key_value_test('key', {'key': 1}, '', int) is None

    def test_missing_key(self):
        with pytest.raises(KeyError) as msg:
            JsonChecker.key_value_test('key', {None: None}, '', None)
        assert msg.value

    def test_wrong_type(self):
        with pytest.raises(TypeError) as msg:
            JsonChecker.key_value_test('key', {'key': 1}, '', str)
        assert msg.value


class TestPowerDispatcher(unittest.TestCase):
    def setUp(self):
        self.payload = {"load": 480, "fuels": {"gas(euro/MWh)": 13.4, "co2(euro/ton)": 20}, "powerplants":
                        [{"name": "gasfiredbig1", "type": "gasfired", "efficiency": 0.53, "pmin": 100, "pmax": 460}]}
        self.power_dispatcher = PowerDispatcher(self.payload, 0.3)

    def test_define_merit_orders(self):
        power_dispatcher = PowerDispatcher(self.payload, 0.3)
        assert len(power_dispatcher.define_merit_orders()) == 1

    def test_fail_merit_order(self):
        self.payload["powerplants"][0]["type"] = 'mock'
        power_dispatcher = PowerDispatcher(self.payload, 0.3)
        with pytest.raises(ValueError) as msg:
            power_dispatcher.define_merit_orders()

        assert msg.value

    def test_get_merit_plant(self):
        power_dispatcher = PowerDispatcher(self.payload, 0.3)
        assert isinstance(power_dispatcher.get_merit_plant(self.payload['powerplants'][0]), float)

    def test_fail_merit_plant_zero(self):
        self.payload["powerplants"][0]["efficiency"] = 0
        power_dispatcher = PowerDispatcher(self.payload, 0.3)
        with pytest.raises(ValueError) as msg:
            power_dispatcher.get_merit_plant(self.payload['powerplants'][0])
        assert msg.value

    def test_get_merit_gasfired(self):
        power_dispatcher = PowerDispatcher(self.payload, 0.3)
        assert isinstance(power_dispatcher.get_merit_gasfired(self.payload['powerplants'][0]['efficiency']), float)

    def test_get_merit_turbojet(self):
        power_dispatcher = PowerDispatcher(self.payload, None)
        self.payload["fuels"]["kerosine(euro/MWh)"] = 50.8
        assert isinstance(power_dispatcher.get_merit_turbojet(self.payload['powerplants'][0]['efficiency']), float)

    def test_dispatch_load_default(self):
        pmax = self.power_dispatcher.required_load
        power_plants = pd.DataFrame(
            {"name": ["gasfiredbig1"], "type": ["gasfired"], "efficiency": [0.53], "pmin": [100], "pmax": [pmax]})
        self.power_dispatcher.dispatch_load(power_plants)

    def test_dispatch_load_overload(self):
        power_plants = pd.DataFrame({"name": ["gasfiredbig1", "gasfiredbig2"], "type": ["gasfired", "gasfired"],
                                     "efficiency": [0.53, 0.53], "pmin": [100, 100], "pmax": [460, 460]})
        assert self.power_dispatcher.dispatch_load(power_plants)

    def test_find_load_for_plant_zero(self):
        assert self.power_dispatcher.find_load_for_plant(0, None) == (0, 0)

    def test_find_load_for_plant_max(self):
        pmax = 100
        plant = {'type': 'gasfired', 'pmin': 0, 'pmax': pmax}
        assert self.power_dispatcher.find_load_for_plant(pmax, plant) == (pmax, 0)

    def test_find_load_for_plant_min(self):
        pmin = 100
        plant = {'type': 'gasfired', 'pmin': pmin, 'pmax': pmin*2}
        assert self.power_dispatcher.find_load_for_plant(pmin/2, plant) == (pmin, pmin/2)

    def test_find_load_for_plant_default(self):
        p = 100
        plant = {'type': 'gasfired', 'pmin': p/2, 'pmax': p*2}
        assert self.power_dispatcher.find_load_for_plant(p, plant) == (p, 0)

    def test_define_max_power(self):
        plant = {'type': 'gasfired', 'pmin': 100, 'pmax': 200}
        assert self.power_dispatcher.find_max_power(plant) == 200

    def test_define_max_power_wind(self):
        self.payload['fuels']['wind(%)'] = 50
        power_dispatcher = PowerDispatcher(self.payload, None)
        plant = {'type': 'windturbine', 'pmin': 0, 'pmax': 200}
        assert power_dispatcher.find_max_power(plant) == 100

    def test_handle_overload_success(self):
        plant = {'name': 'gasfiredbig1', 'p': 100, 'pmin': 100}
        self.power_dispatcher.handle_overload(plant, 5)
        assert self.power_dispatcher.dispatch_build['p'][0] == 0

    def test_handle_overload_failure(self):
        plant = {'name': 'gasfiredbig1', 'p': 100, 'pmin': 100}
        self.power_dispatcher.handle_overload(plant, 0)
        assert self.power_dispatcher.dispatch_build['p'][0] == 100

    def test_compute_power_reduction_null(self):
        previous_plant = {'name': 'gasfiredbig1', 'p': 100, 'pmin': 0}
        overload = 200
        plant_dict, remaining = self.power_dispatcher.compute_power_reduction(previous_plant, overload)
        assert plant_dict['p'] == 0
        assert remaining == overload - previous_plant['p']

    def test_compute_power_reduction_partial(self):
        previous_plant = {'name': 'gasfiredbig1', 'p': 200, 'pmin': 0}
        overload = 100
        plant_dict, remaining = self.power_dispatcher.compute_power_reduction(previous_plant, overload)
        assert plant_dict['p'] == overload
        assert remaining == 0

    def test_compute_power_reduction_ignore(self):
        previous_plant = {'name': 'gasfiredbig1', 'p': 300, 'pmin': 200}
        overload = 200
        plant_dict, remaining = self.power_dispatcher.compute_power_reduction(previous_plant, overload)
        assert plant_dict['p'] == previous_plant['pmin']
        assert remaining == overload - (previous_plant['p'] - previous_plant['pmin'])

    def test_sort_results_fail(self):
        with pytest.raises(ValueError) as msg:
            # required_load is 480 from setUp, current_load is 0
            self.power_dispatcher.sort_results()

        assert msg.value

    def test_sort_results_default(self):
        self.power_dispatcher.dispatch_build = pd.DataFrame({'name': ['plant1'], 'p': [1], 'pmin': [0]})
        self.power_dispatcher.current_load = 1
        self.power_dispatcher.required_load = 1
        results = self.power_dispatcher.sort_results()
        assert isinstance(results, list)
        assert len(results) == 1
        assert len(results[0].keys()) == 2

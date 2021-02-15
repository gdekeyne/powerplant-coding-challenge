"""
This module focuses on input validation
"""


class JsonChecker:
    """
    Validates the content of the input data for the Dispatcher initialization
    """
    def __init__(self, payload):
        self.payload = payload

    @staticmethod
    def key_value_test(key, dictionary, place, value_type):
        """
        Checks that an element from the input json exists and is of the right type
        :param key: a string linking to the value under test
        :param dictionary: the element of the payload to test
        :param place: the data's location in the input json
        :param value_type: the type that the value must have
        :return: an error message for the user, or nothing
        """
        if key not in dictionary:
            raise KeyError('Key {} missing from {}'.format(key, place))

        if not isinstance(dictionary[key], value_type):
            raise TypeError('Key {} in {} links to {} value instead of {}'
                            .format(key, place, type(dictionary[key]), value_type))

    def test_load(self):
        """
        Tests the load value in the payload input json
        """
        self.key_value_test('load', self.payload, 'payload json', (int, float))

    def test_fuels(self):
        """
        Tests the fuels names and values in the payload input json
        """
        self.key_value_test('fuels', self.payload, 'payload json', dict)
        self.key_value_test('gas(euro/MWh)', self.payload['fuels'], 'fuels dictionary', (int, float))
        self.key_value_test('kerosine(euro/MWh)', self.payload['fuels'], 'fuels dictionary', (int, float))
        self.key_value_test('co2(euro/ton)', self.payload['fuels'], 'fuels dictionary', (int, float))
        self.key_value_test('wind(%)', self.payload['fuels'], 'fuels dictionary', (int, float))

    def test_powerplants(self):
        """
        Tests the keys and values for each power plant
        """
        self.key_value_test('powerplants', self.payload, 'payload json', list)
        for n, powerplant in enumerate(self.payload['powerplants']):
            if not isinstance(powerplant, dict):
                raise TypeError('Power plant number {} isn\'t a dictionary'.format(n))

            self.key_value_test('name', powerplant, 'power plant number {}'.format(n), str)
            self.key_value_test('type', powerplant, 'power plant number {}'.format(n), str)
            self.key_value_test('pmin', powerplant, 'power plant number {}'.format(n), (int, float))
            self.key_value_test('pmax', powerplant, 'power plant number {}'.format(n), (int, float))
            self.key_value_test('efficiency', powerplant, 'power plant number {}'.format(n), (int, float))

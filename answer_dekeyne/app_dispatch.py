
import json
import logging as log

from flask import Flask, request
from flask import jsonify

from dispatch_algorithm import PowerDispatcher
from json_checker import JsonChecker


log.basicConfig(level=log.DEBUG)
log.StreamHandler()

logger = log.getLogger()

app = Flask(__name__)


@app.errorhandler(KeyError)
def server_error(err):
    app.logger.exception(err)
    return "Key error: " + str(err) + ', 500\n'


@app.errorhandler(TypeError)
def server_error(err):
    app.logger.exception(err)
    return "Type error: " + str(err) + ', 500\n'


@app.errorhandler(ValueError)
def server_error(err):
    app.logger.exception(err)
    return "Value error: " + str(err) + ', 500\n'


@app.route('/productionplan', endpoint='productionplan', methods=['POST'])
def app_dispatch():
    logger.info('Loading input json payload')
    data = json.loads(request.get_data())

    if 'payload' not in data.keys():
        return KeyError('payload not specified')

    payload = data['payload']

    if 'carbon' not in data.keys():
        carbon = None
    else:
        try:
            carbon = float(data['carbon'])
        except ValueError:
            raise ValueError('cannot convert carbon value {} to float'.format(data['carbon']))

    logger.info('Testing the input json data')
    json_tester = JsonChecker(payload)
    logger.info('Testing the specified load')
    json_tester.test_load()
    logger.info('Testing the fuels content')
    json_tester.test_fuels()
    logger.info('Testing the power plants description')
    json_tester.test_powerplants()
    logger.info('Testing complete, the input json is valid')

    logger.info('Creating power dispatcher')
    power_dispatcher = PowerDispatcher(payload, carbon)
    logger.info('Defining merit order for each plant')
    merit_order = power_dispatcher.define_merit_orders()
    logger.info('Dispatching load')
    load_dispatch = power_dispatcher.dispatch_load(merit_order)
    logger.info('Returning results as json')

    return jsonify(load_dispatch)


if __name__ == '__main__':
    app.run(port='8888')

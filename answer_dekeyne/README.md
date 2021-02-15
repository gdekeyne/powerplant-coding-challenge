### Introduction
This app computes an energy distribution over several power plants for a given input json payload data
using a flask application. It is divided into three main component:

* app_dispatch.py is the flask application
* json_checkers.py contains a batch of test to validate the input data
* dispatch_algorithm.py contains the algorithmic component called by the application

### How to run
Run the flask app in a terminal:
```
python app_dispatch.py
```

Then request with a payload:
```
curl -X POST --data "{\"payload\": $(cat /PATH/TO/PAYLOAD.json)}" http://localhost:8888/productionplan
```

Or request with carbon value:
```
curl -X POST --data "{\"payload\": $(cat /PATH/TO/PAYLOAD.json), \"carbon\": \"0.3\"}" http://localhost:8888/productionplan
```

Use a function to make contiguous runs easier:
```
function powerrun() {
curl -X POST --data "{\"payload\": $(cat $1), \"carbon\": \"0.3\"}" http://localhost:8888/productionplan
}
```

Fill the "payload" with the local path to the json example payload in "payload",
and the "carbon" emission per MWh in "carbon" 

Run the unit tests:
```
python -m unittest unit_tests.py
```
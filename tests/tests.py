import json
import os
from dome.config import TREATMENT_MODE, MODEL_SERVICE, MODELS_API_URLS

class Test:
    def __init__(self, input_file, output_file):
        self.output_file = output_file
        self.input_file = input_file
        self.input = self.read(self.input_file)
        self.generated_response = ""
        self.previous_output = self.read(self.output_file)
        print(self.previous_output)
        self.find_intent = ""
        self.find_entity = ""
        self.model = ""
        self.output = []
        self.treatment_flow = []
        self.treatment_used = ""
    
    def read(self, file_name):
        try:
            data = os.path.abspath(os.path.join(os.path.dirname(__file__), file_name))
            with open(data, 'r') as file:
                return json.load(file)
        except Exception as e:
            return []

    def write(self):
        print("ESCREVEU")
        final_output = self.previous_output + self.output
        output_file = os.path.abspath(os.path.join(os.path.dirname(__file__), self.output_file))
        with open(output_file, 'w') as file:
            json.dump(final_output, file, indent=4)

    def add_treatment_flow(self):
        print("add treatment flow")
        print(self.treatment_used)
        if not self.treatment_used:
            return
        self.treatment_flow.append(self.treatment_used)
        self.treatment_used=''

    def add_treatment(self, treatment):
        self.treatment_used = treatment

    def add_intent(self, intent):
        self.find_intent = intent

    def add_entity(self, entity):
        self.find_entity = entity

    def add_model(self, model):
        if MODEL_SERVICE == 'huggingface':
            self.model = MODELS_API_URLS[0][model]
        else:
            self.model = MODELS_API_URLS[1][model]

    def add_treatment_type(self, treatment):
        if treatment == 'string_and_treatment' or treatment == 'string_noise_treatment':
            return 'string treatment'
        else:
            return 'LLM answer treatment'

    def insert_data(self, index):
        new_output = {'id' : index+1,
                      'input' : self.input[index]['input'], 
                      'expected_result' : self.input[index]['expected_result'], 
                      'find_intent' : self.find_intent,
                      'find_entity' : self.find_entity,
                      'generated_result' : self.generated_response}
        print(self.input[index])
        print(new_output)
        new_output['treatments_used'] = []
        if self.generated_response:
            for list_index, keys in enumerate(self.generated_response.keys()):
                if list_index >= len(self.treatment_flow)+1:
                    print('breko')
                    break
                if not self.generated_response[keys]: 
                    continue
                print('keys')
                print(list_index)
                print(keys)
                print("treatment_flow")
                print(self.treatment_flow)
                if self.treatment_flow:
                    if TREATMENT_MODE and list_index <= len(self.treatment_flow)-1:
                        print("treatment_flow")
                        print(self.treatment_flow)
                        print(self.treatment_flow[list_index])
                        treatment_json = {}
                        treatment_json[keys] = self.generated_response[keys]
                        treatment_json['model'] = self.model
                        treatment_json['treatment'] = self.treatment_flow[list_index]
                        treatment_json['treatment type'] = self.add_treatment_type(self.treatment_flow[list_index])
                        new_output['treatments_used'].append(treatment_json)
                    else:
                        new_output['treatments_used'].append("None")
        else:
            new_output['treatments_used'].append("None")

        valid = False

        for keys in self.input[index]['expected_result'].keys():
            if not keys in self.generated_response:
                print("generated response")
                print(self.generated_response)
                print(keys)
                valid = False
                break
            if self.generated_response[keys].lower() == self.input[index]['expected_result'][keys].lower():
                valid = True
                continue
            print("generated response")
            print(self.generated_response[keys])
            print(self.input[index]['expected_result'][keys])
            valid = False
            break
            
        new_output['valid'] = valid
        self.output.append(new_output)
        self.generated_query = ""
        self.generated_response = ""
        self.treatment_flow = []
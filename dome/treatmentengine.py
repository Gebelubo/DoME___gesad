import tests.tests
import dome.config as config
import re


class TreatmentEngine:
    def __init__(self, parser, test):
        self.__MP = parser
        self.__AIE = self.__MP.get_ai_engine()
        self.entity = self.__MP.entity_class
        self.user_msg = self.__MP.user_msg
        self.tokens = self.__MP.tokens
        self.__Test = test
        self.__TM = TreatmentManager(ResponseChecker(self, test), ResponseFixer(self, test), test)
        self.model_used = 0

    def treat(self, value, key='', request='get_attribute', processed_attributes=''):

        if not config.TREATMENT_MODE:
            print("no treatments")
            return value

        print("value")
        print(value)
        new_response = re.sub(r'^\s+|\s+$', '', value)
        new_response = new_response.replace('=', '').replace("'", '').replace('"', '').replace('\\', '').replace('/','').replace('`', '').replace('´', '').replace('\n', ' ')

        new_response = self.__TM.manage(key, new_response, request, processed_attributes)
        print("new response")
        print(new_response)
        if not self.response_validate(request, {key: new_response}):
            self.change_model()
            new_response = self.__TM.manage(key, value, request, processed_attributes)
        if not self.response_validate(request, {key: new_response}):
            self.__Test.add_treatment("None")
            self.__Test.add_treatment_flow()
            return value
        self.__Test.add_model(self.model_used)
        self.__Test.add_treatment_flow()
        new_response = re.sub(r'^\s+|\s+$', '', new_response)
        return new_response

    def tokenize(self, msg):
        return self.__AIE.posTagMsg(msg)

    def question_answerer_remote(self, question, context):
        return self.__AIE.question_answerer_remote(question, context, '', False, self.model_used)

    def response_validate(self, request, response):
        if self.__TM.response_validate(request, response):
            return True
        return False

    def change_model(self):
        if self.model_used == 0:
            self.model_used = 1
        else:
            self.model_used = 0

class TreatmentManager:
    def __init__(self, checker_obj, fixer_obj, Test):
        self.__RC = checker_obj
        self.__RF = fixer_obj
        self.__Test = Test

    def manage(self, key, value, request, processed_attributes):
        if request == 'get_attribute':
            return self.manage_attributes(key, value, request, processed_attributes)
        elif request == 'get_intent':
            return self.manage_intent(value)
        elif request == 'get_entity':
            return self.manage_entity(value)
        elif request == 'get_where_clause':
            return self.manage_where_clause(value, request, processed_attributes)

    def manage_attributes(self, key, value, request, processed_attributes):
        
        value = self.__RF.search_answer(key, value) # UPDATE SUGESTION: see if it is a treatment
        self.__Test.add_treatment("search_treatment")

        valid = self.__RC.check(key, value, request, processed_attributes)

        if valid:
            print("retornou logo")
            return value

        # first we will try to change the prompt to treat
        new_value = self.manage_prompt(key, request, processed_attributes)
        if new_value is not "":
            print("vai retornar 2")
            return new_value
        
        new_value = self.__RF.searching_treatment(key, value)
        if self.__RC.check(key, new_value, request, processed_attributes):
            return new_value
        
        # if not work try to find anyway
        new_value = self.__RF.string_and_treatment(key)
        if self.__RC.check(key, new_value, request, processed_attributes):
            return new_value
        
        new_value = self.__RF.string_noise_treatment(key)
        if self.__RC.check(key, new_value, request, processed_attributes):
            return new_value

        return value

    def manage_intent(self, value):
        return self.__RF.search_intent(value)

    def manage_entity(self, value):
        return self.__RF.search_entity(value)
    
    def manage_where_clause(self, value, request, processed_attributes):
        valid = self.__RC.check('', value, request, processed_attributes)

        if valid:
            return value 
        
        new_value = self.__RF.search_where_clause(value)
        if self.__RC.check('', new_value, request, processed_attributes):
            print("vai retornar certim ebaaa")
            return new_value
        
        new_value = self.manage_prompt('', request, processed_attributes)
        if new_value is not None:
            return new_value
        
        return value
        


    
    def manage_prompt(self, key, request, processed_attributes):
        if request == 'get_attribute':
            prompts = ["simplified_all", "simplified_question", "invalid_and", "invalid_comma", "simplified_max"]
        elif request == 'get_where_clause':
            prompts = ['where_clause_simplified']
        for prompt in prompts:
            print(prompt)
            print(key)
            new_value = self.__RF.prompt_treatment(key, prompt)
            if request == 'get_attribute':
                new_value = self.__RF.search_answer(key, new_value)
            if self.__RC.check(key, new_value, request, processed_attributes):
                print("vai retornar 1")
                print(new_value)
                return new_value
        return ""

    def response_validate(self, request, response):

        if request == 'get_attribute':
            keys = list(response.keys())

            for key in keys:
                if self.__RC.check(key, response[key], request, response):
                    return True

            return False
        else:
            return True


class ResponseChecker:
    def __init__(self, treatment_engine, test):
        self.__TE = treatment_engine
        self.__Test = test
        self.entity = self.__TE.entity
        self.tokens = self.__TE.tokens
        self.user_msg = self.__TE.user_msg

    def check(self, key, value, request, processed_attributes):
        if request == 'get_attribute':
            methods = [self.len_test, self.key_test, self.and_test, self.entity_test, self.attributes_test, self.pronoun_test,
                        self.ignoring_test, self.float_test, self.character_test]
        elif request == 'get_where_clause':
            methods = [self.len_test, self.where_clause_format_test]
        for method in methods: # UPDATE SUGESTION: run all checks and fix only the ones that breaks
            if method(key, value, processed_attributes) == False:  # args[0], args[1], args[2]
                print(str(method))
                return False
        return True
    
    def len_test(self, *args):
        if len(args[1])<=0:
            print("ta empty")
            return False
        return True

    def key_test(self, *args):
        if args[0].lower() == args[1].lower():  # if the attribute value is equal to the name
            return False
        elif args[0].lower().strip() == args[1].lower().strip():
            return False
        return True

    def and_test(self, *args): 
        if " and " in args[1]:  # if there is "and" in the answer
            return False
        return True

    def entity_test(self, *args):
        if self.entity.lower() == args[1].lower():  # if the entity name is in the attribute value
            return False
        elif self.entity.lower().strip() == args[1].lower().strip():
            return False
        return True

    def attributes_test(self, *args): 
        if args[2] is not None:  # if some other attribute name is in the attribute value
            for keys in list(args[2].keys()):
                if keys == args[1]:
                    return False
        return True

    def pronoun_test(self, *args): 
        tokens = self.__TE.tokenize(args[1])
        propn = False
        for token in tokens:  # if there is a pronoun followed by a comma
            if propn == True and token['entity'] == 'PUNCT':
                return False
            if token['entity'] == 'PROPN':
                propn = True
        return True

    def ignoring_test(self, *args): 
        key_find = False
        tokens_entity = list()
        for token in self.tokens:  # discovering if it is ignoring relevant attributes
            if token['word'] is not None:
                if token['word'] == args[0] and key_find == False:
                    key_find = True
                    continue
                if key_find:
                    if token['word'] in args[1].lower():
                        break
                    tokens_entity.append(token['entity'])

        if 'PROPN' in tokens_entity or 'NUM' in tokens_entity:
            return False
        return True

    def float_test(self, *args): 
        float_find = None
        j = 0
        while j < len(self.tokens):
            if self.tokens[j]['entity'] == 'PUNCT' and j > 0:
                if j+1<len(self.tokens):
                    if self.tokens[j + 1]['entity'] == 'NUM' and self.tokens[j - 1]['entity'] == 'NUM':
                        # exists a float number in the original mensage
                        float_find = self.tokens[j - 1]['word']
            j += 1

        if float_find is None:
            return True

        if float_find in args[1] and (',' not in args[1] and '.' not in args[1]):
            return False

        return True

    def character_test(self, *args): 
        tokens = self.__TE.tokenize(args[1])
        potential_value = False
        for token in tokens:  # if there is some "noise character" on the final answer
            if potential_value == True and token['entity'] == 'SYM':
                return False
            if token['entity'] == 'PROPN' or token['entity'] == 'NUM':
                potential_value = True
        return True
    
    def where_clause_format_test(self, *args):
        if args[1] in self.user_msg:
            return True
        return False


class ResponseFixer:
    def __init__(self, treatment_engine, test):
        self.__TE = treatment_engine
        self.__Test = test
        self.entity = self.__TE.entity
        self.user_msg = self.__TE.user_msg
        self.tokens = self.__TE.tokens

    def prompt_treatment(self, key, prompt):


        if key is None:
            # error
            return None

        question = "What is the '" + key + "' in the sentence fragment?"
        context = ''

        question += "\nThis is the user command: '" + self.user_msg + "'."
        question += "\nThe entity class is '" + str(self.entity) + "'."

        if prompt == "simplified_all":  # simplifying the prompt
            fragment_short = self.user_msg[self.user_msg.find(key) + len(key):]
            context = 'The answer is a substring of "' + fragment_short + '".'
            self.__Test.add_treatment("simplified_all_treatment")
        elif prompt == "simplified_question":  # simplifying the question and enhancing the context
            question = "What is the '" + key + "' in the sentence fragment?"
            fragment_short = self.user_msg[self.user_msg.find(key) + len(key):]
            context = "\nThis is the user command: '" + self.user_msg + "'."
            context += 'The answer is a substring of "' + fragment_short + '".'
            self.__Test.add_treatment("simplified_question_treatment")
        elif prompt == "invalid_and":  # case the answer is returning a word after an 'and'
            fragment_short = self.user_msg[self.user_msg.find(key) + len(key):]
            fragment_short = fragment_short.split('and')[0]
            context = 'The answer is a substring of "' + fragment_short + '".'
            self.__Test.add_treatment("invalid_and_treatment")
        elif prompt == "invalid_comma":  # case the answer is returning a word after an invalid ','
            fragment_short = self.user_msg[self.user_msg.find(key) + len(key):]
            fragment_short = fragment_short.split(',')[0]
            context = 'The answer is a substring of "' + fragment_short + '".'
            self.__Test.add_treatment("invalid_comma_treatment")
        elif prompt == "simplified_max":
            question = (
    f"Identify the value assigned to '{key}' in the following user command. Return only the value. "
    f"value mentioned in the user command. Return only the value. \n\nUser command: '{self.user_msg}' "
    f"\nValue of '{key}': "
            )   
            self.__Test.add_treatment("simplified_max_treatment")
        elif prompt == "where_clause_simplified":
            question = f'What is the where clause in the folowing mensage: "{self.user_msg}". \nReturn only the attribute mentioned.'
            context = 'Return only one word'
        else:
            context = ''
            fragment_short = ''

        response = self.__TE.question_answerer_remote(question, context)
        print(response)
        if response['answer'] is not None and response['answer'] != 'None':
            return re.sub(r'^\s+|\s+$', '', response['answer'])
        else:
            return re.sub(r'^\s+|\s+$', '', fragment_short)

    def searching_treatment(self, key, value):
        print("searching")
        print(value)
        self.__Test.add_treatment("searching_treatment")
        list_value = value.replace('\n', ' ')
        list_value = value.split()
        answer = ''
        print(list_value)
        fragment_short = self.user_msg[self.user_msg.find(key) + len(key):]
        for word in list_value:
            print(word)
            if word.isalnum():
                if word in fragment_short:
                    print("vai retornar")
                    print(word)
                    answer = word
                    break
        if not answer:
            print("retornou value")
            answer = value
        answer = answer.replace('=', '').replace("'", '').replace('"', '').replace('\\', '').replace('/','')
        return re.sub(r'^\s+|\s+$', '', answer)

    def string_and_treatment(self, key):
        # getting everything after the attribute key and before an addition marker
        fragment_short = self.user_msg[self.user_msg.find(key) + len(key):]
        fragment_short = fragment_short.split(' and ')[0]
        self.__Test.add_treatment("string_and_treatment")
        return re.sub(r'^\s+|\s+$', '', fragment_short)
    
    def string_noise_treatment(self, key):
        fragment_short = self.user_msg[self.user_msg.find(key) + len(key):]
        fragment_short = fragment_short.replace('=', '').replace("'", '').replace('"', '')
        self.__Test.add_treatment("string_noise_treatment")
        return fragment_short
    
    def where_clause_normalize(self, value):
        #try to find by the pattern
        sub_normalized = re.sub(r'\s*=\s*', '=', value)

        pattern = re.compile(r'\b' + re.escape(sub_normalized).replace('=', r'\s*=\s*') + r'\b')
        match = pattern.search(self.user_msg)
        print("subnormalized")
        print(sub_normalized)
        if match:
            match = match.group()
            print("match")
            print(match)
            return match
        return value
    
    def search_intent(self, value):
        options = [' Yes ', ' No ', ' CREATE ', ' READ ', ' UPDATE ', ' DELETE ']
        for option in options:
            if option in value:
                return re.sub(r'^\s+|\s+$', '', option)
            
        #trying to find anyway
        for option in options:
            if re.sub(r'^\s+|\s+$', '', option) in value:
                return re.sub(r'^\s+|\s+$', '', option)
        return ''
    
    def search_entity(self, value):
        entity_candidates = []
        for token in self.tokens:
            if token['entity'] == 'NOUN' or token['entity'] == 'PROPN':
                entity_candidates.append(token['word'])
        for entity in entity_candidates:
            if entity in value:
                return re.sub(r'^\s+|\s+$', '', entity)
        if entity_candidates:
            return re.sub(r'^\s+|\s+$', '', entity_candidates[0])
        else:
            return ''

    def search_where_clause(self, value):
        keywords = ['when', 'where', 'which', 'whose', 'with']
        fragment_short = ''
        index = -1
        for word in keywords:
            index = self.user_msg.find(word)
            if index != -1:
                fragment_short = self.user_msg[index + len(word):]
                break
        
        fragment_short = fragment_short.replace('=', ' ').replace(',', '')
        words_list = fragment_short.split(' ')
        new_list = []
        #cleaning the list
        for word in words_list:
            print(word)
            if word != '=':
                print("replece")
                word = word.replace('=', ' ')
                print(word)
            if word:
                new_list.append(word)

        print("words list")
        print(new_list)
        possible_answer = []

        for word in new_list:
            if word in value:
                if word != '':
                    possible_answer.append(word)

        print("possible answer")
        print(possible_answer)

        response=''

        if '=' in possible_answer and '=' not in possible_answer[0]:
            response = '' + possible_answer[possible_answer.find('=')-1] + ' = ' + possible_answer[possible_answer.find('=')+1]
        elif index != -1 and len(possible_answer)>=2:
            print('vai retornar isso aqui')
            response = possible_answer[0] + ' = ' + possible_answer[1]
        if response:
            self.__Test.add_treatment("where_clause_search_treatment")
            return self.where_clause_normalize(response)
        return value


    def search_answer(self, key, value):
        print("will search")
        value_list = value.split(' ')
        value_list = list(filter(lambda x: x != '', value_list))
        fragment_short = ' ' + self.user_msg[self.user_msg.find(key) + len(key):] + ' '
        print(value_list)
        fragment_short=fragment_short.replace('=', ' ').replace(',', ' ').replace('.', ' ')
        print(fragment_short)
        answer_list = []
        for word in value_list:
            if word.startswith('"') and word.endswith('"'):
                word = word[1:-1]
            print(word)
            single_word = ' ' + word.replace('\n', '') + ' '
            if single_word in fragment_short:
                print("Passou um")
                if word not in answer_list:
                    print("passou dois")
                    if len(word.strip())>0:
                        print("apendou")
                        print(word)
                        answer_list.append(word)

        if len(answer_list)>0:
            answer = ' '.join(answer_list)
        else:
            #searching anyway
            for word in value_list:
                if word in fragment_short:
                    if word not in answer_list:
                        answer_list.append(word)
            answer = ' '.join(answer_list)

        new_answer = answer

        #extracting only the answer in mensage
        for _ in answer:
            if new_answer in self.user_msg:
                break
            new_answer = new_answer[1:]
        if len(new_answer)>0:
            answer = new_answer
        print("search answer")
        print(answer)
        self.__Test.add_treatment("search_treatment")
        return re.sub(r'^\s+|\s+$', '', answer)
    

import json, re
from common.container.qapair import QApair
from common.container.uri import Uri
from kb.dbpedia import DBpedia
from parser.answerparser import AnswerParser



class LC_Qaud:
    def __init__(self, path="./data/LC-QUAD/data_v8.json"):
        self.raw_data = []
        self.qapairs = []
        self.path = path
        self.parser = LC_QaudParser()

    def load(self):
        with open(self.path) as data_file:
            self.raw_data = json.load(data_file)

    def parse(self):
        parser = LC_QaudParser()
        for raw_row in self.raw_data:
            sparql_query = raw_row["sparql_query"].replace("DISTINCT COUNT(", "COUNT(DISTINCT ")
            self.qapairs.append(
                QApair(raw_row["corrected_question"], [], sparql_query, raw_row, raw_row["_id"], self.parser))

    def print_pairs(self, n=-1):
        for item in self.qapairs[0:n]:
            print(item)
            print("")


class LC_QaudParser(AnswerParser):
    def __init__(self):
        super(LC_QaudParser, self).__init__(DBpedia(one_hop_bloom_file="./data/blooms/spo1.bloom"))

    def parse_question(self, raw_question):
        return raw_question

    def parse_sparql(self, raw_query):
        uris = [Uri(raw_uri, DBpedia.parse_uri) for raw_uri in re.findall('<[^>]*>', raw_query)]

        return raw_query, True, uris

    def parse_answerset(self, raw_answerset):
        return []

    def parse_answerrow(self, raw_answerrow):
        return []

    def parse_answer(self, answer_type, raw_answer):
        return "", None

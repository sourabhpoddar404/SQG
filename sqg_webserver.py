#!flask/bin/python
import flask
from gevent.pywsgi import WSGIServer
import argparse
from orchestrator import Orchestrator
from common.container.uri import Uri
from common.container.linkeditem import LinkedItem
from parser.lc_quad import LC_QaudParser
from parser.webqsp import WebQSPParser
from learning.classifier.svmclassifier import SVMClassifier
from learning.classifier.naivebayesclassifier import NaiveBayesClassifier
import logging
import common.utility.utility as utility
import sys
import os
import hashlib
from interruptingcow import timeout

app = flask.Flask(__name__)
queryBuilder = None
kb = None
classifier = None
cache_path = "./caches/"
utility.makedirs(cache_path)
hash_file = os.path.join(cache_path, "sqg_webserver.cache")
if os.path.exists(hash_file):
    hash_list = utility.PersistanceDict.load(hash_file)
else:
    hash_list = utility.PersistanceDict()


def hash(input):
    return hashlib.md5(input).hexdigest()


@app.route('/qg/api/v1.0/query', methods=['POST'])
def generate_query():
    if not flask.request.json:
        flask.abort(400)

    question = flask.request.json['question']
    force_count_query = flask.request.json['force_count'] if 'force_count' in flask.request.json else False
    force_bool_query = flask.request.json['force_bool'] if 'force_bool' in flask.request.json else False
    force_list_query = flask.request.json['force_list'] if 'force_list' in flask.request.json else False
    raw_entities = flask.request.json['entities']
    raw_relations = flask.request.json['relations']
    h1_threshold = int(flask.request.json['h1_threshold']) if 'h1_threshold' in flask.request.json else 9999999
    timeout_threshold = int(flask.request.json['timeout']) if 'timeout' in flask.request.json else 9999999
    use_cache = bool(flask.request.json['use_cache']) if 'use_cache' in flask.request.json else True
    update_cache = bool(flask.request.json['update_cache']) if 'update_cache' in flask.request.json else True

    hash_key = hash((str(question) + str(raw_entities) + str(raw_relations) + str(h1_threshold)
                     + str(force_count_query) + str(force_bool_query) + str(force_list_query)).encode('utf-8'))

    if use_cache and hash_key in hash_list:
        return flask.jsonify(hash_list[hash_key]), 201

    logger.info(question)
    entities = []
    for item in raw_entities:
        uris = [Uri(uri["uri"], kb.parse_uri, uri["confidence"]) for uri in item["uris"]]
        entities.append(LinkedItem(item["surface"], uris))


    relations = []
    for item in raw_relations:
        uris = [Uri(uri["uri"], kb.parse_uri, uri["confidence"]) for uri in item["uris"]]
        relations.append(LinkedItem(item["surface"], uris))

    try:
        if len(entities) == 0 or len(relations) == 0:
            raise Exception('Wrong number of input entity/relation!')
        with timeout(timeout_threshold):
            question_type = None
            if force_list_query:
                question_type = 0
            elif force_bool_query:
                question_type = 1
            elif force_count_query:
                question_type = 2

            queries, question_type, type_confidence = queryBuilder.generate_query(question, entities, relations,
                                                                                  h1_threshold,
                                                                                  question_type)
            question_type_str = "list"
            ask_query = False
            count_query = False
            if question_type == 2:
                question_type_str = "count"
                count_query = True
            elif question_type == 1:
                question_type_str = "boolean"
                ask_query = True

            queries = [
                {"query": kb.sparql_query(item["where"], "?u_" + str(item["suggested_id"]), count_query, ask_query),
                 "confidence": item["confidence"]} for item in
                queries]

            result = {'queries': queries, 'type': question_type_str, 'type_confidence': type_confidence}
            if use_cache or update_cache:
                hash_list[hash_key] = result
                hash_list.save(hash_file)
            return flask.jsonify(result), 201
    except RuntimeError as expt:
        logger.error(expt)
        return flask.jsonify({'error': str(expt)}), 408
    except Exception as expt:
        logger.error(expt)
        return flask.jsonify({'error': str(expt)}), 422


@app.errorhandler(404)
def not_found(error):
    return flask.make_response(flask.jsonify({'error': 'Command Not found'}), 404)


if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    utility.setup_logging()

    parser = argparse.ArgumentParser(description='Generate SPARQL query')
    parser.add_argument("--port", help="port", default=5010, type=int, dest="port")
    parser.add_argument("--kb", help="'dbpedia' (default) or 'freebase'", default="dbpedia", dest="kb")
    parser.add_argument("--classifier", help="'svm' (default) or 'naivebayes'", default="svm", dest="classifier")
    args = parser.parse_args()

    if args.kb == "dbpedia":
        parser = LC_QaudParser()
    elif args.kb == "freebase":
        parser = WebQSPParser()

    kb = parser.kb

    if not kb.server_available:
        logger.error("Server is not available. Please check the endpoint at: {}".format(kb.endpoint))
        sys.exit(0)

    base_dir = "./output"
    question_type_classifier_path = os.path.join(base_dir, "question_type_classifier")
    double_relation_classifier_path = os.path.join(base_dir, "double_relation_classifier")
    utility.makedirs(question_type_classifier_path)
    utility.makedirs(double_relation_classifier_path)
    if args.classifier == "svm":
        question_type_classifier = SVMClassifier(os.path.join(question_type_classifier_path, "svm.model"))
        double_relation_classifier = SVMClassifier(os.path.join(double_relation_classifier_path, "svm.model"))
    elif args.classifier == "naivebayes":
        question_type_classifier = NaiveBayesClassifier(os.path.join(question_type_classifier_path, "naivebayes.model"))
        double_relation_classifier = NaiveBayesClassifier(
            os.path.join(double_relation_classifier_path, "naivebayes.model"))

    queryBuilder = Orchestrator(logger, question_type_classifier, double_relation_classifier, parser)
    logger.info("Starting the HTTP server")
    http_server = WSGIServer(('', args.port), app)
    http_server.serve_forever()

# -*- coding: utf-8 -*-
import requests


class ImporterWebUtil(object):

    @staticmethod
    def download(url):
        r = requests.get(url)
        if r.status_code != 200:
            print "! Error {} retrieving url {}\n".format(r.status_code, url)
            return None

        return r

    @staticmethod
    def download_session(url, session):
        # fetch the login page
        session.headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:57.0) Gecko/20100101 Firefox/57.0'}

        # post to the login form
        r = session.post(url=url)

        return r.text

    @staticmethod
    def log_session(url, session, params):
        r = session.post(url=url, data=params)
        if r.status_code == 200:
            return session

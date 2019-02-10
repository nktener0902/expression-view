# coding: utf-8

from bottle import get, post, request, response, run, redirect, Bottle, template, static_file, route, error, default_app
from sympy import *
import numpy.random as npr
from beaker.middleware import SessionMiddleware
import strip_path_middleware as spm
import pymongo
from passlib.apps import custom_app_context as pwd_context
import auth as au
from decimal import Decimal
import common.logger as custom_logger


logger = custom_logger.get_custom_logger(__name__)


class Context:
    def __init__(self):
        self.expression = ''
        self.noise = ''
        self.fineness = ''
        self.x_min_range = ''
        self.x_max_range = ''
        self.comment = ''
        self.plots = []
        self.message = ''

    def json(self):
        return {
            'expression': self.expression,
            'noise': self.noise,
            'fineness': self.fineness,
            'x_min_range': self.x_min_range,
            'x_max_range': self.x_max_range,
            'comment': self.comment,
            'plots': self.plots,
            'message': self.message
        }


class WebApp:
    """is management controller of expression viewer web app"""

    def __init__(self, host='0.0.0.0', port=8080, debug=False, mongo_host='localhost', mongo_port=27017):
        # Initialize web app configuration
        self.host = host
        self.port = port
        self.debug = debug
        # Connect MongoDB
        connection = pymongo.MongoClient(mongo_host, mongo_port)
        db = connection.expression_viewer
        # Initialize session configuration
        collection = db.accounts
        session_opts = {
            'session.type': 'file',
            'session.cookie_expires': 3000,
            'session.data_dir': './sessions',
            'session.auto': True
        }
        self.app = SessionMiddleware(default_app(), session_opts)
        self.app = spm.StripPathMiddleware(self.app)
        self.auth = au.Auth()

        @get('/')
        def view_main_page():
            if session_check():
                context = Context()
                return template('./views/index', context.json())
            else:
                return template('./views/login', {'nomatch': ''})

        def session_check():
            session = request.environ.get('beaker.session')
            if 'user' in session:
                if self.auth.find(session.get('user')):
                    return True
            return False

        @post('/login')
        def login():
            email = request.forms.get('email')
            password = request.forms.get('password')
            hashed_password = pwd_context.hash(password)
            if email is None or password is None:
                return template('./views/login', {'nomatch': ''})
            elif email == '' or password == '':
                return template('./views/login', {'nomatch': 'Please enter your e-mail address and password.'})
            else:
                account = collection.find_one({'email': email})
                if account is not None:
                    if pwd_context.verify(password, account['password']):
                        hashed_email = pwd_context.hash(email)
                        self.auth.login(hashed_email, email)
                        session = request.environ.get('beaker.session')
                        session['user'] = hashed_email
                        return redirect('/')
                else:
                    print("Cound not find account.")
                    return template('./views/login', {'nomatch': 'The e-mail address or password do not match.'})

        @post('/register')
        def register():
            email = request.forms.get('email')
            password = request.forms.get('password')
            hashed_password = pwd_context.hash(password)
            query = {'email': email, 'password': hashed_password}
            if email == "" or password == "":
                return template('./views/login', {'nomatch': 'Registration requires your e-mail address and password.'})
            elif collection.find({'email': email}) is None:
                return template('./views/login', {'nomatch': 'This email has already registered.'})
            else:
                collection.insert_one({'email': email, 'password': hashed_password, 'history': []})
                hashed_email = pwd_context.hash(email)
                self.auth.login(hashed_email, email)
                session = request.environ.get('beaker.session')
                session['user'] = hashed_email
                context = Context()
                return template('./views/index', context.json())

        @get('/logout')
        def logout():
            session = request.environ.get('beaker.session')
            self.auth.logout(session.get('user'))
            if 'user' in session:
                del session['user']
            return redirect('/')

        @get('/history')
        def history_page():
            if not session_check(): redirect('/')
            session = request.environ.get('beaker.session')
            email = self.auth.get_email(session.get('user'))
            history = collection.find_one({'email': email})['history']
            context = {'histories': history}
            return template('./views/history', **context)

        @get('/contact')
        def contact():
            return template('./views/contact')

        @route('/stylesheet/<filename>')
        def server_static(filename):
            return static_file(filename, root='./static/stylesheet')

        @route('/javascript/<filename>')
        def server_static(filename):
            return static_file(filename, root='./static/javascript')

        @route('/favicon/favicon.ico')
        def favicon_static():
            return static_file('favicon.ico', root='./static/pictures')

        @post('/')
        def post_expression():
            if not session_check(): redirect('/')
            expression = request.forms.get('expression')
            noise_function = request.forms.get('noise_function')
            noise = request.forms.get('noise')
            fineness = float(request.forms.get('fineness'))
            x_min_range = float(request.forms.get('x_min_range'))
            x_max_range = float(request.forms.get('x_max_range'))
            comment = request.forms.comment
            x = Symbol('x')
            y = Symbol('y')
            try:
                eq1 = eval(expression)
            except:
                context = {
                    "expression": expression,
                    "noise_function": noise_function,
                    "noise": noise,
                    "fineness": fineness,
                    "x_min_range": x_min_range,
                    "x_max_range": x_max_range,
                    "comment": comment,
                    "plots": [],
                    "message": "Invalid expressoin. Please refer to http://mattpap.github.io/scipy-2011-tutorial/html/basics.html."
                }
                return template('./views/index', **context)
            plots_list = []
            p_x = Decimal(x_min_range)
            while round(float(p_x), 7) <= x_max_range:
                noise_val = 0
                if noise_function == "none":
                    noise_val = 0
                elif noise_function == "uniform":
                    noise_val = npr.rand() * float(noise)
                elif noise_function == "gaussian":
                    noise_val = npr.normal(0, float(noise))
                p_y = eq1.subs([(x, float(p_x))])
                f_p_y = 0
                try:
                    f_p_y = float(p_y)
                except:
                    context = {
                        "expression": expression,
                        "noise_function": noise_function,
                        "noise": noise,
                        "fineness": fineness,
                        "x_min_range": x_min_range,
                        "x_max_range": x_max_range,
                        "comment": comment,
                        "plots": [],
                        "message": "Too complex calcuration such as infinit values. Please review your expression."
                    }
                    return template('./views/index', **context)
                plots_list.append({"x": round(float(p_x), 7), "f": f_p_y + noise_val})
                p_x += Decimal(fineness)
            if noise_function == 'none':
                noise = None
            context = {
                "expression": expression,
                "noise_function": noise_function,
                "noise": noise,
                "fineness": fineness,
                "x_min_range": x_min_range,
                "x_max_range": x_max_range,
                "comment": comment,
                "plots": plots_list,
                "message": ""
            }
            # mongodb
            session = request.environ.get('beaker.session')
            email = self.auth.get_email(session.get('user'))
            history = collection.find_one({'email': email})['history']
            while len(history) > 30:
                del history[-1]
            history.insert(0, context)
            collection.update({'email': email}, {'$set': {'history': history}})
            return template('./views/index', **context)

        @error(404)
        @error(405)
        def error404(error):
            return template('./views/404')

    def start(self):
        run(app=self.app, host=self.host, port=self.port, debug=self.debug, reloader=True)

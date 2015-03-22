from __future__ import print_function
from tornado import gen, web, ioloop, httpserver
from tornado.options import define, options
import json
import mef_tornado as mef
import re, os

define("port", default=8888, help="run on the given port", type=int)
define("production", default=False, help="true if is a production server", type=bool)

class MefJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, mef.Page):
            return [row for row in obj.rows]
        elif isinstance(obj, mef.Row):
            return {"nombre": obj.nombre, "monto": obj.monto}
        else:
            return json.JSONEncoder.default(self, obj)

class IndexHandler(web.RequestHandler):
    def get(self):
        self.render("index.html")

class RucHandler(web.RequestHandler):
    def set_headers(self):
        self.set_header("Content-Type", "application/json; charset=utf-8")

    def get_year_from_path(self, path):
        print("Page path:", path)
        regexp = re.compile("/year:(?P<year>\d+)")
        match = regexp.search(path)
        return match.group("year")
    
    @gen.coroutine
    def get(self, ruc):
        year_page = yield mef.get_by_ruc(ruc)
        pliego_page_future_list = []
        for year in year_page.rows():
            pliego_page_future = year_page.get("pliego", year)
            pliego_page_future_list.append(pliego_page_future)
        pliego_page_list = yield pliego_page_future_list
        pliego_future_dict = {}
        for pliego_page in pliego_page_list:
            year = self.get_year_from_path(pliego_page.path)
            pliego_future_dict[year] = pliego_page.fetch_all()
        pliego_dict = yield pliego_future_dict
        response_dict = {"proveedor": ruc, "pliegos": pliego_dict}
        self.write(json.dumps(response_dict, cls=MefJSONEncoder))

class CategoryHandler(web.RequestHandler):
    def set_headers(self):
        self.set_header("Content-Type", "application/json; charset=utf-8")

    @gen.coroutine
    def get(self, categoria):
        home = yield mef.HomePage()
        page = yield home.get(categoria)
        list_results = yield page.fetch_all()
        response_dict = {"category": categoria, "result": list_results}
        self.write(json.dumps(response_dict, cls=MefJSONEncoder))

class HomeHandler(web.RequestHandler):
    def set_headers(self):
        self.set_header("Content-Type", "application/json; charset=utf-8")

    @gen.coroutine
    def get(self):
        home = yield mef.HomePage()
        self.write(json.dumps(home.rows(), cls=MefJSONEncoder))

handlers = [
    (r"/", web.RedirectHandler, {"url": r"/index.html"}),
    (r"/index\.html", IndexHandler),
    (r"/api/proveedor/([0-9]+)/?", RucHandler),
    (r"/api/(\w+)/?", CategoryHandler),
    (r"/api/?", HomeHandler)
]
settings = {
    "debug": not options.production,
    "compress_response": True,
    "template_path": os.path.join(os.path.dirname(__file__), "templates"),
}

mef_app = web.Application(handlers, **settings)

def deploy_server():
    http_server = httpserver.HTTPServer(mef_app)
    http_server.listen(options.port)
    ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    deploy_server()

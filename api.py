from __future__ import print_function
from tornado import gen, web, ioloop, httpserver
from tornado.options import define, options, parse_command_line
import json
import mef_tornado as mef
import re, os

define("port", default=8888, help="run on the given port", type=int)
define("production", default=False, help="true if is a production server", type=bool)

try:
    parse_command_line()
except:
    pass

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

class ApiBaseHandler(web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Content-Type", "application/json; charset=utf-8")

    def on_connection_close(self):
        # Esto no termina las llamadas asyncronas a get
        raise Exception("Conexion cerrada por el cliente")
        self.finish()

class RucHandler(ApiBaseHandler):
    def get_year_from_path(self, path):
        regexp = re.compile("/year:(?P<year>\d+)")
        match = regexp.search(path)
        return match.group("year")

    def get_row_dict(self, tipo, row):
        return {
            "tipo": tipo,
            "nombre": row.label,
            "monto": row.monto,
            "children": [],
        }

    @gen.coroutine
    def get(self, ruc):
        if len(ruc)!=11:
            self.send_error(400)
        year_page, prov_selected = yield mef.get_by_ruc(ruc)
        if not year_page:
            self.send_error(400)

        prov_dict = self.get_row_dict("proveedor", prov_selected)
        for year in (yield year_page.fetch_all()):
            year_dict = self.get_row_dict("year", year)
            prov_dict["children"].append(year_dict)
            gob_page = yield year_page.get("gobierno", year)

            for gob in (yield gob_page.fetch_all()):
                gob_dict = self.get_row_dict("gobierno", gob)
                year_dict["children"].append(gob_dict)
                sector_page = yield gob_page.get("sector", gob)

                for sector in (yield sector_page.fetch_all()):
                    sector_dict = self.get_row_dict("sector", sector)
                    gob_dict["children"].append(sector_dict)
                    municipio_page = yield sector_page.get("municipio", sector)

                    for municipio in (yield municipio_page.fetch_all()):
                        municipio_dict = self.get_row_dict("municipio", municipio)
                        sector_dict["children"].append(municipio_dict)
                        pliego_page = yield municipio_page.get("pliego", municipio)

                        for pliego in (yield pliego_page.fetch_all()):
                            pliego_dict = self.get_row_dict("pliego", pliego)
                            municipio_dict["children"].append(pliego_dict)

        self.write(json.dumps(prov_dict))


class CategoryHandler(ApiBaseHandler):
    @gen.coroutine
    def get(self, categoria):
        home = yield mef.HomePage()
        page = yield home.get(categoria)
        list_results = yield page.fetch_all()
        response_dict = {"category": categoria, "result": list_results}
        self.write(json.dumps(response_dict, cls=MefJSONEncoder))

class HomeHandler(ApiBaseHandler):
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
    print("Server Listening in port: %d"%options.port)
    ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    deploy_server()

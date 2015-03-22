from __future__ import print_function
from tornado.httpclient import AsyncHTTPClient
from tornado.concurrent import Future
from tornado import gen
from urllib import urlencode
from bs4 import BeautifulSoup
import io
import logging
import time

logger = logging.getLogger("mef")
logger.handlers = []
fhandler = logging.FileHandler(filename='mef_proveedores.log', mode='a')
formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s')
fhandler.setFormatter(formatter)
logger.addHandler(fhandler)
logger.setLevel(logging.INFO)

class Row(object):
    def __init__(self, form_data, row):
        cells = row.find_all("td")
        self.select_id = cells[0].find("input").attrs["value"]
        self.nombre = cells[1].text.strip()
        self.monto = float(cells[2].text.replace(',',''))
        self.form_data = form_data

    def __repr__(self):
        return ('<Row nombre="%s">'%str(self))

    def __unicode__(self):
        prev,name = self.nombre.split(":")
        prev = prev[1:].strip()
        label = u":".join([prev,name])
        return label

    def __str__(self):
        return unicode(self).encode("utf-8")

class NoPage(object):
    def __init__(self, html=""):
        self.html = html
        self.soup = BeautifulSoup(html)
        self.form_data = self._set_form_data()

    def __iter__(self):
        return []
    def __nonzero__(self):
        return False

    def _set_form_data(self):
        inputs = filter(lambda e: e.get("type") not in ("submit","radio"), self.soup.find_all("input"))
        return {input_el.attrs["name"]:input_el.attrs.setdefault("value", None) for input_el in inputs}

    @gen.coroutine
    def fetch_all(self):
        raise gen.Return(None)

class Page(object):
    url = "http://apps5.mineco.gob.pe/proveedor/PageTop.aspx"
    def __init__(self, html, post_form_data=None, path="/home"):
        self.html = html
        self.soup = BeautifulSoup(html)
        self.post_form_data = post_form_data or {}
        self.form_data = self._set_form_data()
        self.path = path
        self.cache = []
        self.cached = False

    def __unicode__(self):
        return "Page:" + self.path

    def __str__(self):
        return unicode(self).encode("utf-8")

    def __repr__(self):
        return ('<Page path="%s">'%str(self))

    def _set_form_data(self):
        inputs = filter(lambda e: e.get("type") not in ("submit","radio"), self.soup.find_all("input"))
        return {input_el.attrs["name"]:input_el.attrs.setdefault("value", None) for input_el in inputs}

    def rows(self):
        """Devuelve una lista de las filas de la tabla"""
        tabla = self.soup.find(class_="Data")
        data = [Row(self.form_data, row) for row in tabla.find_all("tr")]
        return data

    @gen.coroutine
    def navigate(self, form_data, path=None):
        """funcion para hacer las peticiones"""
        url = self.url
        client = AsyncHTTPClient()
        # Form_data de peticion
        post_form_data = self.form_data.copy()
        post_form_data.update(form_data)
        ant_agrupacion = post_form_data["hAntAgrupacion"]
        historico = post_form_data["hHistorico"]
        post_form_data.update({"hHistorico": historico + '/' + ant_agrupacion if historico[-1] != ant_agrupacion else historico})
        # r = req.post(url, post_form_data)
        kargs= {"method": "POST", "body": urlencode(post_form_data)}
        response_future = client.fetch(url, **kargs)
        path = path.strip() if path else self.path
        response = yield response_future
        if not response.error:
            page = Page(response.body, post_form_data, path)
            if page.form_data != self.form_data:
                raise gen.Return(page)
        raise gen.Return(NoPage(response.body))

    @gen.coroutine
    def search_ruc(self, ruc):
        """Funcion para realizar busqueda por ruc"""
        form_data = {
            "__EVENTTARGET": "BtnBuscarRUC",
            "TxtBuscar": ruc,
        }
        page = yield self.navigate(form_data)
        raise gen.Return(page)

    @gen.coroutine
    def get(self, group_name, selected=None):
        """Ayuda a navegar en el buscador de proveedores"""
        lista_names = [ "home", "year", "gobierno", "sector", "pliego", "municipio",
                        "departamento", "provincia", "distrito", "proveedor"]
        if group_name not in lista_names:
            raise gen.Return(NoPage())
        form_data = {"hAgrupacion": str(lista_names.index(group_name)), "hPostedBy": str(1)}
        if not selected:
            selected = self.rows()[0]
        if isinstance(selected, Row):
            selected = selected.select_id
        elif isinstance(select, basestring):
            if not "/" in selected:
                selected += "/"
        form_data.update({"grp1":selected})
        selected_id = selected.split("/")[0].strip()
        params = ":" + selected_id if selected_id else ""
        path = self.path + params + '/' + group_name
        while True:
            page_future = self.navigate(form_data, path)
            page = yield page_future
            excpt = page_future.exception()
            if excpt is not None:
                logger.exception(str(excpt))
                yield gen.sleep(0.1)
                continue
            else:
                break
        raise gen.Return(page)

    @gen.coroutine
    def next_page(self):
        """Devuelve la siguiente pagina. No muta al objeto"""
        paginable = self.soup.find("input", {"name":"Pager1:BtnAdelante"})
        if paginable:
            form_data = {"Pager1:BtnAdelante": ">"}
            page_future = self.navigate(form_data)
            page = yield page_future
            raise gen.Return(page)
        else:
            raise gen.Return(NoPage())

    @property
    @gen.coroutine
    def fetch_next(self):
        """Inspirado en Motor. Consigue la siguiente hoja de resultados.
        Muta al objeto para realizar esto"""
        if self.cached:
            raise gen.Return(False)
        next_page = yield self.next_page()
        if next_page:
            self.cache.extend(self.rows())
            self.html = next_page.html
            self.soup = next_page.soup
            self.post_form_data = next_page.post_form_data
            self.form_data = next_page.form_data
            self.path = next_page.path
            raise gen.Return(True)
        else:
            self.cached = True
            raise gen.Return(False)

    @gen.coroutine
    def fetch_all(self):
        while(yield self.fetch_next):
            pass
        raise gen.Return(self.cache + self.rows())

    def __getitem__(self, i):
        iterable = self.__iter__()
        for _ in range(i+1):
            try:
                item = next(iterable)
            except StopIteration:
                raise IndexError
        return item

@gen.coroutine
def HomePage():
    client = AsyncHTTPClient()
    response = yield client.fetch(Page.url)
    home_page = Page(response.body, path="/home")
    raise gen.Return(home_page)

@gen.coroutine
def get_by_ruc(ruc, btn="year"):
    home = yield HomePage()
    prov_page = yield home.get("proveedor")
    page = yield prov_page.search_ruc(ruc)
    # Verifica si la pagina es valida
    if page:
        rows = page.rows()
        filtr_nombre = [row for row in rows if ruc in row.nombre]
        # Verifica si hay resultados
        if filtr_nombre:
            selected = filtr_nombre[0]
            year_page = yield page.get(btn, selected)
            raise gen.Return((year_page, selected))
    raise gen.Return((NoPage(page.html), None))

from __future__ import print_function
import requests as req
from bs4 import BeautifulSoup
import io
import logging
import time

logger = logging.getLogger()
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

class Page(object):
    def __init__(self, html=None, post_form_data=None, path="/home"):
        if not html:
            self.form_data = None
            html = self.navigate({})
        self.html = html
        self.soup = BeautifulSoup(html)
        self.post_form_data = post_form_data or {}
        self.form_data = self._set_form_data()
        self.path = path

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
        """Devuelve un iterador sobre la data de la tabla"""
        tabla = self.soup.find(class_="Data")
        data = (Row(self.form_data, row) for row in tabla.find_all("tr"))
        return data

    def next_page(self):
        paginable = self.soup.find("input", {"name":"Pager1:BtnAdelante"})
        if paginable:
            form_data = {"Pager1:BtnAdelante": ">"}
            return self.navigate(form_data)
        else:
            return NoPage()

    def navigate(self, form_data, path=None):
        """funcion para hacer las peticiones"""
        url = "http://apps5.mineco.gob.pe/proveedor/PageTop.aspx"
        if not self.form_data:
            return req.get(url).text
        else:
            # Form_data de peticion
            post_form_data = self.form_data.copy()
            post_form_data.update(form_data)
            ant_agrupacion = post_form_data["hAntAgrupacion"]
            historico = post_form_data["hHistorico"]
            post_form_data.update({"hHistorico": historico + '/' + ant_agrupacion if historico[-1] != ant_agrupacion else historico})
            r = req.post(url, post_form_data)
            if r.status_code == req.codes.ok:
                path = path.strip() if path else self.path
                page = Page(r.text, post_form_data, path)
                if page.form_data != self.form_data:
                    return page
            return NoPage(r.text)

    def search_ruc(self, ruc):
        """Funcion para realizar busqueda por ruc"""
        form_data = {
            "__EVENTTARGET": "BtnBuscarRUC",
            "TxtBuscar": ruc,
        }
        return self.navigate(form_data)

    def get(self, group_name, selected=None):
        """Ayuda a navegar en el buscador de proveedores"""
        lista_names = [ "home", "year", "gobierno", "sector", "pliego", "municipio",
                        "departamento", "provincia", "distrito", "proveedor"]
        form_data = {"hAgrupacion": str(lista_names.index(group_name)), "hPostedBy": str(1)}
        if not selected:
            selected = next(iter(self))
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
            try:
                r = self.navigate(form_data, path)
            except req.exceptions.Timeout:
                logging.warning("Timeout Error. Page: %s, Row: %s"(self, selected))
            except req.exceptions.ConnectionError as error:
                errno = error.errno
                err_msg = "ConnectionError"
                if errno == 101:
                    err_msg += (": Esta conectado a internet?")
                logging.warning(err_msg)
                # Esperemos antes de intentar de nuevo
                time.sleep(0.5)
                continue
            except req.exceptions.RequestException as e:
                logging.exception(str(e))
                time.sleep(0.5)
                continue
            else:
                break

        return r

    def __iter__(self):
        def iterable(self):
            page = self
            while True:
                for row in page.rows():
                    yield row
                next_page = self.next_page()
                if next_page:
                    page = next_page
                else:
                    break
        return iterable(self)

    def __getitem__(self, i):
        iterable = self.__iter__()
        for _ in range(i+1):
            try:
                item = next(iterable)
            except StopIteration:
                raise IndexError
        return item

def get_prov(ruc, btn="year"):
    page = Page().get("proveedor").search_ruc(ruc)
    if page:
        rows = page.rows()
        filtr_nombre = [row for row in rows if ruc in row.nombre]
        if filtr_nombre:
            selected = filtr_nombre[0]
            page = page.get(btn, selected)
            return page
    return NoPage(page.html)

if __name__ == "__main__":
    f = io.open("salida_pliegos_proveedores2", "w")
    def done(prov, year, pliego):
        root = u"%s/%s/%s"%(prov, year, pliego)
        name = u">%f"%pliego.monto
        msg = root + name
        print(msg, file=f)


    #Pagina principal
    home_page = Page()
    prov_page = home_page.get("proveedor")
    for prov in prov_page:
        logging.info("/%s"%prov)
        year_page = prov_page.get("year", prov)
        for year in year_page:
            logging.info("/%s/%s"%(prov, year))
            pliego_page = year_page.get("pliego", year)
            for pliego in pliego_page:
                done(prov, year, pliego)

    f.close()

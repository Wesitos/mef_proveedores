from __future__ import print_function
import requests as req
from bs4 import BeautifulSoup


class Row(object):
    def __init__(self, state, row):
        cells = row.find_all("td")
        self.select_id = cells[0].find("input").attrs["value"]
        self.nombre = cells[1].text.encode('utf-8').strip()
        self.monto = float(cells[2].text.replace(',',''))
        self.state = state
        
    def __str__(self):
        return '<Row nombre="%s">'%self.nombre

    __repr__ = __str__
    
class Page(object):
    def __init__(self, html=None, post_form_data=None):
        if not html:
            self.form_data = None
            html = self.navigate({}) 
        self.html = html
        self.soup = BeautifulSoup(html)
        self.post_form_data = post_form_data or {}
        self.form_data = self._set_form_data()
        self.state = self._set_state()
    
    def _set_state(self):
        return self.form_data["__VIEWSTATE"]
    
    def _set_form_data(self):
        inputs = filter(lambda e: e.get("type") not in ("submit","radio"), self.soup.find_all("input"))
        return {input_el.attrs["name"]:input_el.attrs.setdefault("value", None) for input_el in inputs}
    
    def rows(self):
        """Devuelve un iterador sobre la data de la tabla"""
        tabla = self.soup.find(class_="Data")
        data = (Row(self.state, row) for row in tabla.find_all("tr"))
        return data
    
    def next_page(self):
        form_data = {"Pager1:BtnAdelante": ">"}
        return self.navigate(form_data)
    
    def navigate(self, form_data):
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
            #print post_form_data
            if r.status_code == req.codes.ok:
                return Page(r.text, post_form_data)
            elif r.status_code == req.codes.server_error:
                return None
        
    def get(self, group_name, selected=None):
        """Ayuda a navegar en el buscador de proveedores"""
        lista_names = [ "home", "year", "gobierno", "sector", "pliego", "municipio",
                        "departamento", "provincia", "distrito", "proveedor"]
        form_data = {"hAgrupacion": str(lista_names.index(group_name)), "hPostedBy": str(1)}
        if not selected:
            selected = next(iter(self))
        if isinstance(selected, Row):
            form_data.update({"grp1":selected.select_id})        
        elif selected:
            form_data.update({"grp1":selected})
        return self.navigate(form_data)
    
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


if __name__ == "__main__":
    f = open("salida_pliegos_proveedores", "w")
    def done(prov, year, gob, sector, pliego):
        root = "%s/%s/%s/%s/%s"%(prov.nombre, year.nombre, gob.nombre,
                                 sector.nombre, pliego.nombre)
        name = ">%f"%pliego.monto
        print(root + name, file=f)


    #Pagina principal
    home_page = Page()
    prov_page = home_page.get("proveedor")
    for prov in prov_page:
        year_page = prov_page.get("year", prov)
        for year in year_page:
            gob_page = year_page.get("gobierno",year)
            for gob in gob_page:
                sector_page = gob_page.get("sector", gob)
                for sector in sector_page:
                    pliego_page = sector_page.get("pliego", sector)
                    for pliego in pliego_page:
                        done(prov, year, gob, sector, pliego)

    f.close()

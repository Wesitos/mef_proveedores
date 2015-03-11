#!/usr/bin/env python
# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import urllib2
import urllib
from cookielib import CookieJar


#socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9050)
#socket.socket = socks.socksocket

cj = CookieJar()
opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))

domain = "http://apps5.mineco.gob.pe/proveedor/PageTop.aspx"

domain_detalle = "http://www.razonsocialperu.com/empresa/detalle/"


def scrapper(page):

    values = {'__EVENTTARGET': '',
              '__EVENTARGUMENT': '',
              '__VIEWSTATE': '/wEPDwUJODA2Mjc5NjYwDxYEHghPcmRlckRpcgEBAB4IU2VhcmNoQnkLKVtwcm92ZWVkb3IuU2VhcmNoQnksIHByb3ZlZWRvciwgVmVyc2lvbj0xLjAuNTI3NS4yNjQ5MywgQ3VsdHVyZT1uZXV0cmFsLCBQdWJsaWNLZXlUb2tlbj1udWxsABYCZg9kFgQCCw8PFgQeCFJvd0NvdW50At+nGh4HVmlzaWJsZWdkFgQCCQ8WAh4EVGV4dAUyPGI+MTwvYj4gLSA8Yj4yNTA8L2I+IGRlIDxiPjQzMSwwNzE8L2I+IHJlc3VsdGFkb3NkAg0PFgIfBAUMPGI+MSw3MjU8L2I+ZAINDxYCHwNnFgICAw9kFgJmD2QWAgIHDw8WAh8DaGRkZEIgsWQML4bShDwnYoDqufHkVWdi8DesHGSmS1MpCDVb',
              '__EVENTVALIDATION': '/wEdAA+oy/EtT2tk5Wj9bfH7JVrjQ/XnI9JNF8oTY7w8H74w/LPTnR9fOc03xnlp6oT8D8NAwiWIc3ifkY498zcTyDajL8NI3r2BJTed5JhUovWhgQyif6KZc1ESStxnceVeoJ6nfZhfGvB9pDnYk8R04DlDyf3bBtJAsREOSv6Bv5NrawDTwwPrxtqjWLIH1uyteWYkhML6BNfAbMNMh70eHArj4Invb0MbNvZAoosAssfcaRNQgFrBJLXW9t9Im8DSBQZB75oOuKkKInsq/TeFqNARJNHCZxrfWXDJZ+50rUXWXykeI6z8FCyClAytDBydSh5htRMgF3esqDbacE/0eau57Rirxs/hWcBcunD9X96Ycw==',
              'Pager1:TxtPage': page,
              'TxtBuscar': '',
              'hFiltros': '',
              'hAgrupacion': '9',
              'hAntAgrupacion': '9',
              'hHistorico': '0/9',
              'hPostedBy': '0'}

    data = urllib.urlencode(values)
    response = opener.open(domain, data)
    content = BeautifulSoup(response.read(), 'html.parser').find("table", {'class', 'Data'})

    for r in content.findAll("tr"):

        cells = r.findAll("td")
        d = cells[1].getText().encode('utf-8')
        item = d.split(":")
        ruc = ((item[0]).strip()).replace('\xc2\xa0', '')
        rs = ((item[1]).strip())
        total = float((cells[2].getText()).replace(",", ""))

        detalles = opener.open(domain_detalle + ruc)

        detalles_content = BeautifulSoup(detalles.read(), 'html.parser')

        detalles_content = detalles_content.findAll("table")

        detalles = detalles_content[0].findAll("tr")

        data = []

        for d in detalles:
            prov = d.findAll("td")
            proveedores = []
            proveedores.append(ruc)
            proveedores.append(rs)
            proveedores.append(total)
            for x in prov:
                proveedores.append(x.getText().encode("utf-8"))
            data.append(proveedores)
        print data


if __name__ == '__main__':

    for i in range(1, 3):
        scrapper(i)

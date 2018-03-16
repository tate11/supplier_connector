# -*- coding: utf-8 -*-

from lxml import html


class util(object):

    def save_product(listRows):
        fichero = open('./productos_robopolis.csv', 'a')
        obj = csv.writer(fichero, delimiter=';', lineterminator=';\n')
        for row_to_csv in listRows:
            obj.writerow(row_to_csv)

        fichero.close()

    def recover_products_of_url(url):
        page = download(url)
        tree = html.fromstring(page.content)
        xpath_string = '///div[@class="products-grid row-fluid"]/div/h2/a[@href]'
        results = tree.xpath(xpath_string)
        i = 2
        listRows = []
        for detail_product in results:
            if detail_product.attrib.get('href'):
                page_detail = download(detail_product.attrib['href'])
                if page_detail:
                    prod = carga_detalle_producto(i=i, page_detail=page_detail)
                    listRows.append(prod)

        return listRows

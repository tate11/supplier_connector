# -*- coding: utf-8 -*-

import re
from lxml import html
from lxml.html import HtmlElement

import requests
from lxml.etree import XPathEvalError
from odoo import models, fields, api, exceptions

from ImporterWebUtil import ImporterWebUtil


class ImporterProductsSupplierWebCrawler(models.Model):
    _name = 'importer.supplier.webcrawler'
    _description = "Web Crawler for Product's Supplier"

    def _get_expression_result(self, expressions, page_detail):
        result = ''
        try:
            for expression in expressions:
                result = SearchExpression.execute_get_expression(expression=expression, page_detail=page_detail)
                if result:
                    break
            return result
        except Exception, e:
            print str(e)
            return ''

    @api.multi
    def _get_detail_product_from_page(self, page_detail):
        # If the webcrawler hasn't expressions to get data, we go to father to get the expressions
        if not (self.sku_expr_ids) and not (self.price_expr_ids) and \
                not (self.name_expr_ids) and self.parent_crawler_id:
            return self.parent_crawler_id._get_detail_product_from_page(page_detail=page_detail)

        searched_sku = self._get_expression_result(expressions=self.sku_expr_ids, page_detail=page_detail)
        searched_name = self._get_expression_result(expressions=self.name_expr_ids, page_detail=page_detail)
        searched_image = self._get_expression_result(expressions=self.url_image_expr_ids, page_detail=page_detail)
        searched_price = self._get_expression_result(expressions=self.price_expr_ids, page_detail=page_detail)
        searched_stock = self._get_expression_result(expressions=self.stock_expr_ids, page_detail=page_detail)
        searched_short_des = self._get_expression_result(expressions=self.short_description_expr_ids,
                                                         page_detail=page_detail)
        searched_ean = self._get_expression_result(expressions=self.ean_expr_ids, page_detail=page_detail)

        prod = {}

        if searched_sku and searched_name:

            prod['default_code'] = searched_sku[0]
            prod['name'] = searched_name[0]

            if searched_short_des:
                prod['description'] = searched_short_des[0]

            if searched_price and searched_price[0]:
                if ',' in searched_price[0] and '.' in searched_price[0]:
                    searched_price[0] = searched_price[0].replace('.', '').replace(',', '.')
                elif ',' in searched_price[0]:
                    searched_price[0] = searched_price[0].replace(',', '.')
                prod['standard_price'] = re.sub("[^0-9^.]", "", searched_price[0])
                prod['tax_included'] = self._get_taxes_included()

            if searched_image:

                image_list = []
                for url_image in searched_image:
                    image_list.append(
                        (url_image, self.pool.get('base_multi_image.image')._get_image_from_url_cached(
                            self.env['base_multi_image.image'], url_image)))
                prod['urls_image'] = image_list

            if searched_ean:
                prod['barcode'] = searched_ean[0]

            if searched_stock:
                prod['stock'] = searched_stock[0]

            prod['type'] = 'product'
            prod['active'] = True
            prod['purchase_ok'] = True
            prod['sale_ok'] = True

        return prod

    @api.model
    def _get_list_href_product(self, url):
        # Get href of products that we need get the data.
        # If there aren't configuration for import hrefs in self, we search in the father recursevily
        if url:

            list_href = []

            if not (self.product_box_data_expr_ids) and self.parent_crawler_id:
                list_href.extend(self.parent_crawler_id._get_list_href_product(url=url))

            page_content = ImporterWebUtil.download(url)
            url_base = self.get_url_parent()
            for get_expression in self.product_box_data_expr_ids:
                if get_expression.type_expression == 'xpath':
                    tree_detail = html.fromstring(page_content.content, parser=html.HTMLParser(encoding='utf-8'))
                    res_data = tree_detail.xpath(get_expression.expression)
                    if res_data:
                        for url in res_data:
                            if url_base in url:
                                list_href.append(url)
                            else:
                                list_href.append(url_base + url)

                elif get_expression.type_expression == 'regexp':
                    res_data = re.findall(get_expression.expression, page_content.content)
                    if res_data:
                        list_href.extend(res_data)

            return list_href
        return []

    @api.model
    def _get_taxes_included(self):
        if self.importer_id.ensure_one() and self.importer_id.tax_included:
            return self.importer_id.tax_included
        if not self.tax_included and self.parent_crawler_id:
            return self.parent_crawler_id.tax_included
        return False

    @api.model
    def _get_next_pagination_url(self, url, session):
        # Get href of products that we need get the data.
        # If there aren't configuration for import hrefs in self, we search in the father recursevily

        if url:
            if not (self.next_page_expr_href_ids) and self.parent_crawler_id:
                return self.parent_crawler_id._get_next_pagination_url(url=url, session=session)

            if not self.parent_crawler_id and not self.next_page_expr_href_ids:
                raise exceptions.except_orm('Error', 'No está informada la expresión para la paginación')
            else:
                page_content = ImporterWebUtil.download(url)
                url_base = self.get_url_parent()
                for get_expression in self.next_page_expr_href_ids:
                    if get_expression.type_expression == 'xpath':
                        tree_detail = html.fromstring(page_content.content, parser=html.HTMLParser(encoding='utf-8'))
                        res_data = tree_detail.xpath(get_expression.expression)
                        if res_data:
                            next_url = res_data[0]
                            if isinstance(next_url, str):
                                if url_base in next_url:
                                    return next_url
                                else:
                                    return url_base + next_url

                    elif get_expression.type_expression == 'regexp':
                        res_data = re.findall(get_expression.expression, page_content.content)
                        if res_data:
                            return res_data[0]

                return None
        return []

    @api.model
    def _get_data_from_web(self, url, session, urls_navigated):
        list_product = []

        if self.has_pagination:
            next_url = self._get_next_pagination_url(url=url, session=session)
            if next_url and next_url not in urls_navigated:
                urls_navigated.append(next_url)
                list_product.extend(self._get_data_from_web(url=next_url, session=session, urls_navigated=urls_navigated))

        list_href_products = self._get_list_href_product(url)

        if self.get_products:
            # We go around href products and download the page to get data
            for href_product in list_href_products:
                page_detail = self._get_url_content(url=href_product, session=session)
                if page_detail:
                    prod = self._get_detail_product_from_page(page_detail=page_detail)
                    if prod:
                        list_product.append(prod)

        return list_product

    @api.model
    def _get_data_product(self, session=None):
        '''
        This method is called from importer.supplier model to get the data from the web
        and insert it into our odoo database instance.
        :return: list of products that we need to insert
        '''
        list_product = []

        # We throw the recursevely call from the childs webs for example:
        #   supplier.com
        #   suplier.com/catergorie_1.html
        #   suplier.com/catergorie_2.html
        if self.child_crawler_ids:
            for child in self.child_crawler_ids:
                list_product.extend(child._get_data_product(session=session))

        # We get the data from the url that we are processing
        list_product.extend(self._get_data_from_web(url=self.url, session=session, urls_navigated=[]))

        return list_product

    @api.model
    def get_url_login_parent(self):
        if self.parent_crawler_id:
            return self.parent_crawler_id.get_url_parent()

        if self.url_login:
            return self.url_login

        return self.url

    @api.model
    def get_url_parent(self):
        if self.parent_crawler_id:
            return self.parent_crawler_id.get_url_parent()
        return self.url

    @api.model
    def get_params_session(self):
        if self.parent_crawler_id:
            return self.parent_crawler_id.get_params_session()

        dict_params = {}
        if self.params_login_ids:
            for params in self.params_login_ids:
                dict_params[params.name] = params.param
        return dict_params

    @api.model
    def _get_session(self):
        session = requests.session()
        params = self.get_params_session()
        url_login = self.get_url_login_parent()
        session.post(url=url_login, data=params)
        return session

    @api.model
    def _get_url_content(self, url, session):
        if not session:
            session = self._get_session()
        r = session.get(url)
        if r.status_code == 200:
            return r.text
        return ''

    @api.multi
    def import_child_crawlers(self):
        try:
            if self.url:
                page_detail = ImporterWebUtil.download(self.url)
                # Do a bucle on expression to get childs webcrawler
                for child_import in self.child_expr_ids:
                    # Recover urls
                    urls = []
                    for expr in child_import.url_expr_ids:
                        if expr.type_expression == 'xpath':
                            tree_detail = None

                            if isinstance(page_detail, unicode):
                                tree_detail = html.fromstring(page_detail.content, parser=html.HTMLParser(encoding='utf-8'))
                            else:
                                tree_detail = html.fromstring(page_detail, parser=html.HTMLParser(encoding='utf-8'))

                            res_data = tree_detail.xpath(expr.expression)
                            url_base = self.get_url_parent()
                            for data in res_data:
                                if isinstance(data, str):
                                    if url_base in data:
                                        urls.append(data)
                                    else:
                                        urls.append(url_base + data)
                                elif isinstance(data, HtmlElement):
                                    text = data.text
                                    if url_base in text:
                                        urls.append(text)
                                    else:
                                        urls.append(url_base + text)

                    # Recover names
                    names = []
                    for expr in child_import.name_expr_ids:
                        if expr.type_expression == 'xpath':
                            tree_detail = html.fromstring(page_detail.content, parser=html.HTMLParser(encoding='utf-8'))
                            res_data = tree_detail.xpath(expr.expression)
                            for data in res_data:
                                if isinstance(data, str):
                                    names.append(data)
                                elif isinstance(data, HtmlElement):
                                    text = data.text
                                    names.append(text)

                        elif expr.type_expression == 'regexp':
                            res_data = re.findall(expr.expression, page_detail.content)
                            if res_data:
                                for data in res_data:
                                    names.append(data)

                    if len(urls) == len(names):
                        tam = len(urls)
                        i = 0
                        while i < tam:
                            url = urls[i]
                            name = names[i]
                            if not (name):
                                name = url
                            i += 1
                            if not self.child_crawler_ids:
                                self.write({'child_crawler_ids':[(0, 0, {'name':name,
                                                                         'url':url,
                                                                         'get_products':child_import.child_get_products,
                                                                         'has_pagination':child_import.child_has_pagination, })
                                                                 ]})
                            else:
                                finded = False
                                for child in self.child_crawler_ids:
                                    if child.name in data:
                                        finded = True
                                if not finded:
                                    self.write({'child_crawler_ids':[(0, 0, {'name':name,
                                                                             'url':url,
                                                                             'get_products':child_import.child_get_products,
                                                                             'has_pagination':child_import.child_has_pagination, })]})

                    else:
                        for data in urls:
                            if not self.child_crawler_ids:
                                self.write({'child_crawler_ids':[(0, 0, {'name':data,
                                                                         'url':data,
                                                                         'get_products':child_import.child_get_products,
                                                                         'has_pagination':child_import.child_has_pagination,
                                                                         })]})
                            else:
                                finded = False
                                for child in self.child_crawler_ids:
                                    if child.name in data:
                                        finded = True
                                if not finded:
                                    self.write({'child_crawler_ids':[(0, 0, {'name':data,
                                                                             'url':data,
                                                                             'get_products':child_import.child_get_products,
                                                                             'has_pagination':child_import.child_has_pagination,
                                                                             })]})
        except XPathEvalError:
            raise exceptions.except_orm('Error', 'La expresión xpath es inválida')

    importer_id = fields.One2many('importer.supplier',
                                  'importer_web_id',
                                  string='Importer')

    params_login_ids = fields.One2many('importer.supplier.webscrawler.login.param', 'webcrawler_id',
                                       'Params to login on page (like user and password)')

    currency_id = fields.Many2one('res.currency')
    tax_included = fields.Boolean('Taxes included', default=False)
    override_images = fields.Boolean('Override images when update products', default=False)

    name = fields.Char('Name', index=True, required=True, translate=True)
    parent_crawler_id = fields.Many2one('importer.supplier.webcrawler', 'Parent Web crawler', index=True,
                                        ondelete='cascade')
    child_crawler_ids = fields.One2many('importer.supplier.webcrawler', 'parent_crawler_id', 'Child Web Crawlers')

    child_expr_ids = fields.One2many('importer.supplier.webscrawler.child.expr', 'webcrawler_child_id',
                                     'Child search expressions')

    url = fields.Char('Url to get data')
    url_login = fields.Char('Url to login')
    get_products = fields.Boolean(default=False)
    has_pagination = fields.Boolean(default=False)
    next_page_expr_href_ids = fields.One2many('importer.supplier.get.expression',
                                              'webcrawler_id',
                                              'Next page expression')
    discount_percentage = fields.Float('Discount percentage')

    webcrawler_prod_id = fields.Many2one('importer.supplier.webcrawler.product', 'Crawler config for product')

    product_box_data_expr_ids = fields.One2many('importer.supplier.get.expression',
                                                'webcrawler_box_prod_data_id',
                                                'Box of the product\'s data expression')

    sku_expr_ids = fields.One2many('importer.supplier.get.expression', 'webcrawler_sku_id', 'Sku expression')
    name_expr_ids = fields.One2many('importer.supplier.get.expression', 'webcrawler_name_id', 'Name expression')
    ean_expr_ids = fields.One2many('importer.supplier.get.expression', 'webcrawler_ean_id', 'Ean expression')
    price_expr_ids = fields.One2many('importer.supplier.get.expression', 'webcrawler_price_id', 'Price expression')
    stock_expr_ids = fields.One2many('importer.supplier.get.expression', 'webcrawler_stock_id', 'Stock expression')
    type_stock = fields.Selection([('exist', 'If exist'), ('units', 'Units avaiable')],
                                  string='Type import data',
                                  store=True)

    url_image_expr_ids = fields.One2many('importer.supplier.get.expression',
                                         'webcrawler_image_id',
                                         'Url image expression')
    short_description_expr_ids = fields.One2many('importer.supplier.get.expression',
                                                 'webcrawler_short_des_id',
                                                 'Short description expression')
    large_description_expr_ids = fields.One2many('importer.supplier.get.expression',
                                                 'webcrawler_large_des_id',
                                                 'Large description expression')


class SearchExpression(models.Model):
    _name = 'importer.supplier.get.expression'

    @api.multi
    def name_get(self):
        return [(r.id, r.type_expression + ' - ' + r.expression) for r in self]

    @staticmethod
    def execute_get_expression(expression, page_detail):
        if expression.type_expression == 'xpath':
            if isinstance(page_detail, unicode):
                tree_detail = html.fromstring(page_detail, parser=html.HTMLParser(encoding='utf-8'))
            else:
                tree_detail = html.fromstring(page_detail.content, parser=html.HTMLParser(encoding='utf-8'))
            res_data = tree_detail.xpath(expression.expression)
            if res_data:
                list_data = []
                for data in res_data:
                    if isinstance(data, str):
                        list_data.append(data)
                    elif isinstance(data, HtmlElement):
                        list_data.append(data.text)
                return list_data

        elif expression.type_expression == 'regexp':
            res_data = re.findall(expression.expression, page_detail.content)
            if res_data:
                if res_data and isinstance(res_data, list):
                    list_data = []
                    for data in res_data:
                        list_data.append(data)
                return res_data

        return []

    webcrawler_id = fields.Many2one('importer.supplier.webcrawler')
    webcrawler_box_prod_data_id = fields.Many2one('importer.supplier.webcrawler')
    webcrawler_name_id = fields.Many2one('importer.supplier.webcrawler')
    webcrawler_sku_id = fields.Many2one('importer.supplier.webcrawler')
    webcrawler_ean_id = fields.Many2one('importer.supplier.webcrawler')
    webcrawler_price_id = fields.Many2one('importer.supplier.webcrawler')
    webcrawler_stock_id = fields.Many2one('importer.supplier.webcrawler')
    webcrawler_image_id = fields.Many2one('importer.supplier.webcrawler')
    webcrawler_short_des_id = fields.Many2one('importer.supplier.webcrawler')
    webcrawler_large_des_id = fields.Many2one('importer.supplier.webcrawler')

    child_search_name_id = fields.Many2one('importer.supplier.webscrawler.child.expr')
    child_search_url_id = fields.Many2one('importer.supplier.webscrawler.child.expr')

    type_expression = fields.Selection([('xpath', 'Xpath'), ('regexp', 'Regular Expression')],
                                       string='Type of search',
                                       default='xpath',
                                       store=True,
                                       required=True)

    expression = fields.Char(required=True)


class ChildWebcrawlerSearch(models.Model):
    _name = 'importer.supplier.webscrawler.child.expr'

    webcrawler_child_id = fields.Many2one('importer.supplier.webcrawler')

    name_expr_ids = fields.One2many('importer.supplier.get.expression', 'child_search_name_id', 'Name expression')
    url_expr_ids = fields.One2many('importer.supplier.get.expression', 'child_search_url_id', 'Url expression')
    child_get_products = fields.Boolean('Get products in childrens created')
    child_has_pagination = fields.Boolean('Has pagination in childrens created')


class ParamLogin(models.Model):
    _name = 'importer.supplier.webscrawler.login.param'

    webcrawler_id = fields.Many2one('importer.supplier.webcrawler')
    name = fields.Char(required=True)
    param = fields.Char()

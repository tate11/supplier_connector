# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Supplier(models.Model):
    _inherit = 'res.partner'

    @api.depends('prefix_supplier_prod')
    def _compute_sku_products(self):
        import wdb
        wdb.set_trace()
        self.env['product.template'].search([()])

    prefix_supplier_prod = fields.Char('Prefix supplier to import products', default='')

    importer_ids = fields.One2many('importer.supplier', 'partner_id', 'Importer product\'s supplier')

    # margin_min = fields.Integer('Margin min in percentage (%)', default='5')

    # margin_max = fields.Integer('Margin max in percentage (%)', default='30')


class ImporterSupplier(models.Model):
    _name = 'importer.supplier'

    @staticmethod
    def process_image(url):
        return ''

    @api.multi
    def _save_data_product(self, supplier, list_prod, prefix):
        import wdb
        wdb.set_trace()
        for prod in list_prod:
            try:
                res_prod = self.env['product.template'].search(
                    [('default_code', '=', prefix + prod['default_code'])])

                prod_code = prod['default_code']
                if res_prod and res_prod.id:
                    price = res_prod._compute_price_without_taxes(float(prod.get('standard_price'))) if prod.get('tax_included') else prod.get(
                        'standard_price')
                    w_prod = {'id':res_prod.id}
                    w_prod['name'] = prod.get('name')
                    w_prod['description'] = prod.get('description')
                    w_prod['standard_price'] = price
                    w_prod['barcode'] = prod.get('barcode')
                    # res_prod['image'] = prod.get('image')
                    result = self.env['product.template'].write(w_prod)
                    if result:
                        sup_prod = {'name':supplier.id}
                        sup_prod['product_name'] = w_prod['name']
                        sup_prod['product_code'] = prod_code
                        if prod.get('min_qty'):
                            sup_prod['min_qty'] = prod['min_qty']
                        else:
                            sup_prod['min_qty'] = 1
                        sup_prod['price'] = price
                        sup_prod['product_id'] = res_prod.product_variant_id.id
                        sup_prod['product_tmpl_id'] = res_prod.id
                        self.env['product.supplierinfo'].write(sup_prod)
                else:
                    prod['default_code'] = prefix + prod_code
                    prod['type'] = 'product'
                    if prod['urls_image']:
                        prod['image'] = prod['urls_image'][0][1]
                    result = self.env['product.template'].create(prod)
                    if result:
                        sup_prod = {'name':supplier.partner_id.id}
                        sup_prod['product_name'] = prod['name']
                        sup_prod['product_code'] = prod_code
                        sup_prod['price'] = result._compute_price_without_taxes(float(prod.get('standard_price'))) if prod.get('tax_included') \
                            else prod.get('standard_price')
                        sup_prod['product_id'] = result.product_variant_id.id
                        sup_prod['product_tmpl_id'] = result.id
                        result = self.env['product.supplierinfo'].create(sup_prod)
                        if prod.get('urls_image') and result:
                            for url, image in prod['urls_image']:
                                result.write({'product_image_ids':[(0, 0, {'name':url,
                                                                           'image':image,
                                                                           'product_tmpl_id':result.id, })
                                                                   ]})


            except Exception, e:
                print str(e)

    @api.model
    def _get_product_data(self):
        try:
            if self:
                if self.importer_type == 'web':
                    return self.importer_web_id._get_data_product()
                if self.importer_type == 'CSV':
                    return self.importer_csv_id._get_data_product()
        except Exception, e:
            raise e

    @api.multi
    def synchronize_product_supplier(self):
        ids = self.env.context.get('active_ids', [])
        if ids:
            importers = self.search([('partner_id', 'in', ids)])
        else:
            importers = self.search([])

        for importer in importers:
            list_product = importer._get_product_data()
            prefix = importer.partner_id.prefix_supplier_prod
            if prefix:
                prefix = prefix + '_'

            if list_product:
                self._save_data_product(supplier=importer, list_prod=list_product, prefix=prefix)

    partner_id = fields.Many2one('res.partner',
                                 'Supplier of products for import',
                                 domain=[('supplier', '=', True)],
                                 ondelete='cascade')

    tax_included = fields.Boolean('Tax included in price')
    override_images = fields.Boolean('Override images when update products')

    importer_type = fields.Selection(
        [('web', 'Web crawler'), ('CSV', 'Csv with url user and password'), ('SOAP', 'SOAP call')],
        string='Type import data',
        default='web',
        store=True,
        required=True)

    importer_web_id = fields.Many2one('importer.supplier.webcrawler',
                                      string='Web Crawler importer',
                                      ondelete='cascade')
    importer_csv_id = fields.Many2one('importer.supplier.csv',
                                      string='CSV importer',
                                      ondelete='cascade')
    importer_soap_id = fields.Many2one('importer.supplier.soap',
                                       string='Soap importer',
                                       ondelete='cascade')


class ProductSupplier(models.Model):
    _inherit = 'product.supplierinfo'

    url_ficha = fields.Char()


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def _compute_image_url(self):
        import wdb
        wdb.set_trace()
        import base64
        import requests

        return base64.b64encode(requests.get(self.url_image).content)

    @api.model
    def _compute_price_without_taxes(self, price):
        if price:
            for tax in self.taxes_id:
                if tax.type_tax_use == 'sale':
                    price_included_t = (tax.id, tax.price_include, tax.include_base_amount)
                    tax.price_include = True
                    res = self.pool.get('account.tax').compute_all(tax,
                                                                   price_unit=float(price),
                                                                   currency=self.currency_id,
                                                                   product=self)
                    if res:
                        self['standard_price'] = res['total_excluded']

                    tax.price_include = price_included_t[1]
                    tax.include_base_amount = price_included_t[2]

                    break
            return self['standard_price']

    product_image_ids = fields.One2many('product.image', 'product_tmpl_id', string='Images')

# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ImporterProductsSupplierCSV(models.Model):
    _name = 'importer.supplier.csv'

    @api.multi
    def name_get(self):
        if self.url:
            return [(r.id, r.url) for r in self]
        return [(r.id, 'empty id: ' + str(r.id)) for r in self]

    @api.model
    def _get_data_product(self):
        import csv

        if self.url:
            # url = self.url.replace('USER_SUPPLIER', self.user).replace('PASSWORD_SUPPLIER', self.password)
            # r = requests.get(url)
            # filenb = r.iter_lines()
            list_product = []
            filenb = "/mnt/extra-addons/custom/supplier_connector/temp/dmi_catalog.csv"
            with open(filenb, 'rb') as csvFile:
                reader = csv.reader(csvFile,
                                    delimiter=self.delimiter.encode('utf-8'),
                                    lineterminator=self.lineterminator.encode('utf-8'))

                i = 0
                for row in reader:
                    prod = {}

                    if not (self.has_title_row) or (self.has_title_row and i > 0):
                        for relation in self.relation_column_ids:
                            if relation.field_product == 'image':
                                self.importer_id.process_image(row[relation.num_column])
                            if relation.num_column <= len(row) and relation.field_product != 'image':
                                prod[relation.field_product] = row[relation.num_column]
                        list_product.append(prod)
                    i += 1

            return list_product

        return []

    importer_id = fields.One2many('importer.supplier',
                                  'importer_csv_id',
                                  string='Importer')

    url = fields.Char(
        help='If on the url, there are USER_SUPPLIER and PASSWORD_SUPPLIER strings, these will are replaced for user and password params')
    user = fields.Char()
    password = fields.Char()
    delimiter = fields.Char(default=';', required=True)
    lineterminator = fields.Char(default='\\n', required=True)
    has_title_row = fields.Boolean(string='Has title row?', default=True)
    relation_column_ids = fields.One2many('importer.supplier.csv.columnrelation',
                                          'importer_csv_id',
                                          string='Relation column-field')


class CSVColumnRelation(models.Model):
    _name = 'importer.supplier.csv.columnrelation'

    @api.multi
    def name_get(self):
        return [(r.id, str(r.num_colum) + ' - ' + r.field_product) for r in self]

    importer_csv_id = fields.Many2one('importer.supplier.csv')
    num_column = fields.Integer(required=True)
    field_product = fields.Selection([('name', 'name'),
                                      ('description', 'description'),
                                      ('standard_price', 'Supplier price'),
                                      ('default_code', 'Sku'),
                                      ('url_image', 'Image'),
                                      ('EAN', 'ean'),
                                      ('Stock', 'Stock'),
                                      ('weight', 'Weight'),
                                      ('brand', 'Brand')],
                                     string='Fields product',
                                     default='name',
                                     store=True,
                                     required=True)

from openerp.tests.common import TransactionCase
import logging


class TestExchange(TransactionCase):

    def setUp(self):
        super(TestExchange, self).setUp()
        self.product_model = self.registry('product.product')
        self.product_tmpl_model = self.registry('product.template')
        self.exchange_model=self.registry('stock.exchange.picking.line')
        self.sales_order_model=self.registry('sale.order')
        self.stock_return_picking_model = self.registry('stock.return.picking')
        self.stock_picking_model = self.registry('stock.picking')





    def test_product_id_change(self):

        cr, uid = self.cr, self.uid
        product_tmpl_id = self.product_tmpl_model.create(cr, uid, dict(name="test prod",
                                                                       list_price='1327',
                                                                       standard_price='1327',
                                                                       ))
        product_id = self.product_model.create(cr, uid, dict(product_tmpl_id=product_tmpl_id))
        res=self.exchange_model.product_id_change(cr,uid,None,product_id,2,{})
        self.assertEquals(2654, res['value']['price_subtotal'], "Test failed")
        self.assertEquals(1327, res['value']['price_unit'], "Test failed")
        logging.info('TEST test_product_id_change PASSED')

    def test_create_new_delivery(self):

        cr, uid = self.cr, self.uid

        sale_order_id=self.sales_order_model.create(cr,uid,dict(
            partner_id=1
        ))

        sale_order = self.sales_order_model.browse(cr, uid, sale_order_id)

        self.stock_return_picking_model._create_new_delivery(None,None,sale_order)
        self.assertEquals(sale_order.state, 'progress', "Test failed")
        logging.info('TEST test_create_new_delivery PASSED')




    def test_create_exchange(self):

        cr, uid = self.cr, self.uid
        with self.assertRaises(Exception) as error:
           self.stock_return_picking_model.create_exchange(cr, uid, None, None)
           self.assertEqual(error.exception.message, 'You cannot exchange products without sales order.')
        logging.info('TEST test_create_exchange PASSED')


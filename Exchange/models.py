# -*- coding: utf-8 -*-
from openerp.osv import osv, fields
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class stock_exchange_picking_line(osv.osv_memory):
    _name = "stock.exchange.picking.line"
    _rec_name = 'product_id'
    _columns = {
        'product_id': fields.many2one('product.product', string="Product", required=True),
        'name': fields.text('Description'),
        'quantity': fields.float("Quantity", digits_compute=dp.get_precision('Product Unit of Measure'), required=True, default="1"),
        'price_unit': fields.float("Price", digits_compute=dp.get_precision('Product Unit of Measure'), required=True, default="1"),
        'wizard_id': fields.many2one('stock.return.picking', string="Wizard"),
        # 'move_id': fields.many2one('stock.move', "Move"),
        # 'lot_id': fields.many2one('stock.production.lot', 'Serial Number', help="Used to choose the lot/serial number of the product returned"),
    }

    def product_id_change(self, cr, uid, ids, product, context):
        res = {}
        if product:
            product_obj = self.pool.get('product.product').browse(cr, uid, product, context=context)
            name = self.pool.get('product.product').name_get(cr, uid, [product_obj.id], context=context)[0][1]
            if product_obj.description_sale:
                res = {'value': {'name': name + '\n' + product_obj.description_sale}}
                # print(">>>>>", name + '\n' + product_obj.description_sale)
                # print(">>>>>>>>>>>>><<<<<<<<<<")
            else:
                res = {'value': {'name': name}}
                # print(">>>>>>>>>>>>><<<<<<<<<<")
                # print(">>>>>", name)
        return res

class stock_return_picking(osv.osv_memory):
    _inherit = 'stock.return.picking'
    _description = 'Exchange Picking'
    _columns = {
        'invoice_state': fields.selection([('2binvoiced', 'To be refunded/invoiced'), ('none', 'No invoicing')], 'Invoicing',required=True),
        'product_return_moves': fields.one2many('stock.return.picking.line', 'wizard_id', 'Moves'),
        'product_exchange_moves': fields.one2many('stock.exchange.picking.line', 'wizard_id', 'Moves'),
        'move_dest_exists': fields.boolean('Chained Move Exists', readonly=True, help="Technical field used to hide help tooltip if not needed"),
    }

    def create_exchange(self, cr, uid, ids, context=None):
        record_id = context and context.get('active_id', False) or False
        pick_obj = self.pool.get('stock.picking')
        pick = pick_obj.browse(cr, uid, record_id, context=context)
        
        sale_id = self.pool.get('sale.order').search(cr,uid,[('name','=', pick.origin)])[0]
        sale_order = self.pool.get('sale.order').browse(cr,uid,sale_id)


        order_line = sale_order.order_line

        # vals = {}
        # for i in [attr for attr in dir(sale_order) if not callable(getattr(sale_order, attr)) and not attr.startswith("_")]:
        #     if "<class " in str(type(getattr(sale_order, i))):
        #         lis = []
        #         for l in getattr(sale_order, i):
        #             lis.append((4, l.id))
        #         if len(getattr(sale_order, i)) == 1:
        #             vals.update({i : getattr(sale_order, i)[0].id})
        #             continue
        #         vals.update({i : lis})
        #         continue
        #     vals.update({i : getattr(sale_order, i)})
        # print(vals)

        lis = []
        lines = []
        for p in pick.move_lines:
            lis.append(p.product_id.id)
        for o in order_line:
            if o.product_id.id in lis:
                cr.execute('delete from sale_order_line where id=%s', (o.id,))


        sale_order_line = self.pool.get('sale.order.line')
        
        data_obj = self.pool.get('stock.exchange.picking.line')
        data = self.read(cr, uid, ids[0], context=context)
        for product in data_obj.browse(cr, uid, data['product_exchange_moves'], context=context):
            
            # print(">>>>>>>>>>>>>>>>>>>>>", sale_order.pricelist_id)

            proxy = self.pool.get('ir.model.data')
            result = proxy.get_object_reference(cr, uid, 'product', 'product_uom_unit')
                
            cr.execute('INSERT INTO sale_order_line (order_id, product_id, name, product_uom_qty, price_unit, product_uom, delay, state) values (%s, %s, %s, %s, %s, %s, %s, %s)', (sale_id, product.product_id.id, product.name, product.quantity, product.price_unit, result[1], 0.0, 'draft'))
        # print([attr for attr in dir(res) if not callable(getattr(res, attr)) and not attr.startswith("_")])

        # for m in pick.move_lines:
        #     print([attr for attr in dir(m) if not callable(getattr(m, attr)) and not attr.startswith("_")])
        # for data_get in data:
        # sale_order.write({'order_line' : lines})
            # cr.execute('delete from sale_order_line where id=%s', (o.id,))
            # print(">>>>>>>>>", data_get.product_id, data_get.quantity)
            # var = {'product_id': data_get.product_id, 'product_uom_qty': data_get.quantity}
            # s = sale_order_line.create(cr, uid, var, context)
            # lines.append(s.id)

        # vals = {}
        # for i in [attr for attr in dir(self) if not callable(getattr(self, attr)) and not attr.startswith("_")]:
        #     vals.update({i : getattr(self, i)})
        # print(vals)
        

        

        # sales = self.pool.get('sale.order')
        # var = {'date_order': pick.date, 'user_id': uid, 'warehouse_id': pick.picking_type_id.warehouse_id.id, 'partner_id': pick.partner_id.id}
        # sales.create(cr, uid, vals, context)

        return super(stock_return_picking, self).create_returns(cr, uid, ids, context=context)

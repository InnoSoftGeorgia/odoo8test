from openerp.osv import osv, fields
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

# New product list to exchange the old ones
class stock_exchange_picking_line(osv.osv_memory):
    _name = "stock.exchange.picking.line"
    _rec_name = 'product_id'
    _columns = {
        'product_id': fields.many2one('product.product', string="Product", required=True),
        'name': fields.text('Description'),
        'quantity': fields.float("Quantity", digits_compute=dp.get_precision('Product Unit of Measure'), required=True, default="1"),
        'price_unit': fields.float("Price", digits_compute=dp.get_precision('Product Unit of Measure'), required=True, default="1"),
        'wizard_id': fields.many2one('stock.return.picking', string="Wizard"),
    }

    # Set product description when new product is added
    def product_id_change(self, cr, uid, ids, product, context):
        res = {}
        if product:
            # Search for product
            product_obj = self.pool.get('product.product').browse(cr, uid, product, context=context)
            # Get product name
            name = self.pool.get('product.product').name_get(cr, uid, [product_obj.id], context=context)[0][1]
            # Set product description
            if product_obj.description_sale:
                res = {'value': {'name': name + '\n' + product_obj.description_sale}}
            else:
                res = {'value': {'name': name}}
        return res

# Exchange model
class stock_return_picking(osv.osv_memory):
    _inherit = 'stock.return.picking'
    _description = 'Exchange Picking'
    _columns = {
        'invoice_state': fields.selection([('2binvoiced', 'To be refunded/invoiced'), ('none', 'No invoicing')], 'Invoicing',required=True),
        'product_return_moves': fields.one2many('stock.return.picking.line', 'wizard_id', 'Moves'),
        'product_exchange_moves': fields.one2many('stock.exchange.picking.line', 'wizard_id', 'Moves'),
        'move_dest_exists': fields.boolean('Chained Move Exists', readonly=True, help="Technical field used to hide help tooltip if not needed"),
    }

    # Exchange button
    def create_exchange(self, cr, uid, ids, context=None):
        record_id = context and context.get('active_id', False) or False
        pick_obj = self.pool.get('stock.picking')
        pick = pick_obj.browse(cr, uid, record_id, context=context)
        
        sale_id = self.pool.get('sale.order').search(cr,uid,[('name','=', pick.origin)])[0]
        sale_order = self.pool.get('sale.order').browse(cr,uid,sale_id)

        order_line = sale_order.order_line

        lis = []
        # Get returned item ids
        for p in pick.move_lines:
            lis.append(p.product_id.id)
        # Select returned items in Order Line
        for o in order_line:
            if o.product_id.id in lis:

                # Delete returned items from Order Line
                cr.execute('delete from sale_order_line where id=%s', (o.id,))

        sale_order_line = self.pool.get('sale.order.line')
        
        data_obj = self.pool.get('stock.exchange.picking.line')
        data = self.read(cr, uid, ids[0], context=context)

        # Get new products
        for product in data_obj.browse(cr, uid, data['product_exchange_moves'], context=context):
            proxy = self.pool.get('ir.model.data')
            result = proxy.get_object_reference(cr, uid, 'product', 'product_uom_unit')

            # Add new products in Order Line
            cr.execute('INSERT INTO sale_order_line (order_id, product_id, name, product_uom_qty, price_unit, product_uom, delay, state) values (%s, %s, %s, %s, %s, %s, %s, %s)', (sale_id, product.product_id.id, product.name, product.quantity, product.price_unit, result[1], 0.0, 'draft'))
        
        # Return old products
        return super(stock_return_picking, self).create_returns(cr, uid, ids, context=context)

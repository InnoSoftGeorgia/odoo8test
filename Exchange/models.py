from openerp.osv import osv, fields
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
import time

# New product list to exchange the old ones
class stock_exchange_picking_line(osv.osv_memory):
    _name = "stock.exchange.picking.line"
    _rec_name = 'product_id'
    _columns = {
        'product_id': fields.many2one('product.product', string="Product", required=True),
        'name': fields.text('Description'),
        'quantity': fields.float("Quantity", digits_compute=dp.get_precision('Product Unit of Measure'), required=True, default="1"),
        'price_unit': fields.float("Price", digits_compute=dp.get_precision('Product Unit of Measure'), required=True, default="1"),
        'price_subtotal': fields.float("Subtotal", digits_compute=dp.get_precision('Product Unit of Measure'), required=True, default="0"),
        'wizard_id': fields.many2one('stock.return.picking', string="Wizard"),
    }
    
    # Set product description when new product is added
    def product_id_change(self, cr, uid, ids, product, quantity, context):
        res = {'value': {'name': '', 'price_unit': 0.0, 'price_subtotal': 0.0}}
        if product:
            # Search for product
            product_obj = self.pool.get('product.product').browse(cr, uid, product, context=context)
            # Get product name
            name = self.pool.get('product.product').name_get(cr, uid, [product_obj.id], context=context)[0][1]
            # Set product description

            res['value']['price_subtotal'] = quantity * product_obj.standard_price
            res['value']['price_unit'] = product_obj.standard_price
            if product_obj.description_sale:
                res['value']['name'] =  name + '\n' + product_obj.description_sale
            else:
                res['value']['name'] =  name
        return res

class sale_order(osv.Model):
    _inherit = 'sale.order'

    def _make_invoice(self, cr, uid, order, lines, context=None):
        inv_obj = self.pool.get('account.invoice')
        obj_invoice_line = self.pool.get('account.invoice.line')
        if context is None:
            context = {}
        invoiced_sale_line_ids = self.pool.get('sale.order.line').search(cr, uid, [('order_id', '=', order.id), ('invoiced', '=', True)], context=context)
        from_line_invoice_ids = []
        for invoiced_sale_line_id in self.pool.get('sale.order.line').browse(cr, uid, invoiced_sale_line_ids, context=context):
            for invoice_line_id in invoiced_sale_line_id.invoice_lines:
                if invoice_line_id.invoice_id.id not in from_line_invoice_ids:
                    from_line_invoice_ids.append(invoice_line_id.invoice_id.id)
        if not context.get('ignore_prev_invoices', False):
            for preinv in order.invoice_ids:
                if preinv.state not in ('cancel',) and preinv.id not in from_line_invoice_ids:
                    for preline in preinv.invoice_line:
                        inv_line_id = obj_invoice_line.copy(cr, uid, preline.id, {'invoice_id': False, 'price_unit': -preline.price_unit})
                        lines.append(inv_line_id)
        inv = self._prepare_invoice(cr, uid, order, lines, context=context)
        inv_id = inv_obj.create(cr, uid, inv, context=context)
        data = inv_obj.onchange_payment_term_date_invoice(cr, uid, [inv_id], inv['payment_term'], time.strftime(DEFAULT_SERVER_DATE_FORMAT))
        if data.get('value', False):
            inv_obj.write(cr, uid, [inv_id], data['value'], context=context)
        inv_obj.button_compute(cr, uid, [inv_id])
        return inv_id

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
        
        sale_id = self.pool.get('sale.order').search(cr,uid,[('name','=', pick.origin)])
        if sale_id:
            sale_id = sale_id[0]
        else:
            raise osv.except_osv(_('Error!'),
                _('You cannot exchange products without sales order.'))

        sale_order = self.pool.get('sale.order').browse(cr,uid,sale_id)

        if sale_order:
            order_line = sale_order.order_line
            data_obj = self.pool.get('stock.exchange.picking.line')
            data = self.read(cr, uid, ids[0], context=context)

            data_return = self.pool.get('stock.return.picking.line')
            lis = []
            price = sale_order.amount_total
            # Get returned item ids
            for p in data_return.browse(cr, uid, data['product_return_moves'], context=context):
                for o in order_line:
                    if o.product_id.id == p.product_id.id:
                        # Delete returned items from Order Line
                        price -= o.price_subtotal
                        cr.execute('DELETE FROM sale_order_line WHERE id=%s', (o.id,))

            # Get new products
            for product in data_obj.browse(cr, uid, data['product_exchange_moves'], context=context):
                proxy = self.pool.get('ir.model.data')
                result = proxy.get_object_reference(cr, uid, 'product', 'product_uom_unit')
                
                defaults = self.pool.get('sale.order.line').product_id_change(cr, uid, [], sale_order.pricelist_id.id, product.product_id.id,
                    qty=float(product.quantity),
                    uom=result[1],
                    qty_uos=False,
                    uos=False,
                    name=product.name,
                    partner_id=sale_order.partner_id.id,
                    date_order=sale_order.date_order,
                    fiscal_position=False,
                    flag=False,
                    context=dict(context or {}, company_id=sale_order.warehouse_id.id)
                )['value']

                price += defaults['price_unit'] * product.quantity

                # Add new products in Order Line
                cr.execute('INSERT INTO sale_order_line (order_id, product_id, name, product_uom_qty, product_uos_qty, price_unit, product_uom, delay, state) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)', (sale_id, product.product_id.id, product.name, product.quantity, defaults['product_uos_qty'], defaults['price_unit'], result[1], 0.0, 'confirmed'))
            cr.execute('UPDATE sale_order set amount_untaxed=%s, amount_total=%s WHERE id=%s', (price, price, sale_id))
            self._create_new_delivery(cr, uid, sale_order, context=context)
            self._create_new_invoice(cr, uid, sale_order, context=context)
        else:
            raise osv.except_osv(_('Error!'),
                _('You cannot exchange products without sales order.'))

        # Return old products
        return super(stock_return_picking, self).create_returns(cr, uid, ids, context=context)

    def _create_new_delivery(self, cr, uid, sale_order, context=None):
        sale_order.write({'state': 'shipping_except'})
        sale_order.action_ship_create()

    def _create_new_invoice(self, cr, uid, sale_order, context=None):
        for invoice in sale_order.invoice_ids:
            if invoice.state == 'cancel':
                continue
            if invoice.payment_ids:
                refund_obj = self.pool.get('account.invoice.refund')
                refund_id = refund_obj.create(cr, uid, {
                    'date': time.strftime('%Y-%m-%d'),
                    'journal_id': refund_obj._get_journal(cr, uid, context=None),
                    'description': invoice.name,
                    'filter_refund': 'refund',
                }, context=context)
                invoice_ctx = dict(context or {})
                invoice_ctx['active_ids'] = [invoice.id]
                refund_obj.invoice_refund(cr, uid, [refund_id], context=invoice_ctx)
            else:
                # cancel invoice if there is no payments
                invoice.signal_workflow('invoice_cancel')
        for line in sale_order.order_line:
            line.invoiced = False
        sale_order.with_context(ignore_prev_invoices=True).action_invoice_create()
